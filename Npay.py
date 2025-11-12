# =============== Npay.py — نسخهٔ نهایی و کامل ===============
import os
import re
import threading
import requests
import telebot
from telebot import types
from flask import Flask, request, jsonify, redirect

# ---------------- تنظیمات اصلی (متغیرهای محیطی) ----------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("❌ BOT_TOKEN env var is required")

try:
    ADMIN_ID = int(os.getenv("ADMIN_ID", "1611406302"))
except Exception:
    raise RuntimeError("❌ ADMIN_ID must be integer")

MERCHANT = os.getenv("MERCHANT")  # مثال: 67fbd99f6f3803001057a0bf
RAILWAY_DOMAIN = os.getenv("RAILWAY_DOMAIN")  # مثال: bot.navasanpay.com

if not MERCHANT or not RAILWAY_DOMAIN:
    raise RuntimeError("❌ MERCHANT و RAILWAY_DOMAIN باید در env ست شوند")

# ---------------- آماده‌سازی ربات و Flask ----------------
bot = telebot.TeleBot(BOT_TOKEN)
try:
    bot.remove_webhook()
except Exception:
    pass

app = Flask(__name__)

# ---------------- لیست ارزها ----------------
currencies = {
    "USD": "دلار آمریکا 🇺🇸", "EUR": "یورو 🇪🇺", "GBP": "پوند انگلیس 🇬🇧",
    "CHF": "فرانک سوئیس 🇨🇭", "CAD": "دلار کانادا 🇨🇦", "AUD": "دلار استرالیا 🇦🇺",
    "AED": "درهم امارات 🇦🇪", "TRY": "لیر ترکیه 🇹🇷", "CNY": "یوان چین 🇨🇳",
    "INR": "روپیه هند 🇮🇳", "JPY": "ین ژاپن 🇯🇵", "SAR": "ریال عربستان 🇸🇦",
    "KWD": "دینار کویت 🇰🇼", "OMR": "ریال عمان 🇴🇲", "QAR": "ریال قطر 🇶🇦"
}

