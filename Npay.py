import os
import telebot
from telebot import types

# ----------- تنظیمات -----------
BOT_TOKEN = os.getenv("BOT_TOKEN", "8589520464:AAE3x1LjHw0wWepIX6bJePQ_d0z9AXB-1t4")
MERCHANT = os.getenv("MERCHANT", "67fbd99f6f3803001057a0bf")

bot = telebot.TeleBot(BOT_TOKEN)

# ----------- حذف webhook در شروع (خیلی مهم برای رفع خطای 409) -----------
try:
    requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook")
    print("✅ Webhook حذف شد تا polling بدون خطا اجرا شود.")
except Exception as e:
    print(f"⚠️ خطا در حذف webhook: {e}")

# ----------- ارزها و معادل فارسی ----------- 
currencies = {
    "USD": {"currency": "US Dollar", "persian": "دلار آمریکا"},
    "EUR": {"currency": "Euro", "persian": "یورو"},
    "GBP": {"currency": "British Pound", "persian": "پوند انگلیس"},
    "CHF": {"currency": "Swiss Franc", "persian": "فرانک سوئیس"},
    "CAD": {"currency": "Canadian Dollar", "persian": "دلار کانادا"},
    "AUD": {"currency": "Australian Dollar", "persian": "دلار استرالیا"},
    "SEK": {"currency": "Swedish Krona", "persian": "کرون سوئدی"},
    "NOK": {"currency": "Norwegian Krone", "persian": "کرون نروژی"},
    "RUB": {"currency": "Russian Ruble", "persian": "روبل روسیه"},
    "THB": {"currency": "Thai Baht", "persian": "بات تایلند"},
    "SGD": {"currency": "Singapore Dollar", "persian": "دلار سنگاپور"},
    "HKD": {"currency": "Hong Kong Dollar", "persian": "دلار هنگ کنگ"},
    "INR": {"currency": "Indian Rupee", "persian": "روپیه هند"},
    "TRY": {"currency": "Turkish Lira", "persian": "لیر ترکیه"},
    "CNY": {"currency": "Chinese Yuan", "persian": "یوان چین"},
    "SAR": {"currency": "Saudi Riyal", "persian": "ریال سعودی"}
}

