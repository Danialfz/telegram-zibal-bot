import os
import re
import telebot
from telebot import types

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "1611406302"))
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

# ---------------- اطلاعات حساب متناسب با نوع ارز ----------------
currency_info_template = {
    "USD": "نام و نام خانوادگی دریافت‌کننده / نام بانک / شماره حساب / SWIFT Code",
    "EUR": "نام و نام خانوادگی دریافت‌کننده / کشور / نام بانک / شماره حساب یا IBAN",
    "GBP": "نام و نام خانوادگی دریافت‌کننده / شماره حساب / Sort Code / نام بانک",
    "CHF": "نام و نام خانوادگی دریافت‌کننده / نام بانک / شماره حساب یا IBAN / SWIFT",
    "CAD": "نام و نام خانوادگی دریافت‌کننده / نام بانک / شماره حساب / Transit Number / SWIFT",
    "AUD": "نام و نام خانوادگی دریافت‌کننده / نام بانک / BSB Code / شماره حساب",
    "AED": "نام و نام خانوادگی دریافت‌کننده / نام بانک / شماره حساب یا IBAN (AE...) / SWIFT",
    "TRY": "نام و نام خانوادگی دریافت‌کننده / نام بانک / شماره IBAN (TR...)",
    "CNY": "نام و نام خانوادگی دریافت‌کننده / نام بانک / شماره حساب / SWIFT Code / نام شهر",
    "INR": "نام و نام خانوادگی دریافت‌کننده / نام بانک / IFSC Code / شماره حساب",
    "JPY": "نام و نام خانوادگی دریافت‌کننده / نام بانک / شماره حساب / SWIFT / Branch Name",
    "SAR": "نام و نام خانوادگی دریافت‌کننده / نام بانک / شماره IBAN (SA...) / SWIFT",
    "KWD": "نام و نام خانوادگی دریافت‌کننده / نام بانک / شماره حساب / IBAN (KW...)",
    "OMR": "نام و نام خانوادگی دریافت‌کننده / نام بانک / شماره حساب / SWIFT / IBAN (OM...)",
    "QAR": "نام و نام خانوادگی دریافت‌کننده / نام بانک / شماره IBAN (QA...) / SWIFT"
}

# ---------------- وضعیت‌های در حافظه ----------------
pending = {}
awaiting_info = set()

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
    markup.add(
        types.KeyboardButton("🇺🇸 آمریکا"),
        types.KeyboardButton("🇪🇺 اروپا"),
        types.KeyboardButton("🇬🇧 انگلیس"),
        types.KeyboardButton("🇹🇷 ترکیه"),
        types.KeyboardButton("🔙 بازگشت به منوی اصلی")
    )
    return markup

# ---------------- /start ----------------
@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(
        message.chat.id,
        "سلام 👋 به ربات نوسان‌پی خوش‌آمدید.\nبرای شروع گزینه زیر را انتخاب کنید:",
        reply_markup=main_menu_markup()
    )

