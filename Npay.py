import os
import re
import threading
import requests
import telebot
from telebot import types
from flask import Flask, request, jsonify, redirect

# ---------------- تنظیمات اصلی ----------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN env var is required")

try:
    ADMIN_ID = int(os.getenv("ADMIN_ID", "1611406302"))
except Exception:
    raise RuntimeError("ADMIN_ID must be integer")

MERCHANT = os.getenv("MERCHANT")
RAILWAY_DOMAIN = os.getenv("RAILWAY_DOMAIN")

if not MERCHANT:
    raise RuntimeError("MERCHANT env var is required")
if not RAILWAY_DOMAIN:
    raise RuntimeError("RAILWAY_DOMAIN env var is required (e.g. bot.navasanpay.com)")

bot = telebot.TeleBot(BOT_TOKEN)
try:
    bot.remove_webhook()
except Exception:
    pass

app = Flask(__name__)

# ---------------- داده‌ها ----------------
currencies = {
    "USD": "دلار آمریکا 🇺🇸", "EUR": "یورو 🇪🇺", "GBP": "پوند انگلیس 🇬🇧",
    "CHF": "فرانک سوئیس 🇨🇭", "CAD": "دلار کانادا 🇨🇦", "AUD": "دلار استرالیا 🇦🇺",
    "AED": "درهم امارات 🇦🇪", "TRY": "لیر ترکیه 🇹🇷", "CNY": "یوان چین 🇨🇳",
    "INR": "روپیه هند 🇮🇳", "JPY": "ین ژاپن 🇯🇵", "SAR": "ریال عربستان 🇸🇦",
    "KWD": "دینار کویت 🇰🇼", "OMR": "ریال عمان 🇴🇲", "QAR": "ریال قطر 🇶🇦"
}

currency_info_template = {
    "USD": "👤 نام و نام خانوادگی گیرنده\n🏦 نام بانک\n💳 شماره حساب یا IBAN\n🌍 کشور / شهر بانک\n🔢 SWIFT Code",
    "EUR": "👤 نام و نام خانوادگی گیرنده\n🏦 نام بانک\n💳 شماره IBAN\n🌍 کشور بانک\n🔢 SWIFT / BIC Code",
    "GBP": "👤 نام گیرنده\n🏦 نام بانک\n💳 شماره حساب\n🏷 Sort Code",
    "CHF": "👤 نام گیرنده\n🏦 نام بانک\n💳 شماره حساب یا IBAN\n🔢 SWIFT Code\n🌍 کشور بانک",
    "CAD": "👤 نام گیرنده\n🏦 نام بانک\n💳 شماره حساب\n🏷 Transit Number\n🌍 کشور / شهر بانک",
    "AUD": "👤 نام گیرنده\n🏦 نام بانک\n💳 شماره حساب\n🏷 BSB Code\n🌍 کشور بانک",
    "AED": "👤 نام گیرنده\n🏦 نام بانک\n💳 شماره IBAN\n🌍 امارت / شهر بانک\n🔢 SWIFT Code",
    "TRY": "👤 نام گیرنده\n🏦 نام بانک\n💳 شماره IBAN (TR...)\n🌍 شهر بانک\n🔢 SWIFT Code",
    "CNY": "👤 نام گیرنده (به انگلیسی)\n🏦 نام بانک\n💳 شماره حساب\n🌍 شهر / استان\n🔢 SWIFT Code",
    "INR": "👤 نام گیرنده\n🏦 نام بانک\n💳 شماره حساب\n🏷 IFSC Code\n🌍 کشور / شهر بانک",
    "JPY": "👤 نام گیرنده\n🏦 نام بانک\n💳 شماره حساب\n🏷 Branch Code\n🌍 شهر بانک\n🔢 SWIFT Code",
    "SAR": "👤 نام گیرنده\n🏦 نام بانک\n💳 شماره IBAN (SA...)\n🌍 کشور / شهر بانک\n🔢 SWIFT Code",
    "KWD": "👤 نام گیرنده\n🏦 نام بانک\n💳 شماره حساب یا IBAN\n🌍 کشور / شهر بانک\n🔢 SWIFT Code",
    "OMR": "👤 نام گیرنده\n🏦 نام بانک\n💳 شماره حساب یا IBAN\n🌍 کشور / شهر بانک\n🔢 SWIFT Code",
    "QAR": "👤 نام گیرنده\n🏦 نام بانک\n💳 شماره حساب یا IBAN\n🌍 کشور / شهر بانک\n🔢 SWIFT Code"
}

pending = {}
last_target_for_admin = None
active_support = {}  # پشتیبانی فعال (user_id <-> admin)

# ---------------- کیبوردها ----------------
def main_menu():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("💸 انتقال ارز", "🆘 پشتیبانی")
    return kb

def direction_menu():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("🌍 از داخل به خارج", "🏦 از خارج به داخل")
    kb.add("🔙 بازگشت", "🆘 پشتیبانی")
    return kb

def confirm_keyboard():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("✅ تایید", "❌ لغو")
    kb.add("🔙 بازگشت", "🆘 پشتیبانی")
    return kb

