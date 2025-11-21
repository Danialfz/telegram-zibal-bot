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

# pending[user_id] = {
#   "direction": "خرید" یا "فروش",
#   "step": one of ("currency","amount","waiting_rate","confirm","awaiting_info","awaiting_correction","awaiting_manual_payment","awaiting_receipt"),
#   "currency": "USD", "amount": float, "rate": float, "total": int (toman), "info": str
# }
pending = {}

# support_chat:
# for normal users: support_chat[user_id] = True (means user is in support mode)
# for admin: support_chat[ADMIN_ID] = target_user_id (means admin is chatting with that user)
support_chat = {}

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
    # amount expected in Toman (integer), convert to Rial internally
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
    bot.send_message(m.chat.id, "سلام 👋 برای شروع یکی از گزینه‌های زیر را انتخاب کنید:", reply_markup=main_menu())

@bot.message_handler(func=lambda m: m.text == "💸 انتقال ارز")
def start_transfer(m):
    bot.send_message(m.chat.id, "جهت انتقال را انتخاب کنید:", reply_markup=direction_menu())

@bot.message_handler(func=lambda m: m.text == "💬 پیام به پشتیبانی")
def start_support(m):
    support_chat[m.chat.id] = True
    bot.send_message(m.chat.id, "✉️ لطفاً پیام یا تصویر خود را ارسال کنید.\nبرای پایان، روی «🔚 پایان پیام‌رسانی» بزنید.", reply_markup=support_keyboard())
    bot.send_message(ADMIN_ID, f"📩 کاربر {m.chat.id} گفتگو با پشتیبانی را آغاز کرد.")

@bot.message_handler(func=lambda m: m.text == "🔚 پایان پیام‌رسانی")
def end_support(m):
    if m.chat.id in support_chat:
        support_chat.pop(m.chat.id, None)
        bot.send_message(m.chat.id, "✅ گفت‌وگو با پشتیبانی پایان یافت.", reply_markup=main_menu())
        bot.send_message(ADMIN_ID, f"🔕 کاربر {m.chat.id} گفت‌وگو را پایان داد.")
    else:
        bot.send_message(m.chat.id, "شما در حالت پیام‌رسانی نیستید.", reply_markup=main_menu())

