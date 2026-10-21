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
TOKEN = "6162369511:AAEsQxKJiFoTDi4fDbvqThsvPzrIh6ZVTcM"
ADMIN_ID = 6009476963
GROUP_ID = -1004470720510

bot = telebot.TeleBot(TOKEN)

# Безопасные короткие ключи и полные названия регионов
REGIONS = {
    "all": "🌐 Все регионы",
    "tashkent_city": "Ташкент",
    "tashkent_reg": "Ташкентская обл.",
    "samarkand": "Самаркандская обл.",
    "fergana": "Ферганская обл.",
    "andijan": "Андижанская обл.",
    "namangan": "Наманганская обл.",
    "bukhara": "Бухарская обл.",
    "khorezm": "Хорезмская обл.",
    "kashkadarya": "Кашкадарьинская обл.",
    "surkhandarya": "Сурхандарьинская обл.",
    "jizzakh": "Джизакская обл.",
    "syrdarya": "Сырдарьинская обл.",
    "karakalpakstan": "Каракалпакстан"
}

# --- БАЗА ДАННЫХ ---
def init_db():
    conn = sqlite3.connect('shop.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            price REAL NOT NULL,
            description TEXT,
            region TEXT DEFAULT '🌐 Все регионы'
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
def ask_region_catalog(message):
    markup = types.InlineKeyboardMarkup(row_width=1)
    for code, name in REGIONS.items():
        markup.add(types.InlineKeyboardButton(name, callback_data=f"regcat_{code}"))
    
    bot.send_message(message.chat.id, "📍 Выберите ваш регион для просмотра товаров:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('regcat_'))
def show_catalog_by_region(call):
    code = call.data.replace('regcat_', '', 1)
    selected_region = REGIONS.get(code, "🌐 Все регионы")
    
    conn = sqlite3.connect('shop.db')
    cursor = conn.cursor()
    cursor.execute('SELECT id, name, price, description, region FROM products WHERE region = ? OR region = "🌐 Все регионы"', (selected_region,))
    products = cursor.fetchall()
    conn.close()

    bot.answer_callback_query(call.id)
    
    try:
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except Exception:
        pass

    if not products:
        bot.send_message(call.message.chat.id, f"📭 В регионе <b>{selected_region}</b> пока нет доступных товаров.", parse_mode="HTML")
        return

    bot.send_message(call.message.chat.id, f"📦 Актуальные товары для региона: <b>{selected_region}</b>", parse_mode="HTML")

    for prod in products:
        p_id, name, price, desc, prod_region = prod
        formatted_price = f"{int(price):,}".replace(",", " ") if price.is_integer() else f"{price:,.2f}".replace(",", " ")
        
        text = f"<b>{name}</b>\n📍 Регион: {prod_region}\n\nЦена: {formatted_price} сум\nОписание: {desc or 'Отсутствует'}"
        markup = types.InlineKeyboardMarkup()
        
        btn_buy = types.InlineKeyboardButton("🛒 Купить", callback_data=f"buy_{p_id}")
        markup.add(btn_buy)
        
        if call.from_user.id == ADMIN_ID:
            btn_del = types.InlineKeyboardButton("🗑 Удалить товар", callback_data=f"del_{p_id}")
            markup.add(btn_del)
            
        bot.send_message(call.message.chat.id, text, parse_mode="HTML", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('buy_'))
def handle_buy(call):
    prod_id = call.data.split('_')[1]
    conn = sqlite3.connect('shop.db')
    cursor = conn.cursor()
    cursor.execute('SELECT name, price, region FROM products WHERE id = ?', (prod_id,))
    prod = cursor.fetchone()
    conn.close()

    if prod:
        name, price, prod_region = prod
        formatted_price = f"{int(price):,}".replace(",", " ") if price.is_integer() else f"{price:,.2f}".replace(",", " ")
        user_info = f"@{call.from_user.username}" if call.from_user.username else f"ID: {call.from_user.id}"
        
        order_msg = (
            f"🛍 <b>Новый заказ!</b>\n\n"
            f"Товар: {name}\n"
            f"Регион: {prod_region}\n"
            f"Цена: {formatted_price} сум\n"
            f"Покупатель: {user_info} ({call.from_user.first_name})"
        )
        try:
            bot.send_message(GROUP_ID, order_msg, parse_mode="HTML")
        except Exception as e:
            print(f"Ошибка отправки заказа в группу: {e}")

        success_text = (
            f"✅ <b>Заказ успешно оформлен!</b>\n\n"
            f"Вы выбрали: <b>{name}</b>\n"
            f"Сумма к оплате: <b>{formatted_price} сум</b>\n\n"
            f"Менеджер уже получил уведомление и скоро свяжется с вами."
        )
        bot.send_message(call.message.chat.id, success_text, parse_mode="HTML")
        
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except Exception as e:
            print(f"Ошибка удаления сообщения товара: {e}")
            
        bot.answer_callback_query(call.id)
    else:
        bot.answer_callback_query(call.id, "❌ Товар не найден.")

# --- УДАЛЕНИЕ ТОВАРА (ДЛЯ АДМИНА) ---
@bot.callback_query_handler(func=lambda call: call.data.startswith('del_'))
def handle_delete(call):
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "❌ У вас нет прав на это действие.")
        return

    prod_id = call.data.split('_')[1]
    conn = sqlite3.connect('shop.db')
    cursor = conn.cursor()
    cursor.execute('DELETE FROM products WHERE id = ?', (prod_id,))
    conn.commit()
    conn.close()

    bot.answer_callback_query(call.id, "🗑 Товар успешно удален!")
    try:
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except Exception as e:
        print(f"Ошибка удаления сообщения: {e}")

# --- ДОБАВЛЕНИЕ ТОВАРА (АДМИН С ВЫБОРОМ РЕГИОНА) ---
user_states = {}

@bot.message_handler(func=lambda message: message.text == "➕ Добавить товар")
def add_product_start(message):
    if message.from_user.id != ADMIN_ID:
        return
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    for code, name in REGIONS.items():
        markup.add(types.InlineKeyboardButton(name, callback_data=f"addreg_{code}"))
        
    bot.send_message(message.chat.id, "📍 Выберите регион, для которого предназначен товар:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('addreg_'))
def add_product_region_chosen(call):
    if call.from_user.id != ADMIN_ID:
        return
        
    code = call.data.replace('addreg_', '', 1)
    chosen_region = REGIONS.get(code, "🌐 Все регионы")
    
    user_states[call.message.chat.id] = {'step': 'name', 'region': chosen_region}
    
    bot.answer_callback_query(call.id)
    bot.send_message(call.message.chat.id, f"Выбран регион: <b>{chosen_region}</b>\n\nВведите название товара:", parse_mode="HTML")

@bot.message_handler(func=lambda message: message.chat.id in user_states)
def add_product_steps(message):
    state = user_states[message.chat.id]
    step = state.get('step')

    if step == 'name':
        state['name'] = message.text
        state['step'] = 'price'
        bot.send_message(message.chat.id, "Введите цену товара в сумах (цифрами, например 50000):")

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
            'INSERT INTO products (name, price, description, region) VALUES (?, ?, ?, ?)',
            (state['name'], state['price'], state['description'], state['region'])
        )
        conn.commit()
        conn.close()
        
        del user_states[message.chat.id]
        bot.send_message(message.chat.id, f"✅ Товар успешно добавлен в регион: <b>{state['region']}</b>!", parse_mode="HTML")

# --- ЗАПУСК ПОТОКОВ ---
if __name__ == '__main__':
    threading.Thread(target=run_flask, daemon=True).start()
    bot.infinity_polling()
    
