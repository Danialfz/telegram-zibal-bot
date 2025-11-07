import telebot
from flask import Flask, request
import requests
import os

# ---------- تنظیمات ----------
BOT_TOKEN = "8589520464:AAE3x1LjHw0wWepIX6bJePQ_d0z9AXB-1t4"
MERCHANT = "67fbd99f6f3803001057a0bf"
CALLBACK_URL = "https://telegram-zibal-bot-production.up.railway.app/verify"  # آدرس verify واقعی

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

# ---------- دستورات ربات ----------
@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message, "سلام 👋 برای پرداخت، دستور /pay رو بفرست.")

@bot.message_handler(commands=['pay'])
def start_payment(message):
    amount = 10000
    data = {
        "merchant": MERCHANT,
        "amount": amount,
        "callbackUrl": CALLBACK_URL,
        "description": f"پرداخت توسط کاربر {message.from_user.id}"
    }

    res = requests.post("https://gateway.zibal.ir/v1/request", json=data).json()

    if res.get("result") == 100:
        track_id = res["trackId"]
        pay_url = f"https://gateway.zibal.ir/start/{track_id}"
        bot.send_message(message.chat.id, f"💰 برای پرداخت روی لینک زیر کلیک کن:\n{pay_url}")
    else:
        bot.send_message(message.chat.id, f"❌ خطا در ایجاد تراکنش: {res}")

# ---------- بررسی نتیجه پرداخت ----------
@app.route('/verify')
def verify():
    track_id = request.args.get("trackId")
    data = {"merchant": MERCHANT, "trackId": track_id}
    result = requests.post("https://gateway.zibal.ir/v1/verify", json=data).json()

    if result.get("result") == 100:
        return "✅ پرداخت موفق بود!"
    else:
        return "❌ پرداخت ناموفق بود."

# ---------- مسیر وبهوک برای تلگرام ----------
@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def telegram_webhook():
    update = request.get_json(force=True)
    bot.process_new_updates([telebot.types.Update.de_json(update)])
    return "OK", 200

# ---------- اجرا ----------
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)
