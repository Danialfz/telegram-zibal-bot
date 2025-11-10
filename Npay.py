import os
import re
import telebot
from telebot import types

# ---------------- تنظیمات ----------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "1611406302"))  # آی‌دی ادمین
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

# ---------------- اطلاعات لازم برای هر کشور ----------------
country_requirements = {
    "🇹🇷 ترکیه": "نام و نام خانوادگی دریافت‌کننده / شماره IBAN / نام بانک / شهر و شعبه بانک",
    "🇨🇳 چین": "نام و نام خانوادگی دریافت‌کننده / شماره حساب بانکی / نام بانک / شهر",
    "🇪🇺 اروپا": "نام و نام خانوادگی / شماره IBAN / نام بانک / کشور مقصد",
    "🇺🇸 آمریکا": "نام کامل / شماره حساب / نام بانک / ABA Routing Number",
    "🇬🇧 انگلیس": "نام کامل / Sort Code / Account Number / نام بانک"
}

# ---------------- متغیرهای موقت ----------------
pending = {}
awaiting_info = set()
awaiting_admin_fix = {}

# ---------------- منوها ----------------
def main_menu_markup():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("💸 انتقال ارز"))
    return markup

def back_to_main_markup():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("🔙 بازگشت به منوی اصلی"))
    return markup

def country_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    for c in country_requirements.keys():
        markup.add(types.KeyboardButton(c))
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

