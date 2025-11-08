import os
import re
import telebot
from telebot import types

# ----------- تنظیمات -----------
BOT_TOKEN = os.getenv("BOT_TOKEN")
MERCHANT = os.getenv("MERCHANT")

bot = telebot.TeleBot(BOT_TOKEN)

# ----------- لیست ارزها (کد => نام فارسی) -----------
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

# ----------- ذخیره وضعیت موقت کاربران (در حافظه) -----------
# ساختار: pending[chat_id] = {"direction": "داخل"|"خارج", "currency": "USD", "awaiting": "amount"}
pending = {}

# ----------- منوی اصلی خلاصه -----------
@bot.message_handler(commands=['start'])
def start(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    transfer_btn = types.KeyboardButton("💸 انتقال ارز")
    markup.add(transfer_btn)
    bot.send_message(
        message.chat.id,
        "سلام 👋 به ربات نوسان‌پی خوش‌آمدید.\nبرای شروع «💸 انتقال ارز» را انتخاب کنید.",
        reply_markup=markup
    )

# ----------- منوی انتقال خلاصه -----------
@bot.message_handler(func=lambda m: m.text == "💸 انتقال ارز")
def transfer_menu(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    out_btn = types.KeyboardButton("🌍 از داخل به خارج")
    in_btn = types.KeyboardButton("🏦 از خارج به داخل")
    markup.add(out_btn, in_btn)
    bot.send_message(message.chat.id, "لطفاً نوع انتقال را انتخاب کنید:", reply_markup=markup)

# ----------- نمایش فهرست ارزها (پس از انتخاب جهت) -----------
@bot.message_handler(func=lambda m: m.text in ["🌍 از داخل به خارج", "🏦 از خارج به داخل"])
def show_currencies(message):
    direction = "داخل" if "داخل" in message.text else "خارج"
    chat_id = message.chat.id
    # ذخیره جهت در pending
    pending[chat_id] = {"direction": direction, "currency": None, "awaiting": None}

    # کلیدهای ارزها (کوتاه: "دلار آمریکا (USD)")
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    for code, name in currencies.items():
        markup.add(types.KeyboardButton(f"{name} ({code})"))
    markup.add(types.KeyboardButton("🔙 منوی اصلی"))
    bot.send_message(chat_id, f"نوع ارز برای انتقال ({'از داخل به خارج' if direction=='داخل' else 'از خارج به داخل'}) را انتخاب کنید:", reply_markup=markup)

# ----------- وقتی کاربر ارز را انتخاب کرد: بپرس "چه مقدار؟" -----------
@bot.message_handler(func=lambda m: bool(re.match(r".*\([A-Z]{3}\)\s*$", m.text or "")))
def ask_amount(message):
    chat_id = message.chat.id
    text = message.text.strip()
    # استخراج کد ارز از انتهای رشته "(USD)"
    m = re.search(r"\(([A-Z]{3})\)\s*$", text)
    if not m:
        bot.reply_to(message, "لطفاً ارز را با فرمت پیشنهادی (مثلاً: دلار آمریکا (USD)) انتخاب کنید.")
        return

    code = m.group(1)
    if code not in currencies:
        bot.reply_to(message, "این ارز در فهرست موجود نیست. لطفاً مجدداً انتخاب کنید.")
        return

    # ذخیره انتخاب کاربر و علامت‌گذاری که منتظر مقدار هستیم
    pending[chat_id] = {
        "direction": pending.get(chat_id, {}).get("direction", None),
        "currency": code,
        "awaiting": "amount"
    }

    # پرسش رسمی مقدار
    bot.send_message(chat_id,
                     f"شما ارز «{currencies[code]} ({code})» را انتخاب کردید.\n\n"
                     "لطفاً مقدار مورد نظر را به عدد وارد کنید (مثال: 2500 یا 12.5).\n\n"
                     "توجه: فقط عدد وارد کنید؛ واحد را تکرار نکنید.",
                     reply_markup=types.ReplyKeyboardMarkup(resize_keyboard=True).add(types.KeyboardButton("🔙 منوی اصلی")))

# ----------- دریافت مقدار از کاربر و نمایش تأیید -----------
@bot.message_handler(func=lambda m: True)
def receive_amount_and_confirm(message):
    chat_id = message.chat.id
    user_state = pending.get(chat_id)
    text = (message.text or "").strip()

    # اگر کاربر در حالت انتظار مقدار باشد
    if user_state and user_state.get("awaiting") == "amount":
        # بررسی عددی بودن ورودی (ممکنه کاما داشته باشه)
        normalized = text.replace(",", "").replace(" ", "")
        try:
            amount = float(normalized)
            if amount <= 0:
                raise ValueError("مقدار باید مثبت باشد.")
        except Exception:
            bot.reply_to(message, "⚠️ مقدار نامعتبر است. لطفاً فقط عدد مثبت وارد کنید، مثلاً: 2500 یا 12.5")
            return

        # ذخیره مقدار و رفتن به مرحله‌ی تأیید
        pending[chat_id]["amount"] = amount
        pending[chat_id]["awaiting"] = "confirm"

        currency_code = pending[chat_id]["currency"]
        currency_name = currencies.get(currency_code, currency_code)

        # پیام رسمی تأیید (قابلیت اضافه کردن نرخ ریالی بعداً)
        confirm_markup = types.InlineKeyboardMarkup()
        confirm_markup.add(types.InlineKeyboardButton("✅ تأیید و ادامه", callback_data="confirm_transfer"))
        confirm_markup.add(types.InlineKeyboardButton("❌ لغو و بازگشت", callback_data="cancel_transfer"))

        bot.send_message(chat_id,
                         f"📌 لطفاً اطلاعات زیر را بررسی کنید:\n\n"
                         f"• نوع انتقال: {pending[chat_id].get('direction','-')}\n"
                         f"• ارز: {currency_name} ({currency_code})\n"
                         f"• مقدار: {amount}\n\n"
                         "آیا مایل به ادامه هستید؟",
                         reply_markup=confirm_markup)
        return

    # اگر کاربر در حالت دیگری بود یا متن آزاد فرستاد
    # اگر خواسته بازگشت کنه به منوی اصلی
    if text == "🔙 منوی اصلی" or text == "/start":
        return start(message)

    # پیام پیش‌فرض برای متن‌های نامرتبط
    bot.reply_to(message, "اگر می‌خواهید انتقال ارز انجام دهید، ابتدا از منوی اصلی «💸 انتقال ارز» را انتخاب کنید.")

# ----------- هندل کردن تأیید / لغو از طریق کال‌بک -----------
@bot.callback_query_handler(func=lambda call: call.data in ["confirm_transfer", "cancel_transfer"])
def handle_confirm_cancel(call):
    chat_id = call.message.chat.id
    if call.data == "confirm_transfer":
        state = pending.get(chat_id)
        if not state:
            bot.answer_callback_query(call.id, "هیچ درخواستی برای تأیید وجود ندارد.")
            return
        # اینجا مرحلهٔ بعد (محاسبه ریالی، ایجاد سفارش، ارسال لینک پرداخت و...) انجام می‌شود.
        # فعلاً فقط پیام رسمی ارسال می‌کنیم.
        bot.edit_message_text(chat_id=chat_id, message_id=call.message.message_id,
                              text="✅ درخواست شما ثبت اولیه شد.\nما در مرحله بعدی معادل ریالی را محاسبه و برای شما ارسال خواهیم کرد.")
        # پاک کردن pending یا می‌توان نگه داشت برای مراحل بعدی
        pending.pop(chat_id, None)

    elif call.data == "cancel_transfer":
        bot.edit_message_text(chat_id=chat_id, message_id=call.message.message_id,
                              text="❌ درخواست شما لغو شد. برای شروع مجدد از منوی اصلی استفاده کنید.")
        pending.pop(chat_id, None)

# ----------- اجرای ربات -----------
if __name__ == "__main__":
    print("✅ ربات نوسان‌پی با polling در حال اجراست...")
    bot.infinity_polling(timeout=60, long_polling_timeout=30)
