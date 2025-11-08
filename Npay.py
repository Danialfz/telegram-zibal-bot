import os
import telebot
import requests

# ----------- تنظیمات -----------
BOT_TOKEN = os.getenv("BOT_TOKEN", "8589520464:AAE3x1LjHw0wWepIX6bJePQ_d0z9AXB-1t4")
MERCHANT = os.getenv("MERCHANT", "67fbd99f6f3803001057a0bf")

bot = telebot.TeleBot(BOT_TOKEN)

# ----------- حذف webhook در شروع (خیلی مهم برای رفع خطای 409) -----------
try:
    requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook")
    print("✅ Webhook حذف شد تا polling بدون خطا اجرا شود.")
except Exception as e:
    print(f"⚠️ خطا در حذف webhook: {e}")

# ----------- دستورات ربات -----------
@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message, "سلام 👋 به ربات پرداخت نوسان‌پی خوش اومدی.\nبرای پرداخت تستی دستور /pay رو بفرست 💳")

@bot.message_handler(commands=['pay'])
def pay(message):
    amount = 10000  # مبلغ تستی به تومان
    callback_url = "https://zibal.ir"  # چون polling داریم، آدرس تأیید لازم نیست

    data = {
        "merchant": MERCHANT,
        "amount": amount,
        "callbackUrl": callback_url,
        "description": f"پرداخت توسط کاربر {message.from_user.id}"
    }

    try:
        res = requests.post("https://gateway.zibal.ir/v1/request", json=data).json()
        if res.get("result") == 100:
            track_id = res.get("trackId")
            pay_url = f"https://gateway.zibal.ir/start/{track_id}"
            bot.send_message(message.chat.id, f"✅ تراکنش ایجاد شد.\nبرای پرداخت روی لینک زیر کلیک کن:\n{pay_url}")
        else:
            bot.send_message(message.chat.id, f"❌ خطا در ایجاد تراکنش: {res.get('message')}")
    except Exception as e:
        bot.send_message(message.chat.id, f"⚠️ خطا در اتصال به درگاه: {e}")

# ----------- اجرای ربات -----------
if __name__ == "__main__":
    print("✅ ربات نوسان‌پی با polling در حال اجراست...")
    bot.infinity_polling(timeout=60, long_polling_timeout=30)
