# =============== Npay.py — نسخه نهایی ===============
import os
import re
import threading
import requests
import telebot
from telebot import types
from flask import Flask, request, jsonify, redirect

# ---------------- تنظیمات محیطی ----------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "1611406302"))
MERCHANT = os.getenv("MERCHANT")
RAILWAY_DOMAIN = os.getenv("RAILWAY_DOMAIN")

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

# ---------------- اطلاعات ارزها ----------------
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
    "CHF": "👤 نام گیرنده\n🏦 نام بانک\n💳 شماره حساب یا IBAN\n🔢 SWIFT Code\n🌍 کشور بانک"
}

pending = {}
last_target_for_admin = None

# ---------------- کیبوردها ----------------
def main_menu():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("💸 انتقال ارز")
    return kb

def direction_menu():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("🌍 از داخل به خارج", "🏦 از خارج به داخل")
    kb.add("🔙 بازگشت")
    return kb

def confirm_keyboard():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("✅ تایید", "❌ لغو")
    return kb

# ---------------- درگاه زیبال ----------------
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
        res = requests.post("https://gateway.zibal.ir/v1/request", json=req, timeout=10)
        data = res.json()
        if data.get("result") == 100:
            return redirect(f"https://gateway.zibal.ir/start/{data['trackId']}")
        return jsonify({"error": data}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/verify/<int:user_id>", methods=["GET", "POST"])
def verify_payment(user_id):
    track_id = request.args.get("trackId")
    if not track_id:
        return "پارامتر trackId ارسال نشده.", 400
    try:
        req = {"merchant": MERCHANT, "trackId": track_id}
        res = requests.post("https://gateway.zibal.ir/v1/verify", json=req, timeout=10)
        data = res.json()
        if data.get("result") == 100:
            bot.send_message(user_id, "✅ پرداخت با موفقیت انجام شد.")
            bot.send_message(ADMIN_ID, f"💰 پرداخت موفق برای {user_id}")
            return "✅ پرداخت با موفقیت انجام شد."
        bot.send_message(user_id, "❌ پرداخت ناموفق بود.")
        return f"❌ پرداخت ناموفق: {data}"
    except Exception as e:
        return f"⚠️ خطا در بررسی پرداخت: {str(e)}"

# ---------------- منطق ربات ----------------
@bot.message_handler(commands=["start"])
def start_cmd(m):
    bot.send_message(m.chat.id, "سلام 👋 برای شروع انتقال ارز گزینه زیر را انتخاب کن:", reply_markup=main_menu())

@bot.message_handler(func=lambda m: m.text == "💸 انتقال ارز")
def choose_direction(m):
    bot.send_message(m.chat.id, "نوع انتقال را انتخاب کنید:", reply_markup=direction_menu())

@bot.message_handler(func=lambda m: m.text in ["🌍 از داخل به خارج", "🏦 از خارج به داخل"])
def choose_currency(m):
    direction = "از داخل به خارج" if "داخل به خارج" in m.text else "از خارج به داخل"
    pending[m.chat.id] = {"direction": direction, "step": "currency"}
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    for code, name in currencies.items():
        kb.add(types.KeyboardButton(f"{name} ({code})"))
    bot.send_message(m.chat.id, "ارز مورد نظر را انتخاب کنید:", reply_markup=kb)

@bot.message_handler(func=lambda m: re.search(r"\(([A-Z]{3})\)", m.text or ""))
def got_currency(m):
    chat_id = m.chat.id
    match = re.search(r"\(([A-Z]{3})\)", m.text)
    if not match: return
    code = match.group(1)
    st = pending.get(chat_id)
    if not st: return
    st["currency"] = code
    st["step"] = "amount"
    bot.send_message(chat_id, f"مقدار {currencies.get(code, code)} را وارد کنید (مثلاً 2500):")

@bot.message_handler(func=lambda m: True)
def main_logic(m):
    global last_target_for_admin
    chat_id, text = m.chat.id, m.text.strip()
    st = pending.get(chat_id)

    if chat_id == ADMIN_ID:
        # ارسال <user_id> <متن> برای حالت از خارج به داخل
        match = re.match(r"^ارسال\s+(\d+)\s+(.+)$", text)
        if match:
            uid = int(match.group(1))
            msg = match.group(2)
            bot.send_message(uid, f"📩 پیام از پشتیبانی:\n\n{msg}")
            bot.send_message(ADMIN_ID, f"✅ پیام برای {uid} ارسال شد.")
            return
        return bot.send_message(ADMIN_ID, "📘 راهنما:\n- ارسال <user_id> <متن> برای ارسال پیام به کاربر\n- تایید <user_id> برای پرداخت داخل به خارج")

    if not st:
        return bot.send_message(chat_id, "برای شروع انتقال روی 💸 انتقال ارز بزنید.", reply_markup=main_menu())

    step = st.get("step")
    direction = st.get("direction")

    if step == "amount":
        try:
            amount = float(text.replace(",", "").replace(" ", ""))
        except:
            return bot.reply_to(m, "⚠️ عدد معتبر وارد کنید.")
        st["amount"] = amount
        if direction == "از داخل به خارج":
            st["step"] = "waiting_confirm"
            bot.send_message(chat_id, f"مبلغ تقریبی پرداخت شما: {amount:,} تومان.\nتایید می‌کنید؟", reply_markup=confirm_keyboard())
        else:
            st["step"] = "awaiting_admin"
            bot.send_message(chat_id, "✅ درخواست شما ثبت شد و برای ادمین ارسال شد.", reply_markup=main_menu())
            bot.send_message(ADMIN_ID, f"📥 درخواست جدید از خارج به داخل:\nکاربر {chat_id}\nارز: {st['currency']}\nمقدار: {amount}")

    elif step == "waiting_confirm":
        if text in ["✅ تایید", "تایید"]:
            total = int(st["amount"])
            callback_url = f"https://{RAILWAY_DOMAIN}/verify/{chat_id}"
            req = {
                "merchant": MERCHANT,
                "amount": total,
                "callbackUrl": callback_url,
                "description": f"پرداخت {total:,} تومان از طریق ربات نوسان‌پی"
            }
            res = requests.post("https://gateway.zibal.ir/v1/request", json=req)
            data = res.json()
            if data.get("result") == 100:
                pay_link = f"https://gateway.zibal.ir/start/{data['trackId']}"
                bot.send_message(chat_id, f"💳 برای پرداخت کلیک کنید:\n{pay_link}")
                bot.send_message(ADMIN_ID, f"📤 لینک پرداخت برای کاربر {chat_id} ارسال شد.")
            else:
                bot.send_message(chat_id, f"❌ خطا در ایجاد پرداخت: {data}")
        else:
            bot.send_message(chat_id, "پرداخت لغو شد.", reply_markup=main_menu())

# ---------------- اجرای همزمان Bot + Flask ----------------
def run_flask():
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))

def run_bot():
    bot.infinity_polling(timeout=60, long_polling_timeout=30)

if __name__ == "__main__":
    threading.Thread(target=run_flask).start()
    run_bot()
