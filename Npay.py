import os
import re
import telebot
from telebot import types

# ---------------- تنظیمات ----------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "1611406302"))

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

# ---------------- منوی اصلی ----------------
def main_menu(chat_id, text="برای شروع یکی از گزینه‌ها را انتخاب کنید:"):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("💸 انتقال ارز"))
    bot.send_message(chat_id, text, reply_markup=markup)

# ---------------- /start ----------------
@bot.message_handler(commands=['start'])
def start(message):
    main_menu(message.chat.id, "سلام 👋 به ربات نوسان‌پی خوش‌آمدید.\nبرای شروع «💸 انتقال ارز» را انتخاب کنید.")

# ---------------- مرحله ۱: انتخاب نوع انتقال ----------------
@bot.message_handler(func=lambda m: m.text == "💸 انتقال ارز")
def transfer_menu(message):
    chat_id = message.chat.id
    pending[chat_id] = {"step": "direction"}

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("🌍 از داخل به خارج"), types.KeyboardButton("🏦 از خارج به داخل"))
    markup.add(types.KeyboardButton("🔙 منوی اصلی"))

    bot.send_message(chat_id, "لطفاً نوع انتقال را انتخاب کنید:", reply_markup=markup)

# ---------------- مرحله ۲: انتخاب ارز ----------------
@bot.message_handler(func=lambda m: m.text in ["🌍 از داخل به خارج", "🏦 از خارج به داخل"])
def select_currency(message):
    chat_id = message.chat.id
    direction = "متقاضی قصد واریز از داخل به خارج دارد" if "داخل به خارج" in message.text else "متقاضی قصد واریز از خارج به داخل دارد"

    pending[chat_id] = {"step": "currency", "direction": direction}

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    for code, name in currencies.items():
        markup.add(types.KeyboardButton(f"{name} ({code})"))
    markup.add(types.KeyboardButton("🔙 بازگشت"), types.KeyboardButton("🔙 منوی اصلی"))

    bot.send_message(chat_id, "نوع ارز مورد نظر را انتخاب کنید:", reply_markup=markup)

# ---------------- مرحله ۳: وارد کردن مقدار ----------------
@bot.message_handler(func=lambda m: bool(re.match(r".*\([A-Z]{3}\)$", m.text or "")))
def ask_amount(message):
    chat_id = message.chat.id
    match = re.search(r"\(([A-Z]{3})\)$", message.text)
    if not match:
        return

    code = match.group(1)
    state = pending.get(chat_id, {})
    state["currency"] = code
    state["step"] = "amount"
    pending[chat_id] = state

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("🔙 بازگشت"), types.KeyboardButton("🔙 منوی اصلی"))

    bot.send_message(chat_id, f"شما ارز «{currencies[code]} ({code})» را انتخاب کردید.\n\nلطفاً مقدار را وارد کنید:", reply_markup=markup)

