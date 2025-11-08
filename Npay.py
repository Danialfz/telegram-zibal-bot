import os
import re
import requests
import telebot
from telebot import types
from bs4 import BeautifulSoup

# ----------- تنظیمات -----------
BOT_TOKEN = os.getenv("BOT_TOKEN")
MERCHANT = os.getenv("MERCHANT")

bot = telebot.TeleBot(BOT_TOKEN)

# ----------- لیست ارزها (کد => نام فارسی + کلید bonbast) -----------
currencies = {
    "USD": {"name": "دلار آمریکا 🇺🇸", "key": "usd"},
    "EUR": {"name": "یورو 🇪🇺", "key": "eur"},
    "GBP": {"name": "پوند انگلیس 🇬🇧", "key": "gbp"},
    "CHF": {"name": "فرانک سوئیس 🇨🇭", "key": "chf"},
    "CAD": {"name": "دلار کانادا 🇨🇦", "key": "cad"},
    "AUD": {"name": "دلار استرالیا 🇦🇺", "key": "aud"},
    "AED": {"name": "درهم امارات 🇦🇪", "key": "aed"},
    "TRY": {"name": "لیر ترکیه 🇹🇷", "key": "try"},
    "CNY": {"name": "یوان چین 🇨🇳", "key": "cny"},
    "INR": {"name": "روپیه هند 🇮🇳", "key": "inr"},
    "JPY": {"name": "ین ژاپن 🇯🇵", "key": "jpy"},
    "SAR": {"name": "ریال عربستان 🇸🇦", "key": "sar"},
    "KWD": {"name": "دینار کویت 🇰🇼", "key": "kwd"},
    "OMR": {"name": "ریال عمان 🇴🇲", "key": "omr"},
    "QAR": {"name": "ریال قطر 🇶🇦", "key": "qar"}
}

# ----------- وضعیت کاربران -----------
pending = {}

# ----------- تابع دریافت نرخ ارز از bonbast.com -----------
def get_rate_from_bonbast(currency_key):
    """
    currency_key مثل 'usd' یا 'eur'
    خروجی: نرخ فروش به تومان (int)
    """
    try:
        url = "https://www.bon-bast.com/"
        res = requests.get(url, timeout=10)
        res.raise_for_status()
        soup = BeautifulSoup(res.text, "html.parser")
        rate_tag = soup.find("span", {"id": f"ctl00_cphMain_lbl{currency_key.upper()}"})
        if rate_tag:
            # حذف ویرگول و فاصله
            rate_str = rate_tag.text.strip().replace(",", "")
            return int(rate_str)
    except Exception as e:
        print(f"❌ خطا در دریافت نرخ {currency_key}: {e}")
    return None

# ----------- منوی اصلی -----------
@bot.message_handler(commands=['start'])
def start(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("💸 انتقال ارز"))
    bot.send_message(message.chat.id,
                     "سلام 👋 به ربات نوسان‌پی خوش‌آمدید.\nبرای شروع «💸 انتقال ارز» را انتخاب کنید.",
                     reply_markup=markup)

# ----------- انتخاب نوع انتقال -----------
@bot.message_handler(func=lambda m: m.text == "💸 انتقال ارز")
def transfer_menu(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("🌍 از داخل به خارج"),
               types.KeyboardButton("🏦 از خارج به داخل"))
    bot.send_message(message.chat.id, "لطفاً نوع انتقال را انتخاب کنید:", reply_markup=markup)

# ----------- نمایش فهرست ارزها -----------
@bot.message_handler(func=lambda m: m.text in ["🌍 از داخل به خارج", "🏦 از خارج به داخل"])
def show_currencies(message):
    direction = "داخل" if "داخل" in message.text else "خارج"
    chat_id = message.chat.id
    pending[chat_id] = {"direction": direction, "awaiting": None, "currency": None}

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    for code, info in currencies.items():
        markup.add(types.KeyboardButton(f"{info['name']} ({code})"))
    markup.add(types.KeyboardButton("🔙 منوی اصلی"))
    bot.send_message(chat_id,
                     f"نوع ارز برای انتقال ({'از داخل به خارج' if direction=='داخل' else 'از خارج به داخل'}) را انتخاب کنید:",
                     reply_markup=markup)

# ----------- دریافت نوع ارز و درخواست مقدار -----------
@bot.message_handler(func=lambda m: bool(re.match(r".*\([A-Z]{3}\)\s*$", m.text or "")))
def ask_amount(message):
    chat_id = message.chat.id
    match = re.search(r"\(([A-Z]{3})\)\s*$", message.text)
    if not match:
        return bot.reply_to(message, "لطفاً ارز را با فرمت صحیح انتخاب کنید.")

    code = match.group(1)
    if code not in currencies:
        return bot.reply_to(message, "این ارز در فهرست موجود نیست.")

    pending[chat_id].update({"currency": code, "awaiting": "amount"})

    bot.send_message(chat_id,
                     f"شما ارز «{currencies[code]['name']} ({code})» را انتخاب کردید.\n\n"
                     "لطفاً مقدار مورد نظر را به عدد وارد کنید (مثلاً 2500 یا 12.5):",
                     reply_markup=types.ReplyKeyboardMarkup(resize_keyboard=True).add(types.KeyboardButton("🔙 منوی اصلی")))

# ----------- دریافت مقدار و نمایش معادل ریالی -----------
@bot.message_handler(func=lambda m: True)
def get_amount(message):
    chat_id = message.chat.id
    state = pending.get(chat_id)
    text = (message.text or "").strip()

    if not state or state.get("awaiting") != "amount":
        if text == "🔙 منوی اصلی" or text == "/start":
            return start(message)
        return

    try:
        amount = float(text.replace(",", "").replace(" ", ""))
        if amount <= 0:
            raise ValueError()
    except:
        return bot.reply_to(message, "⚠️ مقدار نامعتبر است. لطفاً عدد مثبت وارد کنید.")

    code = state["currency"]
    currency_info = currencies[code]
    rate = get_rate_from_bonbast(currency_info["key"])

    if not rate:
        return bot.send_message(chat_id, "❌ خطا در دریافت نرخ ارز. لطفاً دوباره تلاش کنید.")

    rial_value = amount * rate
    toman_value = rial_value / 10  # تبدیل به تومان

    bot.send_message(chat_id,
                     f"💱 معادل مبلغ واردشده:\n\n"
                     f"• مقدار: {amount} {currency_info['name']} ({code})\n"
                     f"• نرخ هر واحد: {rate:,} ریال\n"
                     f"• معادل کل: {int(rial_value):,} ریال ≈ {int(toman_value):,} تومان\n\n"
                     "آیا مایل به ادامه و ثبت نهایی هستید؟ (فعلاً این بخش تستی است.)")

    # پاک کردن وضعیت
    pending.pop(chat_id, None)

# ----------- اجرای ربات -----------
if __name__ == "__main__":
    print("✅ ربات نوسان‌پی با polling در حال اجراست و نرخ لحظه‌ای از bonbast دریافت می‌کند...")
    bot.infinity_polling(timeout=60, long_polling_timeout=30)
