import telebot
import random
from telebot import types
import time
import json
import os
import threading
import atexit

bot = telebot.TeleBot("8257595632:AAHmrxOUf7qeRXHnsC-uPYbkRA2Q7lYI2ow")

# ID администратора (замените на свой)
ADMIN_ID = 5180925759

# Файл для сохранения данных
DATA_FILE = 'user_data.json'
data_lock = threading.Lock()

# Глобальные переменные
user_data = {}       # словарь пользователей {user_id: данные}
promocodes = {}      # словарь промокодов {code: данные}

def load_user_data():
    """Загружает данные из файла, поддерживает старый и новый формат."""
    global user_data, promocodes
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Проверяем, новый это формат (с ключами 'users' и 'promocodes') или старый
            if isinstance(data, dict) and 'users' in data and 'promocodes' in data:
                # Новый формат
                users_raw = data.get('users', {})
                user_data = {int(k): v for k, v in users_raw.items()}
                promocodes = data.get('promocodes', {})
                print(f"Загружен новый формат: пользователей {len(user_data)}, промокодов {len(promocodes)}")
            else:
                # Старый формат (только пользователи)
                user_data = {int(k): v for k, v in data.items()}
                promocodes = {}
                print(f"Загружен старый формат (конвертирован): пользователей {len(user_data)}")
        else:
            print("Файл данных не найден. Будет создан новый при сохранении.")
            user_data = {}
            promocodes = {}
    except (json.JSONDecodeError, FileNotFoundError, ValueError) as e:
        print(f"Ошибка загрузки данных: {e}. Создаём пустые структуры.")
        user_data = {}
        promocodes = {}

def save_user_data():
    """Сохраняет данные в файл в новом формате."""
    try:
        data = {
            'users': user_data,
            'promocodes': promocodes
        }
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"Данные сохранены. Пользователей: {len(user_data)}, промокодов: {len(promocodes)}")
    except Exception as e:
        print(f"Ошибка при сохранении данных: {e}")

def auto_save():
    while True:
        time.sleep(60)
        with data_lock:
            save_user_data()

# Загружаем данные
with data_lock:
    load_user_data()
    print(f"Загружено пользователей: {len(user_data)}, промокодов: {len(promocodes)}")

# Автосохранение
save_thread = threading.Thread(target=auto_save, daemon=True)
save_thread.start()

# ----- Клавиатуры -----
main_markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
main_markup.add(
    types.KeyboardButton("🎮 Кликер"),
    types.KeyboardButton("💰 Баланс"),
    types.KeyboardButton("🛒 Магазин"),
    types.KeyboardButton("🏆 Топ")
)

clicker_markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
clicker_markup.add(
    types.KeyboardButton("🖱️ Клик!"),
    types.KeyboardButton("🔙 Назад")
)

# ----- Функция топа -----
def send_top(chat_id):
    with data_lock:
        users = []
        for uid, data in user_data.items():
            balance = data.get('balance', 0)
            if data.get('username'):
                name = '@' + data['username']
            else:
                name = data.get('first_name', f'User{uid}')
            users.append((uid, balance, name))
    
    users.sort(key=lambda x: x[1], reverse=True)
    top = users[:10]
    
    if not top:
        bot.send_message(chat_id, "🏆 Пока нет игроков с балансом.")
        return
    
    text = "🏆 <b>Топ игроков по балансу:</b>\n\n"
    for i, (_, bal, name) in enumerate(top, 1):
        text += f"{i}. {name} — {bal} монет\n"
    
    bot.send_message(chat_id, text, parse_mode='html')

