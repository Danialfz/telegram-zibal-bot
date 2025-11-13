import os
import re
import threading
import requests
import telebot
from telebot import types
from flask import Flask, request, jsonify, redirect

# ---------------- تنظیمات اصلی ----------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN env var is required")

try:
    ADMIN_ID = int(os.getenv("ADMIN_ID", "1611406302"))
except Exception:
    raise RuntimeError("ADMIN_ID must be integer")

MERCHANT = os.getenv("MERCHANT")
RAILWAY_DOMAIN = os.getenv("RAILWAY_DOMAIN")

if not MERCHANT:
    raise RuntimeError("MERCHANT env var is required")
if not RAILWAY_DOMAIN:
    raise RuntimeError("RAILWAY_DOMAIN env var is required (e.g. bot.navasanpay.com)")

bot = telebot.TeleBot(BOT_TOKEN)
try:
    bot.remove_webhook()
except Exception:
    pass

app = Flask(__name__)

# ---------------- داده‌ها ----------------
currencies = {
    "USD": "دلار آمریکا 🇺🇸", "EUR": "یورو 🇪🇺", "GBP": "پوند انگلیس 🇬🇧",
    "CHF": "فرانک سوئیس 🇨🇭", "CAD": "دلار کانادا 🇨🇦", "AUD": "دلار استرالیا 🇦🇺",
    "AED": "درهم امارات 🇦🇪", "TRY": "لیر ترکیه 🇹🇷", "CNY": "یوان چین 🇨🇳",
    "INR": "روپیه هند 🇮🇳", "JPY": "ین ژاپن 🇯🇵", "SAR": "ریال عربستان 🇸🇦",
    "KWD": "دینار کویت 🇰🇼", "OMR": "ریال عمان 🇴🇲", "QAR": "ریال قطر 🇶🇦"
}

currency_info_template = {
    "USD": "👤 نام و نام خانوادگی گیرنده\n🏦 نام بانک\n💳 شماره حساب یا IBAN\n🌍 کشور / شهر بانک\n🔢 SWIFT Code",
    "EUR": "👤 نام و نام خانوادگی گیرنده\n🏦 نام بانک\n💳 شماره IBAN\n🌍 کشور بانک\n🔢 SWIFT / BIC Code",
    "GBP": "👤 نام گیرنده\n🏦 نام بانک\n💳 شماره حساب\n🏷 Sort Code",
    "CHF": "👤 نام گیرنده\n🏦 نام بانک\n💳 شماره حساب یا IBAN\n🔢 SWIFT Code\n🌍 کشور بانک",
    "CAD": "👤 نام گیرنده\n🏦 نام بانک\n💳 شماره حساب\n🏷 Transit Number\n🌍 کشور / شهر بانک",
    "AUD": "👤 نام گیرنده\n🏦 نام بانک\n💳 شماره حساب\n🏷 BSB Code\n🌍 کشور بانک",
    "AED": "👤 نام گیرنده\n🏦 نام بانک\n💳 شماره IBAN\n🌍 امارت / شهر بانک\n🔢 SWIFT Code",
    "TRY": "👤 نام گیرنده\n🏦 نام بانک\n💳 شماره IBAN (TR...)\n🌍 شهر بانک\n🔢 SWIFT Code",
    "CNY": "👤 نام گیرنده (به انگلیسی)\n🏦 نام بانک\n💳 شماره حساب\n🌍 شهر / استان\n🔢 SWIFT Code",
    "INR": "👤 نام گیرنده\n🏦 نام بانک\n💳 شماره حساب\n🏷 IFSC Code\n🌍 کشور / شهر بانک",
    "JPY": "👤 نام گیرنده\n🏦 نام بانک\n💳 شماره حساب\n🏷 Branch Code\n🌍 شهر بانک\n🔢 SWIFT Code",
    "SAR": "👤 نام گیرنده\n🏦 نام بانک\n💳 شماره IBAN (SA...)\n🌍 کشور / شهر بانک\n🔢 SWIFT Code",
    "KWD": "👤 نام گیرنده\n🏦 نام بانک\n💳 شماره حساب یا IBAN\n🌍 کشور / شهر بانک\n🔢 SWIFT Code",
    "OMR": "👤 نام گیرنده\n🏦 نام بانک\n💳 شماره حساب یا IBAN\n🌍 کشور / شهر بانک\n🔢 SWIFT Code",
    "QAR": "👤 نام گیرنده\n🏦 نام بانک\n💳 شماره حساب یا IBAN\n🌍 کشور / شهر بانک\n🔢 SWIFT Code"
}