# ---------------- انتخاب نوع انتقال ----------------
@bot.message_handler(func=lambda m: m.text == "💸 انتقال ارز")
def transfer_menu(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(
        types.KeyboardButton("🌍 از داخل به خارج"),
        types.KeyboardButton("🏦 از خارج به داخل"),
        types.KeyboardButton("🔙 بازگشت به منوی اصلی")
    )
    bot.send_message(message.chat.id, "لطفاً نوع انتقال را انتخاب کنید:", reply_markup=markup)

# ---------------- انتخاب کشور برای داخل به خارج ----------------
@bot.message_handler(func=lambda m: m.text == "🌍 از داخل به خارج")
def choose_country(message):
    chat_id = message.chat.id
    pending[chat_id] = {"direction": "متقاضی قصد واریز از داخل به خارج دارد"}
    bot.send_message(chat_id, "لطفاً کشور مقصد را انتخاب کنید:", reply_markup=country_menu())

# ---------------- انتخاب ارز برای خارج به داخل ----------------
@bot.message_handler(func=lambda m: m.text == "🏦 از خارج به داخل")
def show_currencies_in(message):
    chat_id = message.chat.id
    pending[chat_id] = {"direction": "متقاضی قصد واریز از خارج به داخل دارد"}
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    for code, name in currencies.items():
        markup.add(types.KeyboardButton(f"{name} ({code})"))
    markup.add(types.KeyboardButton("🔙 بازگشت به منوی اصلی"))
    bot.send_message(chat_id, "نوع ارز مورد نظر را انتخاب کنید:", reply_markup=markup)

# ---------------- کشور انتخاب شد -> ارز ----------------
@bot.message_handler(func=lambda m: m.text in country_requirements.keys())
def choose_currency_for_country(message):
    chat_id = message.chat.id
    if chat_id not in pending:
        return start(message)

    pending[chat_id]["country"] = message.text
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    for code, name in currencies.items():
        markup.add(types.KeyboardButton(f"{name} ({code})"))
    markup.add(types.KeyboardButton("🔙 بازگشت به منوی اصلی"))
    bot.send_message(chat_id, f"کشور مقصد: {message.text}\nاکنون نوع ارز را انتخاب کنید:", reply_markup=markup)

# ---------------- انتخاب ارز -> مقدار ----------------
@bot.message_handler(func=lambda m: bool(re.match(r".*\([A-Z]{3}\)\s*$", m.text or "")))
def ask_amount(message):
    chat_id = message.chat.id
    match = re.search(r"\(([A-Z]{3})\)\s*$", message.text.strip())
    if not match:
        return bot.reply_to(message, "فرمت ارز صحیح نیست.")

    code = match.group(1)
    if code not in currencies:
        return bot.reply_to(message, "این ارز در فهرست نیست.")

    if chat_id not in pending:
        return start(message)

    pending[chat_id]["currency"] = code
    pending[chat_id]["awaiting"] = "amount"

    bot.send_message(chat_id,
        f"شما ارز «{currencies[code]} ({code})» را انتخاب کردید.\n"
        "لطفاً مقدار را وارد کنید (مثلاً 2500):",
        reply_markup=back_to_main_markup()
    )

# ---------------- منطق اصلی ----------------
@bot.message_handler(func=lambda m: True)
def main_handler(message):
    chat_id = message.chat.id
    text = message.text.strip()

    # --- بازگشت ---
    if text in ["🔙 بازگشت به منوی اصلی", "/start"]:
        pending.pop(chat_id, None)
        awaiting_info.discard(chat_id)
        return start(message)

    # --- مرحله ارسال اطلاعات حساب ---
    if chat_id in awaiting_info:
        if re.search(r"https?://|t\.me|@", text, re.IGNORECASE):
            bot.delete_message(chat_id, message.message_id)
            return bot.send_message(chat_id, "⚠️ لطفاً فقط متن ساده بفرستید.")

        bot.send_message(ADMIN_ID, f"📦 اطلاعات حساب از کاربر {chat_id}:\n\n{text}")
        bot.send_message(chat_id, "✅ اطلاعات شما ارسال شد. منتظر بررسی ادمین باشید.")
        awaiting_info.remove(chat_id)
        awaiting_admin_fix[chat_id] = "pending_check"
        return

    state = pending.get(chat_id)

    # --- مرحله مقدار ---
    if state and state.get("awaiting") == "amount":
        try:
            amount = float(text.replace(",", ""))
            if amount <= 0:
                raise ValueError
        except:
            return bot.reply_to(message, "عدد معتبر وارد کنید (مثلاً 1500).")

        pending[chat_id]["amount"] = amount
        pending[chat_id]["awaiting"] = "waiting_rate"

        bot.send_message(
            ADMIN_ID,
            f"📩 درخواست جدید از کاربر @{message.from_user.username or message.from_user.first_name}\n"
            f"📍 {state.get('direction')}\n"
            f"🌍 کشور مقصد: {state.get('country', '---')}\n"
            f"💱 {currencies[state['currency']]} ({state['currency']})\n"
            f"📊 مقدار: {amount:,}\n"
            f"🆔 Chat ID: {chat_id}\n\n"
            "📌 لطفاً نرخ هر واحد را وارد کنید (عدد)."
        )
        bot.send_message(chat_id, "✅ درخواست شما برای بررسی نرخ ارسال شد.", reply_markup=main_menu_markup())
        return

    # --- نرخ‌گذاری ادمین ---
    if chat_id == ADMIN_ID and re.match(r"^\d+(\.\d+)?$", text):
        rate = float(text)
        target_user = None
        for uid, data in pending.items():
            if data.get("awaiting") == "waiting_rate":
                target_user = uid
                break
        if not target_user:
            return bot.send_message(ADMIN_ID, "هیچ درخواستی در انتظار نرخ نیست.")

        data = pending[target_user]
        total = data["amount"] * rate
        data["total"] = total
        data["awaiting"] = "confirm"

        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add(types.KeyboardButton("✅ تایید"), types.KeyboardButton("❌ لغو"))
        markup.add(types.KeyboardButton("🔙 بازگشت به منوی اصلی"))

        bot.send_message(
            target_user,
            f"💰 مبلغ نهایی مشخص شد:\n"
            f"• مقدار: {data['amount']:,} {data['currency']}\n"
            f"• مبلغ کل پرداختی: {total:,.0f} تومان\n\n"
            "آیا تایید می‌کنید؟",
            reply_markup=markup
        )
        bot.send_message(ADMIN_ID, "✅ نرخ برای کاربر ارسال شد.")
        return

    # --- تایید یا لغو ---
    if state and state.get("awaiting") == "confirm":
        if text == "✅ تایید":
            pending.pop(chat_id, None)
            awaiting_info.add(chat_id)
            direction = state.get("direction", "")

            if "داخل به خارج" in direction:
                country = state.get("country", "")
                form = country_requirements.get(country, "نام و نام خانوادگی دریافت‌کننده / شماره حساب / نام بانک")
                bot.send_message(chat_id, f"✉️ لطفاً اطلاعات حساب دریافت‌کننده را ارسال کنید:\n({form})", reply_markup=back_to_main_markup())
            else:
                bot.send_message(chat_id,
                    "✉️ لطفاً اطلاعات حساب داخلی را ارسال کنید:\n(شماره حساب / شماره کارت / شماره شبا / نام و نام خانوادگی دریافت‌کننده / نام و نام خانوادگی واریزکننده)",
                    reply_markup=back_to_main_markup()
                )
            return

        if text == "❌ لغو":
            pending.pop(chat_id, None)
            bot.send_message(chat_id, "❌ روند انتقال لغو شد.", reply_markup=main_menu_markup())
            return

    bot.send_message(chat_id, "برای شروع گزینه «💸 انتقال ارز» را انتخاب کنید.", reply_markup=main_menu_markup())

# ---------------- اجرا ----------------
if __name__ == "__main__":
    print("✅ ربات نوسان‌پی فعال شد...")
    bot.infinity_polling(timeout=60, long_polling_timeout=30)