# ----- Обработчики команд -----
@bot.message_handler(commands=['start'])
def welcome(message):
    user_id = message.from_user.id
    with data_lock:
        if user_id not in user_data:
            user_data[user_id] = {
                'balance': 0,
                'per_click': 1,
                'double_cost': 1500,
                'stars': 0,                     # поле для звёзд
                'username': message.from_user.username,
                'first_name': message.from_user.first_name,
                'last_name': message.from_user.last_name,
                'total_clicks': 0,
                'registered': time.strftime("%Y-%m-%d %H:%M:%S"),
                'last_bonus': None
            }
            save_user_data()
    
    user = user_data[user_id]
    # Для старых пользователей – добавим недостающие поля
    if 'double_cost' not in user:
        user['double_cost'] = 1500
    if 'last_bonus' not in user:
        user['last_bonus'] = None
    if 'stars' not in user:
        user['stars'] = 0
    save_user_data()
    
    bot.send_message(
        message.chat.id,
        f"👋 Добро пожаловать, {message.from_user.first_name}!\n"
        f"🎮 Это игра-кликер!\n\n"
        f"💰 Твой баланс: {user['balance']} монет\n"
        f"⚡ За клик: {user['per_click']} монет\n"
        f"💡 Используй /help для списка команд.",
        parse_mode='html',
        reply_markup=main_markup
    )

@bot.message_handler(commands=['help'])
def help_command(message):
    text = (
        "📋 <b>Список доступных команд:</b>\n\n"
        "/start — начать игру / перезапустить\n"
        "/top — топ игроков по балансу\n"
        "/activate [код] — активировать промокод\n"
        "/mystars — узнать свой баланс звёзд\n"
        "/resetprogress [user_id] — сбросить прогресс другого игрока (10 звёзд)\n"
        "/donate — информация о донате для получения звёзд\n"
        "/help — это сообщение\n\n"
        "🎮 Также используйте кнопки в меню для навигации."
    )
    bot.send_message(message.chat.id, text, parse_mode='html')

@bot.message_handler(commands=['donate'])
def donate_command(message):
    text = (
        "⭐ <b>Поддержка проекта</b>\n\n"
        "Чтобы получить 10 звёзд (достаточно для сброса прогресса любого игрока), "
        "отправьте 10 рублей по номеру телефона <b>+79129692303</b> на банк ВТБ.\n\n"
        "После перевода напишите администратору (обычно в течение суток звёзды будут начислены).\n"
        "Спасибо за поддержку! ❤️"
    )
    bot.send_message(message.chat.id, text, parse_mode='html')

@bot.message_handler(commands=['top'])
def top_command(message):
    send_top(message.chat.id)

@bot.message_handler(commands=['backup'])
def backup_command(message):
    if message.from_user.id == ADMIN_ID:
        with data_lock:
            backup_file = f"backup_{int(time.time())}.json"
            with open(backup_file, 'w', encoding='utf-8') as f:
                json.dump(user_data, f, ensure_ascii=False, indent=2)
        bot.send_message(
            message.chat.id,
            f"✅ Резервная копия создана: {backup_file}\n"
            f"Всего пользователей: {len(user_data)}"
        )
    else:
        bot.send_message(message.chat.id, "❌ У вас нет прав для этой команды")

# ----- Административные команды для управления пользователями -----
@bot.message_handler(commands=['setbalance'])
def set_balance(message):
    if message.from_user.id != ADMIN_ID:
        bot.send_message(message.chat.id, "❌ У вас нет прав для этой команды")
        return
    args = message.text.split()
    if len(args) != 3:
        bot.send_message(message.chat.id, "❌ Использование: /setbalance <user_id> <сумма>")
        return
    try:
        target_id = int(args[1])
        amount = int(args[2])
    except ValueError:
        bot.send_message(message.chat.id, "❌ ID пользователя и сумма должны быть числами")
        return

    with data_lock:
        if target_id not in user_data:
            bot.send_message(message.chat.id, f"❌ Пользователь с ID {target_id} не найден")
            return
        user_data[target_id]['balance'] = amount
        save_user_data()
    bot.send_message(message.chat.id, f"✅ Баланс пользователя {target_id} установлен на {amount} монет")

