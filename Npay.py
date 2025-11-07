import telebot
from flask import Flask, request
import requests

# ---------- تنظیمات ----------
BOT_TOKEN = "8589520464:AAE3x1LjHw0wWepIX6bJePQ_d0z9AXB-1t4"
MERCHANT = "67fbd99f6f3803001057a0bf"
CALLBACK_URL = "https://example.com/verify"  # بعداً آدرس ngrok جایگزین می‌شود

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

# ---------- دستورات ربات ----------
@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message, "سلام 👋 برای پرداخت، دستور /pay رو بفرست.")

@bot.message_handler(commands=['pay'])
def start_payment(message):
    amount = 10000  # مبلغ به تومان
    data = {
        "merchant": MERCHANT,
        "amount": amount,
        "callbackUrl": CALLBACK_URL,
        "description": f"پرداخت توسط کاربر {message.from_user.id}"
    }

    res = requests.post("https://gateway.zibal.ir/v1/request", json=data).json()

    if res["result"] == 100:
        track_id = res["trackId"]
        pay_url = f"https://gateway.zibal.ir/start/{track_id}"
        bot.send_message(message.chat.id, f"💰 برای پرداخت روی لینک زیر کلیک کن:\n{pay_url}")
    else:
        bot.send_message(message.chat.id, f"❌ خطا در ایجاد تراکنش: {res['message']}")

# ---------- بررسی نتیجه پرداخت ----------
@app.route('/verify')
def verify():
    track_id = request.args.get("trackId")
    data = {"merchant": MERCHANT, "trackId": track_id}
    result = requests.post("https://gateway.zibal.ir/v1/verify", json=data).json()

    if result["result"] == 100:
        return "✅ پرداخت موفق بود!"
    else:
        return "❌ پرداخت ناموفق بود."

# ---------- اجرا ----------
if __name__ == "__main__":
    print("ربات و سرور محلی اجرا شدند 🚀")
    app.run(port=5000)
