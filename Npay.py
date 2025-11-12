# Npay.py — نسخهٔ نهایی (همهٔ فیچرهایی که خواستی)
import os
import re
import threading
import requests
import telebot
from telebot import types
from flask import Flask, request, jsonify, redirect

# ---------------- تنظیمات اصلی (متغیر محیطی) ----------------
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

# ---------------- آماده‌سازی بوت و وب‌فلاسک ----------------
bot = telebot.TeleBot(BOT_TOKEN)
# اگر جایی webhook قبلاً ست شده باشه، حذفش کن تا conflict 409 نیاد
try:
    bot.remove_webhook()
except Exception:
    pass

app = Flask(__name__)

# ---------------- لیست ارزها و قالب اطلاعات برای هر ارز ----------------
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

# ---------------- حافظهٔ موقت داخلی ----------------
pending = {}               # pending[user_id] = { direction, step, currency, amount, rate, total, info }
awaiting_admin_review = set()
last_target_for_admin = None

# ---------------- کیبوردها ----------------
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

# ---------------- مسیر پرداخت (زیبال) ----------------
@app.route("/pay/<int:user_id>/<int:amount>")
def pay(user_id, amount):
    """
    این مسیر مستقیماً برای هدایت کاربر به درگاه زیبال استفاده می‌شود.
    callbackUrl باید دقیقاً دامنه‌ای باشه که توی پنل زیبال روی مرچنت ثبت شده.
    مقدار RAILWAY_DOMAIN باید همان دامنه (مثلاً bot.navasanpay.com یا navasanpay.com) باشد.
    """
    try:
        callback_url = f"https://{RAILWAY_DOMAIN}/verify/{user_id}"
        req = {
            "merchant": MERCHANT,
            "amount": amount,
            "callbackUrl": callback_url,
            "description": f"پرداخت {amount:,} تومان از طریق ربات نوسان‌پی"
        }

        res = requests.post("https://gateway.zibal.ir/v1/request", json=req, timeout=15)
        data = res.json()
    except Exception as e:
        # شبکه یا timeout
        # برای دیباگ، به ادمین گزارش بده
        try:
            bot.send_message(ADMIN_ID, f"❌ خطا در تماس با زیبال: {str(e)}")
        except Exception:
            pass
        return jsonify({"error": f"⚠️ خطا در ساخت لینک پرداخت: {str(e)}"}), 500

    # پاسخ زیبال را بررسی کن
    if data.get("result") == 100:
        track_id = data["trackId"]
        return redirect(f"https://gateway.zibal.ir/start/{track_id}")
    else:
        # خطا از زیبال — به ادمین ارسال می‌کنیم تا بداند چه خطایی آمد
        try:
            bot.send_message(ADMIN_ID, f"❌ Zibal returned error: {data}")
            # اگر خطای 106 است، توضیح واضح هم می‌فرستیم
            if data.get("result") == 106 or ("callbackUrl" in str(data.get("message", ""))):
                bot.send_message(ADMIN_ID,
                    "⚠️ خطای 106 از زیبال: آدرس callbackUrl باید مرتبط با دامنه‌ای باشد که در پنل زیبال برای مرچنت ثبت شده.\n"
                    "راه حل‌ها:\n"
                    "1) دامنه‌ی RAILWAY_DOMAIN را روی همون دامنه‌ای قرار بده که در پنل زیبال ثبت شده (مثلاً navasanpay.com)\n"
                    "2) یا توی پنل زیبال برای مرچنت، دامنه‌ی فعلی (مثل bot.navasanpay.com) را اضافه کن.\n"
                    "بعد از اعمال تغییرات، دوباره 'تایید <user_id>' را اجرا کن.")
        except Exception:
            pass
        return jsonify({"error": data}), 400