@bot.message_handler(commands=['addbalance'])
def add_balance(message):
    if message.from_user.id != ADMIN_ID:
        bot.send_message(message.chat.id, "❌ У вас нет прав для этой команды")
        return
    args = message.text.split()
    if len(args) != 3:
        bot.send_message(message.chat.id, "❌ Использование: /addbalance <user_id> <сумма> (может быть отрицательной)")
        return
    try:
        target_id = int(args[1])
        amount = int(args[2])
    except ValueError:
        bot.send_message(message.chat.id, "❌ ID пользователя и сумма должны быть числами")
        return

    with data_lock:
        if target_id not in user_data:
            bot.send_message(message.chat.id, f"❌ Пользователь с ID {target_id} не найден")
            return
        user_data[target_id]['balance'] += amount
        save_user_data()
    bot.send_message(message.chat.id, f"✅ Баланс пользователя {target_id} изменён на {amount}. Текущий: {user_data[target_id]['balance']} монет")

@bot.message_handler(commands=['setperclick'])
def set_perclick(message):
    if message.from_user.id != ADMIN_ID:
        bot.send_message(message.chat.id, "❌ У вас нет прав для этой команды")
        return
    args = message.text.split()
    if len(args) != 3:
        bot.send_message(message.chat.id, "❌ Использование: /setperclick <user_id> <количество за клик>")
        return
    try:
        target_id = int(args[1])
        amount = int(args[2])
    except ValueError:
        bot.send_message(message.chat.id, "❌ ID пользователя и количество должны быть числами")
        return

    if amount < 1:
        bot.send_message(message.chat.id, "❌ Количество за клик должно быть не менее 1")
        return

    with data_lock:
        if target_id not in user_data:
            bot.send_message(message.chat.id, f"❌ Пользователь с ID {target_id} не найден")
            return
        user_data[target_id]['per_click'] = amount
        save_user_data()
    bot.send_message(message.chat.id, f"✅ Доход за клик пользователя {target_id} установлен на {amount} монет")

# ----- Команды для управления звёздами (админ) -----
@bot.message_handler(commands=['addstars'])
def add_stars(message):
    if message.from_user.id != ADMIN_ID:
        bot.send_message(message.chat.id, "❌ У вас нет прав для этой команды")
        return
    args = message.text.split()
    if len(args) != 3:
        bot.send_message(message.chat.id, "❌ Использование: /addstars <user_id> <количество>")
        return
    try:
        target_id = int(args[1])
        amount = int(args[2])
    except ValueError:
        bot.send_message(message.chat.id, "❌ ID пользователя и количество должны быть числами")
        return

    with data_lock:
        if target_id not in user_data:
            bot.send_message(message.chat.id, f"❌ Пользователь с ID {target_id} не найден")
            return
        user_data[target_id]['stars'] = user_data[target_id].get('stars', 0) + amount
        save_user_data()
    bot.send_message(message.chat.id, f"✅ Звёзды пользователя {target_id} изменены на {amount}. Текущий баланс: {user_data[target_id]['stars']}")

@bot.message_handler(commands=['setstars'])
def set_stars(message):
    if message.from_user.id != ADMIN_ID:
        bot.send_message(message.chat.id, "❌ У вас нет прав для этой команды")
        return
    args = message.text.split()
    if len(args) != 3:
        bot.send_message(message.chat.id, "❌ Использование: /setstars <user_id> <количество>")
        return
    try:
        target_id = int(args[1])
        amount = int(args[2])
    except ValueError:
        bot.send_message(message.chat.id, "❌ ID пользователя и количество должны быть числами")
        return
    if amount < 0:
        bot.send_message(message.chat.id, "❌ Количество звёзд не может быть отрицательным")
        return

    with data_lock:
        if target_id not in user_data:
            bot.send_message(message.chat.id, f"❌ Пользователь с ID {target_id} не найден")
            return
        user_data[target_id]['stars'] = amount
        save_user_data()
    bot.send_message(message.chat.id, f"✅ Баланс звёзд пользователя {target_id} установлен на {amount}")

