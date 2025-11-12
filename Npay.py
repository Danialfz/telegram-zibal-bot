# =============== Npay.py (ورژن کامل با منوی تلگرام و پرداخت زیبال + Railway) ===============
import os
import telebot
from telebot import types
from flask import Flask, request, jsonify, redirect
import requests
import threading

# ====================== تنظیمات اصلی ======================
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "1611406302"))
MERCHANT = os.getenv("MERCHANT")  # مرچنت کد زیبال
RAILWAY_DOMAIN = os.getenv("RAILWAY_DOMAIN", "bot.navasanpay.com")

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

# ====================== حافظه موقت ======================
pending = {}

# ====================== مسیر پرداخت زیبال ======================
@app.route("/pay/<int:user_id>/<int:amount>")
def pay(user_id, amount):
    try:
        callback_url = f"https://{RAILWAY_DOMAIN}/verify/{user_id}"
        req = {
            "merchant": MERCHANT,
            "amount": amount,
            "callbackUrl": callback_url,
            "description": f"پرداخت {amount:,} تومان از طریق ربات نوسان‌پی"
        }

        res = requests.post("https://gateway.zibal.ir/v1/request", json=req, timeout=15)
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
        res = requests.post("https://gateway.zibal.ir/v1/verify", json=req, timeout=15)
        data = res.json()

        if data.get("result") == 100:
            bot.send_message(user_id, "✅ پرداخت شما با موفقیت انجام شد.\nسپاس از اعتماد شما 💚")
            bot.send_message(ADMIN_ID, f"💰 کاربر {user_id} پرداخت موفق داشت.")
            return "✅ پرداخت موفق بود."
        else:
            bot.send_message(user_id, "❌ پرداخت ناموفق بود یا لغو شد.")
            return f"❌ پرداخت ناموفق: {data}"

    except Exception as e:
        return f"⚠️ خطا در بررسی پرداخت: {str(e)}"


# ====================== هندلر شروع ربات ======================
@bot.message_handler(commands=['start'])
def start(message):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("💳 تست پرداخت", "ℹ️ راهنما")
    bot.send_message(message.chat.id,
                     "👋 به ربات نوسان‌پی خوش آمدی!\n\n"
                     "از دکمه‌های زیر استفاده کن 👇",
                     reply_markup=kb)


# ====================== هندلر منو ======================
@bot.message_handler(func=lambda m: m.text == "ℹ️ راهنما")
def help_section(message):
    bot.send_message(message.chat.id,
                     "📘 این ربات برای پرداخت آنلاین از طریق درگاه زیبال ساخته شده است.\n"
                     "برای تست پرداخت، روی گزینه 💳 تست پرداخت بزن.")


# ====================== تست پرداخت ======================
@bot.message_handler(func=lambda m: m.text == "💳 تست پرداخت")
def test_payment(message):
    user_id = message.chat.id
    amount = 2000  # مبلغ تستی به تومان
    pay_url = f"https://{RAILWAY_DOMAIN}/pay/{user_id}/{amount}"
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("💰 پرداخت 2,000 تومان", url=pay_url))
    bot.send_message(user_id,
                     f"برای تست درگاه پرداخت، روی دکمه زیر بزن 👇\n\n"
                     f"💸 مبلغ: {amount:,} تومان",
                     reply_markup=kb)


# ====================== اجرای همزمان Flask و Bot ======================
def run_flask():
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 8080)))

def run_bot():
    bot.infinity_polling(timeout=60, long_polling_timeout=30)


if __name__ == "__main__":
    threading.Thread(target=run_flask).start()
    run_bot()
