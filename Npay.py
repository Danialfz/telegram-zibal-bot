import os
import re
import telebot
from telebot import types

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "1611406302"))

bot = telebot.TeleBot(BOT_TOKEN)

currencies = {
    "USD": "دلار آمریکا 🇺🇸", "EUR": "یورو 🇪🇺", "GBP": "پوند انگلیس 🇬🇧",
    "CHF": "فرانک سوئیس 🇨🇭", "CAD": "دلار کانادا 🇨🇦", "AUD": "دلار استرالیا 🇦🇺",
    "AED": "درهم امارات 🇦🇪", "TRY": "لیر ترکیه 🇹🇷", "CNY": "یوان چین 🇨🇳",
    "INR": "روپیه هند 🇮🇳", "JPY": "ین ژاپن 🇯🇵", "SAR": "ریال عربستان 🇸🇦",
    "KWD": "دینار کویت 🇰🇼", "OMR": "ریال عمان 🇴🇲", "QAR": "ریال قطر 🇶🇦"
}

pending = {}
awaiting_info = set()
awaiting_admin_action = {}
awaiting_admin_correction = None

def main_menu(chat_id, text="برای شروع یکی از گزینه‌ها را انتخاب کنید:"):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("💸 انتقال ارز"))
    bot.send_message(chat_id, text, reply_markup=markup)

@bot.message_handler(commands=['start'])
def start(message):
    main_menu(message.chat.id, "سلام 👋 به ربات نوسان‌پی خوش‌آمدید.\nبرای شروع «💸 انتقال ارز» را انتخاب کنید.")

@bot.message_handler(func=lambda m: m.text == "💸 انتقال ارز")
def transfer_menu(message):
    chat_id = message.chat.id
    pending[chat_id] = {"step": "direction"}
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("🌍 از داخل به خارج"), types.KeyboardButton("🏦 از خارج به داخل"))
    markup.add(types.KeyboardButton("🔙 منوی اصلی"))
    bot.send_message(chat_id, "لطفاً نوع انتقال را انتخاب کنید:", reply_markup=markup)

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

@bot.message_handler(func=lambda m: bool(re.search(r"\([A-Z]{3}\)$", m.text or "")))
def ask_amount(message):
    chat_id = message.chat.id
    code = re.search(r"\(([A-Z]{3})\)$", message.text).group(1)
    state = pending.get(chat_id, {})
    state["currency"] = code
    state["step"] = "amount"
    pending[chat_id] = state

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("🔙 بازگشت"), types.KeyboardButton("🔙 منوی اصلی"))

    bot.send_message(chat_id, f"شما ارز «{currencies[code]} ({code})» را انتخاب کردید.\n\nلطفاً مقدار را وارد کنید:", reply_markup=markup)

@bot.message_handler(func=lambda m: True)
def handle_all(message):
    global awaiting_admin_correction
    chat_id = message.chat.id
    text = (message.text or "").strip()
    state = pending.get(chat_id, {})

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

    # اگر کاربر اطلاعات حساب می‌فرسته
    if chat_id in awaiting_info:
        awaiting_info.remove(chat_id)
        awaiting_admin_action[chat_id] = text
        bot.send_message(
            ADMIN_ID,
            f"📩 اطلاعات حساب از کاربر {chat_id}:\n\n{text}\n\n🔹 بنویسید «تأیید» اگر درست است\n🔹 بنویسید «اصلاح» اگر نیاز به اصلاح دارد."
        )
        return bot.send_message(chat_id, "✅ اطلاعات شما ارسال شد. لطفاً منتظر بررسی ادمین باشید.")

    # اگر ادمین در حال پاسخ است
    if chat_id == ADMIN_ID:
        if text == "تأیید":
            if not awaiting_admin_action:
                return bot.send_message(ADMIN_ID, "هیچ اطلاعاتی برای بررسی وجود ندارد.")
            user_id, info = awaiting_admin_action.popitem()
            bot.send_message(
                user_id,
                "✅ اطلاعات حساب شما توسط ادمین تأیید شد.\n\n💳 لطفاً از طریق لینک زیر پرداخت خود را انجام دهید:\nhttps://example.com/payment-test"
            )
            return bot.send_message(ADMIN_ID, f"✅ لینک پرداخت برای کاربر {user_id} ارسال شد.")

        elif text == "اصلاح":
            if not awaiting_admin_action:
                return bot.send_message(ADMIN_ID, "هیچ اطلاعاتی برای اصلاح وجود ندارد.")
            user_id, info = awaiting_admin_action.popitem()
            awaiting_admin_correction = user_id
            return bot.send_message(ADMIN_ID, "✏️ لطفاً توضیح اصلاح را ارسال کنید:")

        elif awaiting_admin_correction:
            user_id = awaiting_admin_correction
            awaiting_admin_correction = None
            bot.send_message(
                user_id,
                f"⚠️ پیام از ادمین:\n\n{message.text}\n\nلطفاً اطلاعات اصلاح‌شده را ارسال کنید."
            )
            awaiting_info.add(user_id)
            return bot.send_message(ADMIN_ID, f"📨 پیام اصلاح برای کاربر {user_id} ارسال شد.")
        return

    # اگر کاربر مقدار ارز وارد کند
    if state.get("step") == "amount":
        try:
            amount = float(text.replace(",", "").replace(" ", ""))
        except:
            return bot.send_message(chat_id, "⚠️ لطفاً عدد معتبر وارد کنید.")
        state["amount"] = amount
        state["step"] = "waiting_rate"
        pending[chat_id] = state
        bot.send_message(
            ADMIN_ID,
            f"📩 درخواست جدید:\n{state['direction']}\n💱 ارز: {state['currency']}\n💰 مقدار: {amount}\n🆔 کاربر: {chat_id}\n\nلطفاً نرخ واحد را (به تومان) وارد کنید:"
        )
        return bot.send_message(chat_id, "✅ درخواست شما برای بررسی قیمت ارسال شد.")

    # اگر ادمین نرخ وارد کند
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
                    f"💰 مبلغ نهایی تعیین شد:\n• مقدار ارز: {data['amount']} {data['currency']}\n• مبلغ کل: {total:,.0f} تومان\n\nآیا تأیید می‌کنید؟",
                    reply_markup=markup
                )
                bot.send_message(ADMIN_ID, f"✅ نرخ برای کاربر {user_id} ارسال شد.")
                return

    # کاربر تایید یا لغو می‌کند
    if state.get("step") == "confirm":
        if text == "✅ تأیید":
            awaiting_info.add(chat_id)
            bot.send_message(
                chat_id,
                "✅ تراکنش تأیید شد.\n\n✉️ لطفاً اطلاعات حساب را به صورت زیر ارسال کنید:\n"
                "(شماره حساب / شماره کارت / شماره شبا / نام و نام خانوادگی دریافت‌کننده / نام و نام خانوادگی واریزکننده)"
            )
            pending.pop(chat_id, None)
            return
        elif text == "❌ لغو":
            pending.pop(chat_id, None)
            return main_menu(chat_id, "❌ عملیات لغو شد.")
    bot.send_message(chat_id, "برای شروع، گزینه «💸 انتقال ارز» را انتخاب کنید.")

if __name__ == "__main__":
    print("✅ ربات فعال شد...")
    bot.infinity_polling(skip_pending=True)