# یک handler متمرکز برای متن‌ها و عکس‌ها
@bot.message_handler(content_types=["text", "photo"])
def main_handler(m):
    chat_id = m.chat.id
    text = (m.text or "").strip()
    content_type = m.content_type
    st = pending.get(chat_id)

    # دکمه بازگشت کلی
    if text == "🔙 بازگشت":
        pending.pop(chat_id, None)
        return start(m)

    # ---- بخش ادمین ----
    if chat_id == ADMIN_ID:
        # دستور نرخ: نرخ <user_id> <rate_in_toman>
        m_rate = re.match(r"^نرخ\s+(\d+)\s+([\d.,]+)$", text)
        if m_rate:
            uid = int(m_rate.group(1))
            try:
                rate_raw = m_rate.group(2).replace(",", "")
                rate = float(rate_raw)  # تومان به ازای هر واحد ارز
            except:
                return bot.send_message(ADMIN_ID, "فرمت نرخ نامعتبر است. مثال: نرخ 123456789 150000")
            if uid in pending and pending[uid].get("step") == "waiting_rate":
                amount = pending[uid]["amount"]
                total_toman = int(amount * rate)
                pending[uid].update({"rate": rate, "total": total_toman, "step": "confirm"})
                bot.send_message(uid, f"💰 مجموع پرداختی: {total_toman:,} تومان\nتایید می‌کنید؟", reply_markup=confirm_keyboard())
                bot.send_message(ADMIN_ID, f"✅ نرخ {rate:,} تومان برای کاربر {uid} ثبت شد. مجموع: {total_toman:,} تومان")
                global last_target_for_admin
                last_target_for_admin = uid
            else:
                bot.send_message(ADMIN_ID, "کاربر مورد نظر برای تعیین نرخ در وضعیت مناسب نیست.")
            return

        # تایید نهایی admin-triggered
        m_confirm_admin = re.match(r"^تایید\s+(\d+)$", text)
        if m_confirm_admin:
            uid = int(m_confirm_admin.group(1))
            if uid not in pending:
                return bot.send_message(ADMIN_ID, "کاربر پیدا نشد.")
            data = pending[uid]
            total = data.get("total", 0)
            direction = data.get("direction")

            if direction == "خرید":
                # ایجاد لینک پرداخت: total (تومان) -> تبدیل به ریال
                try:
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
                except Exception as e:
                    bot.send_message(ADMIN_ID, f"❌ خطا در تماس با زیبال: {e}")
                return

            elif direction == "فروش":
                # برای فروش: به کاربر اعلام می‌کنیم منتظر اطلاعات حساب از طرف پشتیبانی باشد
                bot.send_message(uid, "✅ اطلاعات تایید شد.\n\n💬 منتظر پیام پشتیبانی باشید تا اطلاعات واریز برای شما ارسال شود.")
                bot.send_message(ADMIN_ID,
                                 f"📦 کاربر {uid} مسیر فروش را تایید کرد.\n"
                                 f"لطفاً اطلاعات حساب دریافت وجه را برای او ارسال کنید.\n"
                                 f"(هر متنی بفرستید برای او قالب‌بندی و ارسال خواهد شد.)")
                pending[uid]["step"] = "awaiting_manual_payment"
                last_target_for_admin = uid
                return

        # درخواست اصلاح اطلاعات
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

        # ادمین شروع گفت‌وگو پشتیبانی: پیام <user_id>
        start_msg = re.match(r"^پیام\s+(\d+)$", text)
        if start_msg:
            uid = int(start_msg.group(1))
            support_chat[ADMIN_ID] = uid
            bot.send_message(ADMIN_ID, f"✅ گفت‌وگو با کاربر {uid} آغاز شد. برای پایان بنویس: پایان {uid}")
            last_target_for_admin = uid
            return

        # ادمین پایان گفت‌وگو پشتیبانی: پایان <user_id>
        end_msg = re.match(r"^پایان\s+(\d+)$", text)
        if end_msg:
            uid = int(end_msg.group(1))
            if support_chat.get(ADMIN_ID) == uid:
                support_chat.pop(ADMIN_ID, None)
                bot.send_message(ADMIN_ID, f"🔚 گفت‌وگو با کاربر {uid} پایان یافت.")
                bot.send_message(uid, "🔕 گفت‌وگو توسط پشتیبانی پایان یافت.", reply_markup=main_menu())
            else:
                bot.send_message(ADMIN_ID, "شما در حال گفتگو با این کاربر نیستید.")
            return

        # اگر admin در حالت پاسخ‌دهی به کاربر است (support_chat[ADMIN_ID] = uid)
        if support_chat.get(ADMIN_ID):
            uid = support_chat[ADMIN_ID]
            # اگر admin عکس بفرستد
            if content_type == "photo":
                bot.send_photo(uid, m.photo[-1].file_id, caption="📩 پیام از پشتیبانی")
            else:
                bot.send_message(uid, f"📩 پیام از پشتیبانی:\n\n{text}")
            bot.send_message(ADMIN_ID, "✅ پیام ارسال شد.")
            return

        # اگر admin باید اطلاعات حساب برای کاربر فروشنده بفرستد (awaiting_manual_payment)
        if last_target_for_admin and last_target_for_admin in pending and pending[last_target_for_admin].get("step") == "awaiting_manual_payment":
            # admin هر متنی که بفرستد به قالب "اطلاعات حساب جهت واریز" تبدیل می‌شود
            info_text = f"💳 اطلاعات حساب جهت واریز:\n{text}\n\n📸 بعد از واریز، متن یا اسکرین‌شات واریز را ارسال کنید."
            bot.send_message(last_target_for_admin, info_text)
            bot.send_message(ADMIN_ID, "✅ اطلاعات حساب برای کاربر ارسال شد و منتظر رسید واریز است.")
            # تغییر وضعیت کاربر به awaiting_receipt
            pending[last_target_for_admin]["step"] = "awaiting_receipt"
            return

        # اگر admin هر پیام دیگری فرستاد که توسط موارد بالا هندل نشده، فقط پاسخ ده
        return

    # ---- بخش کاربر ----

    # حالت پشتیبانی کاربر (send to admin)
    if chat_id in support_chat and chat_id != ADMIN_ID:
        if content_type == "photo":
            bot.send_photo(ADMIN_ID, m.photo[-1].file_id, caption=f"💬 پیام تصویری از کاربر {chat_id}")
        else:
            bot.send_message(ADMIN_ID, f"💬 پیام از کاربر {chat_id}:\n{text}")
        bot.send_message(chat_id, "✅ پیام شما ارسال شد.", reply_markup=support_keyboard())
        return

    # حالت awaiting_receipt (کاربر باید رسید واریز ارسال کند) — مربوط به مسیر فروش است
    if st and st.get("step") == "awaiting_receipt":
        if content_type == "photo":
            bot.send_photo(ADMIN_ID, m.photo[-1].file_id, caption=f"📥 رسید واریز از کاربر {chat_id}")
        else:
            bot.send_message(ADMIN_ID, f"📥 رسید واریز از کاربر {chat_id}:\n{text}")
        bot.send_message(chat_id, "✅ پیام شما ارسال شد و به‌زودی به تراکنش شما رسیدگی خواهد شد.", reply_markup=main_menu())
        # پس از ارسال رسید، پرونده کاربر بسته می‌شود
        pending.pop(chat_id, None)
        return

    # اگر پیام انتخاب خرید/فروش (ممکنه کاربر دکمه زده باشه)
    if text in ["🟢 خرید", "🔴 فروش"]:
        direction = "خرید" if "خرید" in text else "فروش"
        pending[chat_id] = {"direction": direction, "step": "currency"}
        kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        for c, n in currencies.items():
            kb.add(f"{n} ({c})")
        kb.add("🔙 بازگشت")
        bot.send_message(chat_id, "ارز مورد نظر را انتخاب کنید:", reply_markup=kb)
        return

    # اگر کاربر در جریان انتقال است، به تابع پردازش جریان انتقال واگذار می‌کنیم
    if st:
        return handle_transfer_flow(m)

    # اگر هیچ وضعیتی نداشت، منو نمایش داده شود
    bot.send_message(chat_id, "برای شروع «💸 انتقال ارز» یا «💬 پیام به پشتیبانی» را انتخاب کنید.", reply_markup=main_menu())

