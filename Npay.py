import os
import telebot
import requests

# ----------- تنظیمات -----------
BOT_TOKEN = os.getenv("BOT_TOKEN", "8589520464:AAE3x1LjHw0wWepIX6bJePQ_d0z9AXB-1t4")
MERCHANT = os.getenv("MERCHANT", "67fbd99f6f3803001057a0bf")

bot = telebot.TeleBot(BOT_TOKEN)

# ----------- دستورات ربات -----------
@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message, "سلام 👋 به ربات پرداخت نوسان‌پی خوش اومدی.\nبرای پرداخت تستی دستور /pay رو بفرست 💳")

@bot.message_handler(commands=['pay'])
def pay(message):
    amount =
