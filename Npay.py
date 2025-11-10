import os
import re
import telebot
from telebot import types

# ---------------- تنظیمات ----------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "1611406302"))
PAYMENT_LINK = "https://example.com/payment"

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

# ---------------- الگوهای اطلاعات حساب برای هر ارز ----------------
currency_info_template = {
    "USD": "نام و نام خانوادگی دریافت‌کننده / نام بانک / شماره حساب / SWIFT Code",
    "EUR": "نام و نام خانوادگی دریافت‌کننده / کشور / نام بانک / شماره حساب یا IBAN",
    "GBP": "نام و نام خانوادگی دریافت‌کننده / شماره حساب / Sort Code / نام بانک",
    "CHF": "نام و نام خانوادگی دریافت‌کننده / نام بانک / شماره حساب یا IBAN / SWIFT",
    "CAD": "نام و نام خانوادگی دریافت‌کننده / نام بانک / شماره حساب / Transit Number / SWIFT",
    "AUD": "نام و نام خانوادگی دریافت‌کننده / نام بانک / BSB Code / شماره حساب",
    "AED": "نام و نام خانوادگی دریافت‌کننده / نام بانک / شماره حساب یا IBAN (AE...) / SWIFT",
    "TRY": "نام و نام خانوادگی دریافت‌کننده / نام بانک / شماره IBAN (TR...)",
    "CNY": "نام و نام خانوادگی دریافت‌کننده / نام بانک / شماره حساب / SWIFT Code / نام شهر",
    "INR": "نام و نام خانوادگی دریافت‌کننده / نام بانک / IFSC Code / شماره حساب",
    "JPY": "نام و نام خانوادگی دریافت‌کننده / نام بانک / شماره حساب / SWIFT / Branch Name",
    "SAR": "نام و نام خانوادگی دریافت‌کننده / نام بانک / شماره IBAN (SA...) / SWIFT",
    "KWD": "نام و نام خانوادگی دریافت‌کننده / نام بانک / شماره حساب / IBAN (KW...)",
    "OMR": "نام و نام خانوادگی دریافت‌کننده / نام بانک / شماره حساب / SWIFT / IBAN (OM...)",
    "QAR": "نام و نام خانوادگی دریافت‌کننده / نام بانک / شماره IBAN (QA...) / SWIFT"
}

# ---------------- وضعیت‌ها ----------------
pending = {}
awaiting_info = set()

# ---------------- منوها ----------------
def main_menu_markup():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("💸 انتقال ارز"))
    return markup

def back_to_main_markup():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("🔙 بازگشت به منوی اصلی"))
    return markup

# ---------------- /start ----------------
@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(
        message.chat.id,
        "سلام 👋 به ربات نوسان‌پی خوش‌آمدید.\nبرای شروع گزینه زیر را انتخاب کنید:",
        reply_markup=main_menu_markup()
    )

