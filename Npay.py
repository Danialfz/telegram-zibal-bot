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

PAYMENT_LINK = os.getenv("PAYMENT_LINK", "https://example.com/payment")

bot = telebot.TeleBot(BOT_TOKEN, parse_mode=None)

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
    kb.add(types.KeyboardButton("🌍 از داخل به خارج"), types.KeyboardButton("🏦 از خارج به داخل"))
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

# ---------------- فرمان‌ها ----------------
@bot.message_handler(commands=['start'])
def cmd_start(m):
    bot.send_message(m.chat.id, "سلام 👋 به ربات نوسان‌پی خوش آمدید.\nبرای شروع «💸 انتقال ارز» را انتخاب کنید.", reply_markup=main_menu_markup())

@bot.message_handler(func=lambda msg: msg.text == "💸 انتقال ارز")
def cmd_transfer(msg):
    bot.send_message(msg.chat.id, "لطفاً جهت انتقال را انتخاب کنید:", reply_markup=direction_markup())

@bot.message_handler(func=lambda msg: msg.text in ["🌍 از داخل به خارج", "🏦 از خارج به داخل"])
def choose_currency_list(msg):
    chat_id = msg.chat.id
    direction = "از داخل به خارج" if "داخل" in msg.text else "از خارج به داخل"
    pending[chat_id] = {"direction": direction, "currency": None, "awaiting": None}
    # نمایش ارزها
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

# بقیه‌ی کد بدون تغییر است
# ---------------- منطق کلی پیام‌ها ----------------
@bot.message_handler(func=lambda msg: True)
def router(msg):
    chat_id = msg.chat.id
    text = (msg.text or "").strip()
    ...
    # (تمام بقیه‌ی منطق مثل نسخه‌ای که فرستادی بدون تغییر باقی می‌ماند)
    ...

# ---------------- اجرا ----------------
if __name__ == "__main__":
    print("✅ ربات نوسان‌پی در حال اجراست...")
    bot.infinity_polling(timeout=60, long_polling_timeout=30)
