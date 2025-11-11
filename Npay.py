import os
import re
import sys
import telebot
from telebot import types

# ---------------- تنظیمات ----------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    print("ERROR: BOT_TOKEN environment variable not set.")
    sys.exit(1)

try:
    ADMIN_ID = int(os.getenv("ADMIN_ID", "1611406302"))
except Exception:
    print("ERROR: ADMIN_ID must be an integer in environment variables.")
    sys.exit(1)

MERCHANT_CODE = os.getenv("MERCHANT_CODE", "67fbd99f6f3803001057a0bf")  # 🔹 مرچنت واقعی زیبال

bot = telebot.TeleBot(BOT_TOKEN)

# ---------------- فهرست ارزها ----------------
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

# ---------------- قالب اطلاعات برای داخل->خارج بر اساس ارز ----------------
currency_info_template = {
    "USD": "نام و نام خانوادگی دریافت‌کننده / نام بانک / شماره حساب / SWIFT",
    "EUR": "نام و نام خانوادگی دریافت‌کننده / کشور / نام بانک / شماره حساب یا IBAN",
    "GBP": "نام و نام خانوادگی دریافت‌کننده / نام بانک / شماره حساب / Sort Code",
    "CHF": "نام و نام خانوادگی دریافت‌کننده / نام بانک / شماره حساب یا IBAN / SWIFT",
    "CAD": "نام و نام خانوادگی دریافت‌کننده / نام بانک / شماره حساب / Transit Number",
    "AUD": "نام و نام خانوادگی دریافت‌کننده / نام بانک / BSB Code / شماره حساب",
    "AED": "نام و نام خانوادگی دریافت‌کننده / نام بانک / شماره حساب یا IBAN / SWIFT",
    "TRY": "نام و نام خانوادگی دریافت‌کننده / نام بانک / شماره IBAN (TR...)",
    "CNY": "نام و نام خانوادگی دریافت‌کننده / نام بانک / شماره حساب / SWIFT / شهر",
    "INR": "نام و نام خانوادگی دریافت‌کننده / نام بانک / IFSC / شماره حساب",
    "JPY": "نام و نام خانوادگی دریافت‌کننده / نام بانک / شماره حساب / SWIFT",
    "SAR": "نام و نام خانوادگی دریافت‌کننده / نام بانک / شماره IBAN (SA...)",
    "KWD": "نام و نام خانوادگی دریافت‌کننده / نام بانک / شماره حساب / IBAN (KW...)",
    "OMR": "نام و نام خانوادگی دریافت‌کننده / نام بانک / شماره حساب / SWIFT",
    "QAR": "نام و نام خانوادگی دریافت‌کننده / نام بانک / شماره IBAN (QA...)"
}

# ---------------- حافظهٔ موقت ----------------
pending = {}
awaiting_admin_review = set()

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

def back_to_main_markup():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(types.KeyboardButton("🔙 بازگشت به منو"))
    return kb

def confirm_keyboard():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(types.KeyboardButton("✅ تایید"), types.KeyboardButton("❌ لغو"))
    kb.add(types.KeyboardButton("🔙 بازگشت به منو"))
    return kb

# ---------------- رویدادها ----------------
@bot.message_handler(commands=['start'])
def cmd_start(m):
    pending.pop(m.chat.id, None)
    awaiting_admin_review.discard(m.chat.id)
    bot.send_message(m.chat.id,
                     "سلام 👋 به ربات نوسان‌پی خوش آمدید.\nبرای شروع «💸 انتقال ارز» را انتخاب کنید.",
                     reply_markup=main_menu_markup())

@bot.message_handler(func=lambda msg: msg.text == "💸 انتقال ارز")
def cmd_transfer(msg):
    bot.send_message(msg.chat.id, "لطفاً جهت انتقال را انتخاب کنید:", reply_markup=direction_markup())

@bot.message_handler(func=lambda msg: msg.text in ["🌍 از داخل به خارج", "🏦 از خارج به داخل"])
def choose_currency_list(msg):
    chat_id = msg.chat.id
    direction = "از داخل به خارج" if msg.text == "🌍 از داخل به خارج" else "از خارج به داخل"
    pending[chat_id] = {"direction": direction, "currency": None, "awaiting": None}
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    for code, name in currencies.items():
        kb.add(types.KeyboardButton(f"{name} ({code})"))
    kb.add(types.KeyboardButton("🔙 بازگشت به منو"))
    bot.send_message(chat_id, "ارز مورد نظر را انتخاب کنید:", reply_markup=kb)

