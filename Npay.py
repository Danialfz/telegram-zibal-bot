# Npay.py (نسخه‌ی کامل با پشتیبانی از "فقط وارد کردن مبلغ" توسط ادمین)
import os
import re
import telebot
from telebot import types
from flask import Flask, request, jsonify, redirect
import requests
import threading

# ====================== تنظیمات اصلی ======================
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "1611406302"))
MERCHANT = os.getenv("MERCHANT")
RAILWAY_DOMAIN = os.getenv("RAILWAY_DOMAIN")

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

# ====================== اطلاعات ارزها ======================
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

# ====================== قالب اطلاعات حساب بر اساس ارز ======================
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

# ====================== حافظهٔ موقت ======================
pending = {}
awaiting_admin_review = set()

# نگهدارنده‌ای که آخرین user_id نوتیفای‌شده به ادمین را ذخیره می‌کند
last_target_for_admin = None

# ====================== مسیر پرداخت زیبال ======================
@app.route("/pay/<int:user_id>/<int:amount>")
def pay(user_id, amount):
    try:
        callback_url = "https://zibal.ir"
        req = {
            "merchant": MERCHANT,
            "amount": amount,
            "callbackUrl": callback_url,
            "description": f"پرداخت {amount:,} تومان از طریق ربات نوسان‌پی"
        }

        res = requests.post("https://gateway.zibal.ir/v1/request", json=req, timeout=10)
        data = res.json()

        if data.get("result") == 100:
            track_id = data["trackId"]
            return redirect(f"https://gateway.zibal.ir/start/{track_id}")
        else:
            return jsonify({"error": f"❌ خطا از زیبال: {data}"}), 400
    except Exception as e:
        return jsonify({"error": f"⚠️ خطا در ساخت لینک پرداخت: {str(e)}"}), 500

# ====================== مسیر وریفای پرداخت ======================
@app.route("/verify/<int:user_id>", methods=["GET", "POST"])
def verify_payment(user_id):
    try:
        track_id = request.args.get("trackId")
        if not track_id:
            return "پارامتر trackId ارسال نشده."

        req = {"merchant": MERCHANT, "trackId": track_id}
        res = requests.post("https://gateway.zibal.ir/v1/verify", json=req, timeout=10)
        data = res.json()

        if data.get("result") == 100:
            bot.send_message(user_id, "✅ پرداخت شما با موفقیت انجام شد.\nسپاس از اعتماد شما 💚")
            bot.send_message(ADMIN_ID, f"💰 کاربر {user_id} پرداخت را با موفقیت انجام داد.")
            return "✅ پرداخت با موفقیت انجام شد."
        else:
            bot.send_message(user_id, "❌ پرداخت ناموفق بود یا لغو شد.")
            return f"❌ پرداخت ناموفق: {data}"
    except Exception as e:
        return f"⚠️ خطا در بررسی پرداخت: {str(e)}"

# ====================== کیبوردها ======================
def main_menu():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("💸 انتقال ارز")
    return kb

def direction_menu():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("🌍 از داخل به خارج", "🏦 از خارج به داخل")
    kb.add("🔙 بازگشت")
    return kb

def confirm_keyboard():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("✅ تایید", "❌ لغو")
    kb.add("🔙 بازگشت")
    return kb

# ====================== منطق ربات ======================
@bot.message_handler(commands=["start"])
def start_cmd(m):
    pending.pop(m.chat.id, None)
    awaiting_admin_review.discard(m.chat.id)
    bot.send_message(m.chat.id, "سلام 👋 خوش اومدی!\nبرای شروع انتقال ارز، گزینه زیر رو انتخاب کن:", reply_markup=main_menu())

@bot.message_handler(func=lambda m: m.text == "💸 انتقال ارز")
def start_transfer(m):
    bot.send_message(m.chat.id, "جهت انتقال را انتخاب کنید:", reply_markup=direction_menu())

