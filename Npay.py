import os
import telebot
from telebot import types

# ----------- تنظیمات -----------
BOT_TOKEN = os.getenv("BOT_TOKEN")
MERCHANT = os.getenv("MERCHANT")

bot = telebot.TeleBot(BOT_TOKEN)

# ----------- منوی اصلی فقط با گزینه انتقال ارز -----------
@bot.message_handler(commands=['start'])
def start(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    transfer_btn = types.KeyboardButton("💸 انتقال ارز")
    markup.add(transfer_btn)
    bot.send_message(
        message.chat.id,
        "سلام 👋 به ربات نوسان‌پی خوش اومدی.\nلطفاً یکی از گزینه‌های زیر رو انتخاب کن:",
        reply_markup=markup
    )

# ----------- منوی انتقال ارز -----------
@bot.message_handler(func=lambda message: message.text == "💸 انتقال ارز")
def transfer_menu(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    out_btn = types.KeyboardButton("🌍 از داخل به خارج")
    in_btn = types.KeyboardButton("🏦 از خارج به داخل")
    back_btn = types.KeyboardButton("🔙 منوی اصلی")
    markup.add(out_btn, in_btn, back_btn)
    bot.send_message(message.chat.id, "نوع انتقال را انتخاب کنید:", reply_markup=markup)

# ----------- منوی ارزها -----------
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

@bot.message_handler(func=lambda message: message.text in ["🌍 از داخل به خارج", "🏦 از خارج به داخل"])
def choose_currency(message):
    direction = "خارج" if "خارج" in message.text else "داخل"
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    for code, name in currencies.items():
        markup.add(types.KeyboardButton(f"{name} ({code})"))
    markup.add(types.KeyboardButton("🔙 بازگشت"))
    bot.send_message(
        message.chat.id,
        f"ارزی که می‌خواهید به {direction} منتقل کنید را انتخاب کنید:",
        reply_markup=markup
    )

# ----------- بازگشت به منوی اصلی -----------
@bot.message_handler(func=lambda message: message.text in ["🔙 بازگشت", "🔙 منوی اصلی"])
def back_to_main(message):
    start(message)

# ----------- اجرای ربات -----------
if __name__ == "__main__":
    print("✅ ربات نوسان‌پی با polling در حال اجراست (بخش انتقال ارز فعال است)...")
    bot.infinity_polling(timeout=60, long_polling_timeout=30)