# ---------------- درگاه زیبال ----------------
@app.route("/pay/<int:user_id>/<int:amount>")
def pay(user_id, amount):
    try:
        rial_amount = int(amount * 10)
        callback_url = f"https://{RAILWAY_DOMAIN}/verify/{user_id}"
        req = {"merchant": MERCHANT, "amount": rial_amount, "callbackUrl": callback_url,
               "description": f"پرداخت {amount:,} تومان از طریق ربات نوسان‌پی"}
        res = requests.post("https://gateway.zibal.ir/v1/request", json=req, timeout=15)
        data = res.json()
    except Exception as e:
        bot.send_message(ADMIN_ID, f"❌ خطا در تماس با زیبال: {str(e)}")
        return jsonify({"error": f"{e}"}), 500

    if data.get("result") == 100:
        return redirect(f"https://gateway.zibal.ir/start/{data['trackId']}")
    else:
        bot.send_message(ADMIN_ID, f"❌ خطا از زیبال: {data}")
        return jsonify(data), 400

@app.route("/verify/<int:user_id>", methods=["GET", "POST"])
def verify_payment(user_id):
    track_id = request.args.get("trackId")
    if not track_id:
        return "trackId ارسال نشده", 400
    try:
        req = {"merchant": MERCHANT, "trackId": track_id}
        res = requests.post("https://gateway.zibal.ir/v1/verify", json=req, timeout=15)
        data = res.json()
    except Exception as e:
        bot.send_message(ADMIN_ID, f"❌ verify error: {e}")
        return f"خطا: {e}", 500

    if data.get("result") == 100:
        bot.send_message(user_id, "✅ پرداخت موفق انجام شد.")
        bot.send_message(ADMIN_ID, f"💰 پرداخت موفق از کاربر {user_id}")
        return "OK"
    else:
        bot.send_message(user_id, "❌ پرداخت ناموفق بود.")
        bot.send_message(ADMIN_ID, f"❌ پرداخت ناموفق از کاربر {user_id}: {data}")
        return "Failed", 400

# ---------------- منطق ربات ----------------
@bot.message_handler(commands=["start"])
def start(m):
    pending.pop(m.chat.id, None)
    bot.send_message(m.chat.id, "سلام 👋 برای شروع انتقال ارز گزینه زیر را انتخاب کنید:", reply_markup=main_menu())

# ---------------- پشتیبانی ----------------
@bot.message_handler(func=lambda m: m.text == "🆘 پشتیبانی")
def support_start(m):
    uid = m.chat.id
    if uid in active_support:
        bot.send_message(uid, "شما در حال حاضر در گفت‌وگو با پشتیبانی هستید.\nبرای پایان بنویسید: پایان", reply_markup=main_menu())
        return
    active_support[uid] = "waiting_admin"
    bot.send_message(uid, "✉️ پیام خود را بنویسید تا به پشتیبانی ارسال شود.\nبرای پایان بنویسید: پایان")
    bot.send_message(ADMIN_ID, f"📞 درخواست پشتیبانی جدید از کاربر {uid}")

@bot.message_handler(func=lambda m: active_support.get(m.chat.id) == "waiting_admin" or m.chat.id == ADMIN_ID)
def support_chat(m):
    uid = m.chat.id
    text = m.text.strip()

    # پایان مکالمه
    if text.lower() in ("پایان", "/پایان"):
        if uid == ADMIN_ID:
            if last_target_for_admin in active_support:
                del active_support[last_target_for_admin]
                bot.send_message(last_target_for_admin, "🔚 مکالمه پشتیبانی پایان یافت.", reply_markup=main_menu())
                bot.send_message(ADMIN_ID, "🔚 گفت‌وگو پایان یافت.")
            return
        else:
            if uid in active_support:
                del active_support[uid]
                bot.send_message(uid, "🔚 مکالمه پشتیبانی پایان یافت.", reply_markup=main_menu())
                bot.send_message(ADMIN_ID, f"❗️ کاربر {uid} مکالمه را پایان داد.")
            return

    # ارسال پیام کاربر برای ادمین
    if uid != ADMIN_ID:
        bot.send_message(ADMIN_ID, f"📩 پیام جدید از {uid}:\n{text}")
        bot.send_message(uid, "✅ پیام شما برای پشتیبانی ارسال شد.")
        global last_target_for_admin
        last_target_for_admin = uid
        return

    # ارسال پاسخ ادمین برای کاربر فعال
    if uid == ADMIN_ID and last_target_for_admin:
        bot.send_message(last_target_for_admin, f"💬 پیام از پشتیبانی:\n{text}")
        bot.send_message(ADMIN_ID, "✅ پیام ارسال شد.")
        return

# ---------------- بقیه منطق انتقال ارز (بدون تغییر) ----------------
@bot.message_handler(func=lambda m: m.text == "💸 انتقال ارز")
def start_transfer(m):
    bot.send_message(m.chat.id, "جهت انتقال را انتخاب کنید:", reply_markup=direction_menu())

@bot.message_handler(func=lambda m: m.text in ["🌍 از داخل به خارج", "🏦 از خارج به داخل"])
def choose_currency(m):
    direction = "از داخل به خارج" if "داخل به خارج" in m.text else "از خارج به داخل"
    pending[m.chat.id] = {"direction": direction, "step": "currency"}
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    for c, n in currencies.items():
        kb.add(f"{n} ({c})")
    kb.add("🔙 بازگشت", "🆘 پشتیبانی")
    bot.send_message(m.chat.id, "ارز مورد نظر را انتخاب کنید:", reply_markup=kb)

# ... بقیه کدها بدون حذف یا تغییر (همان منطق تایید، نرخ، پرداخت و اطلاعات)
# ---------------- اجرای همزمان ----------------
def run_flask():
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

def run_bot():
    bot.infinity_polling(timeout=60, long_polling_timeout=30)

if __name__ == "__main__":
    print("✅ Npay bot started")
    threading.Thread(target=run_flask).start()
    run_bot()
