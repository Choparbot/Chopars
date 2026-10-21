import sqlite3
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

TOKEN = '8550204424:AAEm7K6hHD5yKpP6U2DrkIMSI7e-h2vpYI4'
ADMIN_ID = 6009476963
GROUP_ID = -1004470720510

bot = telebot.TeleBot(TOKEN)
user_data = {}

# Инициализация базы данных
def init_db():
    conn = sqlite3.connect('shop.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title_ru TEXT,
            title_uz TEXT,
            price REAL,
            photo TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# Команда /start
@bot.message_handler(commands=['start'])
def send_welcome(message):
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🛍 Открыть каталог", callback_data="show_catalog"))

    if message.from_user.id == ADMIN_ID:
        markup.add(InlineKeyboardButton("➕ Добавить товар (Admin)", callback_data="start_add"))

    bot.send_message(
        message.chat.id,
        "Привет! Добро пожаловать в наш магазин. Выберите действие:",
        reply_markup=markup
    )

# Начало добавления товара
@bot.callback_query_handler(func=lambda call: call.data == "start_add")
@bot.message_handler(commands=['add'])
def cmd_add(message_or_call):
    chat_id = message_or_call.message.chat.id if hasattr(message_or_call, 'message') else message_or_call.chat.id
    user_id = message_or_call.from_user.id

    if hasattr(message_or_call, 'data'):
        bot.answer_callback_query(message_or_call.id)

    if user_id != ADMIN_ID:
        bot.send_message(chat_id, "⛔ У вас нет прав администратора для добавления товаров.")
        return

    user_data[chat_id] = {}
    bot.send_message(chat_id, "Введите название товара на русском языке:")
    bot.register_next_step_handler_by_chat_id(chat_id, process_title_ru)

def process_title_ru(message):
    chat_id = message.chat.id
    user_data[chat_id]['title_ru'] = message.text
    bot.send_message(chat_id, "Введите название товара на узбекском языке:")
    bot.register_next_step_handler_by_chat_id(chat_id, process_title_uz)

def process_title_uz(message):
    chat_id = message.chat.id
    user_data[chat_id]['title_uz'] = message.text
    bot.send_message(chat_id, "Введите цену товара (только число, например: 15000):")
    bot.register_next_step_handler_by_chat_id(chat_id, process_price)

def process_price(message):
    chat_id = message.chat.id
    try:
        price = float(message.text)
        user_data[chat_id]['price'] = price
        bot.send_message(chat_id, "Отправьте фотографию для этого товара:")
        bot.register_next_step_handler_by_chat_id(chat_id, process_photo)
    except ValueError:
        bot.send_message(chat_id, "❌ Цена должна быть числом. Попробуйте снова ввести цену:")
        bot.register_next_step_handler_by_chat_id(chat_id, process_price)

def process_photo(message):
    chat_id = message.chat.id
    if not message.photo:
        bot.send_message(chat_id, "❌ Пожалуйста, отправьте именно картинку (фотографию):")
        bot.register_next_step_handler_by_chat_id(chat_id, process_photo)
        return

    photo_id = message.photo[-1].file_id
    data = user_data[chat_id]

    conn = sqlite3.connect('shop.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO products (title_ru, title_uz, price, photo)
        VALUES (?, ?, ?, ?)
    ''', (data['title_ru'], data['title_uz'], data['price'], photo_id))
    conn.commit()
    conn.close()

    bot.send_message(chat_id, "✅ Товар успешно добавлен в базу данных!")

    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🛍 Открыть каталог", callback_data="show_catalog"))
    if chat_id == ADMIN_ID:
        markup.add(InlineKeyboardButton("➕ Добавить еще товар", callback_data="start_add"))
    bot.send_message(chat_id, "Выберите дальнейшее действие:", reply_markup=markup)

# Просмотр каталога
@bot.callback_query_handler(func=lambda call: call.data == "show_catalog")
def show_catalog(call):
    conn = sqlite3.connect('shop.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM products')
    products = cursor.fetchall()
    conn.close()

    if not products:
        bot.answer_callback_query(call.id, "Каталог пока пуст!")
        bot.send_message(call.message.chat.id, "📭 В каталоге пока нет товаров.")
        return

    bot.answer_callback_query(call.id)

    for p in products:
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🛒 Купить", callback_data=f"buy_{p['id']}"))

        if call.from_user.id == ADMIN_ID:
            markup.add(InlineKeyboardButton("❌ Удалить товар", callback_data=f"del_{p['id']}"))

        caption = f"📦 <b>{p['title_ru']}</b>\n🇺🇿 {p['title_uz']}\n💰 <b>{p['price']} сум</b>"

        if p['photo']:
            bot.send_photo(call.message.chat.id, p['photo'], caption=caption, parse_mode='HTML', reply_markup=markup)
        else:
            bot.send_message(call.message.chat.id, caption, parse_mode='HTML', reply_markup=markup)

# Удаление товара администратором
@bot.callback_query_handler(func=lambda call: call.data.startswith('del_'))
def process_delete(call):
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "⛔ У вас нет прав!", show_alert=True)
        return

    product_id = call.data.split('_')[1]

    conn = sqlite3.connect('shop.db')
    cursor = conn.cursor()
    cursor.execute('DELETE FROM products WHERE id = ?', (product_id,))
    conn.commit()
    conn.close()

    bot.answer_callback_query(call.id, "Товар удален!")
    try:
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except Exception:
        pass
    bot.send_message(call.message.chat.id, f"🗑 Товар успешно удален из каталога.")

# Обработка покупки (отправка в группу)
@bot.callback_query_handler(func=lambda call: call.data.startswith('buy_'))
def process_buy(call):
    product_id = call.data.split('_')[1]

    conn = sqlite3.connect('shop.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM products WHERE id = ?', (product_id,))
    product = cursor.fetchone()
    conn.close()

    if not product:
        bot.answer_callback_query(call.id, "Товар не найден!", show_alert=True)
        return

    user = call.from_user
    username = f"@{user.username}" if user.username else "нет username"
    full_name = f"{user.first_name or ''} {user.last_name or ''}".strip()

    order_text = (
        f"🚨 **НОВЫЙ ЗАКАЗ!** (#id{product['id']})\n\n"
        f"📦 Товар: <b>{product['title_ru']}</b>\n"
        f"🇺🇿 Узб: {product['title_uz']}\n"
        f"💰 Цена: <b>{product['price']} сум</b>\n\n"
        f"👤 Покупатель: {full_name} ({username})\n"
        f"🆔 Telegram ID: <code>{user.id}</code>"
    )

    try:
        bot.send_message(GROUP_ID, order_text, parse_mode='HTML')
    except Exception as e:
        print(f"Ошибка отправки в группу: {e}")

    bot.answer_callback_query(call.id, "Заказ успешно оформлен!")
    bot.send_message(
        call.message.chat.id,
        "✅ **Спасибо за заказ!** Мы получили вашу заявку, скоро менеджер свяжется с вами для уточнения деталей.",
        parse_mode='HTML'
    )

if __name__ == '__main__':
    print("Бот запущен...")
    bot.infinity_polling()