@bot.message_handler(func=lambda m: m.text in ["🌍 از داخل به خارج", "🏦 از خارج به داخل"])
def choose_currency(m):
    chat_id = m.chat.id
    direction = "از داخل به خارج" if "داخل به خارج" in m.text else "از خارج به داخل"
    pending[chat_id] = {"direction": direction, "step": "currency"}
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    for code, name in currencies.items():
        kb.add(types.KeyboardButton(f"{name} ({code})"))
    kb.add(types.KeyboardButton("🔙 بازگشت"))
    bot.send_message(chat_id, "ارز مورد نظر را انتخاب کنید:", reply_markup=kb)

@bot.message_handler(func=lambda m: re.search(r"\(([A-Z]{3})\)", m.text or ""))
def ask_amount(m):
    chat_id = m.chat.id
    match = re.search(r"\(([A-Z]{3})\)", m.text)
    code = match.group(1)
    st = pending.get(chat_id)
    if not st:
        return bot.reply_to(m, "ابتدا جهت انتقال را انتخاب کنید.")
    pending[chat_id]["currency"] = code
    pending[chat_id]["step"] = "amount"
    bot.send_message(chat_id, f"مقدار {currencies[code]} را وارد کنید (مثلاً 2500):", reply_markup=types.ReplyKeyboardMarkup(resize_keyboard=True).add("🔙 بازگشت"))