# ---------------- مرحله ۱: انتخاب نوع انتقال ----------------
@bot.message_handler(func=lambda m: m.text == "💸 انتقال ارز")
def choose_direction(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(
        types.KeyboardButton("🌍 از داخل به خارج"),
        types.KeyboardButton("🏦 از خارج به داخل"),
        types.KeyboardButton("🔙 بازگشت به منوی اصلی")
    )
    bot.send_message(message.chat.id, "نوع انتقال را انتخاب کنید:", reply_markup=markup)

# ---------------- مرحله ۲: انتخاب ارز ----------------
@bot.message_handler(func=lambda m: m.text in ["🌍 از داخل به خارج", "🏦 از خارج به داخل"])
def show_currencies(message):
    chat_id = message.chat.id
    direction = message.text
    pending[chat_id] = {"direction": direction, "currency": None, "awaiting": None}

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    for code, name in currencies.items():
        markup.add(types.KeyboardButton(f"{name} ({code})"))
    markup.add(types.KeyboardButton("🔙 بازگشت به منوی اصلی"))

    bot.send_message(chat_id, "ارز مورد نظر را انتخاب کنید:", reply_markup=markup)

# ---------------- مرحله ۳: وارد کردن مقدار ----------------
@bot.message_handler(func=lambda m: bool(re.match(r".*\([A-Z]{3}\)\s*$", m.text or "")))
def ask_amount(message):
    chat_id = message.chat.id
    match = re.search(r"\(([A-Z]{3})\)\s*$", message.text.strip())
    if not match:
        return bot.reply_to(message, "فرمت ارز صحیح نیست.")
    code = match.group(1)

    if chat_id not in pending or "direction" not in pending[chat_id]:
        return bot.reply_to(message, "لطفاً ابتدا نوع انتقال را انتخاب کنید.")

    pending[chat_id]["currency"] = code
    pending[chat_id]["awaiting"] = "amount"

    bot.send_message(
        chat_id,
        f"شما {currencies[code]} را انتخاب کردید.\n"
        "مقدار مورد نظر را وارد کنید (مثلاً 1500):",
        reply_markup=back_to_main_markup()
    )

# ---------------- منطق اصلی ----------------
@bot.message_handler(func=lambda m: True)
def main_handler(message):
    chat_id = message.chat.id
    text = (message.text or "").strip()

    if text in ["🔙 بازگشت به منوی اصلی", "/start"]:
        pending.pop(chat_id, None)
        awaiting_info.discard(chat_id)
        return start(message)

    # اگر در مرحله ارسال اطلاعات حساب است
    if chat_id in awaiting_info:
        if re.search(r"https?://|t\.me|@", text, re.IGNORECASE):
            try:
                bot.delete_message(chat_id, message.message_id)
            except:
                pass
            return bot.send_message(chat_id, "⚠️ لطفاً فقط متن ساده ارسال کنید (بدون لینک یا تگ).")
        bot.send_message(ADMIN_ID, f"📦 اطلاعات حساب از کاربر {chat_id}:\n\n{text}")
        bot.send_message(chat_id, "✅ اطلاعات شما ارسال شد، منتظر بررسی ادمین باشید.")
        awaiting_info.remove(chat_id)
        return

    # مرحله وارد کردن مبلغ
    state = pending.get(chat_id)
    if state and state.get("awaiting") == "amount":
        try:
            amount = float(text.replace(",", "").replace(" ", ""))
            if amount <= 0:
                raise ValueError()
        except:
            return bot.reply_to(message, "⚠️ لطفاً عدد مثبت وارد کنید.")
        state["amount"] = amount
        state["awaiting"] = "waiting_rate"

        bot.send_message(
            ADMIN_ID,
            f"📩 درخواست جدید:\n"
            f"📍 جهت: {state['direction']}\n"
            f"💱 ارز: {currencies[state['currency']]} ({state['currency']})\n"
            f"📊 مقدار: {amount:,}\n"
            f"🆔 Chat ID: {chat_id}\n\n"
            "📌 لطفاً نرخ هر واحد را وارد کنید (فقط عدد)."
        )
        bot.send_message(chat_id, "✅ درخواست شما برای بررسی ارسال شد.", reply_markup=main_menu_markup())
        return

    # ادمین نرخ می‌دهد
    if chat_id == ADMIN_ID and re.match(r"^\d+(\.\d+)?$", text):
        rate = float(text)
        target = None
        for uid, data in pending.items():
            if data.get("awaiting") == "waiting_rate":
                target = uid
                break
        if not target:
            return bot.send_message(ADMIN_ID, "⚠️ درخواستی در انتظار نرخ وجود ندارد.")
        data = pending[target]
        total = data["amount"] * rate
        data["total"] = total
        data["awaiting"] = "confirm"

        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add(types.KeyboardButton("✅ تایید"), types.KeyboardButton("❌ لغو"))
        markup.add(types.KeyboardButton("🔙 بازگشت به منوی اصلی"))

        bot.send_message(
            target,
            f"💰 مبلغ نهایی مشخص شد:\n\n"
            f"• مقدار: {data['amount']:,} {data['currency']}\n"
            f"• مبلغ کل پرداختی: {total:,.0f} تومان\n\n"
            "آیا تأیید می‌کنید؟",
            reply_markup=markup
        )
        bot.send_message(ADMIN_ID, f"✅ نرخ برای کاربر {target} ارسال شد.")
        return

    # کاربر تأیید یا لغو می‌کند
    if state and state.get("awaiting") == "confirm":
        if text == "✅ تایید":
            pending.pop(chat_id, None)
            awaiting_info.add(chat_id)

            # تشخیص نوع درخواست:
            direction = state.get("direction", "")
            currency = state.get("currency")

            if "داخل به خارج" in direction:
                info = currency_info_template.get(currency, "نام و شماره حساب دریافت‌کننده / بانک / کشور")
                bot.send_message(
                    chat_id,
                    f"✅ تراکنش تأیید شد.\n\n"
                    f"✉️ لطفاً اطلاعات حساب مقصد ({currencies[currency]}) را وارد کنید:\n({info})",
                    reply_markup=back_to_main_markup()
                )
            else:
                bot.send_message(
                    chat_id,
                    "✅ تراکنش تأیید شد.\n\n"
                    "✉️ لطفاً اطلاعات حساب بانکی خود را وارد کنید:\n"
                    "(شماره حساب / شماره کارت / شماره شبا / نام و نام خانوادگی)",
                    reply_markup=back_to_main_markup()
                )
            return

        elif text == "❌ لغو":
            pending.pop(chat_id, None)
            bot.send_message(chat_id, "❌ تراکنش لغو شد.", reply_markup=main_menu_markup())
            return

    bot.send_message(chat_id, "برای شروع، گزینه «💸 انتقال ارز» را انتخاب کنید.", reply_markup=main_menu_markup())

# ---------------- اجرای ربات ----------------
if __name__ == "__main__":
    print("✅ Bot is running...")
    bot.infinity_polling(timeout=60, long_polling_timeout=30)
