# =============== Npay.py (ورژن نهایی و سازگار با زیبال و Railway) ===============
import os
import re
import telebot
from telebot import types
from flask import Flask, request, jsonify, redirect
import requests
import threading

# ====================== تنظیمات اصلی ======================
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "1611406302"))
MERCHANT = os.getenv("MERCHANT")
RAILWAY_DOMAIN = os.getenv("RAILWAY_DOMAIN")  # مقدار: bot.navasanpay.com

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

# ====================== اطلاعات ارزها ======================
currencies = {
    "USD": "دلار آمریکا 🇺🇸",
    "EUR": "یورو 🇪🇺",
    "GBP": "پوند انگلیس 🇬🇧",
    "CHF": "فرانک سوئیس 🇨🇭",
    "CAD": "دلار کانادا 🇨🇦",
    "AUD": "دلار استرالیا 🇦🇺",
    "AED": "درهم امارات 🇦🇪",
    "TRY": "لیر ترکیه 🇹🇷",
    "CNY": "یوان چین 🇨🇳",
    "INR": "روپیه هند 🇮🇳",
    "JPY": "ین ژاپن 🇯🇵",
    "SAR": "ریال عربستان 🇸🇦",
    "KWD": "دینار کویت 🇰🇼",
    "OMR": "ریال عمان 🇴🇲",
    "QAR": "ریال قطر 🇶🇦"
}

# ====================== قالب اطلاعات حساب ======================
currency_info_template = {
    "USD": "👤 نام گیرنده\n🏦 نام بانک\n💳 شماره حساب یا IBAN\n🌍 کشور / شهر بانک\n🔢 SWIFT Code",
    "EUR": "👤 نام گیرنده\n🏦 نام بانک\n💳 شماره IBAN\n🌍 کشور بانک\n🔢 SWIFT / BIC Code",
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

# ====================== حافظه موقت ======================
pending = {}
awaiting_admin_review = set()
last_target_for_admin = None

# ====================== مسیر پرداخت زیبال ======================
@app.route("/pay/<int:user_id>/<int:amount>")
def pay(user_id, amount):
    try:
        # ✅ استفاده از دامنه‌ی navasanpay.com برای جلوگیری از خطای 106
        callback_url = f"https://{RAILWAY_DOMAIN}/verify/{user_id}"

        req = {
            "merchant": MERCHANT,
            "amount": amount,
            "callbackUrl": callback_url,
            "description": f"پرداخت {amount:,} تومان از طریق ربات نوسان‌پی"
        }

        res = requests.post("https://gateway.zibal.ir/v1/request", json=req, timeout=10)
        data = res.json()

        if data.get("result") == 100:
            track_id = data["trackId"]
            return redirect(f"https://gateway.zibal.ir/start/{track_id}")
        else:
            return jsonify({"error": f"❌ خطا از زیبال: {data}"}), 400

    except Exception as e:
        return jsonify({"error": f"⚠️ خطا در ساخت لینک پرداخت: {str(e)}"}), 500


# ====================== مسیر وریفای پرداخت ======================
@app.route("/verify/<int:user_id>", methods=["GET", "POST"])
def verify_payment(user_id):
    try:
        track_id = request.args.get("trackId")
        if not track_id:
            return "پارامتر trackId ارسال نشده."

        req = {"merchant": MERCHANT, "trackId": track_id}
        res = requests.post("https://gateway.zibal.ir/v1/verify", json=req, timeout=10)
        data = res.json()

        if data.get("result") == 100:
            bot.send_message(user_id, "✅ پرداخت شما با موفقیت انجام شد.\nسپاس از اعتماد شما 💚")
            bot.send_message(ADMIN_ID, f"💰 کاربر {user_id} پرداخت را با موفقیت انجام داد.")
            return "✅ پرداخت با موفقیت انجام شد."
        else:
            bot.send_message(user_id, "❌ پرداخت ناموفق بود یا لغو شد.")
            return f"❌ پرداخت ناموفق: {data}"

    except Exception as e:
        return f"⚠️ خطا در بررسی پرداخت: {str(e)}"


# ====================== منو و سایر بخش‌ها ======================
def main_menu():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("💸 انتقال ارز")
    return kb

# ====================== اجرای همزمان Flask و Bot ======================
def run_flask():
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))

def run_bot():
    bot.infinity_polling(timeout=60, long_polling_timeout=30)

if __name__ == "__main__":
    threading.Thread(target=run_flask).start()
    run_bot()