# ----------- دستورات ربات -----------
@bot.message_handler(commands=['start'])
def start(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    
    # دکمه‌ها
    item1 = types.KeyboardButton("ثبت سایر سفارش‌ها")
    item2 = types.KeyboardButton("آزمون‌ها")
    item3 = types.KeyboardButton("هزینه اپلای")
    item4 = types.KeyboardButton("انتقال ارز")
    
    markup.add(item1, item2, item3, item4)
    
    bot.send_message(message.chat.id, "سلام 👋 به ربات نوسان‌پی خوش اومدی.\n"
                                      "لطفاً گزینه مورد نظر رو انتخاب کن:", reply_markup=markup)

# ----------- ثبت سایر سفارش‌ها ----------- 
@bot.message_handler(func=lambda message: message.text == "ثبت سایر سفارش‌ها")
def show_orders(message):
    markup = types.InlineKeyboardMarkup(row_width=2)
    
    item1 = types.InlineKeyboardButton("پرداخت با پی پال", callback_data="paypal")
    item2 = types.InlineKeyboardButton("خرید بلیط پرواز خارجی", callback_data="flight_ticket")
    item3 = types.InlineKeyboardButton("اکانت Grammarly Premium", callback_data="grammarly")
    item4 = types.InlineKeyboardButton("رزرو خانه در AirBnb", callback_data="airbnb")
    item5 = types.InlineKeyboardButton("خرید اکانت تریدینگ ویو", callback_data="trading_view")
    item6 = types.InlineKeyboardButton("رزرو هتل با Booking.com", callback_data="booking")
    
    markup.add(item1, item2, item3, item4, item5, item6)
    
    bot.send_message(message.chat.id, "لطفاً نوع سفارش خود را انتخاب کنید:", reply_markup=markup)

# ----------- آزمون‌ها ----------- 
@bot.message_handler(func=lambda message: message.text == "آزمون‌ها")
def show_exams(message):
    markup = types.InlineKeyboardMarkup(row_width=2)
    
    item1 = types.InlineKeyboardButton("ثبت نام CFA", callback_data="cfa")
    item2 = types.InlineKeyboardButton("ثبت نام آیلتس (IELTS)", callback_data="ielts")
    item3 = types.InlineKeyboardButton("ثبت نام USMLE", callback_data="usmle")
    item4 = types.InlineKeyboardButton("ثبت نام GRE", callback_data="gre")
    
    markup.add(item1, item2, item3, item4)
    
    bot.send_message(message.chat.id, "لطفاً نوع آزمون مورد نظر رو انتخاب کن:", reply_markup=markup)

# ----------- هزینه اپلای ----------- 
@bot.message_handler(func=lambda message: message.text == "هزینه اپلای")
def show_apply_fees(message):
    markup = types.InlineKeyboardMarkup(row_width=2)
    
    item1 = types.InlineKeyboardButton("اپلیکیشن فی دانشگاه", callback_data="university_fee")
    item2 = types.InlineKeyboardButton("پرداخت uni-assist آلمان", callback_data="uni_assist")
    item3 = types.InlineKeyboardButton("دیپازیت فی دانشگاه", callback_data="deposit_fee")
    
    markup.add(item1, item2, item3)
    
    bot.send_message(message.chat.id, "لطفاً نوع هزینه اپلای را انتخاب کنید:", reply_markup=markup)

# ----------- انتقال ارز ----------- 
@bot.message_handler(func=lambda message: message.text == "انتقال ارز")
def show_currency_transfer(message):
    markup = types.InlineKeyboardMarkup(row_width=2)
    
    item1 = types.InlineKeyboardButton("انتقال از داخل به خارج", callback_data="transfer_in_out")
    item2 = types.InlineKeyboardButton("انتقال از خارج به داخل", callback_data="transfer_out_in")
    
    markup.add(item1, item2)
    
    bot.send_message(message.chat.id, "لطفاً نوع انتقال ارز را انتخاب کنید:", reply_markup=markup)

# ----------- پیاده‌سازی callback ها -----------

# زمانی که کاربر گزینه‌ای رو انتخاب کرد
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    if call.data == "paypal":
        bot.answer_callback_query(call.id, "پرداخت با پی پال انتخاب شد.")
    elif call.data == "flight_ticket":
        bot.answer_callback_query(call.id, "خرید بلیط پرواز خارجی انتخاب شد.")
    elif call.data == "grammarly":
        bot.answer_callback_query(call.id, "اکانت Grammarly Premium انتخاب شد.")
    elif call.data == "airbnb":
        bot.answer_callback_query(call.id, "رزرو خانه در AirBnb انتخاب شد.")
    elif call.data == "trading_view":
        bot.answer_callback_query(call.id, "خرید اکانت تریدینگ ویو انتخاب شد.")
    elif call.data == "booking":
        bot.answer_callback_query(call.id, "رزرو هتل با Booking.com انتخاب شد.")
    elif call.data == "cfa":
        bot.answer_callback_query(call.id, "ثبت نام CFA انتخاب شد.")
    elif call.data == "ielts":
        bot.answer_callback_query(call.id, "ثبت نام آیلتس (IELTS) انتخاب شد.")
    elif call.data == "usmle":
        bot.answer_callback_query(call.id, "ثبت نام USMLE انتخاب شد.")
    elif call.data == "gre":
        bot.answer_callback_query(call.id, "ثبت نام GRE انتخاب شد.")
    elif call.data == "university_fee":
        bot.answer_callback_query(call.id, "پرداخت اپلیکیشن فی دانشگاه انتخاب شد.")
    elif call.data == "uni_assist":
        bot.answer_callback_query(call.id, "پرداخت uni-assist آلمان انتخاب شد.")
    elif call.data == "deposit_fee":
        bot.answer_callback_query(call.id, "دیپازیت فی دانشگاه انتخاب شد.")
    elif call.data == "transfer_in_out":
        bot.answer_callback_query(call.id, "انتقال از داخل به خارج انتخاب شد.")
    elif call.data == "transfer_out_in":
        bot.answer_callback_query(call.id, "انتقال از خارج به داخل انتخاب شد.")

# ----------- اجرای ربات -----------
if __name__ == "__main__":
    print("✅ ربات نوسان‌پی با polling در حال اجراست...")
    bot.infinity_polling(timeout=60, long_polling_timeout=30)