# ---------------- مسیر وریفای زیبال ----------------
@app.route("/verify/<int:user_id>", methods=["GET", "POST"])
def verify_payment(user_id):
    """
    زیبال کاربر را به این آدرس redirect می‌کند با پارامتر trackId.
    این endpoint، verify را به زیبال می‌فرستد و نتیجه را به کاربر و ادمین گزارش می‌دهد.
    """
    track_id = request.args.get("trackId")
    if not track_id:
        return "پارامتر trackId ارسال نشده.", 400

    try:
        req = {"merchant": MERCHANT, "trackId": track_id}
        res = requests.post("https://gateway.zibal.ir/v1/verify", json=req, timeout=15)
        data = res.json()
    except Exception as e:
        try:
            bot.send_message(ADMIN_ID, f"❌ خطا در تماس verify با زیبال: {str(e)}")
        except Exception:
            pass
        return f"⚠️ خطا در بررسی پرداخت: {str(e)}", 500

    if data.get("result") == 100:
        # پرداخت موفق
        try:
            bot.send_message(user_id, "✅ پرداخت شما با موفقیت انجام شد.\nسپاس از اعتماد شما 💚")
            bot.send_message(ADMIN_ID, f"💰 کاربر {user_id} پرداخت را با موفقیت انجام داد.")
        except Exception:
            pass
        return "✅ پرداخت با موفقیت انجام شد."
    else:
        try:
            bot.send_message(user_id, "❌ پرداخت ناموفق بود یا لغو شد.")
            bot.send_message(ADMIN_ID, f"❌ پرداخت ناموفق برای کاربر {user_id}: {data}")
        except Exception:
            pass
        return f"❌ پرداخت ناموفق: {data}", 400

# ---------------- منطق ربات (پیغام‌ها) ----------------
@bot.message_handler(commands=["start"])
def cmd_start(m):
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
def got_currency(m):
    chat_id = m.chat.id
    match = re.search(r"\(([A-Z]{3})\)", m.text)
    if not match:
        return
    code = match.group(1)
    st = pending.get(chat_id)
    if not st:
        return bot.reply_to(m, "ابتدا جهت انتقال را انتخاب کنید.")
    pending[chat_id]["currency"] = code
    pending[chat_id]["step"] = "amount"
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(types.KeyboardButton("🔙 بازگشت"))
    bot.send_message(chat_id, f"مقدار {currencies.get(code, code)} را وارد کنید (مثلاً 2500):", reply_markup=kb)

@bot.message_handler(func=lambda m: True)
def general_handler(m):
    global last_target_for_admin
    chat_id = m.chat.id
    text = (m.text or "").strip()
    st = pending.get(chat_id)

    # بازگشت به منو
    if text == "🔙 بازگشت":
        pending.pop(chat_id, None)
        return cmd_start(m)

    # ----- بخش ادمین -----
    if chat_id == ADMIN_ID:
        # دستور کامل: نرخ <user_id> <rate>
        m_full = re.match(r"^نرخ\s+(\d+)\s+(\d+(\.\d+)?)$", text)
        if m_full:
            uid = int(m_full.group(1))
            rate = float(m_full.group(2))
            if uid in pending and pending[uid].get("step") == "waiting_rate":
                amount = pending[uid].get("amount", 0)
                total = int(amount * rate)
                pending[uid].update({"rate": rate, "total": total, "step": "confirm"})
                bot.send_message(uid, f"💰 مجموع پرداختی شما: {total:,} تومان\n\nآیا تایید می‌کنید؟", reply_markup=confirm_keyboard())
                bot.send_message(ADMIN_ID, f"✅ نرخ {rate} برای کاربر {uid} تنظیم شد.")
                last_target_for_admin = uid
                return
            else:
                return bot.send_message(ADMIN_ID, "⚠️ کاربر پیدا نشد یا در مرحله‌ی انتظار نرخ نیست.")

        # فقط عدد: اعمال برای last_target_for_admin یا fallback اولین waiting_rate
        m_num = re.match(r"^(\d+(\.\d+)?)$", text)
        if m_num:
            rate = float(m_num.group(1))
            # اگر last_target_for_admin معتبر باشد
            if last_target_for_admin and last_target_for_admin in pending and pending[last_target_for_admin].get("step") == "waiting_rate":
                uid = last_target_for_admin
                amount = pending[uid].get("amount", 0)
                total = int(amount * rate)
                pending[uid].update({"rate": rate, "total": total, "step": "confirm"})
                bot.send_message(uid, f"💰 مجموع پرداختی شما: {total:,} تومان\n\nآیا تایید می‌کنید؟", reply_markup=confirm_keyboard())
                bot.send_message(ADMIN_ID, f"✅ نرخ {rate} برای کاربر {uid} تنظیم شد (با عدد ساده).")
                return
            # fallback: اولین waiting_rate
            target = None
            for uid, data in pending.items():
                if data.get("step") == "waiting_rate":
                    target = uid
                    break
            if target:
                amount = pending[target].get("amount", 0)
                total = int(amount * rate)
                pending[target].update({"rate": rate, "total": total, "step": "confirm"})
                last_target_for_admin = target
                bot.send_message(target, f"💰 مجموع پرداختی شما: {total:,} تومان\n\nآیا تایید می‌کنید؟", reply_markup=confirm_keyboard())
                bot.send_message(ADMIN_ID, f"✅ نرخ {rate} برای کاربر {target} تنظیم شد (fallback).")
                return
            return bot.send_message(ADMIN_ID, "⚠️ در حال حاضر هیچ درخواستی در انتظار نرخ نیست.")

        # تایید نهایی: تایید <user_id> -> ساخته و ارسال لینک زیبال
        m_confirm = re.match(r"^تایید\s+(\d+)$", text)
        if m_confirm:
            uid = int(m_confirm.group(1))
            if uid in pending:
                total = pending[uid].get("total", 0)
                if not total or total <= 0:
                    return bot.send_message(ADMIN_ID, "⚠️ مجموع پرداختی برای این کاربر تعیین نشده. ابتدا نرخ را ثبت کن.")
                # ساخت درخواست زیبال
                try:
                    callback_url = f"https://{RAILWAY_DOMAIN}/verify/{uid}"
                    req = {"merchant": MERCHANT, "amount": total, "callbackUrl": callback_url,
                           "description": f"پرداخت {total:,} تومان از طریق ربات نوسان‌پی"}
                    res = requests.post("https://gateway.zibal.ir/v1/request", json=req, timeout=15)
                    data = res.json()
                    # گزارش برای ادمین
                    bot.send_message(ADMIN_ID, f"🧾 Zibal request: callbackUrl={callback_url}\nrequest={req}\nresponse={data}")
                    direction = pending[uid].get("direction")

