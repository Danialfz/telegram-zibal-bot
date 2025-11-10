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

# ---------------- وضعیت کاربران ----------------
pending = {}
awaiting_info = set()  # کاربرانی که باید اطلاعات واریز ارسال کنند

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

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("🔙 منوی اصلی"))

    bot.send_message(chat_id,
                     f"شما ارز «{currencies[code]} ({code})» را انتخاب کردید.\n"
                     "لطفاً مقدار را وارد کنید (مثلاً 2500 یا 12.5):",
                     reply_markup=markup)

# ---------------- پردازش مقدار و ارسال به ادمین ----------------
@bot.message_handler(func=lambda m: True)
def receive_amount(message):
    chat_id = message.chat.id
    text = (message.text or "").strip()

    # ✅ بازگشت به منوی اصلی
    if text in ["🔙 منوی اصلی", "/start"]:
        pending.pop(chat_id, None)
        return start(message)

    # اگر کاربر در مرحله ارسال اطلاعات واریز است:
    if chat_id in awaiting_info:
        if re.search(r"https?://|t\.me|@", text, re.IGNORECASE):
            bot.delete_message(chat_id, message.message_id)
            bot.send_message(chat_id, "⚠️ لطفاً فقط متن ساده ارسال کنید. ارسال لینک یا تگ مجاز نیست.")
            return

        bot.send_message(
            ADMIN_ID,
            f"📦 اطلاعات واریز از کاربر {chat_id}:\n{text}"
        )
        bot.send_message(chat_id, "✅ اطلاعات شما با موفقیت ارسال شد. در حال بررسی توسط پشتیبانی هستیم.")
        awaiting_info.remove(chat_id)
        return

    state = pending.get(chat_id)

    # مرحله دریافت مقدار از کاربر
    if state and state.get("awaiting") == "amount":
        normalized = text.replace(",", "").replace(" ", "")
        try:
            amount = float(normalized)
            if amount <= 0:
                raise ValueError()
        except Exception:
            bot.reply_to(message, "⚠️ لطفاً عدد مثبت وارد کنید (مثلاً: 2500)")
            return

        currency_code = state["currency"]
        direction = state["direction"]

        # ذخیره برای بررسی ادمین
        pending[chat_id]["amount"] = amount
        pending[chat_id]["awaiting"] = None

        # ارسال درخواست به ادمین
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

    # مرحله پاسخ ادمین (تعیین نرخ واحد)
    if chat_id == ADMIN_ID and re.match(r"^\d+(\.\d+)?$", text):
        rate = float(text)
        for user_id, data in pending.items():
            if data.get("amount") and data.get("currency") and not data.get("total"):
                total = data["amount"] * rate
                data["total"] = total
                data["awaiting"] = "confirm"

                # ساخت دکمه‌های تأیید و لغو
                markup = types.InlineKeyboardMarkup()
                markup.row(
                    types.InlineKeyboardButton("✅ تأیید تراکنش", callback_data="confirm"),
                    types.InlineKeyboardButton("❌ لغو تراکنش", callback_data="cancel")
                )

                bot.send_message(
                    user_id,
                    f"💰 مبلغ نهایی توسط ادمین مشخص شد:\n\n"
                    f"• مقدار ارز: {data['amount']:,} {data['currency']}\n"
                    f"• مبلغ کل پرداختی: {total:,.0f} تومان\n\n"
                    "لطفاً یکی از گزینه‌های زیر را انتخاب کنید:",
                    reply_markup=markup
                )

                bot.send_message(chat_id, f"✅ نرخ برای کاربر {user_id} ثبت و ارسال شد.")
                return

        bot.send_message(chat_id, "⚠️ در حال حاضر هیچ درخواست فعالی برای قیمت‌گذاری وجود ندارد.")
        return

# ---------------- هندل دکمه‌های تأیید یا لغو ----------------
@bot.callback_query_handler(func=lambda call: call.data in ["confirm", "cancel"])
def handle_confirmation(call):
    chat_id = call.message.chat.id
    state = pending.get(chat_id)

    if not state:
        bot.answer_callback_query(call.id, "درخواست منقضی شده است.")
        return

    if call.data == "confirm":
        # تأیید تراکنش
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("📤 ارسال اطلاعات جهت واریز", callback_data="send_info"))
        bot.edit_message_text(
            "✅ تراکنش شما تأیید شد.\nلطفاً اطلاعات مورد نیاز جهت واریز را ارسال کنید:",
            chat_id=chat_id,
            message_id=call.message.message_id,
            reply_markup=markup
        )
    else:
        # لغو تراکنش
        pending.pop(chat_id, None)
        bot.edit_message_text("❌ روند انتقال ارز شما لغو شد.", chat_id=chat_id, message_id=call.message.message_id)
        start(types.SimpleNamespace(chat=types.SimpleNamespace(id=chat_id)))

# ---------------- کلیک دکمه ارسال اطلاعات ----------------
@bot.callback_query_handler(func=lambda call: call.data == "send_info")
def send_info_handler(call):
    chat_id = call.message.chat.id
    bot.send_message(chat_id, "✉️ لطفاً اطلاعات مورد نیاز جهت واریز را به صورت متن ارسال کنید (بدون لینک، عکس یا فایل).")
    awaiting_info.add(chat_id)

# ---------------- اجرای ربات ----------------
if __name__ == "__main__":
    print("✅ ربات نوسان‌پی در حال اجراست...")
    bot.infinity_polling(timeout=60, long_polling_timeout=30)
