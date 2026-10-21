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
TOKEN = "6162369511:AAGBtBJI3u3b3JvsBYZlttjV67nj-gt2aLg"
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
        
        # 1. Отправляем уведомление администраторам в группу
        order_msg = (
            f"🛍 <b>Новый заказ!</b>\n\n"
            f"Товар: {name}\n"
            f"Цена: {price} руб.\n"
            f"Покупатель: {user_info} ({call.from_user.first_name})"
        )
        try:
            bot.send_message(GROUP_ID, order_msg, parse_mode="HTML")
        except Exception as e:
            print(f"Ошибка отправки заказа в группу: {e}")

        # 2. Отправляем клиенту заметное сообщение прямо в чат (вместо маленького окошка сверху)
        success_text = (
            f"✅ <b>Заказ успешно оформлен!</b>\n\n"
            f"Вы выбрали: <b>{name}</b>\n"
            f"Сумма к оплате: <b>{price} руб.</b>\n\n"
            f"Менеджер уже получил уведомление и скоро свяжется с вами."
        )
        bot.send_message(call.message.chat.id, success_text, parse_mode="HTML")

        # 3. Гасим анимацию загрузки на самой кнопке
        bot.answer_callback_query(call.id)
    else:
        bot.answer_callback_query(call.id, "❌ Товар не найден.")
)

# --- ДОБАВЛЕНИЕ ТОВАРА (АДМИН) ---
user_states = {}

@bot.message_handler(func=lambda message: message.text == "➕ Добавить товар")
def add_product_start(message):
    if message.from_user.id != ADMIN_ID:
        return
    user_states[message.chat.id] = {'step': 'name'}
    bot.send_message(message.chat.id, "Введите название товара:")

@bot.message_handler(func=lambda message: message.chat.id in user_states)
def add_product_steps(message):
    state = user_states[message.chat.id]
    step = state.get('step')

    if step == 'name':
        state['name'] = message.text
        state['step'] = 'price'
        bot.send_message(message.chat.id, "Введите цену товара (цифрами):")

    elif step == 'price':
        try:
            price = float(message.text)
            state['price'] = price
            state['step'] = 'description'
            bot.send_message(message.chat.id, "Введите описание товара:")
        except ValueError:
            bot.send_message(message.chat.id, "Пожалуйста, введите корректное число для цены.")

    elif step == 'description':
        state['description'] = message.text
        conn = sqlite3.connect('shop.db')
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO products (name, price, description) VALUES (?, ?, ?)',
            (state['name'], state['price'], state['description'])
        )
        conn.commit()
        conn.close()
        
        del user_states[message.chat.id]
        bot.send_message(message.chat.id, "✅ Товар успешно добавлен в каталог!")

# --- ЗАПУСК ПОТОКОВ ---
if __name__ == '__main__':
    # Запускаем Flask в отдельном потоке
    threading.Thread(target=run_flask, daemon=True).start()
    # Запускаем бота
    bot.infinity_polling()
    
