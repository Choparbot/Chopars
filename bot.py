import os
import sqlite3
import threading
from flask import Flask
import telebot
from telebot import types

# === НАСТРОЙКИ FLASK СЕРВЕРА ДЛЯ RENDER ===
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

# === НАСТРОЙКИ TELEGRAM БОТА ===
TOKEN = "8550204424:AAEm7K6hHD5yKpP6U2DrkIMSI7e-h2vpYI4"
ADMIN_ID = 6009476963
GROUP_ID = -1004470720510

bot = telebot.TeleBot(TOKEN)

# --- БАЗА ДАННЫХ ---
def init_db():
    conn = sqlite3.connect('shop.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            price REAL NOT NULL,
            description TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# --- ОБРАБОТЧИКИ КОМАНД ---
@bot.message_handler(commands=['start'])
def send_welcome(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    item1 = types.KeyboardButton("📦 Каталог товаров")
    markup.add(item1)
    
    if message.from_user.id == ADMIN_ID:
        item2 = types.KeyboardButton("➕ Добавить товар")
        markup.add(item2)
        
    bot.send_message(
        message.chat.id, 
        f"Привет, {message.from_user.first_name}! Добро пожаловать в наш магазин.", 
        reply_markup=markup
    )

@bot.message_handler(func=lambda message: message.text == "📦 Каталог товаров")
def show_catalog(message):
    conn = sqlite3.connect('shop.db')
    cursor = conn.cursor()
    cursor.execute('SELECT id, name, price, description FROM products')
    products = cursor.fetchall()
    conn.close()

    if not products:
        bot.send_message(message.chat.id, "В каталоге пока нет товаров.")
        return

    for prod in products:
        p_id, name, price, desc = prod
        text = f"<b>{name}</b>\n\nЦена: {price} руб.\nОписание: {desc or 'Отсутствует'}"
        markup = types.InlineKeyboardMarkup()
        btn = types.InlineKeyboardButton("🛒 Купить", callback_data=f"buy_{p_id}")
        markup.add(btn)
        bot.send_message(message.chat.id, text, parse_mode="HTML", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('buy_'))
def handle_buy(call):
    prod_id = call.data.split('_')[1]
    conn = sqlite3.connect('shop.db')
    cursor = conn.cursor()
    cursor.execute('SELECT name, price FROM products WHERE id = ?', (prod_id,))
    prod = cursor.fetchone()
    conn.close()

    if prod:
        name, price = prod
        user_info = f"@{call.from_user.username}" if call.from_user.username else f"ID: {call.from_user.id}"
        order_msg = (
            f
        
