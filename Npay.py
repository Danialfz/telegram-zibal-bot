import os
import re
import time
import json
import requests
import telebot
from telebot import types

# ---------------- تنظیمات ----------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
MERCHANT = os.getenv("MERCHANT")

bot = telebot.TeleBot(BOT_TOKEN)

# ---------------- فهرست ارزها (کد => نام فارسی) ----------------
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

# ---------------- کش نرخ‌ها ----------------
CACHE_PATH = "rates_cache.json"
CACHE_TTL = 60 * 5  # ثبات کش: ۵ دقیقه

def load_cache():
    try:
        with open(CACHE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save_cache(cache):
    try:
        with open(CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False)
    except Exception as e:
        print("⚠️ couldn't save cache:", e)

# ---------------- گرفتن نرخ از API رایگان (exchangerate.host) ----------------
BASE_URL = "https://api.exchangerate.host/convert"

def fetch_rate_api(from_code: str, to_code: str = "IRR"):
    """
    فراخوانی رایگان برای تبدیل 1 واحد from_code به IRR (ریال).
    خروجی: نرخ (float) یا None در صورت خطا.
    """
    try:
        params = {"from": from_code.upper(), "to": to_code.upper(), "amount": 1}
        headers = {"User-Agent": "Mozilla/5.0 (compatible; NpayBot/1.0)"}
        r = requests.get(BASE_URL, params=params, headers=headers, timeout=8)
        r.raise_for_status()
        data = r.json()
        # اگر مقدار result موجود باشد، مقدار تبدیل شده بر حسب IRR برمی‌گردد
        if isinstance(data, dict):
            if "result" in data and data["result"] is not None:
                return float(data["result"])
            if "info" in data and isinstance(data["info"], dict) and "rate" in data["info"]:
                # rate در info ممکن است موجود باشد (برای amount=1 همان نرخ است)
                return float(data["info"]["rate"])
    except Exception as e:
        print("❌ fetch_rate_api error:", e)
    return None

def get_rate(from_code: str):
    """
    نرخ هر واحد from_code را به IRR برمی‌گرداند.
    خروجی: (rate: float or None, from_cache: bool, age_seconds: int or None)
    """
    from_code = from_code.upper()
    cache = load_cache()
    key = f"{from_code}_IRR"
    now = int(time.time())

    # استفاده از کش در صورت تازه بودن
    if key in cache:
        entry = cache[key]
        age = now - entry.get("ts", 0)
        if age <= CACHE_TTL and entry.get("rate") is not None:
            return entry["rate"], True, age

    # تلاش برای دریافت از API
    rate = fetch_rate_api(from_code, "IRR")
    if rate is not None:
        cache[key] = {"rate": rate, "ts": now}
        try:
            save_cache(cache)
        except:
            pass
        return rate, False, 0

    # در صورت شکست API، اگر کش قدیمی موجود است از آن استفاده کن
    if key in cache and cache[key].get("rate") is not None:
        entry = cache[key]
        age = now - entry.get("ts", 0)
        return entry["rate"], True, age

    # هیچ داده‌ای موجود نیست
    return None, False, None

# ---------------- منوها و جریان کاربری (همان کد قبلی با تغییرات محاسبه) ----------------
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

@bot.message_handler(func=lambda m: m.text == "💸 انتقال ارز")
def transfer_menu(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("🌍 از داخل به خارج"),
               types.KeyboardButton("🏦 از خارج به داخل"))
    bot.send_message(message.chat.id, "لطفاً نوع انتقال را انتخاب کنید:", reply_markup=markup)

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
        # گرفتن نرخ (بر حسب ریال IRR) با کش و fallback
        rate, from_cache, age = get_rate(currency_code)

        if rate is None:
            bot.send_message(chat_id, "❌ متأسفانه نرخ ارز فعلاً در دسترس نیست. لطفاً کمی بعد تلاش کنید.")
            return

        # rate بر حسب ریال است. تبدیل به تومان:
        toman_per_unit = rate / 10.0
        total_toman = amount * toman_per_unit

        note = ""
        if from_cache:
            if age is not None:
                minutes = int(age / 60)
                note = f"\n(نرخ از کش استفاده شد — به‌روز {minutes} دقیقه قبل)"
            else:
                note = "\n(نرخ از کش استفاده شد)"

        # ارسال نتیجه (بدون اشاره به منبع)
        bot.send_message(
            chat_id,
            f"💰 معادل مبلغ واردشده:\n\n"
            f"• مقدار: {amount:,} {currency_code}\n"
            f"• نرخ هر واحد: {toman_per_unit:,.0f} تومان\n"
            f"• معادل کل: {total_toman:,.0f} تومان{note}\n\n"
            "✅ اگر مایلید ثبت نهایی انجام شود، اعلام کنید."
        )

        pending.pop(chat_id, None)
        return

    if text == "🔙 منوی اصلی" or text == "/start":
        return start(message)

    bot.reply_to(message, "برای انتقال ارز، ابتدا از منوی اصلی «💸 انتقال ارز» را انتخاب کنید.")

# ---------------- اجرای ربات ----------------
if __name__ == "__main__":
    print("✅ ربات نوسان‌پی با polling در حال اجراست...")
    bot.infinity_polling(timeout=60, long_polling_timeout=30)