def handle_transfer_flow(m):
    chat_id = m.chat.id
    text = (m.text or "").strip()
    content_type = m.content_type
    st = pending.get(chat_id)
    if not st:
        return

    step = st.get("step")

    # برگشت کلی
    if text == "🔙 بازگشت":
        pending.pop(chat_id, None)
        return start(m)

    if step == "currency":
        match = re.search(r"\(([A-Z]{3})\)", text)
        if match:
            code = match.group(1)
            st["currency"] = code
            st["step"] = "amount"
            return bot.send_message(chat_id, f"مقدار {currencies.get(code)} را وارد کنید (مثلاً 2500):")

    elif step == "amount":
        try:
            st["amount"] = float(text.replace(",", ""))
        except:
            return bot.reply_to(m, "عدد معتبر وارد کنید.")
        st["step"] = "waiting_rate"
        # اطلاع به ادمین برای تعیین نرخ واحد (به تومان)
        bot.send_message(ADMIN_ID,
            f"📩 درخواست جدید:\nuser_id={chat_id}\nجهت: {st['direction']}\nارز: {st['currency']}\nمقدار: {st['amount']}\n\n"
            f"برای تعیین نرخ بنویس: نرخ {chat_id} <نرخ_واحد_تومان>\nمثال: نرخ {chat_id} 150000")
        return bot.send_message(chat_id, "✅ درخواست شما ثبت شد و برای ادمین ارسال شد.")

    elif step == "confirm":
        if text in ("✅ تایید", "تایید", "بله"):
            st["step"] = "awaiting_info"
            if st["direction"] == "خرید":
                info_text = currency_info_template.get(st["currency"], "👤 اطلاعات گیرنده را وارد کنید:")
            else:
                info_text = "👤 لطفاً اطلاعات فرستنده و گیرنده را وارد کنید (نام و شماره حساب در خارج از کشور برای فرستنده / نام و شماره حساب گیرنده در داخل کشور)"
            bot.send_message(chat_id, f"لطفاً اطلاعات زیر را ارسال کنید:\n\n{info_text}")
        elif text in ("❌ لغو", "لغو"):
            pending.pop(chat_id, None)
            bot.send_message(chat_id, "درخواست لغو شد.", reply_markup=main_menu())
        return

    elif step in ("awaiting_info", "awaiting_correction"):
        # کاربر اطلاعات حساب گیرنده/فرستنده را ارسال می‌کند
        st["info"] = text
        st["step"] = None
        bot.send_message(ADMIN_ID, f"📦 اطلاعات حساب از کاربر {chat_id}:\n\n{text}\n\nبرای تایید بنویس: تایید {chat_id}\nیا در صورت نیاز به اصلاح بنویس: اصلاح {chat_id} <دلیل>")
        bot.send_message(chat_id, "✅ اطلاعات شما ارسال شد و در انتظار بررسی ادمین است.")
        return

    # هیچکدام از موارد بالا: پیام غیرمرتبط در جریان انتقال
    bot.send_message(chat_id, "در حال حاضر منتظر اقدامات ادمین هستید یا گزینه نامعتبر ارسال کردید.", reply_markup=main_menu())

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

