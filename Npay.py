import os
import re
import sys
import telebot
from telebot import types
from flask import Flask, request, jsonify, redirect
import requests
import threading

# ====================== تنظیمات اصلی ======================
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "1611406302"))
MERCHANT_CODE = os.getenv("MERCHANT_CODE", "67fbd99f6f3803001057a0bf")
RAILWAY_DOMAIN = os.getenv("RAILWAY_DOMAIN", "primary-production-87fa.up.railway.app")

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

pending = {}
awaiting_admin_review = set()

# ====================== رابط زیبال (ایمن) ======================
@app.route("/pay/<int:amount>")
def pay(amount):
    callback_url = f"https://t.me/YourBotUsername"  # می‌تونی آدرس دلخواه بدی
    req = {
        "merchant": MERCHANT_CODE,
        "amount": amount,
        "callbackUrl": callback_url,
        "description": f"پرداخت {amount:,} تومان از طریق ربات نوسان‌پی"
    }

    try:
        res = requests.post("https://gateway.zibal.ir/v1/request", json=req)
        data = res.json()
        if data.get("result") == 100:
            track_id = data["trackId"]
            return redirect(f"https://gateway.zibal.ir/start/{track_id}")
        else:
            return jsonify({"error": data})
    except Exception as e:
        return jsonify({"error": str(e)})

# ====================== کیبوردها ======================
def main_menu():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(types.KeyboardButton("💸 انتقال ارز"))
    return kb

def direction_menu():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(types.KeyboardButton("🌍 از داخل به خارج"))
    kb.add(types.KeyboardButton("🏦 از خارج به داخل"))
    kb.add(types.KeyboardButton("🔙 بازگشت"))
    return kb

# ====================== شروع ربات ======================
@bot.message_handler(commands=["start"])
def start_cmd(m):
    bot.send_message(m.chat.id,
                     "سلام 👋 خوش اومدی!\nبرای شروع انتقال ارز، گزینه زیر رو انتخاب کن:",
                     reply_markup=main_menu())

@bot.message_handler(func=lambda m: m.text == "💸 انتقال ارز")
def start_transfer(m):
    bot.send_message(m.chat.id, "جهت انتقال را انتخاب کنید:", reply_markup=direction_menu())

@bot.message_handler(func=lambda m: m.text in ["🌍 از داخل به خارج", "🏦 از خارج به داخل"])
def choose_currency(m):
    chat_id = m.chat.id
    direction = "از داخل به خارج" if "داخل" in m.text else "از خارج به داخل"
    pending[chat_id] = {"direction": direction, "step": "currency"}
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    for code, name in currencies.items():
        kb.add(types.KeyboardButton(f"{name} ({code})"))
    bot.send_message(chat_id, "ارز مورد نظر را انتخاب کنید:", reply_markup=kb)

@bot.message_handler(func=lambda m: re.search(r"\(([A-Z]{3})\)", m.text or ""))
def ask_amount(m):
    chat_id = m.chat.id
    match = re.search(r"\(([A-Z]{3})\)", m.text)
    code = match.group(1)
    pending[chat_id]["currency"] = code
    pending[chat_id]["step"] = "amount"
    bot.send_message(chat_id, f"مقدار {currencies[code]} را وارد کنید (مثلاً 2500):")

@bot.message_handler(func=lambda m: True)
def process(m):
    chat_id = m.chat.id
    text = m.text.strip()
    st = pending.get(chat_id)

    if text == "🔙 بازگشت":
        pending.pop(chat_id, None)
        return start_cmd(m)

    # === ادمین نرخ تعیین می‌کند ===
    if chat_id == ADMIN_ID and re.match(r"^\d+(\.\d+)?$", text):
        for uid, data in pending.items():
            if data.get("step") == "waiting_rate":
                rate = float(text)
                total = int(data["amount"] * rate)
                data["rate"] = rate
                data["total"] = total
                data["step"] = "confirm"

                bot.send_message(uid, f"💰 نرخ هر واحد تعیین شد.\nمجموع پرداختی شما: {total:,} تومان.\nتایید می‌کنید؟ (✅ بله / ❌ خیر)")
                bot.send_message(ADMIN_ID, f"نرخ ثبت شد برای کاربر {uid}")
                return

    # === درخواست کاربر ===
    if st:
        step = st.get("step")

        if step == "amount":
            try:
                st["amount"] = float(text)
            except:
                return bot.reply_to(m, "عدد نامعتبر است، فقط مقدار وارد کنید.")
            st["step"] = "waiting_rate"
            bot.send_message(ADMIN_ID,
                             f"📩 درخواست جدید از {chat_id}\n"
                             f"جهت: {st['direction']}\n"
                             f"ارز: {st['currency']}\n"
                             f"مقدار: {st['amount']}\n\n"
                             f"لطفاً نرخ هر واحد به تومان را وارد کنید.")
            return bot.send_message(chat_id, "✅ درخواست شما ثبت شد و برای ادمین ارسال شد.")

        if step == "confirm":
            if "✅" in text or "بله" in text:
                st["step"] = "awaiting_info"
                bot.send_message(chat_id, "لطفاً اطلاعات حساب خود را وارد کنید (نام / شماره حساب / ...):")
            elif "❌" in text or "خیر" in text:
                pending.pop(chat_id, None)
                bot.send_message(chat_id, "❌ درخواست لغو شد.")
            return

        if step == "awaiting_info":
            st["info"] = text
            awaiting_admin_review.add(chat_id)
            st["step"] = None
            bot.send_message(ADMIN_ID,
                             f"📦 اطلاعات کاربر {chat_id}:\n{text}\n\n"
                             f"برای تایید بنویس: تایید {chat_id}\n"
                             f"برای اصلاح بنویس: اصلاح {chat_id} دلیل")
            bot.send_message(chat_id, "✅ اطلاعات شما ارسال شد، منتظر تایید پشتیبانی باشید.")
            return

    # === بررسی پیام‌های تایید/اصلاح ادمین ===
    if chat_id == ADMIN_ID:
        m1 = re.match(r"^تایید\s+(\d+)$", text)
        if m1:
            uid = int(m1.group(1))
            if uid in pending:
                total = pending[uid].get("total", 0)
                payment_url = f"https://{RAILWAY_DOMAIN}/pay/{total}"
                bot.send_message(uid, f"✅ اطلاعات شما تایید شد.\nلینک پرداخت:\n{payment_url}")
                bot.send_message(ADMIN_ID, f"✅ لینک پرداخت برای {uid} ارسال شد.")
            return

        m2 = re.match(r"^اصلاح\s+(\d+)\s+(.+)$", text)
        if m2:
            uid = int(m2.group(1))
            reason = m2.group(2)
            bot.send_message(uid, f"⚠️ پشتیبانی درخواست اصلاح داده:\n{reason}\nلطفاً اصلاح و ارسال کنید.")
            return

# ====================== اجرای موازی Flask + Bot ======================
def run_flask():
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))

def run_bot():
    bot.infinity_polling(timeout=60, long_polling_timeout=30)

if __name__ == "__main__":
    threading.Thread(target=run_flask).start()
    run_bot()