@bot.message_handler(func=lambda m: True)
def process(m):
    global last_target_for_admin
    chat_id = m.chat.id
    text = (m.text or "").strip()
    st = pending.get(chat_id)

    if text == "🔙 بازگشت":
        pending.pop(chat_id, None)
        return start_cmd(m)

    # ========== بخش ادمین ==========
    if chat_id == ADMIN_ID:
        # حالت 1: admin استفاده از دستور کامل: "نرخ <user_id> <rate>"
        m_full = re.match(r"^نرخ\s+(\d+)\s+(\d+(\.\d+)?)$", text)
        if m_full:
            uid = int(m_full.group(1))
            rate = float(m_full.group(2))
            if uid in pending and pending[uid].get("step") in ("waiting_rate", "waiting_rate"):
                amount = pending[uid].get("amount", 0)
                total = int(amount * rate)
                pending[uid]["rate"] = rate
                pending[uid]["total"] = total
                pending[uid]["step"] = "confirm"
                # پیام به کاربر
                bot.send_message(uid,
                    f"💰 مجموع پرداختی شما: {total:,} تومان\n\nآیا تایید می‌کنید؟",
                    reply_markup=confirm_keyboard()
                )
                bot.send_message(ADMIN_ID, f"✅ نرخ {rate:,} برای کاربر {uid} تنظیم شد.")
                # به‌روز کن last target
                last_target_for_admin = uid
                return
            else:
                return bot.send_message(ADMIN_ID, "⚠️ کاربر پیدا نشد یا در مرحله‌ی انتظار نرخ نیست.")

        # حالت 2: admin فقط یک عدد می‌فرسته — اعمال برای last_target_for_admin
        m_num = re.match(r"^(\d+(\.\d+)?)$", text)
        if m_num:
            rate = float(m_num.group(1))
            # اگر last_target_for_admin ست شده و برایش در انتظار نرخ است => استفاده کن
            if last_target_for_admin and last_target_for_admin in pending and pending[last_target_for_admin].get("step") == "waiting_rate":
                uid = last_target_for_admin
                amount = pending[uid].get("amount", 0)
                total = int(amount * rate)
                pending[uid]["rate"] = rate
                pending[uid]["total"] = total
                pending[uid]["step"] = "confirm"
                bot.send_message(uid,
                    f"💰 مجموع پرداختی شما: {total:,} تومان\n\nآیا تایید می‌کنید؟",
                    reply_markup=confirm_keyboard()
                )
                bot.send_message(ADMIN_ID, f"✅ نرخ {rate:,} برای کاربر {uid} تنظیم شد (با عدد ساده).")
                return
            # اگر last_target_for_admin معتبر نیست، fallback بگرد اولین درخواست waiting_rate
            target = None
            for uid, data in pending.items():
                if data.get("step") == "waiting_rate":
                    target = uid
                    break
            if target:
                amount = pending[target].get("amount", 0)
                total = int(amount * rate)
                pending[target]["rate"] = rate
                pending[target]["total"] = total
                pending[target]["step"] = "confirm"
                last_target_for_admin = target
                bot.send_message(target,
                    f"💰 مجموع پرداختی شما: {total:,} تومان\n\nآیا تایید می‌کنید؟",
                    reply_markup=confirm_keyboard()
                )
                bot.send_message(ADMIN_ID, f"✅ نرخ {rate:,} برای کاربر {target} تنظیم شد (fallback).")
                return
            return bot.send_message(ADMIN_ID, "⚠️ در حال حاضر هیچ درخواستی در انتظار نرخ نیست.")

        # تایید اطلاعات ادمین: "تایید <user_id>"
        m1 = re.match(r"^تایید\s+(\d+)$", text)
        if m1:
            uid = int(m1.group(1))
            if uid in pending:
                total = pending[uid].get("total", 0)
                # ساخت لینک زیبال و ارسال مستقیم (track via request)
                try:
                    req = {
                        "merchant": MERCHANT,
                        "amount": total,
                        "callbackUrl": f"https://{RAILWAY_DOMAIN}/verify/{uid}",
                        "description": f"پرداخت {total:,} تومان از طریق ربات نوسان‌پی"
                    }
                    res = requests.post("https://gateway.zibal.ir/v1/request", json=req, timeout=10)
                    data = res.json()
                    if data.get("result") == 100:
                        track_id = data["trackId"]
                        pay_link = f"https://gateway.zibal.ir/start/{track_id}"
                        bot.send_message(uid, f"✅ اطلاعات شما تایید شد.\n\n💳 برای پرداخت کلیک کنید:\n{pay_link}")
                        bot.send_message(ADMIN_ID, f"💰 لینک پرداخت برای کاربر {uid} ارسال شد.")
                    else:
                        bot.send_message(ADMIN_ID, f"❌ خطا در ساخت لینک پرداخت: {data}")
                except Exception as e:
                    bot.send_message(ADMIN_ID, f"❌ خطا در درخواست زیبال: {str(e)}")
            else:
                bot.send_message(ADMIN_ID, "⚠️ کاربر یافت نشد.")
            return

        # اصلاح: "اصلاح <user_id> <دلیل>"
        m2 = re.match(r"^اصلاح\s+(\d+)\s+(.+)$", text)
        if m2:
            uid = int(m2.group(1))
            reason = m2.group(2).strip()
            if uid in pending:
                pending[uid]["step"] = "awaiting_info"
                bot.send_message(uid, f"⚠️ پشتیبانی درخواست اصلاح کرد:\n\n{reason}\n\nلطفاً اطلاعات اصلاح‌شده را ارسال کنید (فقط متن).")
                bot.send_message(ADMIN_ID, f"✅ پیام اصلاح برای {uid} ارسال شد.")
                # update last target
                last_target_for_admin = uid
            else:
                bot.send_message(ADMIN_ID, "⚠️ کاربر یافت نشد.")
            return

        # راهنمایی برای ادمین اگر پیام ناشناخته بود
        return bot.send_message(ADMIN_ID,
            "راهنما برای ادمین:\n"
            "- برای تعیین نرخ سریع: فقط عدد (مثلاً `1250000`) -> برای آخرین درخواست\n"
            "- یا: نرخ <user_id> <rate>\n"
            "- برای تایید نهایی و ارسال لینک پرداخت: تایید <user_id>\n"
            "- برای اصلاح اطلاعات: اصلاح <user_id> <دلیل>"
        )

    # ========== کاربران عادی ==========
    if st:
        step = st.get("step")
        if step == "amount":
            # کاربر مقدار رو می‌فرسته
            try:
                st["amount"] = float(text.replace(",", "").replace(" ", ""))
            except:
                return bot.reply_to(m, "⚠️ مقدار نامعتبر. فقط عدد مثبت وارد کنید (مثلاً 2500).")
            st["step"] = "waiting_rate"
            # اطلاع به ادمین + ذخیره last_target_for_admin
            bot.send_message(ADMIN_ID,
                f"📩 درخواست جدید از {m.from_user.username or m.from_user.first_name} (id: {m.chat.id})\n"
                f"جهت: {st['direction']}\n"
                f"ارز: {st['currency']}\n"
                f"مقدار: {st['amount']}\n\n"
                f"🔹 لطفاً برای تعیین نرخ سریع فقط عدد را ارسال کنید (این عدد برای آخرین درخواست اعمال می‌شود)،\n"
                f"یا از دستور کامل استفاده کنید:\nنرخ {m.chat.id} <نرخ_تومانی>"
            )
            # ثبت آخرین هدف برای ادمین
            last_target_for_admin = m.chat.id
            bot.send_message(m.chat.id, "✅ درخواست شما ثبت شد و برای ادمین ارسال شد.", reply_markup=main_menu())
            return

        if step == "confirm":
            # کاربر دکمه تایید/لغو رو زد
            if text in ("✅ تایید", "تایید", "بله", "✅"):
                st["step"] = "awaiting_info"
                direction = st["direction"]
                currency = st["currency"]
                if direction == "از داخل به خارج":
                    info_text = currency_info_template.get(currency, "👤 لطفاً اطلاعات گیرنده را وارد کنید.")
                else:
                    info_text = "👤 نام و نام خانوادگی\n💳 شماره کارت / حساب / شبا"
                bot.send_message(m.chat.id, f"لطفاً اطلاعات زیر را ارسال کنید:\n\n{info_text}", reply_markup=types.ReplyKeyboardMarkup(resize_keyboard=True).add("🔙 بازگشت"))
            elif text in ("❌ لغو", "لغو", "خیر", "❌"):
                pending.pop(m.chat.id, None)
                bot.send_message(m.chat.id, "❌ درخواست لغو شد.", reply_markup=main_menu())
            else:
                bot.send_message(m.chat.id, "لطفاً یکی از دکمه‌ها را فشار دهید.", reply_markup=confirm_keyboard())
            return

        if step == "awaiting_info":
            # ذخیره اطلاعات و ارسال به ادمین برای بررسی نهایی
            if re.search(r"https?://|t\.me|@", text, re.IGNORECASE):
                try:
                    bot.delete_message(m.chat.id, m.message_id)
                except:
                    pass
                return bot.send_message(m.chat.id, "⚠️ لطفاً فقط متن ساده ارسال کنید (بدون لینک یا تگ).")
            st["info"] = text
            st["step"] = None
            awaiting_admin_review.add(m.chat.id)
            bot.send_message(ADMIN_ID,
                f"📦 اطلاعات حساب از کاربر {m.chat.id}:\n\n{text}\n\n"
                f"برای تایید بنویس: تایید {m.chat.id}\nیا برای اصلاح بنویس: اصلاح {m.chat.id} <دلیل>"
            )
            bot.send_message(m.chat.id, "✅ اطلاعات شما ارسال شد و در انتظار تایید ادمین است.", reply_markup=main_menu())
            return

    # اگر هیچ مسیر فعال نبود، هِلم بده
    return bot.send_message(m.chat.id, "برای شروع «💸 انتقال ارز» را انتخاب کنید.", reply_markup=main_menu())

# ====================== اجرای همزمان Flask و Bot ======================
def run_flask():
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))

def run_bot():
    bot.infinity_polling(timeout=60, long_polling_timeout=30)

if __name__ == "__main__":
    threading.Thread(target=run_flask).start()
    run_bot()