# ---------------- قالب اطلاعات حساب ----------------
currency_info_template = {
    "USD": "👤 نام و نام خانوادگی گیرنده\n🏦 نام بانک\n💳 شماره حساب یا IBAN\n🌍 کشور / شهر بانک\n🔢 SWIFT Code",
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

# ---------------- متغیرهای موقت ----------------
pending = {}
awaiting_admin_review = set()
last_target_for_admin = None

# ---------------- منوها ----------------
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
    kb.add("🔙 بازگشت")
    return kb

# ---------------- مسیر پرداخت زیبال ----------------
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
    except Exception as e:
        return jsonify({"error": f"⚠️ خطا در ساخت لینک پرداخت: {str(e)}"}), 500

    if data.get("result") == 100:
        track_id = data["trackId"]
        return redirect(f"https://gateway.zibal.ir/start/{track_id}")
    else:
        return jsonify({"error": data}), 400

# ---------------- مسیر وریفای زیبال ----------------
@app.route("/verify/<int:user_id>", methods=["GET", "POST"])
def verify_payment(user_id):
    track_id = request.args.get("trackId")
    if not track_id:
        return "پارامتر trackId ارسال نشده.", 400
    try:
        req = {"merchant": MERCHANT, "trackId": track_id}
        res = requests.post("https://gateway.zibal.ir/v1/verify", json=req, timeout=15)
        data = res.json()
    except Exception as e:
        return f"⚠️ خطا در بررسی پرداخت: {str(e)}", 500
    if data.get("result") == 100:
        bot.send_message(user_id, "✅ پرداخت با موفقیت انجام شد 💚")
        bot.send_message(ADMIN_ID, f"💰 کاربر {user_id} پرداخت را انجام داد.")
        return "✅ موفق"
    else:
        bot.send_message(user_id, "❌ پرداخت ناموفق بود.")
        return f"❌ {data}", 400

# ---------------- منطق ربات ----------------
@bot.message_handler(commands=["start"])
def start(m):
    pending.pop(m.chat.id, None)
    bot.send_message(m.chat.id, "سلام 👋 به ربات نوسان‌پی خوش آمدید", reply_markup=main_menu())

@bot.message_handler(func=lambda m: m.text == "💸 انتقال ارز")
def ask_direction(m):
    bot.send_message(m.chat.id, "جهت انتقال را انتخاب کنید:", reply_markup=direction_menu())

@bot.message_handler(func=lambda m: m.text in ["🌍 از داخل به خارج", "🏦 از خارج به داخل"])
def choose_currency(m):
    direction = "از داخل به خارج" if "داخل به خارج" in m.text else "از خارج به داخل"
    pending[m.chat.id] = {"direction": direction, "step": "currency"}
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    for code, name in currencies.items():
        kb.add(f"{name} ({code})")
    kb.add("🔙 بازگشت")
    bot.send_message(m.chat.id, "ارز مورد نظر را انتخاب کنید:", reply_markup=kb)

@bot.message_handler(func=lambda m: re.search(r"\(([A-Z]{3})\)", m.text or ""))
def got_currency(m):
    match = re.search(r"\(([A-Z]{3})\)", m.text)
    if not match:
        return
    code = match.group(1)
    st = pending.get(m.chat.id)
    if not st:
        return
    st["currency"] = code
    st["step"] = "amount"
    bot.send_message(m.chat.id, f"مقدار {currencies.get(code)} را وارد کنید:", reply_markup=types.ReplyKeyboardMarkup(resize_keyboard=True).add("🔙 بازگشت"))

@bot.message_handler(func=lambda m: True)
def all_msgs(m):
    global last_target_for_admin
    chat_id = m.chat.id
    text = (m.text or "").strip()
    st = pending.get(chat_id)

    if text == "🔙 بازگشت":
        pending.pop(chat_id, None)
        return start(m)

    # ----------- ادمین -----------
    if chat_id == ADMIN_ID:
        m_confirm = re.match(r"^تایید\s+(\d+)$", text)
        if m_confirm:
            uid = int(m_confirm.group(1))
            if uid not in pending:
                return bot.send_message(ADMIN_ID, "⚠️ کاربر یافت نشد.")
            direction = pending[uid].get("direction")
            total = pending[uid].get("total", 0)

            # ✅ اگر از خارج به داخل → بدون پرداخت آنلاین
            if direction == "از خارج به داخل":
                bot.send_message(uid,
                    "✅ اطلاعات شما تایید شد.\n\n"
                    "💵 لطفاً مبلغ را به حساب زیر واریز کنید:\n"
                    "🏦 بانک ملت\n💳 6104-3371-1234-5678\n👤 شرکت نوسان‌پی\n\n"
                    "پس از واریز، رسید پرداخت را ارسال کنید 🙏"
                )
                bot.send_message(ADMIN_ID, f"📨 تایید شد (از خارج به داخل) برای {uid}")
                return

            # 🌍 اگر از داخل به خارج → لینک زیبال
            try:
                callback_url = f"https://{RAILWAY_DOMAIN}/verify/{uid}"
                req = {"merchant": MERCHANT, "amount": total, "callbackUrl": callback_url,
                       "description": f"پرداخت {total:,} تومان از طریق ربات نوسان‌پی"}
                res = requests.post("https://gateway.zibal.ir/v1/request", json=req, timeout=15)
                data = res.json()
                if data.get("result") == 100:
                    link = f"https://gateway.zibal.ir/start/{data['trackId']}"
                    bot.send_message(uid, f"✅ اطلاعات شما تایید شد.\n\n💳 <a href='{link}'>برای پرداخت کلیک کنید</a>",
                                     parse_mode="HTML")
                    bot.send_message(ADMIN_ID, f"💰 لینک پرداخت برای {uid} ارسال شد.")
                else:
                    bot.send_message(ADMIN_ID, f"❌ خطا از زیبال: {data}")
            except Exception as e:
                bot.send_message(ADMIN_ID, f"⚠️ خطا در تماس زیبال: {e}")
            return

        # نرخ <id> <rate>
        m_rate = re.match(r"^نرخ\s+(\d+)\s+(\d+(\.\d+)?)$", text)
        if m_rate:
            uid, rate = int(m_rate.group(1)), float(m_rate.group(2))
            if uid in pending:
                amount = pending[uid].get("amount", 0)
                total = int(amount * rate)
                pending[uid].update({"rate": rate, "total": total, "step": "confirm"})
                bot.send_message(uid, f"💰 مبلغ نهایی: {total:,} تومان\nآیا تایید می‌کنید؟", reply_markup=confirm_keyboard())
                bot.send_message(ADMIN_ID, f"✅ نرخ {rate} برای {uid} تنظیم شد.")
            return

        return bot.send_message(ADMIN_ID, "📘 راهنما:\nتایید <id>\nنرخ <id> <rate>")
    
    # ----------- کاربران -----------
    if st:
        step = st.get("step")
        if step == "amount":
            try:
                st["amount"] = float(text)
                st["step"] = "waiting_rate"
                bot.send_message(ADMIN_ID, f"📩 درخواست جدید از {chat_id}\nجهت: {st['direction']}\nارز: {st['currency']}\nمقدار: {st['amount']}")
            except:
                bot.send_message(chat_id, "⚠️ فقط عدد وارد کنید.")
            return

        if step == "confirm":
            if text in ["✅ تایید", "تایید"]:
                st["step"] = "awaiting_info"
                if st["direction"] == "از داخل به خارج":
                    msg = currency_info_template.get(st["currency"])
                else:
                    msg = "👤 نام و نام خانوادگی\n💳 شماره کارت / حساب / شبا"
                bot.send_message(chat_id, msg)
            elif text in ["❌ لغو", "لغو"]:
                pending.pop(chat_id, None)
                bot.send_message(chat_id, "❌ لغو شد.", reply_markup=main_menu())
            return

        if step == "awaiting_info":
            st["info"] = text
            st["step"] = None
            bot.send_message(ADMIN_ID, f"📦 اطلاعات حساب {chat_id}:\n{text}\n\nبرای تایید بنویس: تایید {chat_id}")
            bot.send_message(chat_id, "✅ اطلاعات ارسال شد و در انتظار تایید ادمین هستید.", reply_markup=main_menu())
            return

    bot.send_message(chat_id, "برای شروع، دکمه «💸 انتقال ارز» را بزنید.", reply_markup=main_menu())

# ---------------- اجرای Flask و Bot ----------------
def run_flask():
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))

def run_bot():
    bot.infinity_polling(timeout=60, long_polling_timeout=30)

if __name__ == "__main__":
    print("✅ Npay bot started")
    threading.Thread(target=run_flask).start()
    run_bot()
