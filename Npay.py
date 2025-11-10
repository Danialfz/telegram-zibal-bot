import os
import re
import telebot
from telebot import types

# ---------------- تنظیمات ----------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "1611406302"))  # آی‌دی ادمین
PAYMENT_LINK_TEMPLATE = "https://example.com/payment?amount={amount}"  # لینک پرداخت با مبلغ

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

# وضعیت‌های در حافظه
pending = {}              # pending[chat_id] = {...state...}
awaiting_info = set()     # کاربرانی که باید اطلاعات حساب بفرستند
awaiting_admin_fix = {}   # {user_id: "pending_check" یا "awaiting_reason"}
total_amounts = {}        # {user_id: مبلغ کل نهایی برای پرداخت}

# ---------------- منوها ----------------
def main_menu_markup():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("💸 انتقال ارز"))
    return markup

def back_to_main_markup():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("🔙 بازگشت به منوی اصلی"))
    return markup

# ---------------- /start ----------------
@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(
        message.chat.id,
        "سلام 👋 به ربات نوسان‌پی خوش‌آمدید.\nبرای شروع گزینه زیر را انتخاب کنید:",
        reply_markup=main_menu_markup()
    )

# ---------------- انتخاب نوع انتقال ----------------
@bot.message_handler(func=lambda m: m.text == "💸 انتقال ارز")
def transfer_menu(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(
        types.KeyboardButton("🌍 از داخل به خارج"),
        types.KeyboardButton("🏦 از خارج به داخل"),
        types.KeyboardButton("🔙 بازگشت به منوی اصلی")
    )
    bot.send_message(message.chat.id, "لطفاً نوع انتقال را انتخاب کنید:", reply_markup=markup)

# ---------------- نمایش ارزها ----------------
@bot.message_handler(func=lambda m: m.text in ["🌍 از داخل به خارج", "🏦 از خارج به داخل"])
def show_currencies(message):
    chat_id = message.chat.id
    direction = "متقاضی قصد واریز از داخل به خارج دارد" if "داخل به خارج" in message.text else "متقاضی قصد واریز از خارج به داخل دارد"
    pending[chat_id] = {"direction": direction, "currency": None, "awaiting": None}

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    for code, name in currencies.items():
        markup.add(types.KeyboardButton(f"{name} ({code})"))
    markup.add(types.KeyboardButton("🔙 بازگشت به منوی اصلی"))
    bot.send_message(chat_id, "نوع ارز مورد نظر را انتخاب کنید:", reply_markup=markup)

# ---------------- کاربر ارز را انتخاب می‌کند -> پرسش مقدار ----------------
@bot.message_handler(func=lambda m: bool(re.match(r".*\([A-Z]{3}\)\s*$", m.text or "")))
def ask_amount(message):
    chat_id = message.chat.id
    match = re.search(r"\(([A-Z]{3})\)\s*$", message.text.strip())
    if not match:
        return bot.reply_to(message, "فرمت ارز صحیح نیست. لطفاً مجدداً انتخاب کنید.")

    code = match.group(1)
    if code not in currencies:
        return bot.reply_to(message, "این ارز در فهرست نیست.")

    # ذخیره جهت و ارز و تعیین مرحله انتظار مقدار
    pending[chat_id] = {
        "direction": pending.get(chat_id, {}).get("direction", None),
        "currency": code,
        "awaiting": "amount"   # مرحله بعد: منتظر عدد مقدار
    }

    bot.send_message(chat_id,
        f"شما ارز «{currencies[code]} ({code})» را انتخاب کردید.\n"
        "لطفاً مقدار را وارد کنید (مثلاً 2500 یا 12.5):",
        reply_markup=back_to_main_markup()
    )

# ---------------- ارسال اطلاعات حساب به ادمین ----------------
@bot.message_handler(func=lambda m: True)
def main_handler(message):
    chat_id, text = message.chat.id, (message.text or "").strip()

    # بازگشت به منوی اصلی
    if text in ["🔙 بازگشت به منوی اصلی", "/start"]:
        pending.pop(chat_id, None)
        awaiting_info.discard(chat_id)
        awaiting_admin_fix.pop(chat_id, None)
        return start(message)

    # اگر کاربر در مرحله ارسال اطلاعات پس از تایید است
    if chat_id in awaiting_info:
        # جلوگیری از ارسال لینک و تگ
        if re.search(r"https?://|t\.me|@", text, re.IGNORECASE):
            try:
                bot.delete_message(chat_id, message.message_id)
            except:
                pass
            return bot.send_message(chat_id, "⚠️ فقط متن ساده ارسال کنید.")

        # ارسال اطلاعات به ادمین
        bot.send_message(ADMIN_ID, f"📦 اطلاعات حساب از کاربر {chat_id}:\n\n{text}")
        bot.send_message(chat_id, "✅ اطلاعات شما ارسال شد، منتظر بررسی ادمین باشید.")
        awaiting_info.remove(chat_id)
        awaiting_admin_fix[chat_id] = "pending_check"
        return

    # کاربر در مرحله‌ی وارد کردن مقدار است
    state = pending.get(chat_id)
    if state and state.get("awaiting") == "amount":
        try:
            amount = float(text.replace(",", "").replace(" ", ""))
        except:
            return bot.reply_to(message, "⚠️ لطفاً عدد معتبر وارد کنید.")
        pending[chat_id].update({"amount": amount, "awaiting": "waiting_rate"})
        bot.send_message(
            ADMIN_ID,
            f"📩 درخواست جدید از کاربر @{message.from_user.username or message.from_user.first_name}\n"
            f"📍 {state['direction']}\n💱 {currencies[state['currency']]} ({state['currency']})\n"
            f"📊 مقدار: {amount}\n🆔 {chat_id}\n\n📌 لطفاً نرخ هر واحد را به تومان وارد کنید."
        )
        return bot.send_message(chat_id, "✅ درخواست شما برای بررسی قیمت ارسال شد.")

    # ادمین نرخ می‌فرستد
    if chat_id == ADMIN_ID and re.match(r"^\d+(\.\d+)?$", text):
        rate = float(text)
        # پیدا کردن اولین درخواستِ waiting_rate (اولویت به ترتیب ورود در dict)
        target_user = None
        for uid, data in pending.items():
            if data.get("awaiting") == "waiting_rate":
                target_user = uid
                break

        if not target_user:
            return bot.send_message(ADMIN_ID, "⚠️ درخواستی در انتظار نرخ نیست.")
        data = pending[target_user]
        total = data["amount"] * rate
        total_amounts[target_user] = total
        data.update({"total": total, "awaiting": "confirm"})

        # برای کاربر دکمه‌های تأیید/لغو/بازگشت نشان بده
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add(types.KeyboardButton("✅ تایید"), types.KeyboardButton("❌ لغو"))
        markup.add(types.KeyboardButton("🔙 بازگشت به منوی اصلی"))
        bot.send_message(
            target_user,
            f"💰 مبلغ نهایی مشخص شد:\n\n"
            f"• مقدار: {data['amount']:,} {data['currency']}\n"
            f"• مبلغ کل پرداختی: {total:,.0f} تومان\n\n"
            "آیا تأیید می‌کنید؟",
            reply_markup=markup
        )

        bot.send_message(ADMIN_ID, f"✅ نرخ برای کاربر {target_user} ثبت شد.")
        return

    # تایید یا لغو توسط کاربر
    if state and state.get("awaiting") == "confirm":
        if text == "✅ تایید":
            pending.pop(chat_id, None)
            awaiting_info.add(chat_id)
            bot.send_message(chat_id, "✉️ لطفاً اطلاعات حساب را ارسال کنید.", reply_markup=back_to_main_markup())
            return
        if text == "❌ لغو":
            pending.pop(chat_id, None)
            return bot.send_message(chat_id, "❌ عملیات لغو شد.", reply_markup=main_menu_markup())

    # اصلاح اطلاعات توسط ادمین
    if chat_id == ADMIN_ID:
        m = re.match(r"^\s*تایید\s+(\d+)", text)
        if m:
            uid = int(m.group(1))
            if uid in awaiting_admin_fix:
                del awaiting_admin_fix[uid]
                amount = total_amounts.get(uid, 0)
                link = PAYMENT_LINK_TEMPLATE.format(amount=int(amount))
                bot.send_message(uid, f"✅ اطلاعات شما تایید شد.\n💳 پرداخت از طریق لینک زیر:\n{link}")
                bot.send_message(ADMIN_ID, f"لینک پرداخت برای {uid} ارسال شد.")
            return
        # اصلاح
        m2 = re.match(r"^\s*اصلاح\s+(\d+)", text)
        if m2:
            uid = int(m2.group(1))
            awaiting_admin_fix[uid] = "awaiting_reason"
            return bot.send_message(ADMIN_ID, f"✏️ لطفاً دلیل اصلاح برای کاربر {uid} را بنویسید:")

        # اگر در حال نوشتن دلیل اصلاح است
        if any(v == "awaiting_reason" for v in awaiting_admin_fix.values()):
            for uid, status in list(awaiting_admin_fix.items()):
                if status == "awaiting_reason":
                    bot.send_message(uid, f"⚠️ پیام از ادمین:\n{text}\n\nلطفاً اطلاعات اصلاح‌شده را ارسال کنید.")
                    awaiting_admin_fix[uid] = "pending_check"
                    return bot.send_message(ADMIN_ID, f"پیام اصلاح برای {uid} ارسال شد.")
    return

# ---------------- اجرای ربات ----------------
if __name__ == "__main__":
    print("✅ ربات نوسان‌پی در حال اجراست...")
    bot.infinity_polling(timeout=60, long_polling_timeout=30)
