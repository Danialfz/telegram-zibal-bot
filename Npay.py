import os
import re
import sys
import time
import threading
import requests
import telebot
from telebot import types
from flask import Flask, redirect, jsonify

# ---------------- تنظیمات از ENV ----------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    print("ERROR: BOT_TOKEN environment variable not set.")
    sys.exit(1)

try:
    ADMIN_ID = int(os.getenv("ADMIN_ID", "1611406302"))
except Exception:
    print("ERROR: ADMIN_ID must be an integer in environment variables.")
    sys.exit(1)

MERCHANT = os.getenv("MERCHANT")  # مرچنت زیبال (محرمانه - از ENV خوانده می‌شود)
RAILWAY_DOMAIN = os.getenv("RAILWAY_DOMAIN", None)  # برای callback یا لینک‌سازی (اختیاری)

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

# ---------------- اطلاعات ارزها ----------------
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

# قالب اطلاعات مقصد برای داخل -> خارج براساس ارز
currency_info_template = {
    "USD": "نام و نام خانوادگی دریافتی / نام بانک / شماره حساب / SWIFT",
    "EUR": "نام و نام خانوادگی دریافتی / کشور / نام بانک / شماره حساب یا IBAN",
    "GBP": "نام و نام خانوادگی دریافتی / نام بانک / شماره حساب / Sort Code",
    "CHF": "نام و نام خانوادگی دریافتی / نام بانک / شماره حساب یا IBAN / SWIFT",
    "CAD": "نام و نام خانوادگی دریافتی / نام بانک / شماره حساب / Transit Number",
    "AUD": "نام و نام خانوادگی دریافتی / نام بانک / BSB Code / شماره حساب",
    "AED": "نام و نام خانوادگی دریافتی / نام بانک / شماره حساب یا IBAN / SWIFT",
    "TRY": "نام و نام خانوادگی دریافتی / نام بانک / شماره IBAN (TR...)",
    "CNY": "نام و نام خانوادگی دریافتی / نام بانک / شماره حساب / SWIFT / شهر",
    "INR": "نام و نام خانوادگی دریافتی / نام بانک / IFSC / شماره حساب",
    "JPY": "نام و نام خانوادگی دریافتی / نام بانک / شماره حساب / SWIFT",
    "SAR": "نام و نام خانوادگی دریافتی / نام بانک / شماره IBAN (SA...)",
    "KWD": "نام و نام خانوادگی دریافتی / نام بانک / شماره حساب / IBAN (KW...)",
    "OMR": "نام و نام خانوادگی دریافتی / نام بانک / شماره حساب / SWIFT",
    "QAR": "نام و نام خانوادگی دریافتی / نام بانک / شماره IBAN (QA...)"
}

# ---------------- حافظه موقت ----------------
# pending[chat_id] = {
#   "direction": "از داخل به خارج" | "از خارج به داخل",
#   "currency": "USD",
#   "amount": float,
#   "awaiting": "choose_currency"|"amount"|"waiting_rate"|"confirm"|"awaiting_info"|"edit"|None,
#   "rate": float,
#   "total": int,
#   "last_menu": str (برای بازگشت راحت)
# }
pending = {}
awaiting_admin_review = set()  # کاربرانی که اطلاعات‌شان برای ادمین فرستاده شده

# ---------------- کیبوردها ----------------
def main_menu_markup():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(types.KeyboardButton("💸 انتقال ارز"))
    return kb

def direction_markup():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(types.KeyboardButton("🌍 از داخل به خارج"))
    kb.add(types.KeyboardButton("🏦 از خارج به داخل"))
    kb.add(types.KeyboardButton("🔙 بازگشت به منو"))
    return kb

def currencies_markup(back_label="🔙 بازگشت"):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    for code, name in currencies.items():
        kb.add(types.KeyboardButton(f"{name} ({code})"))
    kb.add(types.KeyboardButton(back_label))
    return kb

def back_to_direction_markup():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(types.KeyboardButton("🔙 بازگشت"))
    return kb

def confirm_keyboard():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    kb.add(types.KeyboardButton("✅ تایید"), types.KeyboardButton("❌ لغو"))
    kb.add(types.KeyboardButton("🔙 بازگشت"))
    return kb

