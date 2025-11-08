import os
import re
import requests
from bs4 import BeautifulSoup
import telebot
from telebot import types

# ---------------- تنظیمات ----------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
MERCHANT = os.getenv("MERCHANT")

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

# ---------------- وضعیت موقت کاربران ----------------
pending = {}

# ---------------- تابع دریافت نرخ ارز از Bonbast ----------------
def fetch_currency_rate(code: str):
    """
    نرخ فروش ارز را از سایت bonbast.com به تومان می‌خواند.
    """
    try:
        url = "https://bonbast.com/"
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, headers=headers, timeout=10)

        if resp.status_code != 200:
            return None

        soup = BeautifulSoup(resp.text, "html.parser")

        # جستجوی جدول ارزها
        rows = soup.find_all("tr")
        for row in rows:
            cols = [c.get_text(strip=True) for c in row.find_all("td")]
            if len(cols) >= 3 and cols[0].strip().upper().startswith(code.upper()):
                sell_price = cols[1].replace(",", "").replace("٬", "")
                return float(sell_price)

        return None

    except Exception as e:
        print(f"❌ Error fetching rate for {code}: {e}")
        return None

# ---------------- شروع ----------------
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

# ---------------- منوی انتقال ----------------
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
    direction = "داخل" if "داخل" in message.text else "خارج"
    chat_id = message.chat.id
    pending[chat_id] = {"direction": direction, "currency": None, "awaiting": None}

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    for code, name in currencies.items():
        markup.add(types.KeyboardButton(f"{name} ({code})"))
    markup.add(types.KeyboardButton("🔙 منوی اصلی"))
    bot.send_message(chat_id, f"نوع ارز مورد نظر برای انتقال ({'از داخل به خارج' if direction=='داخل' else 'از خارج به داخل'}) را انتخاب کنید:", reply_markup=markup)

# ---------------- وقتی ارز انتخاب شد ----------------
@bot.message_handler(func=lambda m: bool(re.match(r".*\([A-Z]{3}\)\s*$", m.text or "")))
def ask_amount(message):
    chat_id = message.chat.id
    match = re.search(r"\(([A-Z]{3})\)\s*$", message.text.strip())
    if not match:
        bot.reply_to(message, "لطفاً ارز را با فرمت صحیح انتخاب کنید (مثلاً: دلار آمریکا (USD)).")
        return

    code = match.group(1)
    if code not in currencies:
        bot.reply_to(message, "این ارز در فهرست نیست، لطفاً مجدداً انتخاب کنید.")
        return

    pending[chat_id] = {
        "direction": pending.get(chat_id, {}).get("direction", None),
        "currency": code,
        "awaiting": "amount"
    }

    bot.send_message(chat_id,
                     f"شما ارز «{currencies[code]} ({code})» را انتخاب کردید.\n"
                     "لطفاً مقدار مورد نظر را به عدد وارد کنید (مثال: 2500 یا 12.5).",
                     reply_markup=types.ReplyKeyboardMarkup(resize_keyboard=True).add(types.KeyboardButton("🔙 منوی اصلی")))

# ---------------- دریافت مقدار ----------------
@bot.message_handler(func=lambda m: True)
def receive_amount(message):
    chat_id = message.chat.id
    state = pending.get(chat_id)
    text = (message.text or "").strip()

    if state and state.get("awaiting") == "amount":
        normalized = text.replace(",", "").replace(" ", "")
        try:
            amount = float(normalized)
            if amount <= 0:
                raise ValueError()
        except Exception:
            bot.reply_to(message, "⚠️ لطفاً فقط عدد مثبت وارد کنید (مثلاً: 2500 یا 12.5)")
            return

        currency_code = state["currency"]
        rate = fetch_currency_rate(currency_code)

        if not rate:
            bot.send_message(chat_id, "❌ خطا در دریافت قیمت ارز از Bonbast. لطفاً بعداً دوباره تلاش کنید.")
            return

        total_toman = amount * rate
        bot.send_message(
            chat_id,
            f"💰 نرخ فعلی {currencies[currency_code]}: {rate:,.0f} تومان\n"
            f"📦 مبلغ کل برای {amount} واحد: {total_toman:,.0f} تومان\n\n"
            "✅ درخواست شما ثبت شد و به مرحله بعد منتقل می‌شود."
        )

        pending.pop(chat_id, None)
        return

    if text == "🔙 منوی اصلی" or text == "/start":
        return start(message)

    bot.reply_to(message, "برای انتقال ارز، از منوی اصلی «💸 انتقال ارز» را انتخاب کنید.")

# ---------------- اجرای ربات ----------------
if __name__ == "__main__":
    print("✅ ربات نوسان‌پی با polling در حال اجراست...")
    bot.infinity_polling(timeout=60, long_polling_timeout=30)