@bot.message_handler(commands=['getuser'])
def get_user(message):
    if message.from_user.id != ADMIN_ID:
        bot.send_message(message.chat.id, "❌ У вас нет прав для этой команды")
        return
    args = message.text.split()
    if len(args) != 2:
        bot.send_message(message.chat.id, "❌ Использование: /getuser <user_id>")
        return
    try:
        target_id = int(args[1])
    except ValueError:
        bot.send_message(message.chat.id, "❌ ID пользователя должен быть числом")
        return

    with data_lock:
        if target_id not in user_data:
            bot.send_message(message.chat.id, f"❌ Пользователь с ID {target_id} не найден")
            return
        u = user_data[target_id]
        info = (f"👤 Информация о пользователе {target_id}\n"
                f"Имя: {u.get('first_name', '—')}\n"
                f"Username: @{u.get('username', '—')}\n"
                f"💰 Баланс монет: {u.get('balance', 0)}\n"
                f"⭐ Баланс звёзд: {u.get('stars', 0)}\n"
                f"⚡ За клик: {u.get('per_click', 1)}\n"
                f"🖱️ Всего кликов: {u.get('total_clicks', 0)}\n"
                f"📅 Зарегистрирован: {u.get('registered', '—')}")
        bot.send_message(message.chat.id, info)

# ----- Промокоды (только для администратора) -----
@bot.message_handler(commands=['createpromo'])
def create_promo(message):
    if message.from_user.id != ADMIN_ID:
        bot.send_message(message.chat.id, "❌ У вас нет прав для этой команды")
        return
    args = message.text.split()
    if len(args) < 4:
        bot.send_message(message.chat.id, "❌ Использование: /createpromo <code> <reward> <max_uses> [days]")
        return
    code = args[1]
    try:
        reward = int(args[2])
        max_uses = int(args[3])
    except ValueError:
        bot.send_message(message.chat.id, "❌ Награда и макс. использований должны быть числами")
        return
    if reward <= 0 or max_uses < 0:
        bot.send_message(message.chat.id, "❌ Награда должна быть положительной, макс. использований >= 0 (0 = безлимит)")
        return

    expiry = None
    if len(args) >= 5:
        try:
            days = int(args[4])
            if days > 0:
                expiry = time.time() + days * 86400
        except ValueError:
            bot.send_message(message.chat.id, "❌ Срок должен быть числом (дни)")
            return

    with data_lock:
        if code in promocodes:
            bot.send_message(message.chat.id, f"❌ Промокод с кодом {code} уже существует")
            return
        promocodes[code] = {
            'reward': reward,
            'max_uses': max_uses,
            'expiry': expiry,
            'created_by': message.from_user.id,
            'created_at': time.time(),
            'activated_by': []
        }
        save_user_data()
    bot.send_message(
        message.chat.id,
        f"✅ Промокод {code} создан: +{reward} монет, макс. активаций: {max_uses if max_uses>0 else 'безлимит'}, "
        f"срок: {'бессрочно' if expiry is None else time.strftime('%Y-%m-%d', time.localtime(expiry))}"
    )

@bot.message_handler(commands=['deletepromo'])
def delete_promo(message):
    if message.from_user.id != ADMIN_ID:
        bot.send_message(message.chat.id, "❌ У вас нет прав для этой команды")
        return
    args = message.text.split()
    if len(args) != 2:
        bot.send_message(message.chat.id, "❌ Использование: /deletepromo <code>")
        return
    code = args[1]
    with data_lock:
        if code not in promocodes:
            bot.send_message(message.chat.id, f"❌ Промокод {code} не найден")
            return
        del promocodes[code]
        save_user_data()
    bot.send_message(message.chat.id, f"✅ Промокод {code} удален")

