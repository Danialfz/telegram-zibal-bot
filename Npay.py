import os
import telebot
from telebot import types
import requests

# ----------- تنظیمات -----------
BOT_TOKEN = os.getenv("BOT_TOKEN", "8589520464:AAE3x1LjHw0wWepIX6bJePQ_d0z9AXB-1t4")
MERCHANT = os.getenv("MERCHANT", "67fbd99f6f3803001057a0bf")

bot = telebot.TeleBot(BOT_TOKEN)

# ----------- حذف webhook برای جلوگیری از خطای 409 -----------
try:
    requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook")
except:
    pass

# ----------- ارزها (فقط نام و معادل فارسی) -----------
currencies = {
    "USD": "دلار آمریکا",
    "EUR": "یورو",
    "GBP": "پوند انگلیس",
    "CHF": "فرانک سوئیس",
    "CAD": "دلار کانادا",
    "AUD": "دلار استرالیا",
    "SEK": "کرون سوئد",
    "NOK": "کرون نروژ",
    "RUB": "روبل روسیه",
    "THB": "بات تایلند",
    "SGD": "دلار سنگاپور",
    "HKD": "دلار هنگ‌کنگ",
    "INR": "روپیه هند",
    "TRY": "لیر ترکیه",
    "CNY": "یوان چین",
    "SAR": "ریال سعودی"
}

# ----------- شروع ربات -----------
@bot.message_handler(commands=['start'])
def start(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(
        types.KeyboardButton("ثبت سایر سفارش‌ها"),
        types.KeyboardButton("آزمون‌ها"),
        types.KeyboardButton("هزینه اپلای"),
        types.KeyboardButton("انتقال ارز")
    )
    bot.send_message(message.chat.id,
                     "سلام 👋 به ربات نوسان‌پی خوش اومدی.\nلطفاً یکی از گزینه‌های زیر رو انتخاب کن:",
                     reply_markup=markup)

# ----------- بخش 1: ثبت سایر سفارش‌ها -----------
@bot.message_handler(func=lambda message: message.text == "ثبت سایر سفارش‌ها")
def others(message):
    markup = types.InlineKeyboardMarkup(row_width=2)
    buttons = [
        ("پرداخت با پی پال (Paypal)", "paypal"),
        ("خرید بلیط پرواز خارجی", "flight"),
        ("کنسل کردن/تغییر پرواز خارجی", "flight_change"),
        ("اکانت Grammarly Premium", "grammarly"),
        ("سایت مگوش (Magoosh)", "magoosh"),
        ("سایت زوم (Zoom.us)", "zoom"),
        ("اکانت تریدینگ ویو", "tradingview"),
        ("رزرو خانه در AirBnb", "airbnb"),
        ("رزرو هتل با Booking.com", "booking"),
        ("خرید اکانت کورسرا (Coursera)", "coursera"),
        ("خرید اکانت ChatGPT", "chatgpt"),
        ("خرید سرور و خدمات هتزنر", "hetzner"),
        ("پرداخت هزینه وکیل Wenzo", "wenzo"),
        ("پرداخت اشتراک Cursor", "cursor"),
        ("هزینه چاپ مقاله در ژورنال‌ها", "paper")
    ]
    for text, data in buttons:
        markup.add(types.InlineKeyboardButton(text, callback_data=data))
    bot.send_message(message.chat.id, "📦 لطفاً نوع سفارش خود را انتخاب کنید:", reply_markup=markup)

# ----------- بخش 2: آزمون‌ها -----------
@bot.message_handler(func=lambda message: message.text == "آزمون‌ها")
def exams(message):
    markup = types.InlineKeyboardMarkup(row_width=2)
    buttons = [
        ("سایر", "exam_other"),
        ("CFA", "cfa"),
        ("آیلتس (IELTS)", "ielts"),
        ("عضویت ACCA", "acca"),
        ("USMLE", "usmle"),
        ("PMP", "pmp"),
        ("IMAT", "imat"),
        ("TOLC", "tolc"),
        ("OET", "oet"),
        ("Prometric", "prometric"),
        ("GRE", "gre"),
        ("TOEFL", "toefl"),
        ("PTE", "pte"),
        ("GMAT", "gmat"),
        ("Duolingo", "duolingo")
    ]
    for text, data in buttons:
        markup.add(types.InlineKeyboardButton(text, callback_data=data))
    bot.send_message(message.chat.id, "🧾 لطفاً آزمون مورد نظر را انتخاب کنید:", reply_markup=markup)

# ----------- بخش 3: هزینه اپلای -----------
@bot.message_handler(func=lambda message: message.text == "هزینه اپلای")
def apply_costs(message):
    markup = types.InlineKeyboardMarkup(row_width=2)
    buttons = [
        ("اپلیکیشن فی دانشگاه", "app_fee"),
        ("اپلیکیشن فی سوئد", "app_fee_sweden"),
        ("دیپازیت فی دانشگاه", "deposit_fee"),
        ("پرداخت uni-assist آلمان", "uni_assist"),
        ("پست eShipGlobal", "eship"),
        ("اجاره خوابگاه", "dorm"),
        ("اپلیکیشن فی دانشگاه میلان", "milan_fee"),
        ("عضویت/تمدید IEEE", "ieee"),
        ("ارزیابی مدارک WES", "wes"),
        ("ارزیابی مهندسین استرالیا", "engineer_australia"),
        ("تمدید عضویت PMI", "pmi"),
        ("حق عضویت APEGS", "apegs"),
        ("ارزیابی مدارک پزشکی استرالیا (AMC)", "amc"),
        ("پرداخت اداره بهداشت دبی (DHA)", "dha")
    ]
    for text, data in buttons:
        markup.add(types.InlineKeyboardButton(text, callback_data=data))
    bot.send_message(message.chat.id, "🎓 لطفاً نوع هزینه اپلای را انتخاب کنید:", reply_markup=markup)

# ----------- بخش 4: انتقال ارز -----------
@bot.message_handler(func=lambda message: message.text == "انتقال ارز")
def transfer(message):
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("داخل به خارج", callback_data="transfer_out"),
        types.InlineKeyboardButton("خارج به داخل", callback_data="transfer_in")
    )
    bot.send_message(message.chat.id, "💱 لطفاً نوع انتقال ارز را انتخاب کنید:", reply_markup=markup)

# ----------- پاسخ به کلیک‌ها -----------
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    bot.answer_callback_query(call.id, f"✅ {call.data} انتخاب شد.")
    bot.send_message(call.message.chat.id, f"شما گزینه‌ی «{call.data}» را انتخاب کردید ✅")

# ----------- اجرای ربات -----------
if __name__ == "__main__":
    print("✅ ربات نوسان‌پی با polling در حال اجراست...")
    bot.infinity_polling(timeout=60, long_polling_timeout=30)
