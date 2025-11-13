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
last_target_for_admin = None

# ---------------- کیبوردها ----------------
def main_menu():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("💸 انتقال ارز")
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
    bot.send_message(m.chat.id, "سلام 👋 برای شروع انتقال ارز گزینه زیر را انتخاب کنید:", reply_markup=main_menu())

@bot.message_handler(func=lambda m: m.text == "💸 انتقال ارز")
def start_transfer(m):
    bot.send_message(m.chat.id, "جهت انتقال را انتخاب کنید:", reply_markup=direction_menu())

@bot.message_handler(func=lambda m: m.text in ["🟢 خرید", "🔴 فروش"])
def choose_currency(m):
    direction = "خرید" if "خرید" in m.text else "فروش"
    pending[m.chat.id] = {"direction": direction, "step": "currency"}
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    for c, n in currencies.items():
        kb.add(f"{n} ({c})")
    kb.add("🔙 بازگشت")
    bot.send_message(m.chat.id, "ارز مورد نظر را انتخاب کنید:", reply_markup=kb)

@bot.message_handler(func=lambda m: re.search(r"\(([A-Z]{3})\)", m.text or ""))
def got_currency(m):
    chat_id = m.chat.id
    match = re.search(r"\(([A-Z]{3})\)", m.text)
    if not match: return
    code = match.group(1)
    if chat_id not in pending: return
    pending[chat_id]["currency"] = code
    pending[chat_id]["step"] = "amount"
    bot.send_message(chat_id, f"مقدار {currencies.get(code)} را وارد کنید (مثلاً 2500):")