# ---------------- توابع کمکی ----------------
def create_zibal_payment(amount_toman: int, description: str = ""):
    """
    ایجاد درخواست درگاه زیبال — مقدار را بر حسب تومان بفرست (int).
    مرچنت از ENV خوانده می‌شود. مقدار بازگشتی: آدرس redirect (start) یا None و خطا.
    """
    if not MERCHANT:
        return None, "MERCHANT not configured"

    payload = {
        "merchant": MERCHANT,
        "amount": int(amount_toman),
        "callbackUrl": f"https://{RAILWAY_DOMAIN}/zibal/callback" if RAILWAY_DOMAIN else "",
        "description": description
    }
    try:
        r = requests.post("https://gateway.zibal.ir/v1/request", json=payload, timeout=10)
        r.raise_for_status()
        data = r.json()
        if data.get("result") == 100:
            track_id = data.get("trackId")
            return f"https://gateway.zibal.ir/start/{track_id}", None
        else:
            return None, data
    except Exception as e:
        return None, str(e)

# ---------------- ربات: رویدادها ----------------
@bot.message_handler(commands=['start'])
def cmd_start(m):
    pending.pop(m.chat.id, None)
    awaiting_admin_review.discard(m.chat.id)
    bot.send_message(m.chat.id,
                     "سلام 👋 به ربات نوسان‌پی خوش‌آمدید.\nبرای شروع «💸 انتقال ارز» را انتخاب کنید.",
                     reply_markup=main_menu_markup())

@bot.message_handler(func=lambda msg: msg.text == "💸 انتقال ارز")
def cmd_transfer(msg):
    bot.send_message(msg.chat.id, "لطفاً جهت انتقال را انتخاب کنید:", reply_markup=direction_markup())

@bot.message_handler(func=lambda msg: msg.text in ["🌍 از داخل به خارج", "🏦 از خارج به داخل"])
def choose_currency_list(msg):
    chat_id = msg.chat.id
    direction = "از داخل به خارج" if msg.text == "🌍 از داخل به خارج" else "از خارج به داخل"
    pending[chat_id] = {
        "direction": direction,
        "currency": None,
        "amount": None,
        "awaiting": "choose_currency",
        "rate": None,
        "total": None
    }
    bot.send_message(chat_id, "ارز مورد نظر را انتخاب کنید:", reply_markup=currencies_markup(back_label="🔙 بازگشت"))

@bot.message_handler(func=lambda msg: bool(re.match(r".*\([A-Z]{3}\)\s*$", msg.text or "")))
def handle_currency_choice(msg):
    chat_id = msg.chat.id
    if chat_id not in pending or pending[chat_id].get("awaiting") not in ("choose_currency",):
        # کاربر شاید از ابتدا نیامده
        return bot.reply_to(msg, "ابتدا جهت انتقال را انتخاب کنید (داخل به خارج یا خارج به داخل).")

    match = re.search(r"\(([A-Z]{3})\)\s*$", msg.text.strip())
    if not match:
        return bot.reply_to(msg, "لطفاً از کلیدهای ارز استفاده کنید.")
    code = match.group(1)
    if code not in currencies:
        return bot.reply_to(msg, "این ارز در فهرست نیست.")

    pending[chat_id]["currency"] = code
    pending[chat_id]["awaiting"] = "amount"
    bot.send_message(chat_id,
                     f"شما {currencies[code]} را انتخاب کردید.\nلطفاً مقدار (به عدد) را وارد کنید:",
                     reply_markup=back_to_direction_markup())