pending = {}
support_chat = {}  # برای حالت چت پشتیبانی
last_target_for_admin = None

# ---------------- کیبوردها ----------------
def main_menu():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("💸 انتقال ارز", "💬 پیام به پشتیبانی")
    return kb

def direction_menu():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("🟢 خرید", "🔴 فروش")
    kb.add("🔙 بازگشت")
    return kb

def confirm_keyboard():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("✅ تایید", "❌ لغو")
    kb.add("🔙 بازگشت")
    return kb

def support_keyboard():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("🔚 پایان پیام‌رسانی")
    return kb

# ---------------- درگاه زیبال ----------------
@app.route("/pay/<int:user_id>/<int:amount>")
def pay(user_id, amount):
    try:
        rial_amount = int(amount * 10)
        callback_url = f"https://{RAILWAY_DOMAIN}/verify/{user_id}"
        req = {"merchant": MERCHANT, "amount": rial_amount, "callbackUrl": callback_url,
               "description": f"پرداخت {amount:,} تومان از طریق ربات نوسان‌پی"}
        res = requests.post("https://gateway.zibal.ir/v1/request", json=req, timeout=15)
        data = res.json()
    except Exception as e:
        bot.send_message(ADMIN_ID, f"❌ خطا در تماس با زیبال: {str(e)}")
        return jsonify({"error": f"{e}"}), 500

    if data.get("result") == 100:
        return redirect(f"https://gateway.zibal.ir/start/{data['trackId']}")
    else:
        bot.send_message(ADMIN_ID, f"❌ خطا از زیبال: {data}")
        return jsonify(data), 400

@app.route("/verify/<int:user_id>", methods=["GET", "POST"])
def verify_payment(user_id):
    track_id = request.args.get("trackId")
    if not track_id:
        return "trackId ارسال نشده", 400
    try:
        req = {"merchant": MERCHANT, "trackId": track_id}
        res = requests.post("https://gateway.zibal.ir/v1/verify", json=req, timeout=15)
        data = res.json()
    except Exception as e:
        bot.send_message(ADMIN_ID, f"❌ verify error: {e}")
        return f"خطا: {e}", 500

    if data.get("result") == 100:
        bot.send_message(user_id, "✅ پرداخت موفق انجام شد.")
        bot.send_message(ADMIN_ID, f"💰 پرداخت موفق از کاربر {user_id}")
        return "OK"
    else:
        bot.send_message(user_id, "❌ پرداخت ناموفق بود.")
        bot.send_message(ADMIN_ID, f"❌ پرداخت ناموفق از کاربر {user_id}: {data}")
        return "Failed", 400

# ---------------- منطق ربات ----------------
@bot.message_handler(commands=["start"])
def start(m):
    pending.pop(m.chat.id, None)
    support_chat.pop(m.chat.id, None)
    bot.send_message(m.chat.id, "سلام 👋 برای شروع، گزینه مورد نظر را انتخاب کنید:", reply_markup=main_menu())

@bot.message_handler(func=lambda m: m.text == "💸 انتقال ارز")
def start_transfer(m):
    bot.send_message(m.chat.id, "جهت انتقال را انتخاب کنید:", reply_markup=direction_menu())

@bot.message_handler(func=lambda m: m.text == "💬 پیام به پشتیبانی")
def start_support(m):
    support_chat[m.chat.id] = True
    bot.send_message(m.chat.id, "✉️ لطفاً پیام یا تصویر خود را ارسال کنید.\nبرای پایان، روی «🔚 پایان پیام‌رسانی» بزنید.",
                     reply_markup=support_keyboard())
    bot.send_message(ADMIN_ID, f"📩 کاربر {m.chat.id} گفتگو با پشتیبانی را آغاز کرد.")

@bot.message_handler(func=lambda m: m.text == "🔚 پایان پیام‌رسانی")
def end_support(m):
    if m.chat.id in support_chat:
        support_chat.pop(m.chat.id)
        bot.send_message(m.chat.id, "✅ گفت‌وگو با پشتیبانی پایان یافت.", reply_markup=main_menu())
        bot.send_message(ADMIN_ID, f"🔕 کاربر {m.chat.id} گفت‌وگو را پایان داد.")
    else:
        bot.send_message(m.chat.id, "شما در حالت پیام‌رسانی نیستید.", reply_markup=main_menu())