# اگر جهت از خارج به داخل است → بدون لینک پرداخت
if direction == "از خارج به داخل":
    bot.send_message(
        uid,
        "✅ اطلاعات شما تایید شد.\n\n"
        "💵 لطفاً مبلغ مورد نظر را به حساب زیر واریز کنید:\n\n"
        "🏦 بانک: ملت\n"
        "💳 شماره کارت: 6104-3371-****-****\n"
        "👤 به نام: شرکت نوسان پی\n\n"
        "پس از واریز، رسید یا تأیید پرداخت را برای پشتیبانی ارسال کنید 🙏",
        parse_mode="HTML"
    )
    bot.send_message(ADMIN_ID, f"📨 اطلاعات تایید شد برای کاربر {uid} (از خارج به داخل) — واریز دستی.")
    return

# در غیر این صورت، یعنی از داخل به خارج → ارسال لینک پرداخت زیبال
if data.get("result") == 100:
    track_id = data["trackId"]
    pay_link = f"https://gateway.zibal.ir/start/{track_id}"
    bot.send_message(uid,
                     "✅ اطلاعات شما تایید شد.\n\n"
                     f"💳 <a href=\"{pay_link}\">برای پرداخت کلیک کنید</a>",
                     parse_mode="HTML",
                     disable_web_page_preview=True)
    bot.send_message(ADMIN_ID, f"💰 لینک پرداخت برای کاربر {uid} ارسال شد.")
                    else:
                        bot.send_message(ADMIN_ID, f"❌ خطا در ساخت لینک پرداخت: {data}")
                        if data.get("result") == 106:
                            bot.send_message(ADMIN_ID,
                                             "⚠️ خطای 106: callbackUrl باید مرتبط با دامنه‌ای باشد که در پنل زیبال ثبت شده.\n"
                                             "از دامنه‌ای که در مرچنت ثبت شده استفاده کن یا آن دامنه را در پنل زیبال اضافه کن.")
                except Exception as e:
                    bot.send_message(ADMIN_ID, f"❌ خطا در درخواست زیبال: {str(e)}")
            else:
                bot.send_message(ADMIN_ID, "⚠️ کاربر پیدا نشد.")
            return

        # اصلاح: اصلاح <user_id> <دلیل>
        m_fix = re.match(r"^اصلاح\s+(\d+)\s+(.+)$", text)
        if m_fix:
            uid = int(m_fix.group(1))
            reason = m_fix.group(2).strip()
            if uid in pending:
                pending[uid]["step"] = "awaiting_info"
                bot.send_message(uid, f"⚠️ پشتیبانی درخواست اصلاح کرد:\n\n{reason}\n\nلطفاً اطلاعات اصلاح‌شده را ارسال کنید (فقط متن).")
                bot.send_message(ADMIN_ID, f"✅ پیام اصلاح برای {uid} ارسال شد.")
                last_target_for_admin = uid
            else:
                bot.send_message(ADMIN_ID, "⚠️ کاربر پیدا نشد.")
            return

        # اگر پیام ادمین هیچکدوم نبود، راهنما بفرست
        return bot.send_message(ADMIN_ID,
            "راهنما برای ادمین:\n"
            "- برای تعیین نرخ سریع: فقط عدد (مثلاً `1250000`) -> برای آخرین درخواست\n"
            "- یا: نرخ <user_id> <rate>\n"
            "- برای تایید نهایی و ارسال لینک پرداخت: تایید <user_id>\n"
            "- برای اصلاح اطلاعات: اصلاح <user_id> <دلیل>"
        )

    # ----- کاربران عادی -----
    if st:
        step = st.get("step")

        # وقتی کاربر مقدار را می‌فرستد (بعد از انتخاب ارز)
        if step == "amount":
            try:
                st["amount"] = float(text.replace(",", "").replace(" ", ""))
            except:
                return bot.reply_to(m, "⚠️ مقدار نامعتبر. فقط عدد مثبت وارد کنید (مثلاً 2500).")
            # تغییر وضعیت به waiting_rate و اطلاع به ادمین
            st["step"] = "waiting_rate"
            bot.send_message(ADMIN_ID,
                f"📩 درخواست جدید از user_id={m.chat.id}\n"
                f"جهت: {st['direction']}\n"
                f"ارز: {st['currency']}\n"
                f"مقدار: {st['amount']}\n\n"
                f"🔹 برای تعیین نرخ سریع: فقط عدد (مثلاً `1250000`) -> برای آخرین درخواست\n"
                f"یا: نرخ {m.chat.id} <نرخ_تومانی>"
            )
            last_target_for_admin = m.chat.id
            bot.send_message(m.chat.id, "✅ درخواست شما ثبت شد و برای ادمین ارسال شد.", reply_markup=main_menu())
            return

        # وقتی ادمین نرخ رو زد و کاربر حالا باید تایید کنه
        if step == "confirm":
            if text in ("✅ تایید", "تایید", "بله", "✅"):
                st["step"] = "awaiting_info"
                direction = st["direction"]
                currency = st.get("currency")
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

        # ذخیرهٔ اطلاعات حساب و ارسال به ادمین برای بررسی
        if step == "awaiting_info":
            # اگر متن شامل لینک/تگ بود، حذف کن و هشدار بده
            if re.search(r"https?://|t\.me|@", text, re.IGNORECASE):
                try:
                    bot.delete_message(m.chat.id, m.message_id)
                except Exception:
                    pass
                return bot.send_message(m.chat.id, "⚠️ لطفاً فقط متن ساده ارسال کنید (بدون لینک یا تگ).")
            st["info"] = text
            st["step"] = None
            awaiting_admin_review.add(m.chat.id)
            bot.send_message(ADMIN_ID,
                f"📦 اطلاعات حساب از user_id={m.chat.id}:\n\n{text}\n\n"
                f"برای تایید بنویس: تایید {m.chat.id}\nیا برای اصلاح بنویس: اصلاح {m.chat.id} <دلیل>"
            )
            bot.send_message(m.chat.id, "✅ اطلاعات شما ارسال شد و در انتظار تایید ادمین است.", reply_markup=main_menu())
            return

    # هیچ مسیر فعالی نبود -> راهنمایی
    return bot.send_message(m.chat.id, "برای شروع «💸 انتقال ارز» را انتخاب کنید.", reply_markup=main_menu())

# ---------------- اجرای همزمان Flask و Bot ----------------
def run_flask():
    # Railway/Heroku/سرویس‌های مشابه متغیر PORT را ست می‌کنند
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

def run_bot():
    # polling با حذف webhook انجام می‌شود (remove_webhook در بالا)
    bot.infinity_polling(timeout=60, long_polling_timeout=30)

if __name__ == "__main__":
    print("✅ Npay bot started")
    threading.Thread(target=run_flask).start()
    run_bot()