@bot.message_handler(func=lambda msg: True)
def router(msg):
    chat_id = msg.chat.id
    text = (msg.text or "").strip()

    # بازگشت به منو
    if text in ["🔙 بازگشت به منو", "/start"]:
        pending.pop(chat_id, None)
        awaiting_admin_review.discard(chat_id)
        return cmd_start(msg)

    # اگر کاربر در مرحله "amount" است
    st = pending.get(chat_id)
    if st and st.get("awaiting") == "amount":
        # handle back
        if text == "🔙 بازگشت":
            # بازگشت به انتخاب ارز (فهرست ارزها)
            st["awaiting"] = "choose_currency"
            return bot.send_message(chat_id, "لطفاً ارز مورد نظر را انتخاب کنید:", reply_markup=currencies_markup(back_label="🔙 بازگشت"))

        # مقدار را بخوان
        try:
            amount = float(text.replace(",", "").replace(" ", ""))
            if amount <= 0:
                raise ValueError()
        except:
            return bot.reply_to(msg, "⚠️ مقدار نامعتبر. لطفاً فقط عدد مثبت وارد کنید (مثلاً: 2500).")

        st["amount"] = amount
        st["awaiting"] = "waiting_rate"

        # اطلاع به ادمین برای تعیین نرخ (اولویت: قدیمی‌ترین waiting_rate)
        bot.send_message(ADMIN_ID,
                         f"📩 درخواست جدید از @{msg.from_user.username or msg.from_user.first_name}\n"
                         f"📍 جهت: {st['direction']}\n"
                         f"💱 ارز: {currencies[st['currency']]} ({st['currency']})\n"
                         f"📊 مقدار: {amount:,}\n"
                         f"🆔 Chat ID: {chat_id}\n\n"
                         "📌 لطفاً نرخ هر واحد را به تومان وارد کنید (فقط عدد).")
        return bot.send_message(chat_id, "✅ درخواست شما ثبت شد؛ منتظر پاسخ ادمین باشید.", reply_markup=main_menu_markup())

    # اگر کاربر در مرحله confirm است (دکمه‌ها ساخته می‌شود)
    if st and st.get("awaiting") == "confirm":
        if text == "🔙 بازگشت":
            # برگشت به منوی اصلی (یا انتخاب ارز) — تصمیم به برگشت به منو
            st["awaiting"] = "choose_currency"
            return bot.send_message(chat_id, "شما به مرحلهٔ انتخاب ارز بازگشتید.", reply_markup=currencies_markup(back_label="🔙 بازگشت"))
        if text == "✅ تایید":
            # حرکت به مرحله ارسال اطلاعات بسته به جهت
            st["awaiting"] = "awaiting_info"
            currency = st.get("currency")
            if st.get("direction") == "از داخل به خارج":
                info_req = currency_info_template.get(currency, "نام و نام خانوادگی دریافت‌کننده / نام بانک / شماره حساب / کشور")
                bot.send_message(chat_id,
                                 "✅ تراکنش تأیید شد.\n\n"
                                 f"✉️ لطفاً اطلاعات حساب مقصد را به صورت متن ارسال کنید:\n({info_req})",
                                 reply_markup=back_to_direction_markup())
            else:
                # خارج->داخل: الگوی داخلی
                bot.send_message(chat_id,
                                 "✅ تراکنش تأیید شد.\n\n"
                                 "✉️ لطفاً اطلاعات حساب (برای واریز داخلی) را به صورت متن ارسال کنید:\n"
                                 "(شماره حساب / شماره کارت / شماره شبا / نام و نام خانوادگی دریافت‌کننده / نام و نام خانوادگی واریزکننده)",
                                 reply_markup=back_to_direction_markup())
            return
        if text == "❌ لغو":
            pending.pop(chat_id, None)
            return bot.send_message(chat_id, "❌ روند انتقال ارز شما لغو شد.", reply_markup=main_menu_markup())
        # اگر متن دیگری باشد
        return bot.send_message(chat_id, "لطفاً از دکمه‌های «✅ تایید» یا «❌ لغو» استفاده کنید.", reply_markup=confirm_keyboard())

    # اگر کاربر در مرحله ارسال اطلاعات (awaiting_info)
    if st and st.get("awaiting") == "awaiting_info":
        # از ارسال لینک یا تگ جلوگیری کن
        if re.search(r"https?://|t\.me|@", text, re.IGNORECASE):
            try:
                bot.delete_message(chat_id, msg.message_id)
            except:
                pass
            return bot.send_message(chat_id, "⚠️ لطفاً فقط متن ساده ارسال کنید (بدون لینک یا تگ).")

        # ارسال اطلاعات به ادمین (فقط متن)
        bot.send_message(ADMIN_ID,
                         f"📦 اطلاعات حساب از کاربر {chat_id}:\n\n{text}\n\n"
                         f"برای تایید بنویسید: تایید {chat_id}\n"
                         f"برای اصلاح بنویسید: اصلاح {chat_id} <دلیل>")
        awaiting_admin_review.add(chat_id)
        # نگه داشتن pending کامل تا ادمین تایید/اصلاح کند
        st["awaiting"] = None
        return bot.send_message(chat_id, "✅ اطلاعات شما ارسال شد؛ منتظر بررسی پشتیبانی باشید.", reply_markup=main_menu_markup())

    # -- ادمین: پیام‌های ویژه --
    if chat_id == ADMIN_ID:
        # تایید: "تایید <user_id>"
        m1 = re.match(r"^\s*تایید\s+(\d+)\s*$", text, re.IGNORECASE)
        if m1:
            uid = int(m1.group(1))
            if uid in awaiting_admin_review or uid in pending:
                p = pending.get(uid)
                if not p:
                    # اگر pending پاک شده یا نداشتیم، به ادمین بگو
                    return bot.send_message(ADMIN_ID, "⚠️ خطا: درخواستی برای آن کاربر موجود نیست.")
                total = p.get("total")
                # اگر total موجود نباشد، باید ادمین ابتدا نرخ را وارد کند؛ اطلاع بده
                if not total:
                    return bot.send_message(ADMIN_ID, f"⚠️ مجموع برای کاربر {uid} موجود نیست. ابتدا نرخ را وارد کنید یا بررسی کنید.")
                # ساخت لینک پرداخت امن با استفاده از MERCHANT (مخفی در ENV)
                payment_url, err = create_zibal_payment(int(total), description=f"پرداخت سفارش {uid}")
                if payment_url:
                    # ارسال لینک به کاربر
                    bot.send_message(uid, f"✅ اطلاعات شما تأیید شد.\nلینک پرداخت:\n{payment_url}\n\n💰 مبلغ قابل پرداخت: {int(total):,} تومان")
                    awaiting_admin_review.discard(uid)
                    return bot.send_message(ADMIN_ID, f"✅ لینک پرداخت برای {uid} ارسال شد.")
                else:
                    return bot.send_message(ADMIN_ID, f"❌ خطا در ساخت لینک پرداخت: {err}")
            return bot.send_message(ADMIN_ID, "⚠️ این کاربر در انتظار بررسی نیست.")

        # اصلاح: "اصلاح <user_id> <متن دلیل>"
        m2 = re.match(r"^\s*اصلاح\s+(\d+)\s+(.+)$", text, re.IGNORECASE)
        if m2:
            uid = int(m2.group(1))
            reason = m2.group(2).strip()
            if uid in awaiting_admin_review or uid in pending:
                # علامت گذاری تا کاربر اصلاح کند
                pending.setdefault(uid, {})["awaiting"] = "edit"
                # ارسال دلیل برای کاربر (فقط متن)
                bot.send_message(uid, f"⚠️ پشتیبانی درخواست اصلاح کرد:\n\n{reason}\n\nلطفاً اطلاعات اصلاح‌شده را ارسال کنید (متن ساده، بدون لینک).")
                awaiting_admin_review.discard(uid)
                return bot.send_message(ADMIN_ID, f"✅ پیام اصلاح برای {uid} ارسال شد.")
            return bot.send_message(ADMIN_ID, "⚠️ این کاربر در انتظار بررسی نیست.")

        # اگر پیام فقط عدد باشد => تعیین نرخ (اولین waiting_rate)
        if re.match(r"^\d+(\.\d+)?$", text):
            rate = float(text)
            # پیدا کردن قدیمی‌ترین waiting_rate
            target = None
            for uid, data in pending.items():
                if data.get("awaiting") == "waiting_rate":
                    target = uid
                    break
            if not target:
                return bot.send_message(ADMIN_ID, "⚠️ در حال حاضر هیچ درخواستی در انتظار نرخ نیست.")
            data = pending[target]
            total = int(data["amount"] * rate)
            data["rate"] = rate
            data["total"] = total
            data["awaiting"] = "confirm"
            # ارسال مجموع به کاربر (بدون نمایش نرخ واحد)
            bot.send_message(target,
                             f"💰 مبلغ نهایی مشخص شد:\n\n"
                             f"• مقدار: {data['amount']:,} {data['currency']}\n"
                             f"• مبلغ کل پرداختی: {total:,} تومان\n\n"
                             "لطفاً تأیید یا لغو کنید.",
                             reply_markup=confirm_keyboard())
            return bot.send_message(ADMIN_ID, f"✅ نرخ ثبت شد و مجموع برای کاربر {target} ارسال شد.")

        # پیام ادمین دیگر
        return bot.send_message(ADMIN_ID,
                                "راهنمای ادمین:\n"
                                "- برای تعیین نرخ: فقط عدد (مثلاً 1234500)\n"
                                "- برای تایید اطلاعات: تایید <user_id>\n"
                                "- برای اصلاح: اصلاح <user_id> <متن دلیل>")

    # اگر هیچ شرطی برقرار نبود، راهنمایی نمایش بده
    return bot.send_message(chat_id, "برای شروع «💸 انتقال ارز» را انتخاب کنید.", reply_markup=main_menu_markup())


# ---------------- Flask endpoints (برای redirect پرداخت) ----------------
@app.route("/zibal/callback", methods=["GET", "POST"])
def zibal_callback():
    # زیبال بعد از پرداخت بازمی‌گردد؛ این‌جا می‌توان وضعیت پرداخت را بررسی یا ذخیره کرد.
    # ما اینجا فقط پاسخ می‌دهیم (می‌توانید لاگ یا پردازش اضافه کنید).
    data = request.values.to_dict()
    return jsonify({"status": "received", "data": data})

# اجرای موازی Flask + Bot
def run_flask():
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

def run_bot():
    bot.infinity_polling(timeout=60, long_polling_timeout=30)

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    run_bot()
