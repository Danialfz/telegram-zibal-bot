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
RAILWAY_DOMAIN = os.getenv("RAILWAY_DOMAIN")

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

# ====================== قالب اطلاعات حساب بر اساس ارز ======================
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
awaiting_admin_review = set()

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

        res = requests.post("https://gateway.zibal.ir/v1/request", json=req, timeout=10)
        data = res.json()

        if data.get("result") == 100:
            track_id = data["trackId"]
            return redirect(f"https://gateway.zibal.ir/start/{track_id}")
        else:
            return jsonify({"error": f"❌ خطا از زیبال: {data}"})
    except Exception as e:
        return jsonify({"error": f"⚠️ خطا در ساخت لینک پرداخت: {str(e)}"})

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

# ====================== کیبوردها ======================
def main_menu():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(types.KeyboardButton("💸 انتقال ارز"))
    return kb

def direction_menu():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(types.KeyboardButton("🌍 از داخل به خارج"), types.KeyboardButton("🏦 از خارج به داخل"))
    kb.add(types.KeyboardButton("🔙 بازگشت"))
    return kb

# ====================== شروع ربات ======================
@bot.message_handler(commands=["start"])
def start_cmd(m):
    bot.send_message(m.chat.id, "سلام 👋 خوش اومدی!\nبرای شروع انتقال ارز، گزینه زیر رو انتخاب کن:", reply_markup=main_menu())

@bot.message_handler(func=lambda m: m.text == "💸 انتقال ارز")
def start_transfer(m):
    bot.send_message(m.chat.id, "جهت انتقال را انتخاب کنید:", reply_markup=direction_menu())

@bot.message_handler(func=lambda m: m.text in ["🌍 از داخل به خارج", "🏦 از خارج به داخل"])
def choose_currency(m):
    chat_id = m.chat.id
    direction = "از داخل به خارج" if "داخل به خارج" in m.text else "از خارج به داخل"
    pending[chat_id] = {"direction": direction, "step": "currency"}

    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    for code, name in currencies.items():
        kb.add(types.KeyboardButton(f"{name} ({code})"))
    kb.add(types.KeyboardButton("🔙 بازگشت"))
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

    # ===== ادمین نرخ وارد کند =====
    if chat_id == ADMIN_ID and re.match(r"^\d+(\.\d+)?$", text):
        for uid, data in pending.items():
            if data.get("step") == "waiting_rate":
                rate = float(text)
                total = int(data["amount"] * rate)
                data["rate"] = rate
                data["total"] = total
                data["step"] = "confirm"

                kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
                kb.add(types.KeyboardButton("✅ تایید"), types.KeyboardButton("❌ لغو"))
                bot.send_message(uid, f"💰 نرخ هر واحد تعیین شد.\nمجموع پرداختی: {total:,} تومان\nآیا تایید می‌کنید؟", reply_markup=kb)
                bot.send_message(ADMIN_ID, f"✅ نرخ ثبت شد برای کاربر {uid}")
                return

    if st:
        step = st.get("step")

        if step == "amount":
            try:
                st["amount"] = float(text)
            except:
                return bot.reply_to(m, "عدد نامعتبر است.")
            st["step"] = "waiting_rate"
            bot.send_message(ADMIN_ID, f"📩 درخواست جدید از {chat_id}\nجهت: {st['direction']}\nارز: {st['currency']}\nمقدار: {st['amount']}\n\nلطفاً نرخ هر واحد (تومان) را وارد کنید.")
            bot.send_message(chat_id, "✅ درخواست شما ثبت شد و برای ادمین ارسال شد.")
            return

        if step == "confirm":
            if "✅" in text or "تایید" in text or "بله" in text:
                st["step"] = "awaiting_info"
                direction = st["direction"]
                currency = st["currency"]
                if direction == "از داخل به خارج":
                    info_text = currency_info_template.get(currency, "👤 لطفاً اطلاعات گیرنده را وارد کنید.")
                else:
                    info_text = "👤 نام و نام خانوادگی\n💳 شماره کارت / حساب / شبا"
                bot.send_message(chat_id, f"لطفاً اطلاعات زیر را ارسال کنید:\n\n{info_text}")
            elif "❌" in text or "لغو" in text:
                pending.pop(chat_id, None)
                bot.send_message(chat_id, "❌ درخواست لغو شد.", reply_markup=main_menu())
            return

        if step == "awaiting_info":
            st["info"] = text
            st["step"] = None
            awaiting_admin_review.add(chat_id)
            bot.send_message(ADMIN_ID, f"📦 اطلاعات کاربر {chat_id}:\n{text}\n\nبرای تایید بنویس: تایید {chat_id}\nبرای اصلاح بنویس: اصلاح {chat_id} دلیل")
            bot.send_message(chat_id, "✅ اطلاعات شما ارسال شد و در انتظار تایید ادمین است.")
            return

    # ===== بررسی تایید یا اصلاح ادمین =====
    if chat_id == ADMIN_ID:
        m1 = re.match(r"^تایید\s+(\d+)$", text)
        if m1:
            uid = int(m1.group(1))
            if uid in pending:
                total = pending[uid].get("total", 0)
                payment_url = f"[برای پرداخت کلیک کنید](https://{RAILWAY_DOMAIN}/pay/{uid}/{total})"
                bot.send_message(uid, f"✅ اطلاعات شما تایید شد.\n{payment_url}", parse_mode="Markdown")
                bot.send_message(ADMIN_ID, f"💰 لینک پرداخت برای {uid} ارسال شد.")
            return

        m2 = re.match(r"^اصلاح\s+(\d+)\s+(.+)$", text)
        if m2:
            uid = int(m2.group(1))
            reason = m2.group(2)
            bot.send_message(uid, f"⚠️ اطلاعات نیاز به اصلاح دارد:\n{reason}")
            bot.send_message(ADMIN_ID, "✅ پیام اصلاح ارسال شد.")
            pending[uid]["step"] = "awaiting_info"
            return

# ====================== اجرای همزمان Flask و Bot ======================
def run_flask():
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))

def run_bot():
    bot.infinity_polling(timeout=60, long_polling_timeout=30)

if __name__ == "__main__":
    threading.Thread(target=run_flask).start()
    run_bot()
