import os
import re
import telebot
from telebot import types

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "1611406302"))
bot = telebot.TeleBot(BOT_TOKEN)

currencies = {
    "USD": "دلار آمریکا 🇺🇸",
    "EUR": "یورو 🇪🇺",
    "GBP": "پوند انگلیس 🇬🇧",
    "AED": "درهم امارات 🇦🇪",
}

pending = {}
awaiting_info = set()
awaiting_admin_fix = {}
PAYMENT_LINK = "https://example.com/payment"

def main_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("💸 انتقال ارز"))
    return markup

def back_button():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("🔙 بازگشت به منوی اصلی"))
    return markup

@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(message.chat.id, "سلام 👋 خوش اومدی! لطفاً از منوی زیر استفاده کن:", reply_markup=main_menu())

@bot.message_handler(func=lambda m: m.text == "💸 انتقال ارز")
def transfer_menu(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(
        types.KeyboardButton("🌍 از داخل به خارج"),
        types.KeyboardButton("🏦 از خارج به داخل"),
        types.KeyboardButton("🔙 بازگشت به منوی اصلی")
    )
    bot.send_message(message.chat.id, "نوع انتقال رو انتخاب کن:", reply_markup=markup)

@bot.message_handler(func=lambda m: m.text in ["🌍 از داخل به خارج", "🏦 از خارج به داخل"])
def choose_currency(message):
    direction = "داخل به خارج" if "داخل به خارج" in message.text else "خارج به داخل"
    pending[message.chat.id] = {"direction": direction, "awaiting": "currency"}
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    for code, name in currencies.items():
        markup.add(types.KeyboardButton(f"{name} ({code})"))
    markup.add(types.KeyboardButton("🔙 بازگشت به منوی اصلی"))
    bot.send_message(message.chat.id, "ارز مورد نظر رو انتخاب کن:", reply_markup=markup)

@bot.message_handler(func=lambda m: re.search(r"\([A-Z]{3}\)", m.text or ""))
def ask_amount(message):
    chat_id = message.chat.id
    code = re.search(r"\(([A-Z]{3})\)", message.text).group(1)
    if code not in currencies:
        return bot.reply_to(message, "ارز انتخابی نامعتبره.")
    pending[chat_id]["currency"] = code
    pending[chat_id]["awaiting"] = "amount"
    bot.send_message(chat_id, f"چه مقدار {currencies[code]} نیاز داری؟ (مثلاً 2000)", reply_markup=back_button())

@bot.message_handler(func=lambda m: True)
def all_messages(message):
    chat_id = message.chat.id
    text = (message.text or "").strip()

    # بازگشت
    if text in ["🔙 بازگشت به منوی اصلی", "/start"]:
        pending.pop(chat_id, None)
        awaiting_info.discard(chat_id)
        return start(message)

    # اگر کاربر داره مقدار می‌فرسته
    if chat_id in pending and pending[chat_id].get("awaiting") == "amount":
        try:
            amount = float(text.replace(",", "").replace(" ", ""))
        except:
            return bot.reply_to(message, "لطفاً عدد معتبر وارد کن.")
        pending[chat_id]["amount"] = amount
        pending[chat_id]["awaiting"] = "waiting_rate"

        bot.send_message(
            ADMIN_ID,
            f"📩 درخواست جدید:\n"
            f"🧾 جهت: {pending[chat_id]['direction']}\n"
            f"💱 ارز: {pending[chat_id]['currency']}\n"
            f"📊 مقدار: {amount}\n"
            f"🆔 کاربر: {chat_id}\n\n"
            "📌 لطفاً نرخ هر واحد را وارد کنید (عدد به تومان):"
        )
        bot.send_message(chat_id, "✅ درخواستت ارسال شد، منتظر تعیین نرخ از سوی ادمین باش.", reply_markup=main_menu())
        return

    # اگر ادمین نرخ وارد کنه
    if chat_id == ADMIN_ID and re.match(r"^\d+(\.\d+)?$", text):
        rate = float(text)
        # پیدا کردن کاربر در حالت انتظار نرخ
        user_id = None
        for uid, data in pending.items():
            if data.get("awaiting") == "waiting_rate":
                user_id = uid
                break

        if not user_id:
            return bot.send_message(ADMIN_ID, "⚠️ در حال حاضر کاربری در انتظار نرخ نیست.")

        data = pending[user_id]
        total = data["amount"] * rate
        data["total"] = total
        data["awaiting"] = "confirm"

        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add("✅ تایید", "❌ لغو", "🔙 بازگشت به منوی اصلی")

        bot.send_message(
            user_id,
            f"💰 مبلغ نهایی مشخص شد:\n\n"
            f"• مقدار: {data['amount']:,} {data['currency']}\n"
            f"• نرخ واحد: {rate:,.0f} تومان\n"
            f"• مبلغ کل پرداختی: {total:,.0f} تومان\n\n"
            "آیا تایید می‌کنید؟",
            reply_markup=markup
        )
        bot.send_message(ADMIN_ID, f"✅ نرخ {rate:,} ثبت و برای کاربر {user_id} ارسال شد.")
        return

    # اگر کاربر تایید یا لغو کنه
    if chat_id in pending and pending[chat_id].get("awaiting") == "confirm":
        if text == "✅ تایید":
            direction = pending[chat_id]['direction']
            pending.pop(chat_id, None)
            awaiting_info.add(chat_id)

            if direction == "داخل به خارج":
                bot.send_message(
                    chat_id,
                    "لطفاً اطلاعات حساب دریافت‌کننده در خارج از کشور را ارسال کنید:\n"
                    "🔹 نام و نام خانوادگی\n🔹 کشور / بانک / شماره حساب یا IBAN",
                    reply_markup=back_button()
                )
            else:
                bot.send_message(
                    chat_id,
                    "لطفاً اطلاعات حساب داخلی را ارسال کنید:\n"
                    "🔹 شماره حساب\n🔹 شماره کارت\n🔹 شماره شبا\n🔹 نام و نام خانوادگی دریافت‌کننده\n🔹 نام و نام خانوادگی واریزکننده",
                    reply_markup=back_button()
                )
            return

        elif text == "❌ لغو":
            pending.pop(chat_id, None)
            bot.send_message(chat_id, "❌ درخواست لغو شد.", reply_markup=main_menu())
            return

    # دریافت اطلاعات حساب بعد از تایید
    if chat_id in awaiting_info:
        bot.send_message(ADMIN_ID, f"📦 اطلاعات حساب از کاربر {chat_id}:\n{text}")
        awaiting_info.remove(chat_id)
        awaiting_admin_fix[chat_id] = "pending"
        bot.send_message(chat_id, "✅ اطلاعاتت ارسال شد، منتظر تایید ادمین باش.")
        return

    # ادمین تایید یا اصلاح کند
    if chat_id == ADMIN_ID:
        if text.startswith("تایید "):
            uid = int(text.split()[1])
            if uid in awaiting_admin_fix:
                bot.send_message(uid, f"✅ اطلاعات شما تایید شد.\n💳 لینک پرداخت:\n{PAYMENT_LINK}")
                del awaiting_admin_fix[uid]
                bot.send_message(ADMIN_ID, f"✅ لینک پرداخت برای {uid} ارسال شد.")
            return

        elif text.startswith("اصلاح "):
            m = re.match(r"اصلاح\s+(\d+)\s*(.*)", text)
            if m:
                uid = int(m.group(1))
                fix_msg = m.group(2)
                if uid in awaiting_admin_fix:
                    bot.send_message(uid, f"⚠️ لطفاً اطلاعات زیر را اصلاح کنید:\n{fix_msg}")
                    del awaiting_admin_fix[uid]
                    bot.send_message(ADMIN_ID, "✅ پیام اصلاح ارسال شد.")
            return

    bot.send_message(chat_id, "برای شروع از منوی اصلی گزینه «💸 انتقال ارز» را انتخاب کنید.", reply_markup=main_menu())

print("✅ Bot running...")
bot.infinity_polling()
