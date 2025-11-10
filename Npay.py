import os
import re
import telebot
from telebot import types

# ---------------- تنظیمات ----------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "1611406302"))  # آی‌دی ادمین

bot = telebot.TeleBot(BOT_TOKEN)

# ---------------- فهرست ارزها ----------------
currencies = {
    "USD": "دلار آمریکا 🇺🇸", "EUR": "یورو 🇪🇺", "GBP": "پوند انگلیس 🇬🇧",
    "CHF": "فرانک سوئیس 🇨🇭", "CAD": "دلار کانادا 🇨🇦", "AUD": "دلار استرالیا 🇦🇺",
    "AED": "درهم امارات 🇦🇪", "TRY": "لیر ترکیه 🇹🇷", "CNY": "یوان چین 🇨🇳",
    "INR": "روپیه هند 🇮🇳", "JPY": "ین ژاپن 🇯🇵", "SAR": "ریال عربستان 🇸🇦",
    "KWD": "دینار کویت 🇰🇼", "OMR": "ریال عمان 🇴🇲", "QAR": "ریال قطر 🇶🇦"
}

# ---------------- وضعیت کاربران ----------------
pending = {}
awaiting_info = set()

# ---------------- شروع ----------------
@bot.message_handler(commands=['start'])
def start(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("💸 انتقال ارز"))
    bot.send_message(
        message.chat.id,
        "سلام 👋 به ربات نوسان‌پی خوش‌آمدید.\nبرای شروع «💸 انتقال ارز» را انتخاب کنید.",
        reply_markup=markup
    )