# ---------------- مرحله ۴: پردازش مقدار ----------------
@bot.message_handler(func=lambda m: True)
def all_messages(message):
    chat_id = message.chat.id
    text = (message.text or "").strip()
    state = pending.get(chat_id, {})

    # بازگشت به منوی اصلی
    if text == "🔙 منوی اصلی" or text == "/start":
        pending.pop(chat_id, None)
        return main_menu(chat_id, "به منوی اصلی بازگشتید.")

    # بازگشت به مرحله قبل
    if text == "🔙 بازگشت":
        step = state.get("step")
        if step == "currency":
            return transfer_menu(message)
        elif step == "amount":
            return select_currency(message)
        elif step == "confirm":
            return ask_amount(type("obj", (object,), {"chat": message.chat, "text": f"{currencies[state['currency']]} ({state['currency']})"}))
        else:
            return main_menu(chat_id, "به منوی اصلی بازگشتید.")

    # اگر کاربر در مرحله ارسال اطلاعات هست
    if chat_id in awaiting_info:
        if re.search(r"https?://|t\.me|@", text, re.IGNORECASE):
            bot.send_message(chat_id, "⚠️ لطفاً فقط متن ساده ارسال کنید.")
            return

        bot.send_message(ADMIN_ID, f"📦 اطلاعات واریز از کاربر {chat_id}:\n{text}")
        bot.send_message(chat_id, "✅ اطلاعات شما با موفقیت ارسال شد و در حال بررسی است.")
        awaiting_info.remove(chat_id)
        return

    # مرحله وارد کردن مقدار
    if state.get("step") == "amount":
        try:
            amount = float(text.replace(",", "").replace(" ", ""))
            if amount <= 0:
                raise ValueError()
        except:
            bot.send_message(chat_id, "⚠️ لطفاً عدد معتبر وارد کنید.")
            return

        state["amount"] = amount
        state["step"] = "waiting_rate"
        pending[chat_id] = state

        bot.send_message(
            ADMIN_ID,
            f"📩 درخواست جدید از کاربر @{message.from_user.username or message.from_user.first_name}\n"
            f"📍 {state['direction']}\n"
            f"💱 ارز: {currencies[state['currency']]} ({state['currency']})\n"
            f"📊 مقدار: {amount:,}\n"
            f"🆔 Chat ID: {chat_id}\n\n"
            "📌 لطفاً نرخ هر واحد را به تومان وارد کنید (فقط عدد):"
        )
        bot.send_message(chat_id, "✅ درخواست شما برای بررسی قیمت ارسال شد. لطفاً منتظر پاسخ ادمین باشید.")
        return

    # مرحله ادمین برای نرخ
    if chat_id == ADMIN_ID and re.match(r"^\d+(\.\d+)?$", text):
        rate = float(text)
        for user_id, data in pending.items():
            if data.get("step") == "waiting_rate":
                total = data["amount"] * rate
                data["total"] = total
                data["step"] = "confirm"

                markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
                markup.add(types.KeyboardButton("✅ تأیید"), types.KeyboardButton("❌ لغو"))
                markup.add(types.KeyboardButton("🔙 بازگشت"), types.KeyboardButton("🔙 منوی اصلی"))

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

        bot.send_message(chat_id, "⚠️ هیچ درخواستی برای قیمت‌گذاری نیست.")
        return

    # مرحله تأیید یا لغو توسط کاربر
    if state.get("step") == "confirm":
        if text == "✅ تأیید":
            awaiting_info.add(chat_id)

            direction = state.get("direction", "")
            markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
            markup.add(types.KeyboardButton("🔙 منوی اصلی"))

            if "داخل به خارج" in direction:
                bot.send_message(
                    chat_id,
                    "✅ تراکنش تأیید شد.\n\n"
                    "✉️ لطفاً اطلاعات حساب دریافت‌کننده را به صورت متن ارسال کنید.\n"
                    "(نام و نام خانوادگی دریافت‌کننده، کشور، شهر، نام بانک، شماره حساب و سایر جزئیات لازم)",
                    reply_markup=markup
                )
            else:
                bot.send_message(
                    chat_id,
                    "✅ تراکنش تأیید شد.\n\n"
                    "✉️ لطفاً اطلاعات حساب جهت واریز را به صورت متن ارسال کنید.\n"
                    "(شماره حساب / شماره کارت / شماره شبا / نام و نام خانوادگی دریافت‌کننده / نام و نام خانوادگی واریزکننده)",
                    reply_markup=markup
                )

            pending.pop(chat_id, None)
            return

        elif text == "❌ لغو":
            pending.pop(chat_id, None)
            bot.send_message(chat_id, "❌ روند انتقال ارز شما لغو شد.")
            return main_menu(chat_id)
        else:
            bot.send_message(chat_id, "لطفاً یکی از گزینه‌های «✅ تأیید» یا «❌ لغو» را انتخاب کنید.")
            return

    bot.send_message(chat_id, "برای شروع، «💸 انتقال ارز» را انتخاب کنید.")

# ---------------- اجرای ربات ----------------
if __name__ == "__main__":
    print("✅ ربات نوسان‌پی در حال اجراست...")
    bot.infinity_polling(skip_pending=True)