@bot.message_handler(commands=['listpromo'])
def list_promo(message):
    if message.from_user.id != ADMIN_ID:
        bot.send_message(message.chat.id, "❌ У вас нет прав для этой команды")
        return
    with data_lock:
        if not promocodes:
            bot.send_message(message.chat.id, "📋 Список промокодов пуст")
            return
        text = "📋 <b>Список промокодов:</b>\n\n"
        for code, info in promocodes.items():
            used = len(info['activated_by'])
            total = info['max_uses'] if info['max_uses'] > 0 else '∞'
            expiry = "бессрочно" if info['expiry'] is None else time.strftime("%Y-%m-%d", time.localtime(info['expiry']))
            text += f"<b>{code}</b>: +{info['reward']} монет, использовано {used}/{total}, срок: {expiry}\n"
        bot.send_message(message.chat.id, text, parse_mode='html')

# ----- Активация промокода пользователем -----
@bot.message_handler(commands=['activate'])
def activate_promo(message):
    user_id = message.from_user.id
    args = message.text.split()
    if len(args) != 2:
        bot.send_message(message.chat.id, "❌ Использование: /activate <код>")
        return
    code = args[1].strip()

    with data_lock:
        # Убедимся, что пользователь есть в базе
        if user_id not in user_data:
            user_data[user_id] = {
                'balance': 0,
                'per_click': 1,
                'double_cost': 1500,
                'stars': 0,
                'username': message.from_user.username,
                'first_name': message.from_user.first_name,
                'last_name': message.from_user.last_name,
                'total_clicks': 0,
                'registered': time.strftime("%Y-%m-%d %H:%M:%S"),
                'last_bonus': None
            }

        promo = promocodes.get(code)
        if promo is None:
            bot.send_message(message.chat.id, f"❌ Промокод {code} не найден")
            return

        # Проверка срока действия
        if promo['expiry'] is not None and time.time() > promo['expiry']:
            bot.send_message(message.chat.id, f"❌ Промокод {code} истек")
            return

        # Проверка лимита активаций
        if promo['max_uses'] > 0 and len(promo['activated_by']) >= promo['max_uses']:
            bot.send_message(message.chat.id, f"❌ Промокод {code} больше не доступен (лимит использований исчерпан)")
            return

        # Проверка, активировал ли уже пользователь
        if user_id in promo['activated_by']:
            bot.send_message(message.chat.id, f"❌ Вы уже активировали промокод {code}")
            return

        # Начисляем награду
        user_data[user_id]['balance'] += promo['reward']
        promo['activated_by'].append(user_id)
        save_user_data()

    bot.send_message(
        message.chat.id,
        f"✅ Промокод {code} активирован! Вы получили {promo['reward']} монет.\n"
        f"💰 Текущий баланс: {user_data[user_id]['balance']}"
    )

# ----- Команды для работы со звёздами (пользовательские) -----
@bot.message_handler(commands=['mystars'])
def my_stars(message):
    user_id = message.from_user.id
    with data_lock:
        if user_id not in user_data:
            user_data[user_id] = {
                'balance': 0,
                'per_click': 1,
                'double_cost': 1500,
                'stars': 0,
                'username': message.from_user.username,
                'first_name': message.from_user.first_name,
                'last_name': message.from_user.last_name,
                'total_clicks': 0,
                'registered': time.strftime("%Y-%m-%d %H:%M:%S"),
                'last_bonus': None
            }
            save_user_data()
        stars = user_data[user_id].get('stars', 0)
    bot.send_message(message.chat.id, f"⭐ У вас {stars} звёзд.")

