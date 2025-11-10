import os
import re
import telebot
from telebot import types

# ---------------- تنظیمات ----------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "1611406302"))

bot = telebot.TeleBot(BOT_TOKEN)

# ---------------- داده‌ها ----------------
currencies = {
    "USD": "دلار آمریکا 🇺🇸", "EUR": "یورو 🇪🇺", "GBP": "پوند انگلیس 🇬🇧",
    "CHF": "فرانک سوئیس 🇨🇭", "CAD": "دلار کانادا 🇨🇦", "AUD": "دلار استرالیا 🇦🇺",
    "AED": "درهم امارات 🇦🇪", "TRY": "لیر ترکیه 🇹🇷", "CNY": "یوان چین 🇨🇳",
    "INR": "روپیه هند 🇮🇳", "JPY": "ین ژاپن 🇯🇵", "SAR": "ریال عربستان 🇸🇦",
    "KWD": "دینار کویت 🇰🇼", "OMR": "ریال عمان 🇴🇲", "QAR": "ریال قطر 🇶🇦"
}

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

# ---------------- پردازش مقدار و پاسخ ادمین ----------------
@bot.message_handler(func=lambda m: True)
def receive_amount(message):
    chat_id = message.chat.id
    text = message.text.strip()
    state = pending.get(chat_id)

    # بازگشت به منو
    if text in ["🔙 منوی اصلی", "/start"]:
        pending.pop(chat_id, None)
        return start(message)

    # اگر در مرحله ارسال اطلاعات است
    if chat_id in awaiting_info:
        if re.search(r"https?://|t\.me|@", text, re.IGNORECASE):
            bot.send_message(chat_id, "⚠️ فقط متن ساده مجاز است (بدون لینک یا تگ).")
            return
        bot.send_message(ADMIN_ID, f"📦 اطلاعات واریز از کاربر {chat_id}:\n{text}")
        bot.send_message(chat_id, "✅ اطلاعات شما ارسال شد و در حال بررسی است.")
        awaiting_info.remove(chat_id)
        return

    # دریافت مقدار
    if state and state.get("awaiting") == "amount":
        try:
            amount = float(text.replace(",", "").replace(" ", ""))
            if amount <= 0:
                raise ValueError()
        except Exception:
            bot.reply_to(message, "⚠️ عدد معتبر وارد کنید.")
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
        bot.send_message(chat_id, "✅ درخواست شما ارسال شد. منتظر پاسخ ادمین باشید.")
        return

    # پاسخ ادمین (نرخ)
    if chat_id == ADMIN_ID and re.match(r"^\d+(\.\d+)?$", text):
        rate = float(text)
        for uid, data in pending.items():
            if data.get("amount") and not data.get("total"):
                total = data["amount"] * rate
                data["total"] = total

                markup = types.InlineKeyboardMarkup()
                markup.add(
                    types.InlineKeyboardButton("✅ تأیید", callback_data=f"confirm_{uid}"),
                    types.InlineKeyboardButton("❌ لغو", callback_data=f"cancel_{uid}")
                )

                bot.send_message(
                    uid,
                    f"💰 مبلغ نهایی مشخص شد:\n"
                    f"• مقدار ارز: {data['amount']:,} {data['currency']}\n"
                    f"• مبلغ کل پرداختی: {total:,.0f} تومان\n\n"
                    "آیا تأیید می‌کنید؟",
                    reply_markup=markup
                )
                bot.send_message(chat_id, f"✅ نرخ برای کاربر {uid} ارسال شد.")
                return
        bot.send_message(chat_id, "⚠️ هیچ درخواستی برای قیمت‌گذاری نیست.")
        return

# ---------------- هندل دکمه تأیید / لغو ----------------
@bot.callback_query_handler(func=lambda call: call.data.startswith("confirm_") or call.data.startswith("cancel_"))
def handle_confirm_cancel(call):
    data = call.data
    chat_id = call.message.chat.id
    target_id = int(data.split("_")[1])

    if data.startswith("confirm_"):
        bot.answer_callback_query(call.id, "تأیید شد ✅")
        bot.send_message(
            target_id,
            "✅ تراکنش تأیید شد.\n✉️ لطفاً اطلاعات مورد نیاز جهت واریز را فقط به صورت متن ارسال کنید (بدون لینک یا فایل)."
        )
        awaiting_info.add(target_id)
        pending.pop(target_id, None)
    elif data.startswith("cancel_"):
        bot.answer_callback_query(call.id, "لغو شد ❌")
        bot.send_message(target_id, "❌ روند انتقال ارز شما لغو شد.")
        start(call.message)

# ---------------- اجرا ----------------
if __name__ == "__main__":
    print("✅ ربات نوسان‌پی در حال اجراست...")
    bot.infinity_polling(skip_pending=True)