@bot.message_handler(content_types=["text", "photo"])
def handle_messages(m):
    chat_id = m.chat.id
    text = (m.text or "").strip()

    # --- حالت گفت‌وگو پشتیبانی کاربر ---
    if chat_id in support_chat and chat_id != ADMIN_ID:
        if m.content_type == "photo":
            file_id = m.photo[-1].file_id
            bot.send_photo(ADMIN_ID, file_id, caption=f"📸 پیام تصویری از کاربر {chat_id}")
        else:
            bot.send_message(ADMIN_ID, f"💬 پیام از کاربر {chat_id}:\n{text}")
        bot.send_message(chat_id, "✅ پیام شما ارسال شد.")
        return

    # --- ادمین در حالت پاسخ‌دهی ---
    if chat_id == ADMIN_ID:
        # شروع گفت‌وگو با کاربر خاص
        start_msg = re.match(r"^پیام\s+(\d+)$", text)
        if start_msg:
            uid = int(start_msg.group(1))
            support_chat[ADMIN_ID] = uid
            bot.send_message(ADMIN_ID, f"✅ گفت‌وگو با کاربر {uid} آغاز شد. برای پایان بنویس: پایان {uid}")
            return

        # پایان گفت‌وگو
        end_msg = re.match(r"^پایان\s+(\d+)$", text)
        if end_msg:
            uid = int(end_msg.group(1))
            if support_chat.get(ADMIN_ID) == uid:
                support_chat.pop(ADMIN_ID)
                bot.send_message(ADMIN_ID, f"🔚 گفت‌وگو با کاربر {uid} پایان یافت.")
                bot.send_message(uid, "🔕 گفت‌وگو توسط پشتیبانی پایان یافت.", reply_markup=main_menu())
            return

        # اگر در حال گفت‌وگو با کاربر است
        if ADMIN_ID in support_chat:
            uid = support_chat[ADMIN_ID]
            if m.content_type == "photo":
                bot.send_photo(uid, m.photo[-1].file_id, caption="📩 تصویر از پشتیبانی")
            else:
                bot.send_message(uid, f"📩 پیام از پشتیبانی:\n\n{text}")
            bot.send_message(ADMIN_ID, "✅ پیام ارسال شد.")
            return

    # --- بقیه منطق قبلی (خرید/فروش و غیره) ---
    if text in ["🟢 خرید", "🔴 فروش"]:
        direction = "خرید" if "خرید" in text else "فروش"
        pending[chat_id] = {"direction": direction, "step": "currency"}
        kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        for c, n in currencies.items():
            kb.add(f"{n} ({c})")
        kb.add("🔙 بازگشت")
        bot.send_message(chat_id, "ارز مورد نظر را انتخاب کنید:", reply_markup=kb)
        return

    if chat_id in pending:
        handle_transfer_flow(m)

def handle_transfer_flow(m):
    chat_id = m.chat.id
    text = (m.text or "").strip()
    st = pending.get(chat_id)

    if text == "🔙 بازگشت":
        pending.pop(chat_id, None)
        return start(m)

    if st.get("step") == "currency":
        match = re.search(r"\(([A-Z]{3})\)", text)
        if match:
            code = match.group(1)
            st["currency"] = code
            st["step"] = "amount"
            return bot.send_message(chat_id, f"مقدار {currencies.get(code)} را وارد کنید (مثلاً 2500):")

    if st.get("step") == "amount":
        try:
            st["amount"] = float(text.replace(",", ""))
        except:
            return bot.reply_to(m, "عدد معتبر وارد کنید.")
        st["step"] = "waiting_rate"
        bot.send_message(ADMIN_ID,
                         f"📩 درخواست جدید:\nuser_id={chat_id}\nجهت: {st['direction']}\nارز: {st['currency']}\nمقدار: {st['amount']}\n\n"
                         f"برای تعیین نرخ بنویس: نرخ {chat_id} <نرخ>")
        return bot.send_message(chat_id, "✅ درخواست شما ثبت شد و برای ادمین ارسال شد.")

# ---------------- اجرای همزمان ----------------
def run_flask():
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

def run_bot():
    bot.infinity_polling(timeout=60, long_polling_timeout=30)

if __name__ == "__main__":
    print("✅ Npay bot started")
    threading.Thread(target=run_flask).start()
    run_bot()