@bot.message_handler(commands=['resetprogress'])
def reset_progress_command(message):
    user_id = message.from_user.id
    args = message.text.split()
    if len(args) != 2:
        bot.send_message(message.chat.id, "❌ Использование: /resetprogress <user_id>")
        return
    try:
        target_id = int(args[1])
    except ValueError:
        bot.send_message(message.chat.id, "❌ ID пользователя должен быть числом")
        return

    # Нельзя сбросить свой прогресс (опционально, можно разрешить)
    if target_id == user_id:
        bot.send_message(message.chat.id, "❌ Нельзя сбросить свой собственный прогресс.")
        return

    with data_lock:
        # Проверяем существование цели
        if target_id not in user_data:
            bot.send_message(message.chat.id, f"❌ Пользователь с ID {target_id} не найден")
            return

        # Проверяем наличие 10 звёзд у отправителя
        if user_id not in user_data:
            user_data[user_id] = {
                'balance': 0,
                'per_click': 1,
                'double_cost': 1500,
                'stars': 0,
                'username': message.from_user.username,
                'first_name': message.from_user.first_name,
                'last_name': message.from_user.last_name,
                'total_clicks': 0,
                'registered': time.strftime("%Y-%m-%d %H:%M:%S"),
                'last_bonus': None
            }
        if user_data[user_id].get('stars', 0) < 10:
            bot.send_message(message.chat.id, "❌ У вас недостаточно звёзд. Нужно 10.")
            return

    # Запрашиваем подтверждение
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("✅ Да, сбросить", callback_data=f"confirm_reset:{target_id}"),
        types.InlineKeyboardButton("❌ Отмена", callback_data="cancel_reset")
    )
    bot.send_message(
        message.chat.id,
        f"⚠️ Вы действительно хотите потратить 10 звёзд, чтобы обнулить прогресс пользователя {target_id}?",
        reply_markup=markup
    )

# ----- Обработчик подтверждения сброса -----
@bot.callback_query_handler(func=lambda call: call.data.startswith('confirm_reset:') or call.data == 'cancel_reset')
def reset_confirmation(call):
    user_id = call.from_user.id
    if call.data == 'cancel_reset':
        bot.answer_callback_query(call.id, "❌ Отменено")
        bot.edit_message_text("❌ Сброс отменён.", call.message.chat.id, call.message.message_id)
        return

    # Парсим ID цели
    target_id = int(call.data.split(':')[1])

    with data_lock:
        # Повторно проверяем наличие звёзд (на случай, если потратили в другом месте)
        if user_data[user_id].get('stars', 0) < 10:
            bot.answer_callback_query(call.id, "❌ Недостаточно звёзд")
            bot.edit_message_text("❌ Недостаточно звёзд для сброса.", call.message.chat.id, call.message.message_id)
            return

        # Проверяем, что цель всё ещё существует
        if target_id not in user_data:
            bot.answer_callback_query(call.id, "❌ Цель не найдена")
            bot.edit_message_text("❌ Пользователь больше не существует.", call.message.chat.id, call.message.message_id)
            return

        # Списываем 10 звёзд у отправителя
        user_data[user_id]['stars'] -= 10

        # Обнуляем прогресс цели (сохраняем stars, регистрационные данные)
        target = user_data[target_id]
        target['balance'] = 0
        target['per_click'] = 1
        target['double_cost'] = 1500
        target['total_clicks'] = 0
        # Не трогаем: stars, username, first_name, last_name, registered, last_bonus

        save_user_data()

    bot.answer_callback_query(call.id, "✅ Прогресс сброшен!")
    bot.edit_message_text(
        f"✅ Прогресс пользователя {target_id} успешно сброшен. Вы потратили 10 звёзд.",
        call.message.chat.id,
        call.message.message_id
    )

@bot.message_handler(commands=['admin'])
def admin_help(message):
    if message.from_user.id != ADMIN_ID:
        bot.send_message(message.chat.id, "❌ У вас нет прав для этой команды")
        return
    text = (
        "🔧 <b>Административные команды</b>\n\n"
        "/setbalance user_id сумма — установить баланс монет\n"
        "/addbalance user_id сумма — добавить к балансу монет\n"
        "/setperclick user_id кол-во — установить доход за клик\n"
        "/addstars user_id кол-во — добавить звёзды (может быть отрицательным)\n"
        "/setstars user_id кол-во — установить количество звёзд\n"
        "/getuser user_id — информация о пользователе\n"
        "/backup — создать резервную копию данных\n"
        "/createpromo код награда макс_использований [дни] — создать промокод\n"
        "/deletepromo код — удалить промокод\n"
        "/listpromo — список промокодов\n"
        "/admin — это сообщение\n\n"
        "👤 <b>Пользовательские команды:</b>\n"
        "/help — помощь\n"
        "/donate — информация о донате\n"
        "/mystars — баланс звёзд\n"
        "/resetprogress user_id — сбросить прогресс за 10 звёзд\n"
        "/activate код — активировать промокод\n"
        "/top — топ игроков"
    )
    bot.send_message(message.chat.id, text, parse_mode='html')