@bot.message_handler(func=lambda msg: bool(re.match(r".*\([A-Z]{3}\)\s*$", msg.text or "")))
def ask_amount(msg):
    chat_id = msg.chat.id
    t = msg.text.strip()
    m = re.search(r"\(([A-Z]{3})\)\s*$", t)
    if not m:
        return bot.reply_to(msg, "لطفاً از کلیدهای ارز استفاده کنید.")
    code = m.group(1)
    state = pending.get(chat_id)
    if not state:
        return bot.reply_to(msg, "ابتدا جهت انتقال را انتخاب کنید.")
    pending[chat_id]["currency"] = code
    pending[chat_id]["awaiting"] = "amount"
    bot.send_message(chat_id, f"شما {currencies.get(code)} را انتخاب کردید.\nلطفاً مقدار (عدد) را وارد کنید:", reply_markup=back_to_main_markup())

@bot.message_handler(func=lambda msg: True)
def router(msg):
    chat_id = msg.chat.id
    text = (msg.text or "").strip()

    if text in ["🔙 بازگشت به منو", "/start"]:
        pending.pop(chat_id, None)
        awaiting_admin_review.discard(chat_id)
        return cmd_start(msg)

    # ---------- ادمین ----------
    if chat_id == ADMIN_ID:
        # ✅ تایید کاربر
        m1 = re.match(r"^\s*تایید\s+(\d+)\s*$", text, re.IGNORECASE)
        if m1:
            uid = int(m1.group(1))
            if uid in awaiting_admin_review:
                awaiting_admin_review.discard(uid)
                p = pending.get(uid, {})
                total = p.get("total")
                if total is None:
                    bot.send_message(ADMIN_ID, f"⚠️ برای کاربر {uid} مجموع موجود نیست. ابتدا نرخ را وارد کن یا بررسی کن.")
                    return

                # 🔹 لینک پرداخت واقعی زیبال بر اساس مرچنت و مبلغ
                payment_url = f"https://gateway.zibal.ir/start/{MERCHANT_CODE}?amount={int(total)}"

                bot.send_message(uid,
                                 f"✅ اطلاعات شما تأیید شد.\n"
                                 f"برای پرداخت از لینک زیر استفاده کنید:\n\n{payment_url}\n\n"
                                 f"💰 مبلغ قابل پرداخت: {total:,.0f} تومان")
                return bot.send_message(ADMIN_ID, f"✅ لینک پرداخت برای {uid} ارسال شد.")
            return bot.send_message(ADMIN_ID, "⚠️ این کاربر در انتظار بررسی نیست.")

        # 🟡 اصلاح کاربر
        m2 = re.match(r"^\s*اصلاح\s+(\d+)\s+(.+)$", text, re.IGNORECASE)
        if m2:
            uid = int(m2.group(1))
            reason = m2.group(2).strip()
            if uid in awaiting_admin_review:
                pending.setdefault(uid, {})["awaiting"] = "edit"
                bot.send_message(uid, f"⚠️ پشتیبانی درخواست اصلاح کرد:\n\n{reason}\n\nلطفاً اطلاعات اصلاح‌شده را ارسال کنید (متن ساده).")
                awaiting_admin_review.discard(uid)
                return bot.send_message(ADMIN_ID, f"✅ پیام اصلاح برای {uid} ارسال شد.")
            return bot.send_message(ADMIN_ID, "⚠️ این کاربر در انتظار بررسی نیست.")

        # 🔢 تعیین نرخ
        if re.match(r"^\d+(\.\d+)?$", text):
            rate = float(text)
            target = None
            for uid, data in pending.items():
                if data.get("awaiting") == "waiting_rate":
                    target = uid
                    break
            if not target:
                return bot.send_message(ADMIN_ID, "⚠️ در حال حاضر هیچ درخواستی در انتظار نرخ نیست.")
            data = pending[target]
            total = data["amount"] * rate
            data["rate"] = rate
            data["total"] = total
            data["awaiting"] = "confirm"
            bot.send_message(target,
                             f"💰 مبلغ نهایی مشخص شد:\n\n"
                             f"• مقدار: {data['amount']:,} {data['currency']}\n"
                             f"• مبلغ کل پرداختی: {total:,.0f} تومان\n\n"
                             "لطفاً با یکی از دکمه‌ها پاسخ دهید:",
                             reply_markup=confirm_keyboard())
            return bot.send_message(ADMIN_ID, f"✅ نرخ ثبت شد و مجموع برای کاربر {target} ارسال شد.")

        return bot.send_message(ADMIN_ID,
                                "راهنما برای ادمین:\n"
                                "- برای تعیین نرخ: فقط عدد (مثلاً 1234500)\n"
                                "- برای تایید اطلاعات: تایید <user_id>\n"
                                "- برای اصلاح: اصلاح <user_id> <متن دلیل>")

    # ---------- سایر کاربران ----------
    st = pending.get(chat_id)

    if st and st.get("awaiting") == "edit":
        if re.search(r"https?://|t\.me|@", text, re.IGNORECASE):
            try: bot.delete_message(chat_id, msg.message_id)
            except: pass
            return bot.send_message(chat_id, "⚠️ لطفاً فقط متن ساده ارسال کنید (بدون لینک یا تگ).")
        bot.send_message(ADMIN_ID,
                         f"📦 اطلاعات اصلاح‌شده از کاربر {chat_id}:\n\n{text}\n\n"
                         f"برای تایید: تایید {chat_id}\nیا برای اصلاح دوباره: اصلاح {chat_id} <متن دلیل>")
        awaiting_admin_review.add(chat_id)
        pending[chat_id]["awaiting"] = None
        return bot.send_message(chat_id, "✅ اطلاعات اصلاح‌شده ارسال شد. منتظر بررسی پشتیبانی باشید.", reply_markup=main_menu_markup())

    if st and st.get("awaiting") == "awaiting_info":
        if re.search(r"https?://|t\.me|@", text, re.IGNORECASE):
            try: bot.delete_message(chat_id, msg.message_id)
            except: pass
            return bot.send_message(chat_id, "⚠️ لطفاً فقط متن ساده ارسال کنید (بدون لینک یا تگ).")
        bot.send_message(ADMIN_ID,
                         f"📦 اطلاعات حساب از کاربر {chat_id}:\n\n{text}\n\n"
                         f"اگر اوکی است بنویسید: تایید {chat_id}\nیا اگر نیاز به اصلاح است: اصلاح {chat_id} <دلیل>")
        awaiting_admin_review.add(chat_id)
        pending[chat_id]["awaiting"] = None
        return bot.send_message(chat_id, "✅ اطلاعات شما ارسال شد؛ منتظر بررسی پشتیبانی باشید.", reply_markup=main_menu_markup())

    if st and st.get("awaiting") == "amount":
        try:
            amount = float(text.replace(",", "").replace(" ", ""))
            if amount <= 0:
                raise ValueError()
        except:
            return bot.reply_to(msg, "⚠️ مقدار نامعتبر. لطفاً فقط عدد مثبت وارد کنید (مثلاً 2500).")
        st["amount"] = amount
        st["awaiting"] = "waiting_rate"
        bot.send_message(ADMIN_ID,
                         f"📩 درخواست جدید از @{msg.from_user.username or msg.from_user.first_name}\n"
                         f"📍 جهت: {st['direction']}\n"
                         f"💱 ارز: {currencies[st['currency']]} ({st['currency']})\n"
                         f"📊 مقدار: {amount:,}\n"
                         f"🆔 Chat ID: {chat_id}\n\n"
                         "📌 لطفاً نرخ هر واحد به تومان را وارد کنید (فقط عدد).")
        return bot.send_message(chat_id, "✅ درخواست ثبت شد؛ منتظر پاسخ ادمین باشید.", reply_markup=main_menu_markup())

    if st and st.get("awaiting") == "confirm":
        if text == "✅ تایید":
            st["awaiting"] = "awaiting_info"
            currency = st.get("currency")
            if st.get("direction") == "از داخل به خارج":
                info = currency_info_template.get(currency, "نام و شماره حساب دریافت‌کننده / نام بانک / کشور")
                bot.send_message(chat_id,
                                 "✅ تراکنش تأیید شد.\n\n"
                                 f"✉️ لطفاً اطلاعات حساب مقصد را به صورت متن ارسال کنید:\n({info})",
                                 reply_markup=back_to_main_markup())
            else:
                bot.send_message(chat_id,
                                 "✅ تراکنش تأیید شد.\n\n"
                                 "✉️ لطفاً اطلاعات حساب (برای واریز داخلی) را به صورت متن ارسال کنید:\n"
                                 "(شماره حساب / شماره کارت / شماره شبا / نام و نام خانوادگی دریافت‌کننده / نام و نام خانوادگی واریزکننده)",
                                 reply_markup=back_to_main_markup())
            return

        if text == "❌ لغو":
            pending.pop(chat_id, None)
            return bot.send_message(chat_id, "❌ روند انتقال لغو شد.", reply_markup=main_menu_markup())

        return bot.send_message(chat_id, "لطفاً یکی از دکمه‌ها را انتخاب کنید: «✅ تایید» یا «❌ لغو».")

    return bot.send_message(chat_id, "برای شروع «💸 انتقال ارز» را انتخاب کنید.", reply_markup=main_menu_markup())

# ---------------- اجرا ----------------
if __name__ == "__main__":
    print("✅ ربات نوسان‌پی در حال اجراست...")
    bot.infinity_polling(timeout=60, long_polling_timeout=30)
