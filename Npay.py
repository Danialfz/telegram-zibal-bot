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

# ---------------- کیبوردها ----------------
def main_menu():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("💸 انتقال ارز", "💬 ارتباط با پشتیبانی")
    return kb

def direction_menu():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("🌍 از داخل به خارج", "🏦 از خارج به داخل")
    kb.add("🔙 بازگشت", "💬 ارتباط با پشتیبانی")
    return kb

def confirm_keyboard():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("✅ تایید", "❌ لغو")
    kb.add("🔙 بازگشت", "💬 ارتباط با پشتیبانی")
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
    bot.send_message(m.chat.id, "سلام 👋 برای شروع انتقال ارز یا ارتباط با پشتیبانی یکی از گزینه‌ها را انتخاب کنید:", reply_markup=main_menu())

# === ارتباط با پشتیبانی ===
@bot.message_handler(func=lambda m: m.text == "💬 ارتباط با پشتیبانی")
def support_start(m):
    bot.send_message(m.chat.id, "💬 لطفاً پیام یا تصویر خود را ارسال کنید تا برای پشتیبانی ارسال شود.")
    bot.send_message(ADMIN_ID, f"📩 کاربر {m.chat.id} وارد گفت‌وگو با پشتیبانی شد.")
    pending[m.chat.id] = {"support": True}

@bot.message_handler(func=lambda m: pending.get(m.chat.id, {}).get("support") is True, content_types=["text", "photo", "document"])
def forward_to_admin(m):
    bot.forward_message(ADMIN_ID, m.chat.id, m.message_id)
    bot.send_message(ADMIN_ID, f"📨 پیام از کاربر {m.chat.id}")
    bot.send_message(m.chat.id, "✅ پیام شما برای پشتیبانی ارسال شد.", reply_markup=main_menu())

# --- پاسخ ادمین به کاربر با آیدی ---
@bot.message_handler(func=lambda m: m.chat.id == ADMIN_ID)
def admin_reply(m):
    # ✅ ارسال پاسخ با الگوی: پاسخ <id> <متن>
    match = re.match(r"^پاسخ\s+(\d+)\s+(.+)$", m.text or "")
    if match:
        user_id = int(match.group(1))
        text = match.group(2)
        try:
            bot.send_message(user_id, f"📩 پیام از پشتیبانی:\n\n{text}")
            bot.send_message(ADMIN_ID, f"✅ پاسخ برای {user_id} ارسال شد.")
        except Exception as e:
            bot.send_message(ADMIN_ID, f"❌ خطا در ارسال پیام: {e}")
        return

    # سایر منطق‌های ادمین (تعیین نرخ، تأیید و ...)
    # بقیه‌ی کد تو نسخه‌ی قبلت بدون تغییر می‌مونه


# ---------------- اجرای همزمان ----------------
def run_flask():
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

def run_bot():
    bot.infinity_polling(timeout=60, long_polling_timeout=30)

if __name__ == "__main__":
    print("✅ Npay bot started with Support via ID")
    threading.Thread(target=run_flask).start()
    run_bot()