# ---------------- انتخاب ارز ----------------
@bot.message_handler(func=lambda m: m.text == "💸 انتقال ارز")
def show_currencies(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    for code, name in currencies.items():
        markup.add(types.KeyboardButton(f"{name} ({code})"))
    markup.add(types.KeyboardButton("🔙 بازگشت به منوی اصلی"))
    bot.send_message(message.chat.id, "لطفاً ارز مورد نظر را انتخاب کنید:", reply_markup=markup)

# ---------------- انتخاب ارز و ورود مقدار ----------------
@bot.message_handler(func=lambda m: bool(re.match(r".*\([A-Z]{3}\)\s*$", m.text or "")))
def ask_amount(message):
    chat_id = message.chat.id
    match = re.search(r"\(([A-Z]{3})\)\s*$", message.text.strip())
    if not match:
        return bot.reply_to(message, "فرمت ارز صحیح نیست.")
    code = match.group(1)
    if code not in currencies:
        return bot.reply_to(message, "این ارز در فهرست نیست.")

    pending[chat_id] = {"currency": code, "awaiting": "amount"}

    bot.send_message(chat_id,
        f"شما ارز {currencies[code]} را انتخاب کردید.\n"
        "لطفاً مقدار را وارد کنید (مثلاً 1500):",
        reply_markup=back_to_main_markup()
    )

# ---------------- همه پیام‌ها (منطق اصلی) ----------------
@bot.message_handler(func=lambda m: True)
def main_handler(message):
    chat_id = message.chat.id
    text = (message.text or "").strip()

    # --- بازگشت به منوی اصلی ---
    if text in ["🔙 بازگشت به منوی اصلی", "/start"]:
        pending.pop(chat_id, None)
        awaiting_info.discard(chat_id)
        return start(message)

    # --- اگر کاربر در مرحله ارسال اطلاعات پس از تایید است ---
    if chat_id in awaiting_info:
        # از ارسال لینک و تگ جلوگیری کن
        if re.search(r"https?://|t\.me|@", text, re.IGNORECASE):
            try:
                bot.delete_message(chat_id, message.message_id)
            except:
                pass
            return bot.send_message(chat_id, "⚠️ لطفاً فقط متن ساده ارسال کنید (بدون لینک یا تگ).")

        # ارسال اطلاعات به ادمین و علامت‌گذاری برای انتظار بررسی
        bot.send_message(ADMIN_ID, f"📦 اطلاعات حساب از کاربر {chat_id}:\n\n{text}")
        bot.send_message(chat_id, "✅ اطلاعات شما ارسال شد، منتظر بررسی ادمین باشید.")
        awaiting_info.remove(chat_id)
        return

    # --- اگر کاربر در مرحله وارد کردن مقدار است ---
    state = pending.get(chat_id)
    if state and state.get("awaiting") == "amount":
        normalized = text.replace(",", "").replace(" ", "")
        try:
            amount = float(normalized)
            if amount <= 0:
                raise ValueError()
        except Exception:
            return bot.reply_to(message, "⚠️ لطفاً عدد مثبت وارد کنید (مثلاً 2500)")

        # ذخیره مقدار و ست کردن وضعیت به waiting_rate تا ادمین بدونه برای چه درخواستی باید نرخ بزنه
        pending[chat_id]["amount"] = amount
        pending[chat_id]["awaiting"] = "waiting_rate"

        # پیام به ادمین: درخواست جدید و درخواست نرخ واحد
        bot.send_message(
            ADMIN_ID,
            f"📩 درخواست جدید از کاربر @{message.from_user.username or message.from_user.first_name}\n"
            f"💱 ارز: {currencies[state['currency']]} ({state['currency']})\n"
            f"📊 مقدار: {amount:,}\n"
            f"🆔 Chat ID: {chat_id}\n\n"
            "📌 لطفاً نرخ هر واحد را به تومان وارد کنید (فقط عدد)."
        )

        bot.send_message(chat_id, "✅ درخواست شما برای بررسی قیمت ارسال شد. لطفاً منتظر پاسخ ادمین باشید.", reply_markup=main_menu_markup())
        return

    # --- بخش نرخ‌گذاری ادمین: فقط وقتی ادمین به صورت عددی نرخ را می‌فرستد ---
    if chat_id == ADMIN_ID and re.match(r"^\d+(\.\d+)?$", text):
        rate = float(text)
        # پیدا کردن اولین درخواستِ waiting_rate (اولویت به ترتیب ورود در dict)
        target_user = None
        for uid, data in pending.items():
            if data.get("awaiting") == "waiting_rate":
                target_user = uid
                break

        if not target_user:
            return bot.send_message(ADMIN_ID, "⚠️ در حال حاضر هیچ درخواستی در انتظار نرخ وجود ندارد.")

        data = pending[target_user]
        total = data["amount"] * rate
        data["total"] = total
        data["awaiting"] = "confirm"

        # برای کاربر دکمه‌های تأیید/لغو/بازگشت نشان بده
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add(types.KeyboardButton("✅ تایید"), types.KeyboardButton("❌ لغو"))
        markup.add(types.KeyboardButton("🔙 بازگشت به منوی اصلی"))

        # ارسال فقط مجموع به کاربر (مطابق خواسته‌ات)
        bot.send_message(
            target_user,
            f"💰 مبلغ نهایی مشخص شد:\n\n"
            f"• مقدار: {data['amount']:,} {data['currency']}\n"
            f"• مبلغ کل پرداختی: {total:,.0f} تومان\n\n"
            "آیا تأیید می‌کنید؟",
            reply_markup=markup
        )

        bot.send_message(ADMIN_ID, f"✅ نرخ برای کاربر {target_user} ارسال شد.")
        return

    # --- کاربر تأیید یا لغو می‌کند (پس از دریافت مجموع) ---
    state = pending.get(chat_id)
    if state and state.get("awaiting") == "confirm":
        if text == "✅ تایید":
            # آماده دریافت اطلاعات حساب
            pending.pop(chat_id, None)
            awaiting_info.add(chat_id)

            # بسته به کشور ارز، اطلاعات را درخواست می‌کنیم
            if "USD" in state.get("currency"):
                bot.send_message(
                    chat_id,
                    "✅ تراکنش تأیید شد.\n\n"
                    "✉️ لطفاً اطلاعات حساب دریافت‌کننده (خارجی) را به صورت متن ارسال کنید:\n"
                    "(نام و نام خانوادگی دریافت‌کننده / کشور / نام بانک / شماره حساب یا SWIFT Code)",
                    reply_markup=back_to_main_markup()
                )
            elif "EUR" in state.get("currency"):
                bot.send_message(
                    chat_id,
                    "✅ تراکنش تأیید شد.\n\n"
                    "✉️ لطفاً اطلاعات حساب دریافت‌کننده (خارجی) را به صورت متن ارسال کنید:\n"
                    "(نام و نام خانوادگی دریافت‌کننده / کشور / نام بانک / شماره حساب یا IBAN)",
                    reply_markup=back_to_main_markup()
                )
            # می‌توانید اینطور ادامه بدید تا برای هر کشور اطلاعات متفاوت رو درخواست کنید.

            return

        # لغو
        if text == "❌ لغو":
            pending.pop(chat_id, None)
            bot.send_message(chat_id, "❌ روند انتقال ارز شما لغو شد.", reply_markup=main_menu_markup())
            return

        # هر ورودی دیگر را تذکر بده
        return bot.send_message(chat_id, "لطفاً یکی از دکمه‌ها را انتخاب کنید: «✅ تایید» یا «❌ لغو».")
    
    bot.send_message(chat_id, "برای شروع، گزینه «💸 انتقال ارز» را انتخاب کنید.", reply_markup=main_menu_markup())

# ---------------- اجرای ربات ----------------
if __name__ == "__main__":
    print("✅ Bot Running...")
    bot.infinity_polling(timeout=60, long_polling_timeout=30)
