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
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))  # 👈 شناسه ادمین از Railway

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

pending = {}

# ---------------- کش نرخ‌ها ----------------
CACHE_PATH = "rates_cache.json"
CACHE_TTL = 60 * 5

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

BASE_URL = "https://api.exchangerate.host/convert"

def fetch_rate_api(from_code: str, to_code: str = "IRR"):
    try:
        params = {"from": from_code.upper(), "to": to_code.upper(), "amount": 1}
        headers = {"User-Agent": "Mozilla/5.0 (compatible; NpayBot/1.0)"}
        r = requests.get(BASE_URL, params=params, headers=headers, timeout=8)
        r.raise_for_status()
        data = r.json()
        if isinstance(data, dict) and data.get("result"):
            return float(data["result"])
    except Exception as e:
        print("❌ fetch_rate_api error:", e)
    return None

def get_rate(from_code: str):
    from_code = from_code.upper()
    cache = load_cache()
    key = f"{from_code}_IRR"
    now = int(time.time())

    if key in cache:
        entry = cache[key]
        age = now - entry.get("ts", 0)
        if age <= CACHE_TTL and entry.get("rate") is not None:
            return entry["rate"], True, age

    rate = fetch_rate_api(from_code, "IRR")
    if rate is not None:
        cache[key] = {"rate": rate, "ts": now}
        save_cache(cache)
        return rate, False, 0

    return None, False, None

# ---------------- منوها ----------------
@bot.message_handler(commands=['start'])
def start(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("💸 انتقال ارز"))
    bot.send_message(message.chat.id, "سلام 👋 به ربات نوسان‌پی خوش‌آمدید.\nبرای شروع «💸 انتقال ارز» را انتخاب کنید.", reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "💸 انتقال ارز")
def transfer_menu(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("🌍 از داخل به خارج"), types.KeyboardButton("🏦 از خارج به داخل"))
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
    bot.send_message(chat_id, f"نوع ارز مورد نظر برای انتقال را انتخاب کنید:", reply_markup=markup)

@bot.message_handler(func=lambda m: bool(re.match(r".*\([A-Z]{3}\)\s*$", m.text or "")))
def ask_amount(message):
    chat_id = message.chat.id
    match = re.search(r"\(([A-Z]{3})\)\s*$", message.text.strip())
    if not match:
        bot.reply_to(message, "فرمت صحیح نیست.")
        return
    code = match.group(1)
    pending[chat_id] = {"direction": pending.get(chat_id, {}).get("direction"), "currency": code, "awaiting": "amount"}
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("🔙 منوی اصلی"))
    bot.send_message(chat_id, f"شما ارز «{currencies[code]} ({code})» را انتخاب کردید.\nلطفاً مقدار را وارد کنید:", reply_markup=markup)

@bot.message_handler(func=lambda m: True)
def receive_amount(message):
    chat_id = message.chat.id
    text = (message.text or "").strip()

    if text in ["🔙 منوی اصلی", "/start"]:
        pending.pop(chat_id, None)
        return start(message)

    state = pending.get(chat_id)
    if state and state.get("awaiting") == "amount":
        try:
            amount = float(text.replace(",", "").replace(" ", ""))
            if amount <= 0:
                raise ValueError()
        except:
            bot.reply_to(message, "⚠️ لطفاً فقط عدد مثبت وارد کنید.")
            return

        code = state["currency"]
        rate, _, _ = get_rate(code)
        if rate is None:
            bot.send_message(chat_id, "❌ نرخ فعلاً در دسترس نیست.")
            return

        toman_per_unit = rate / 10
        total_toman = amount * toman_per_unit

        # ارسال به ادمین برای تأیید
        confirm_msg = (
            f"📩 درخواست جدید از کاربر {message.from_user.first_name or ''}\n\n"
            f"💱 ارز: {currencies[code]} ({code})\n"
            f"🔢 مقدار: {amount:,}\n"
            f"💰 معادل: {total_toman:,.0f} تومان\n\n"
            f"🆔 Chat ID: {chat_id}"
        )

        admin_markup = types.InlineKeyboardMarkup()
        admin_markup.add(
            types.InlineKeyboardButton("✅ تأیید", callback_data=f"approve_{chat_id}_{total_toman}"),
            types.InlineKeyboardButton("❌ رد", callback_data=f"reject_{chat_id}")
        )

        bot.send_message(ADMIN_ID, confirm_msg, reply_markup=admin_markup)
        bot.send_message(chat_id, "درخواست شما برای بررسی به ادمین ارسال شد ✅")
        pending.pop(chat_id, None)
        return

    bot.reply_to(message, "برای شروع، «💸 انتقال ارز» را انتخاب کنید.")

# ---------------- هندل پاسخ ادمین ----------------
@bot.callback_query_handler(func=lambda call: call.data.startswith("approve_") or call.data.startswith("reject_"))
def admin_response(call):
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "⛔ فقط ادمین می‌تواند پاسخ دهد.")
        return

    if call.data.startswith("approve_"):
        _, chat_id, total = call.data.split("_")
        bot.send_message(int(chat_id), f"✅ درخواست شما تایید شد.\nمبلغ نهایی: {total} تومان.\nلطفاً ادامه پرداخت را انجام دهید.")
        bot.edit_message_text("✅ درخواست تایید شد.", chat_id=call.message.chat.id, message_id=call.message.message_id)
    elif call.data.startswith("reject_"):
        _, chat_id = call.data.split("_")
        bot.send_message(int(chat_id), "❌ درخواست شما توسط ادمین رد شد.")
        bot.edit_message_text("❌ درخواست رد شد.", chat_id=call.message.chat.id, message_id=call.message.message_id)

# ---------------- اجرای ربات ----------------
if __name__ == "__main__":
    print("✅ ربات نوسان‌پی با polling در حال اجراست...")
    bot.infinity_polling(timeout=60, long_polling_timeout=30)
