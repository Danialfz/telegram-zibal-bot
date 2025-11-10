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
pending_approval = {}  # برای ذخیره درخواست‌های منتظر تأیید ادمین

# ---------------- منوی اصلی ----------------
def main_menu(chat_id, text="برای شروع یکی از گزینه‌ها را انتخاب کنید:"):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("💸 انتقال ارز"))
    bot.send_message(chat_id, text, reply_markup=markup)

# ---------------- /start ----------------
@bot.message_handler(commands=['start'])
def start(message):
    main_menu(message.chat.id, "سلام 👋 به ربات نوسان‌پی خوش‌آمدید.\nبرای شروع «💸 انتقال ارز» را انتخاب کنید.")

# ---------------- مرحله ۱ ----------------
@bot.message_handler(func=lambda m: m.text == "💸 انتقال ارز")
def transfer_menu(message):
    chat_id = message.chat.id
    pending[chat_id] = {"step": "direction"}

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("🌍 از داخل به خارج"), types.KeyboardButton("🏦 از خارج به داخل"))
    markup.add(types.KeyboardButton("🔙 منوی اصلی"))
    bot.send_message(chat_id, "لطفاً نوع انتقال را انتخاب کنید:", reply_markup=markup)

# ---------------- مرحله ۲ ----------------
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

# ---------------- مرحله ۳ ----------------
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

# ---------------- مرحله‌های بعد ----------------
@bot.message_handler(func=lambda m: True)
def all_messages(message):
    chat_id = message.chat.id
    text = (message.text or "").strip()
    state = pending.get(chat_id, {})

    # بازگشت‌ها
    if text == "🔙 منوی اصلی":
        pending.pop(chat_id, None)
        return main_menu(chat_id, "به منوی اصلی بازگشتید.")

    if text == "🔙 بازگشت":
        step = state.get("step")
        if step == "currency":
            return transfer_menu(message)
        elif step == "amount":
            return select_currency(message)
        else:
            return main_menu(chat_id, "به منوی اصلی بازگشتید.")

    # کاربر در حال ارسال اطلاعات حساب است
    if chat_id in awaiting_info:
        if re.search(r"https?://|t\.me|@", text, re.IGNORECASE):
            bot.send_message(chat_id, "⚠️ لطفاً فقط متن ساده ارسال کنید.")
            return

        awaiting_info.remove(chat_id)
        pending_approval[chat_id] = text

        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("✅ تأیید اطلاعات", callback_data=f"approve_{chat_id}"),
            types.InlineKeyboardButton("✏️ درخواست اصلاح", callback_data=f"reject_{chat_id}")
        )

        bot.send_message(
            ADMIN_ID,
            f"📩 اطلاعات حساب از کاربر {chat_id}:\n\n{text}\n\n📌 انتخاب کنید:",
            reply_markup=markup
        )
        bot.send_message(chat_id, "✅ اطلاعات شما ارسال شد. لطفاً منتظر بررسی ادمین باشید.")
        return

    # دریافت مقدار ارز
    if state.get("step") == "amount":
        try:
            amount = float(text.replace(",", "").replace(" ", ""))
        except:
            bot.send_message(chat_id, "⚠️ لطفاً عدد معتبر وارد کنید.")
            return

        state["amount"] = amount
        state["step"] = "waiting_rate"
        pending[chat_id] = state

        bot.send_message(
            ADMIN_ID,
            f"📩 درخواست جدید:\n📍 {state['direction']}\n💱 ارز: {state['currency']}\n💰 مقدار: {amount}\n🆔 {chat_id}\n\n📌 لطفاً نرخ واحد را (به تومان) وارد کنید:"
        )
        bot.send_message(chat_id, "✅ درخواست شما برای بررسی قیمت ارسال شد.")
        return

    # نرخ توسط ادمین
    if chat_id == ADMIN_ID and re.match(r"^\d+(\.\d+)?$", text):
        rate = float(text)
        for user_id, data in pending.items():
            if data.get("step") == "waiting_rate":
                total = data["amount"] * rate
                data["total"] = total
                data["step"] = "confirm"

                markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
                markup.add(types.KeyboardButton("✅ تأیید"), types.KeyboardButton("❌ لغو"))

                bot.send_message(
                    user_id,
                    f"💰 مبلغ نهایی توسط ادمین مشخص شد:\n\n"
                    f"• مقدار ارز: {data['amount']} {data['currency']}\n"
                    f"• مبلغ کل: {total:,.0f} تومان\n\nآیا تأیید می‌کنید؟",
                    reply_markup=markup
                )
                bot.send_message(chat_id, f"✅ نرخ برای کاربر {user_id} ارسال شد.")
                return

    # تأیید یا لغو توسط کاربر
    if state.get("step") == "confirm":
        if text == "✅ تأیید":
            awaiting_info.add(chat_id)
            direction = state.get("direction", "")
            bot.send_message(
                chat_id,
                "✅ تراکنش تأیید شد.\n\n"
                "✉️ لطفاً اطلاعات حساب دریافت‌کننده را به صورت متن ارسال کنید:\n"
                "(نام و نام خانوادگی، کشور، شهر، نام بانک، شماره حساب و سایر جزئیات)",
            )
            pending.pop(chat_id, None)
            return
        elif text == "❌ لغو":
            bot.send_message(chat_id, "❌ عملیات لغو شد.")
            pending.pop(chat_id, None)
            return main_menu(chat_id)

    bot.send_message(chat_id, "برای شروع، «💸 انتقال ارز» را انتخاب کنید.")

# ---------------- بررسی تأیید ادمین ----------------
@bot.callback_query_handler(func=lambda call: call.data.startswith("approve_") or call.data.startswith("reject_"))
def admin_action(call):
    data = call.data
    admin_id = call.from_user.id

    if admin_id != ADMIN_ID:
        return bot.answer_callback_query(call.id, "شما ادمین نیستید ❌")

    user_id = int(data.split("_")[1])

    if data.startswith("approve_"):
        bot.send_message(
            user_id,
            "✅ اطلاعات حساب شما توسط ادمین تأیید شد.\n\n"
            "💳 لطفاً از طریق لینک زیر پرداخت خود را انجام دهید:\n"
            "🔗 https://example.com/payment-test",
        )
        bot.send_message(admin_id, f"✅ اطلاعات کاربر {user_id} تأیید شد و لینک پرداخت ارسال گردید.")
        pending_approval.pop(user_id, None)

    elif data.startswith("reject_"):
        bot.send_message(admin_id, "✏️ لطفاً توضیح دهید چه اصلاحی لازم است:")
        pending["awaiting_correction"] = user_id
        bot.answer_callback_query(call.id, "در انتظار پیام اصلاح هستم...")

# ---------------- پیام اصلاح از ادمین ----------------
@bot.message_handler(func=lambda m: "awaiting_correction" in pending and m.chat.id == ADMIN_ID)
def correction_message(message):
    user_id = pending.pop("awaiting_correction")
    bot.send_message(user_id, f"⚠️ پیام از ادمین:\n\n{message.text}\n\nلطفاً اطلاعات اصلاح‌شده را ارسال کنید.")
    awaiting_info.add(user_id)
    bot.send_message(ADMIN_ID, f"📨 پیام اصلاح برای کاربر {user_id} ارسال شد.")

# ---------------- اجرای ربات ----------------
if __name__ == "__main__":
    print("✅ ربات نوسان‌پی در حال اجراست...")
    bot.infinity_polling(skip_pending=True)
