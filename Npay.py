import os
import re
import telebot
from telebot import types

# ---------------- تنظیمات ----------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "1611406302"))  # آی‌دی ادمین
PAYMENT_LINK = "https://example.com/payment"  # لینک پرداخت آزمایشی

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
awaiting_info = set()     # کاربرانی که باید اطلاعات حساب بفرستند (پس از تایید)
awaiting_admin_fix = {}   # user_id -> "pending_check" (وقتی اطلاعات به ادمین فرستاده شد)

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
    # متن جهت دقیق (طبق خواسته‌ات)
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
        awaiting_admin_fix[chat_id] = "pending_check"
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
            return bot.reply_to(message, "⚠️ لطفاً عدد مثبت وارد کنید (مثلاً: 2500)")

        # ذخیره مقدار و ست کردن وضعیت به waiting_rate تا ادمین بدونه برای چه درخواستی باید نرخ بزنه
        pending[chat_id]["amount"] = amount
        pending[chat_id]["awaiting"] = "waiting_rate"

        # پیام به ادمین: درخواست جدید و درخواست نرخ واحد
        bot.send_message(
            ADMIN_ID,
            f"📩 درخواست جدید از کاربر @{message.from_user.username or message.from_user.first_name}\n"
            f"📍 {state.get('direction')}\n"
            f"💱 {currencies[state['currency']]} ({state['currency']})\n"
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

        bot.send_message(ADMIN_ID, f"✅ نرخ ({rate:,.0f}) ثبت و برای کاربر {target_user} ارسال شد.")
        return

    # --- کاربر تأیید یا لغو می‌کند (پس از دریافت مجموع) ---
    state = pending.get(chat_id)
    if state and state.get("awaiting") == "confirm":
        # تأیید
        if text == "✅ تایید":
            # آماده دریافت اطلاعات حساب
            pending.pop(chat_id, None)
            awaiting_info.add(chat_id)

            # پیام بسته به جهت انتقال (طبق خواسته‌ات)
            if "داخل به خارج" in state.get("direction", ""):
                bot.send_message(
                    chat_id,
                    "✅ تراکنش تأیید شد.\n\n"
                    "✉️ لطفاً اطلاعات حساب دریافت‌کننده (خارجی) را به صورت متن ارسال کنید:\n"
                    "(نام و نام خانوادگی دریافت‌کننده / کشور / نام بانک / شماره حساب یا IBAN)",
                    reply_markup=back_to_main_markup()
                )
            else:
                bot.send_message(
                    chat_id,
                    "✅ تراکنش تأیید شد.\n\n"
                    "✉️ لطفاً اطلاعات حساب (برای واریز داخلی) را به صورت متن ارسال کنید:\n"
                    "(شماره حساب / شماره کارت / شماره شبا / نام و نام خانوادگی دریافت‌کننده / نام و نام خانوادگی واریزکننده)",
                    reply_markup=back_to_main_markup()
                )
            return

        # لغو
        if text == "❌ لغو":
            pending.pop(chat_id, None)
            bot.send_message(chat_id, "❌ روند انتقال ارز شما لغو شد.", reply_markup=main_menu_markup())
            return

        # هر ورودی دیگر را تذکر بده
        return bot.send_message(chat_id, "لطفاً یکی از دکمه‌ها را انتخاب کنید: «✅ تایید» یا «❌ لغو».")

    # --- ادمین: تایید یا اصلاح پیام اطلاعات کاربر (وقتی اطلاعات به ادمین رسیده) ---
    if chat_id == ADMIN_ID:
        # فرمت پیشنهادی: "تایید <user_id>" یا "اصلاح <user_id> <متن_اصلاح>"
        # تایید
        m = re.match(r"^\s*تایید\s+(\d+)\s*$", text, re.IGNORECASE)
        if m:
            uid = int(m.group(1))
            if uid in awaiting_admin_fix:
                del awaiting_admin_fix[uid]
                bot.send_message(uid, f"✅ اطلاعات شما تایید شد.\n\n💳 لطفاً از طریق لینک زیر پرداخت را انجام دهید:\n{PAYMENT_LINK}")
                bot.send_message(ADMIN_ID, f"✅ لینک پرداخت برای کاربر {uid} ارسال شد.")
            else:
                bot.send_message(ADMIN_ID, "⚠️ برای این کاربر اطلاعاتی در انتظار بررسی وجود ندارد.")
            return

        # اصلاح
        m2 = re.match(r"^\s*اصلاح\s+(\d+)\s+(.*)$", text, re.IGNORECASE)
        if m2:
            uid = int(m2.group(1))
            fix_msg = m2.group(2).strip()
            if uid in awaiting_admin_fix:
                # ارسال پیام اصلاح به کاربر؛ سپس او دوباره اطلاعات ارسال کند
                bot.send_message(uid, f"⚠️ پیام از ادمین (نیاز به اصلاح):\n\n{fix_msg}\n\nلطفاً اطلاعات اصلاح‌شده را ارسال کنید.")
                del awaiting_admin_fix[uid]
                bot.send_message(ADMIN_ID, f"✅ پیام اصلاح برای کاربر {uid} ارسال شد.")
            else:
                bot.send_message(ADMIN_ID, "⚠️ برای این کاربر اطلاعاتی در انتظار بررسی وجود ندارد.")
            return

    # --- اگر هیچ شرطی برقرار نبود، پیام راهنما بفرست ---
    bot.send_message(chat_id, "برای شروع، گزینه «💸 انتقال ارز» را انتخاب کنید.", reply_markup=main_menu_markup())

# ---------------- اجرای ربات ----------------
if __name__ == "__main__":
    print("✅ ربات نوسان‌پی در حال اجراست...")
    bot.infinity_polling(timeout=60, long_polling_timeout=30)