@bot.message_handler(func=lambda m: True)
def main_handler(m):
    chat_id = m.chat.id
    text = (m.text or "").strip()
    st = pending.get(chat_id)

    if text == "🔙 بازگشت":
        pending.pop(chat_id, None)
        return start(m)

    # ==== ادمین ====
    if chat_id == ADMIN_ID:
        # 🔹 نرخ
        m_rate = re.match(r"^نرخ\s+(\d+)\s+([\d.]+)$", text)
        if m_rate:
            uid = int(m_rate.group(1))
            rate = float(m_rate.group(2))
            if uid in pending and pending[uid].get("step") == "waiting_rate":
                amount = pending[uid]["amount"]
                total = int(amount * rate)
                pending[uid].update({"rate": rate, "total": total, "step": "confirm"})
                bot.send_message(uid, f"💰 مجموع پرداختی: {total:,} تومان\nتایید می‌کنید؟", reply_markup=confirm_keyboard())
                bot.send_message(ADMIN_ID, f"✅ نرخ {rate} برای کاربر {uid} ثبت شد.")
                global last_target_for_admin
                last_target_for_admin = uid
            return

        # 🔹 تایید نهایی
        m_confirm = re.match(r"^تایید\s+(\d+)$", text)
        if m_confirm:
            uid = int(m_confirm.group(1))
            if uid not in pending: return bot.send_message(ADMIN_ID, "کاربر پیدا نشد.")
            data = pending[uid]
            total = data.get("total", 0)
            direction = data.get("direction")

            if direction == "خرید":
                rial_total = int(total * 10)
                callback_url = f"https://{RAILWAY_DOMAIN}/verify/{uid}"
                req = {"merchant": MERCHANT, "amount": rial_total, "callbackUrl": callback_url,
                       "description": f"پرداخت {total:,} تومان از طریق ربات نوسان‌پی"}
                res = requests.post("https://gateway.zibal.ir/v1/request", json=req, timeout=15)
                d = res.json()
                if d.get("result") == 100:
                    pay_link = f"https://gateway.zibal.ir/start/{d['trackId']}"
                    bot.send_message(uid, f"✅ اطلاعات تایید شد.\n💳 <a href=\"{pay_link}\">برای پرداخت کلیک کنید</a>",
                                     parse_mode="HTML", disable_web_page_preview=True)
                    bot.send_message(ADMIN_ID, f"💰 لینک پرداخت برای {uid} ارسال شد.")
                else:
                    bot.send_message(ADMIN_ID, f"❌ خطا از زیبال: {d}")
                return

            elif direction == "فروش":
                bot.send_message(uid, "✅ اطلاعات تایید شد.\n\n💬 منتظر پیام پشتیبانی باشید تا اطلاعات واریز برای شما ارسال شود.")
                bot.send_message(ADMIN_ID,
                                 f"📦 کاربر {uid} مسیر فروش را تایید کرد.\n"
                                 f"لطفاً اطلاعات حساب دریافت وجه را برای او ارسال کنید.\n"
                                 f"(هر متنی بفرستید برای او فوروارد می‌شود.)")
                pending[uid]["step"] = "awaiting_manual_payment"
                last_target_for_admin = uid
                return

        # 🔹 درخواست اصلاح اطلاعات
        m_fix = re.match(r"^اصلاح\s+(\d+)\s+(.+)$", text)
        if m_fix:
            uid = int(m_fix.group(1))
            reason = m_fix.group(2)
            if uid in pending:
                pending[uid]["step"] = "awaiting_correction"
                bot.send_message(uid,
                    f"⚠️ ادمین درخواست اصلاح اطلاعات داده است:\n\n📝 {reason}\n\n"
                    "لطفاً اطلاعات اصلاح‌شده را دوباره ارسال کنید.")
                bot.send_message(ADMIN_ID, f"📩 پیام اصلاح برای کاربر {uid} ارسال شد.")
            else:
                bot.send_message(ADMIN_ID, "❌ کاربر مورد نظر یافت نشد.")
            return

        # 🔹 پیام دستی پشتیبانی
        if last_target_for_admin and last_target_for_admin in pending and pending[last_target_for_admin].get("step") == "awaiting_manual_payment":
            bot.send_message(last_target_for_admin, f"📩 پیام از پشتیبانی:\n\n{text}")
            return bot.send_message(ADMIN_ID, "✅ پیام برای کاربر ارسال شد.")
        return

    # ==== کاربر ====
    if not st:
        return bot.send_message(chat_id, "برای شروع «💸 انتقال ارز» را انتخاب کنید.", reply_markup=main_menu())

    step = st.get("step")

    if step == "amount":
        try:
            st["amount"] = float(text.replace(",", ""))
        except:
            return bot.reply_to(m, "عدد معتبر وارد کنید.")
        st["step"] = "waiting_rate"
        bot.send_message(ADMIN_ID,
            f"📩 درخواست جدید:\nuser_id={chat_id}\nجهت: {st['direction']}\nارز: {st['currency']}\nمقدار: {st['amount']}\n\n"
            f"برای تعیین نرخ بنویس: نرخ {chat_id} <نرخ>")
        return bot.send_message(chat_id, "✅ درخواست شما ثبت شد و برای ادمین ارسال شد.")

    if step == "confirm":
        if text in ("✅ تایید", "تایید", "بله"):
            st["step"] = "awaiting_info"
            if st["direction"] == "خرید":
                info_text = currency_info_template.get(st["currency"], "👤 اطلاعات گیرنده را وارد کنید:")
            else:
                info_text = "👤 لطفاً اطلاعات فرستنده را وارد کنید (نام و شماره حساب در خارج از کشور)"
            bot.send_message(chat_id, f"لطفاً اطلاعات زیر را ارسال کنید:\n\n{info_text}")
        elif text in ("❌ لغو", "لغو"):
            pending.pop(chat_id, None)
            bot.send_message(chat_id, "درخواست لغو شد.", reply_markup=main_menu())
        return

    if step in ("awaiting_info", "awaiting_correction"):
        st["info"] = text
        st["step"] = None
        bot.send_message(ADMIN_ID, f"📦 اطلاعات حساب از کاربر {chat_id}:\n\n{text}\n\nبرای تایید بنویس: تایید {chat_id}\n"
                                   f"یا در صورت نیاز به اصلاح بنویس: اصلاح {chat_id} <دلیل>")
        bot.send_message(chat_id, "✅ اطلاعات شما ارسال شد و در انتظار بررسی ادمین است.")
        return

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