# ---------------- انتخاب نوع انتقال ----------------
@bot.message_handler(func=lambda m: m.text == "💸 انتقال ارز")
def transfer_menu(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(
        types.KeyboardButton("🌍 از داخل به خارج"),
        types.KeyboardButton("🏦 از خارج به داخل")
    )
    bot.send_message(message.chat.id, "لطفاً نوع انتقال را انتخاب کنید:", reply_markup=markup)

# ---------------- انتخاب ارز ----------------
@bot.message_handler(func=lambda m: m.text in ["🌍 از داخل به خارج", "🏦 از خارج به داخل"])
def show_currencies(message):
    chat_id = message.chat.id
    direction = "متقاضی قصد واریز از داخل به خارج دارد" if "داخل به خارج" in message.text else "متقاضی قصد واریز از خارج به داخل دارد"
    pending[chat_id] = {"direction": direction, "currency": None, "awaiting": None}

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    for code, name in currencies.items():
        markup.add(types.KeyboardButton(f"{name} ({code})"))
    markup.add(types.KeyboardButton("🔙 منوی اصلی"))
    bot.send_message(chat_id, "نوع ارز مورد نظر را انتخاب کنید:", reply_markup=markup)

# ---------------- دریافت مقدار ----------------
@bot.message_handler(func=lambda m: bool(re.match(r".*\([A-Z]{3}\)\s*$", m.text or "")))
def ask_amount(message):
    chat_id = message.chat.id
    match = re.search(r"\(([A-Z]{3})\)\s*$", message.text.strip())
    if not match:
        bot.reply_to(message, "فرمت ارز صحیح نیست. لطفاً مجدداً انتخاب کنید.")
        return

    code = match.group(1)
    if code not in currencies:
        bot.reply_to(message, "این ارز در فهرست نیست.")
        return

    pending[chat_id] = {
        "direction": pending.get(chat_id, {}).get("direction", None),
        "currency": code,
        "awaiting": "amount"
    }

    bot.send_message(chat_id,
                     f"شما ارز «{currencies[code]} ({code})» را انتخاب کردید.\n"
                     "لطفاً مقدار را وارد کنید (مثلاً 2500 یا 12.5):")

# ---------------- پردازش مقدار و ارسال به ادمین ----------------
@bot.message_handler(func=lambda m: True)
def receive_amount(message):
    chat_id = message.chat.id
    text = (message.text or "").strip()

    # بازگشت به منوی اصلی
    if text in ["🔙 منوی اصلی", "/start"]:
        pending.pop(chat_id, None)
        return start(message)

    # اگر در مرحله ارسال اطلاعات واریز است
    if chat_id in awaiting_info:
        if re.search(r"https?://|t\.me|@", text, re.IGNORECASE):
            bot.send_message(chat_id, "⚠️ لطفاً فقط متن ساده ارسال کنید. ارسال لینک یا تگ مجاز نیست.")
            return

        bot.send_message(
            ADMIN_ID,
            f"📦 اطلاعات واریز از کاربر {chat_id}:\n{text}"
        )
        bot.send_message(chat_id, "✅ اطلاعات شما با موفقیت ارسال شد و در حال بررسی توسط پشتیبانی هستیم.")
        awaiting_info.remove(chat_id)
        return

    state = pending.get(chat_id)

    # مرحله دریافت مقدار
    if state and state.get("awaiting") == "amount":
        try:
            amount = float(text.replace(",", "").replace(" ", ""))
            if amount <= 0:
                raise ValueError()
        except Exception:
            bot.reply_to(message, "⚠️ لطفاً عدد معتبر وارد کنید.")
            return

        currency_code = state["currency"]
        direction = state["direction"]

        pending[chat_id]["amount"] = amount
        pending[chat_id]["awaiting"] = None

        bot.send_message(
            ADMIN_ID,
            f"📩 درخواست جدید از کاربر @{message.from_user.username or message.from_user.first_name}\n"
            f"📍 {direction}\n"
            f"💱 ارز: {currencies[currency_code]} ({currency_code})\n"
            f"📊 مقدار: {amount:,}\n"
            f"🆔 Chat ID: {chat_id}\n\n"
            "📌 لطفاً نرخ هر واحد را به تومان وارد کنید (فقط عدد):"
        )
        bot.send_message(chat_id, "✅ درخواست شما برای بررسی قیمت ارسال شد. لطفاً منتظر پاسخ ادمین باشید.")
        return

    # مرحله پاسخ ادمین (تعیین نرخ)
    if chat_id == ADMIN_ID and re.match(r"^\d+(\.\d+)?$", text):
        rate = float(text)
        for user_id, data in pending.items():
            if data.get("amount") and not data.get("total"):
                total = data["amount"] * rate
                data["total"] = total
                data["awaiting"] = "confirm"

                markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
                markup.add(types.KeyboardButton("✅ تأیید"), types.KeyboardButton("❌ لغو"))

                bot.send_message(
                    user_id,
                    f"💰 مبلغ نهایی توسط ادمین مشخص شد:\n\n"
                    f"• مقدار ارز: {data['amount']:,} {data['currency']}\n"
                    f"• مبلغ کل پرداختی: {total:,.0f} تومان\n\n"
                    "آیا مایل به ادامه روند هستید؟",
                    reply_markup=markup
                )

                bot.send_message(chat_id, f"✅ نرخ برای کاربر {user_id} ارسال شد.")
                return

        bot.send_message(chat_id, "⚠️ در حال حاضر هیچ درخواست فعالی برای قیمت‌گذاری وجود ندارد.")
        return

    # مرحله تأیید یا لغو توسط کاربر
    if state and state.get("awaiting") == "confirm":
        if text == "✅ تأیید":
            awaiting_info.add(chat_id)
            markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
            markup.add(types.KeyboardButton("🔙 منوی اصلی"))
            bot.send_message(
                chat_id,
                "✅ تراکنش تأیید شد.\n✉️ لطفاً اطلاعات مورد نیاز جهت واریز را فقط به صورت متن ارسال کنید (بدون لینک یا فایل).",
                reply_markup=markup
            )
            pending.pop(chat_id, None)
            return

        elif text == "❌ لغو":
            pending.pop(chat_id, None)
            bot.send_message(chat_id, "❌ روند انتقال ارز شما لغو شد.")
            return start(message)

        else:
            bot.send_message(chat_id, "لطفاً یکی از گزینه‌های «✅ تأیید» یا «❌ لغو» را انتخاب کنید.")
            return

    bot.reply_to(message, "برای شروع، گزینه «💸 انتقال ارز» را از منوی اصلی انتخاب کنید.")

# ---------------- اجرای ربات ----------------
if __name__ == "__main__":
    print("✅ ربات نوسان‌پی در حال اجراست...")
    bot.infinity_polling(skip_pending=True)