# ----- Обработчик текстовых кнопок -----
@bot.message_handler(content_types=['text'])
def handle_text(message):
    user_id = message.from_user.id

    # Инициализация нового пользователя
    with data_lock:
        if user_id not in user_data:
            user_data[user_id] = {
                'balance': 0,
                'per_click': 1,
                'double_cost': 1500,
                'stars': 0,
                'username': message.from_user.username,
                'first_name': message.from_user.first_name,
                'last_name': message.from_user.last_name,
                'total_clicks': 0,
                'registered': time.strftime("%Y-%m-%d %H:%M:%S"),
                'last_bonus': None
            }
            save_user_data()
    
    user = user_data[user_id]
    # Для старых пользователей – добавим недостающие поля
    if 'double_cost' not in user:
        user['double_cost'] = 1500
    if 'last_bonus' not in user:
        user['last_bonus'] = None
    if 'stars' not in user:
        user['stars'] = 0
    save_user_data()

    if message.text == "🎮 Кликер":
        bot.send_message(
            message.chat.id,
            f"🎮 Добро пожаловать в кликер!\n"
            f"💰 Баланс: {user['balance']} монет\n"
            f"⚡ За клик: {user['per_click']} монет\n"
            f"🖱️ Всего кликов: {user.get('total_clicks', 0)}",
            reply_markup=clicker_markup
        )

    elif message.text == "💰 Баланс":
        try:
            reg_time = time.mktime(time.strptime(user.get('registered', '2024-01-01'), "%Y-%m-%d %H:%M:%S"))
            hours_passed = max(1, (time.time() - reg_time) / 3600)
            clicks_per_hour = user.get('total_clicks', 0) / hours_passed
        except:
            clicks_per_hour = 0
        income_per_hour = clicks_per_hour * user['per_click']

        bot.send_message(
            message.chat.id,
            f"💰 Ваш баланс монет: {user['balance']}\n"
            f"⭐ Ваш баланс звёзд: {user.get('stars', 0)}\n"
            f"⚡ За клик: {user['per_click']} монет\n"
            f"🖱️ Всего кликов: {user.get('total_clicks', 0)}\n"
            f"📈 Примерно в час: {income_per_hour:.1f} монет"
        )

    elif message.text == "🛒 Магазин":
        shop_markup = types.InlineKeyboardMarkup(row_width=2)
        shop_markup.add(
            types.InlineKeyboardButton(
                text=f"Улучшить клик ({user['per_click'] * 100} монет)",
                callback_data="upgrade_click"
            ),
            types.InlineKeyboardButton(
                text=f"Удвоитель ({user['double_cost']} монет)",
                callback_data="double_click"
            ),
            types.InlineKeyboardButton(
                text=f"Бонус (1 раз в день)",
                callback_data="daily_bonus"
            )
        )
        bot.send_message(
            message.chat.id,
            f"🛒 Магазин улучшений:\n💰 Ваш баланс: {user['balance']} монет",
            reply_markup=shop_markup
        )

    elif message.text == "🖱️ Клик!":
        with data_lock:
            user['balance'] += user['per_click']
            user['total_clicks'] = user.get('total_clicks', 0) + 1
            save_user_data()

        if random.random() < 0.1:
            bonus = user['per_click'] * 2
            with data_lock:
                user['balance'] += bonus
                save_user_data()
            bot.send_message(
                message.chat.id,
                f"🎉 КРИТИЧЕСКИЙ КЛИК! +{bonus} монет!\n💰 Баланс: {user['balance']} монет"
            )
        else:
            bot.send_message(
                message.chat.id,
                f"🖱️ +{user['per_click']} монет!\n💰 Баланс: {user['balance']} монет"
            )

    elif message.text == "🏆 Топ":
        send_top(message.chat.id)

    elif message.text == "🔙 Назад":
        bot.send_message(
            message.chat.id,
            "🔙 Возвращаемся в главное меню",
            reply_markup=main_markup
        )

