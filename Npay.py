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

# ---------------- کیبوردها ----------------
def main_menu():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("💸 انتقال ارز", "💬 ارتباط با پشتیبانی")
    return kb

def direction_menu():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("🌍 از داخل به خارج", "🏦 از خارج به داخل")
    kb.add("🔙 بازگشت")
    return kb

def confirm_keyboard():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("✅ تایید", "❌ لغو")
    kb.add("🔙 بازگشت")
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

# ---------------- پشتیبانی ----------------
@bot.message_handler(func=lambda m: m.text == "💬 ارتباط با پشتیبانی")
def contact_support(m):
    pending[m.chat.id] = {"support": True}
    bot.send_message(m.chat.id, "💬 لطفاً پیام خود را برای پشتیبانی ارسال کنید (متن یا تصویر).")

@bot.message_handler(func=lambda m: pending.get(m.chat.id, {}).get("support") is True, content_types=["text", "photo", "document"])
def forward_support(m):
    bot.forward_message(ADMIN_ID, m.chat.id, m.message_id)
    bot.send_message(ADMIN_ID, f"📩 پیام جدید از کاربر {m.chat.id}")
    bot.send_message(m.chat.id, "✅ پیام شما به پشتیبانی ارسال شد.", reply_markup=main_menu())

# --- پاسخ ادمین با دستور «پاسخ <id> <متن>»
@bot.message_handler(func=lambda m: m.chat.id == ADMIN_ID)
def admin_responder(m):
    text = (m.text or "").strip()

    match = re.match(r"^پاسخ\s+(\d+)\s+(.+)$", text)
    if match:
        uid = int(match.group(1))
        msg = match.group(2)
        try:
            bot.send_message(uid, f"📩 پیام از پشتیبانی:\n\n{msg}")
            bot.send_message(ADMIN_ID, f"✅ پاسخ برای کاربر {uid} ارسال شد.")
        except Exception as e:
            bot.send_message(ADMIN_ID, f"❌ خطا در ارسال پاسخ: {e}")
        return

    # ادامه‌ی منطق ادمین (نرخ، تایید و ...)
    handle_admin_commands(m, text)

# ---------------- منطق اصلی ادمین ----------------
def handle_admin_commands(m, text):
    global last_target_for_admin
    chat_id = m.chat.id

    # نرخ
    m_rate = re.match(r"^نرخ\s+(\d+)\s+([\d.]+)$", text)
    if m_rate:
        uid = int(m_rate.group(1))
        rate = float(m_rate.group(2))
        if uid in pending and pending[uid].get("step") == "waiting_rate":
            amount = pending[uid]["amount"]
            total = int(amount * rate)
            pending[uid].update({"rate": rate, "total": total, "step": "confirm"})
            bot.send_message(uid, f"💰 مجموع پرداختی: {total:,} تومان\nتایید می‌کنید؟", reply_markup=confirm_keyboard())
            bot.send_message(ADMIN_ID, f"✅ نرخ {rate} برای کاربر {uid} ثبت شد.")
            last_target_for_admin = uid
        return

    # تایید و پرداخت
    m_confirm = re.match(r"^تایید\s+(\d+)$", text)
    if m_confirm:
        uid = int(m_confirm.group(1))
        if uid not in pending:
            return bot.send_message(chat_id, "کاربر پیدا نشد.")
        data = pending[uid]
        total = data.get("total", 0)
        direction = data.get("direction")

        if direction == "از داخل به خارج":
            rial_total = int(total * 10)
            callback_url = f"https://{RAILWAY_DOMAIN}/verify/{uid}"
            req = {"merchant": MERCHANT, "amount": rial_total, "callbackUrl": callback_url,
                   "description": f"پرداخت {total:,} تومان از طریق ربات نوسان‌پی"}
            res = requests.post("https://gateway.zibal.ir/v1/request", json=req, timeout=15)
            d = res.json()
            if d.get("result") == 100:
                pay_link = f"https://gateway.zibal.ir/start/{d['trackId']}"
                bot.send_message(uid, f"✅ اطلاعات تایید شد.\n💳 <a href=\"{pay_link}\">برای پرداخت کلیک کنید</a>",
                                 parse_mode="HTML", disable_web_page_preview=True)
                bot.send_message(ADMIN_ID, f"💰 لینک پرداخت برای {uid} ارسال شد.")
            else:
                bot.send_message(ADMIN_ID, f"❌ خطا از زیبال: {d}")
            return

        elif direction == "از خارج به داخل":
            bot.send_message(uid, "✅ اطلاعات تایید شد.\n💬 منتظر پیام پشتیبانی باشید.")
            bot.send_message(ADMIN_ID,
                             f"📦 کاربر {uid} مسیر از خارج به داخل را تایید کرد.\nبرای او اطلاعات واریز بفرستید با دستور:\nپاسخ {uid} <متن>")
            pending[uid]["step"] = "awaiting_manual_payment"
            last_target_for_admin = uid
            return

# ---------------- بقیه منطق کاربر (مثل کد قبلی تو) ----------------
# (می‌تونی عین کد بالای خودت رو بعد از این تابع paste کنی، از بخش:
# @bot.message_handler(commands=['start'])
# تا انتهای main_handler — بدون تغییر نیاز.)

# ---------------- اجرا ----------------
def run_flask():
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

def run_bot():
    bot.infinity_polling(timeout=60, long_polling_timeout=30)

if __name__ == "__main__":
    print("✅ Npay bot started with full support + admin replies")
    threading.Thread(target=run_flask).start()
    run_bot()