# ----- Обработчик инлайн-кнопок (магазин) -----
@bot.callback_query_handler(func=lambda call: True)
def callback_inline(call):
    user_id = call.from_user.id

    with data_lock:
        if user_id not in user_data:
            user_data[user_id] = {
                'balance': 0,
                'per_click': 1,
                'double_cost': 1500,
                'stars': 0,
                'username': call.from_user.username,
                'first_name': call.from_user.first_name,
                'last_name': call.from_user.last_name,
                'total_clicks': 0,
                'registered': time.strftime("%Y-%m-%d %H:%M:%S"),
                'last_bonus': None
            }
            save_user_data()
        user = user_data[user_id]
        # Для старых пользователей – добавим недостающие поля
        if 'double_cost' not in user:
            user['double_cost'] = 1500
        if 'last_bonus' not in user:
            user['last_bonus'] = None
        if 'stars' not in user:
            user['stars'] = 0
        save_user_data()

    # ----- Улучшение клика -----
    if call.data == "upgrade_click":
        cost = user['per_click'] * 100
        if user['balance'] >= cost:
            with data_lock:
                user['balance'] -= cost
                user['per_click'] += 1
                save_user_data()
            bot.answer_callback_query(call.id, f"✅ Улучшение куплено! Теперь +{user['per_click']} за клик")
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=f"🛒 Магазин улучшений:\n💰 Ваш баланс: {user['balance']} монет",
                reply_markup=call.message.reply_markup
            )
        else:
            bot.answer_callback_query(call.id, f"❌ Не хватает {cost - user['balance']} монет")

    # ----- Удвоитель -----
    elif call.data == "double_click":
        cost = user['double_cost']
        if user['balance'] >= cost:
            with data_lock:
                user['balance'] -= cost
                user['per_click'] *= 2
                user['double_cost'] *= 3
                save_user_data()
            bot.answer_callback_query(call.id, f"✅ Удвоитель куплен! Теперь +{user['per_click']} за клик")
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=f"🛒 Магазин улучшений:\n💰 Ваш баланс: {user['balance']} монет",
                reply_markup=call.message.reply_markup
            )
        else:
            bot.answer_callback_query(call.id, f"❌ Недостаточно средств! Нужно {cost} монет")

    # ----- Ежедневный бонус -----
    elif call.data == "daily_bonus":
        now = time.time()
        last = user.get('last_bonus')
        if last and (now - last) < 86400:
            hours = int((86400 - (now - last)) / 3600)
            bot.answer_callback_query(call.id, f"❌ Бонус можно получить раз в день. Осталось {hours} ч.")
        else:
            bonus = 100 + user['per_click'] * 10
            with data_lock:
                user['balance'] += bonus
                user['last_bonus'] = now
                save_user_data()
            bot.answer_callback_query(call.id, f"✅ Ежедневный бонус: +{bonus} монет!")
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=f"🛒 Магазин улучшений:\n💰 Ваш баланс: {user['balance']} монет",
                reply_markup=call.message.reply_markup
            )

# ----- Сохранение при выходе -----
def save_on_exit():
    print("Сохранение данных перед выходом...")
    with data_lock:
        save_user_data()

atexit.register(save_on_exit)

# ----- Запуск бота -----
if __name__ == '__main__':
    print("Бот запущен...")
    try:
        bot.polling(none_stop=True)
    except Exception as e:
        print(f"Ошибка: {e}")
    finally:
        with data_lock:
            save_user_data()