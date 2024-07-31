import subprocess
import telebot
from telebot import types
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import json
import os

API_TOKEN = '7069278495:AAGdtf2xPht9rCScyDUJqUYBvEMr2YpSsTo'
bot = telebot.TeleBot(API_TOKEN)

# Файлы для сохранения данных
USERS_FILE = 'users.txt'
BALANCE_FILE = 'balance.txt'
SUBSCRIPTION_FILE = 'subscriptions.txt'
FREE_SUBS_FILE = 'free_subs.txt'
DATA_FILE = 'data.txt'
MESSAGES_SENT_FILE = 'messages_sent.txt'

# Инициализация очереди данных
data_queue = []


# Чтение пользователей из файла
def read_users():
    users = {}
    try:
        with open(USERS_FILE, 'r') as file:
            for line in file:
                user_id, phone_number = line.strip().split(':')
                users[user_id] = phone_number
    except FileNotFoundError:
        pass
    return users


# Чтение балансов
def read_balances():
    balances = {}
    try:
        with open(BALANCE_FILE, 'r') as file:
            for line in file:
                user_id, balance = line.strip().split(':')
                balances[user_id] = float(balance)
    except FileNotFoundError:
        pass
    return balances


# Чтение подписок
def read_subscriptions():
    try:
        with open(SUBSCRIPTION_FILE, 'r') as file:
            subscriptions = json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        subscriptions = {}
    return subscriptions


# Сохранение подписок
def save_subscriptions(subscriptions):
    with open(SUBSCRIPTION_FILE, 'w') as file:
        json.dump(subscriptions, file, indent=4)


# Чтение бесплатных подписок
def read_free_subs():
    try:
        with open(FREE_SUBS_FILE, 'r') as file:
            free_subs = set(line.strip() for line in file)
    except FileNotFoundError:
        free_subs = set()
    return free_subs


# Сохранение пользователей, активировавших бесплатную подписку
def save_free_sub(user_id):
    with open(FREE_SUBS_FILE, 'a') as file:
        file.write(f"{user_id}\n")


# Проверка и обновление подписок
def update_subscriptions(subscriptions):
    updated = False
    current_time = datetime.now()
    expired_users = []

    for user_id, sub_info in subscriptions.items():
        expiry_date = datetime.strptime(sub_info['subscription']['end'], '%Y-%m-%d %H:%M:%S')
        if current_time > expiry_date:
            expired_users.append(user_id)

    for user_id in expired_users:
        del subscriptions[user_id]
        updated = True

    if updated:
        save_subscriptions(subscriptions)


# Инициализация данных
users = read_users()
balances = read_balances()
subscriptions = read_subscriptions()
free_subs = read_free_subs()
update_subscriptions(subscriptions)


# Команда /start
@bot.message_handler(commands=['start'])
def start(message):
    user_id = str(message.from_user.id)
    if user_id in users:
        bot.send_message(message.chat.id, "Откройте для себя бесконечные возможности.", reply_markup=main_menu_markup())
    else:
        markup = types.ReplyKeyboardMarkup(one_time_keyboard=True)
        button_phone = types.KeyboardButton(text="Поделиться номером телефона", request_contact=True)
        markup.add(button_phone)
        bot.send_message(message.chat.id, "Пожалуйста, поделитесь своим номером телефона для регистрации.",
                         reply_markup=markup)


# Главное меню
def main_menu_markup():
    markup = types.InlineKeyboardMarkup()
    button_spam = types.InlineKeyboardButton(text="📱 Начать спам", callback_data="start_spam")
    button_account = types.InlineKeyboardButton(text="⚙️ Мой аккаунт", callback_data="my_account")
    markup.add(button_spam)
    markup.add(button_account)
    return markup


# Обработка контакта
@bot.message_handler(content_types=['contact'])
def contact(message):
    if message.contact is not None:
        user_id = str(message.from_user.id)
        phone_number = message.contact.phone_number
        users[user_id] = phone_number
        with open(USERS_FILE, 'a') as file:
            file.write(f"{user_id}:{phone_number}\n")
        bot.send_message(message.chat.id, "Откройте для себя бесконечные возможности.", reply_markup=main_menu_markup())


# Обработка нажатия на кнопку Начать спам
@bot.callback_query_handler(func=lambda call: call.data == "start_spam")
def start_spam(call):
    bot.send_message(call.message.chat.id,
                     "Введите @имя пользователя или ID чата, в который нужно отправить сообщение.")
    bot.register_next_step_handler(call.message, get_chat_id)


def get_chat_id(message):
    chat_id = message.text
    bot.send_message(message.chat.id, "Введите сообщение, которое нужно отправить.")
    bot.register_next_step_handler(message, get_message, chat_id)


def get_message(message, chat_id):
    spam_message = message.text
    bot.send_message(message.chat.id, "Укажите количество сообщений, которые нужно отправить.")
    bot.register_next_step_handler(message, get_count, chat_id, spam_message)


def read_messages_sent():
    messages_sent = {}
    try:
        with open(MESSAGES_SENT_FILE, 'r') as file:
            for line in file:
                user_id, sent = line.strip().split(':')
                messages_sent[user_id] = int(sent)
    except FileNotFoundError:
        pass
    return messages_sent

def save_messages_sent(user_id, count):
    messages_sent = read_messages_sent()
    messages_sent[user_id] = messages_sent.get(user_id, 0) + count
    with open(MESSAGES_SENT_FILE, 'w') as file:
        for uid, sent in messages_sent.items():
            file.write(f"{uid}:{sent}\n")

def get_message_limit(subscription_type):
    if subscription_type == "Admin":
        return float('inf')  # Используем бесконечность для Админа
    elif subscription_type == "Pro":
        return 100
    elif subscription_type == "Free":
        return 20
    return 0

# Функция для проверки лимита сообщений
def check_message_limit(user_id, count):
    subscription_info = subscriptions.get(user_id, {"subscription": {"type": "None"}})
    subscription_type = subscription_info["subscription"]["type"]
    limit = get_message_limit(subscription_type)

    if limit == float('inf'):
        return True

    sent_today = read_messages_sent().get(user_id, 0)
    remaining_limit = limit - sent_today

    return remaining_limit >= count

# Изменяем функцию обработки количества сообщений
def get_count(message, chat_id, spam_message):
    try:
        count = int(message.text)
        user_id = str(message.from_user.id)

        if not check_message_limit(user_id, count):
            bot.send_message(message.chat.id, "Вы превысили лимит сообщений на сегодня.")
            return

        # Записываем отправленные сообщения
        save_messages_sent(user_id, count)

        # Считываем текущую очередь из файла
        with open(DATA_FILE, 'r') as file:
            lines = file.readlines()

        if not lines:
            queue_number = 0
        else:
            last_line = lines[-1]
            last_queue_number = int(last_line.split('|')[0])
            queue_number = last_queue_number + 1

        data_queue.append(f"{queue_number}|{user_id}|{chat_id}|{spam_message}|{count}")
        with open(DATA_FILE, 'a') as file:
            file.write(f"{queue_number}|{user_id}|{chat_id}|{spam_message}|{count}\n")

        bot.send_message(message.chat.id, f"Сообщения будут отправлены {count} раз в чат {chat_id}.")
        bot.send_message(message.chat.id, "Откройте для себя бесконечные возможности.", reply_markup=main_menu_markup())

        # Запуск main.py
        subprocess.Popen(["python", "main.py"])

    except ValueError:
        bot.send_message(message.chat.id, "Количество сообщений должно быть числом. Попробуйте еще раз.")
        bot.register_next_step_handler(message, get_count, chat_id, spam_message)

# Обработка нажатия на кнопку Мой аккаунт
@bot.callback_query_handler(func=lambda call: call.data == "my_account")
def my_account(call):
    user_id = str(call.from_user.id)
    phone_number = users.get(user_id, "Неизвестно")
    masked_phone = phone_number[:-4] + "****"
    balance = balances.get(user_id, 0.0)

    subscription_info = subscriptions.get(user_id, {"subscription": {"type": "None", "end": "отсутствует"}})
    subscription_type = subscription_info["subscription"]["type"]
    expiry_date = subscription_info["subscription"]["end"]

    if subscription_type == "Admin":
        message_text = (f"👁‍🗨 ID: {user_id}\n"
                        f"👁‍🗨 Телефон: {masked_phone}\n\n"
                        f"💶 Мой кошелёк: {balance}₽\n"
                        f"💎 Подписка до: {expiry_date}\n"
                        f"⚙️ Лимит сообщений: нет ограничений\n")
    else:
        daily_limit = get_message_limit(subscription_type)
        sent_today = read_messages_sent().get(user_id, 0)
        remaining_limit = daily_limit - sent_today

        message_text = (f"👁‍🗨 ID: {user_id}\n"
                        f"👁‍🗨 Телефон: {masked_phone}\n\n"
                        f"💶 Мой кошелёк: {balance}₽\n"
                        f"💎 Подписка до: {expiry_date}\n"
                        f"⚙️ Лимит сообщений: {remaining_limit}/{daily_limit}\n")

    markup = types.InlineKeyboardMarkup()
    button_subscription = types.InlineKeyboardButton(text="💎 Управление подпиской", callback_data="manage_subscription")
    button_top_up = types.InlineKeyboardButton(text="💳 Пополнить Баланс", callback_data="top_up")
    button_back = types.InlineKeyboardButton(text="◀️ Назад", callback_data="back_from_account")
    markup.add(button_subscription)
    markup.add(button_top_up)
    markup.add(button_back)

    if subscription_type == "Admin":
        button_give_subscription = types.InlineKeyboardButton(text="🔧 Выдать подписку", callback_data="give_subscription")
        button_remove_subscription = types.InlineKeyboardButton(text="🛑 Снять подписку", callback_data="remove_subscription")
        button_balance = types.InlineKeyboardButton(text="💳 Баланс", callback_data="balance")  # Новая кнопка
        markup.add(button_give_subscription)
        markup.add(button_remove_subscription)
        markup.add(button_balance)  # Добавляем кнопку

    bot.send_message(call.message.chat.id, message_text, reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data == "balance")
def balance(call):
    user_id = str(call.from_user.id)
    if subscriptions.get(user_id, {"subscription": {"type": "None"}})["subscription"]["type"] != "Admin":
        bot.send_message(call.message.chat.id, "У вас нет доступа к этой функции.")
        return

    bot.send_message(call.message.chat.id, "Введите ID пользователя, которому нужно пополнить баланс.")
    bot.register_next_step_handler(call.message, get_user_id_for_balance)


def get_user_id_for_balance(message):
    user_id_to_update = message.text
    bot.send_message(message.chat.id, "Введите сумму для пополнения баланса.")
    bot.register_next_step_handler(message, get_balance_amount, user_id_to_update)


def get_balance_amount(message, user_id_to_update):
    try:
        amount = float(message.text)
        if amount <= 0:
            bot.send_message(message.chat.id, "Сумма должна быть положительной.")
            return

        # Обновляем баланс пользователя
        if user_id_to_update in balances:
            balances[user_id_to_update] += amount
        else:
            balances[user_id_to_update] = amount

        # Сохраняем новый баланс
        with open(BALANCE_FILE, 'w') as file:
            for uid, bal in balances.items():
                file.write(f"{uid}:{bal}\n")

        # Отправляем уведомления
        bot.send_message(message.chat.id, f"Баланс пользователя {user_id_to_update} был пополнен на {amount}₽.")
        bot.send_message(user_id_to_update, f"Ваш баланс был пополнен на {amount}₽.")

    except ValueError:
        bot.send_message(message.chat.id, "Пожалуйста, введите корректную сумму.")
        bot.register_next_step_handler(message, get_balance_amount, user_id_to_update)


# Обработка нажатия на кнопку Назад из меню "Мой аккаунт"
@bot.callback_query_handler(func=lambda call: call.data == "back_from_account")
def back_from_account(call):
    bot.send_message(call.message.chat.id, "Откройте для себя бесконечные возможности.",
                     reply_markup=main_menu_markup())


# Обработка нажатия на кнопку Управление подпиской
@bot.callback_query_handler(func=lambda call: call.data == "manage_subscription")
def manage_subscription(call):
    user_id = str(call.from_user.id)
    markup = types.InlineKeyboardMarkup()

    # Проверяем, активирован ли Free
    activated_free_subs = read_free_subs()

    if user_id not in activated_free_subs:
        button_free = types.InlineKeyboardButton(text="✅ Free", callback_data="activate_free_subscription")
    else:
        button_free = types.InlineKeyboardButton(text="✅ Free (уже активировалась)",
                                                 callback_data="free_subscription_already_activated")

    button_pro = types.InlineKeyboardButton(text="👤 Pro", callback_data="choose_pro_subscription")
    button_back = types.InlineKeyboardButton(text="◀️ Назад", callback_data="my_account")

    # Добавляем каждую кнопку на новую строку
    markup.add(button_free)
    markup.add(button_pro)
    markup.add(button_back)

    bot.send_message(call.message.chat.id, "Выберите желаемую подписку:", reply_markup=markup)


# Обработка нажатия на кнопку активировать бесплатную подписку
@bot.callback_query_handler(func=lambda call: call.data == "activate_free_subscription")
def activate_free_subscription(call):
    user_id = str(call.from_user.id)
    activated_free_subs = read_free_subs()

    if user_id in activated_free_subs:
        bot.send_message(call.message.chat.id, "Вы уже активировали бесплатную подписку.")
        return

    expiry_date = datetime.now() + timedelta(days=3)
    formatted_end_date = expiry_date.strftime('%Y-%m-%d %H:%M:%S')

    subscriptions[user_id] = {
        "subscription": {
            "type": "Free",
            "end": formatted_end_date
        }
    }
    save_subscriptions(subscriptions)
    save_free_sub(user_id)

    bot.send_message(call.message.chat.id, f"Вам выдана бесплатная подписка на 3 дня до {formatted_end_date}.")
    bot.send_message(user_id, f"Вам была выдана бесплатная подписка до {formatted_end_date}.")

    bot.send_message(call.message.chat.id, "Выберите действие:", reply_markup=my_account())


# Обработка нажатия на кнопку выбрать подписку Pro
@bot.callback_query_handler(func=lambda call: call.data == "choose_pro_subscription")
def choose_pro_subscription(call):
    user_id = str(call.from_user.id)
    if user_id in subscriptions and subscriptions[user_id]['subscription']['type'] != "None":
        bot.send_message(call.message.chat.id, "У вас уже есть активная подписка.")
        return

    markup = types.InlineKeyboardMarkup()
    button_week = types.InlineKeyboardButton(text="На 1 неделю - 30₽", callback_data="pro_week")
    button_month = types.InlineKeyboardButton(text="На 1 месяц - 120₽", callback_data="pro_month")
    button_halfyear = types.InlineKeyboardButton(text="На 6 месяцев - 720₽", callback_data="pro_halfyear")
    button_back = types.InlineKeyboardButton(text="◀️ Назад", callback_data="my_account")

    markup.add(button_week)
    markup.add(button_month)
    markup.add(button_halfyear)
    markup.add(button_back)

    bot.send_message(call.message.chat.id, "Выберите срок подписки:", reply_markup=markup)


# Обработка выбора срока подписки Pro
@bot.callback_query_handler(func=lambda call: call.data.startswith("pro_"))
def choose_pro_period(call):
    period = call.data.split("_")[1]  # Ожидаем 'week', 'month', 'half_year'
    print(f"Выбранный период: {period}")  # Отладочная информация

    prices = {"week": 30, "month": 120, "halfyear": 720}
    duration = {"week": 7, "month": 30, "halfyear": 180}
    period_names = {"week": "неделя", "month": "месяц", "halfyear": "6 месяцев"}

    user_id = str(call.from_user.id)
    balance = balances.get(user_id, 0.0)
    price = prices.get(period)
    days = duration.get(period)

    if price is None or days is None:
        bot.send_message(call.message.chat.id, f"Ошибка при выборе подписки. - выбранный период: {period}")
        return

    if balance < price:
        bot.send_message(call.message.chat.id, "У вас недостаточно средств. Пожалуйста, пополните баланс.")
        return

    # Списание средств
    balances[user_id] -= price
    with open(BALANCE_FILE, 'w') as file:
        for uid, bal in balances.items():
            file.write(f"{uid}:{bal}\n")

    expiry_date = datetime.now() + timedelta(days=days)
    formatted_end_date = expiry_date.strftime('%Y-%m-%d %H:%M:%S')

    subscriptions[user_id] = {
        "subscription": {
            "type": "Pro",
            "end": formatted_end_date
        }
    }
    save_subscriptions(subscriptions)

    period_russian = period_names.get(period, period)  # Перевод периода на русский
    bot.send_message(call.message.chat.id,
                     f"Вы купили подписку Pro на {period_russian}. Подписка активирована до {formatted_end_date}.")

    # Открываем меню аккаунта
    my_account(call)

period_names = {
    "week": "неделя",
    "month": "месяц",
    "halfyear": "6 месяцев"
}

# Обработка нажатия на кнопку Выдать подписку
@bot.callback_query_handler(func=lambda call: call.data == "give_subscription")
def give_subscription(call):
    bot.send_message(call.message.chat.id, "Выберите нужную подписку:", reply_markup=subscription_types_markup())


def my_account_markup():
    markup = types.InlineKeyboardMarkup()
    button_subscription = types.InlineKeyboardButton(text="💎 Управление подпиской", callback_data="manage_subscription")
    button_top_up = types.InlineKeyboardButton(text="💳 Пополнить", callback_data="top_up")
    button_back = types.InlineKeyboardButton(text="◀️ Назад", callback_data="my_account")
    markup.add(button_subscription)
    markup.add(button_top_up)
    markup.add(button_back)

    return markup

def reset_daily_limits():
    # Сброс лимитов сообщений каждый день в 00:00 по МСК
    current_time = datetime.now()
    if current_time.hour == 0 and current_time.minute == 0:
        with open(MESSAGES_SENT_FILE, 'w') as file:
            pass  # Очищаем файл, чтобы сбросить отправленные сообщения

def subscription_types_markup():
    markup = types.InlineKeyboardMarkup()
    button_admin = types.InlineKeyboardButton(text="Admin", callback_data="subscription_Admin")
    button_pro = types.InlineKeyboardButton(text="Pro", callback_data="subscription_Pro")
    button_free = types.InlineKeyboardButton(text="Free", callback_data="subscription_Free")
    button_back = types.InlineKeyboardButton(text="◀️ Назад", callback_data="my_account")
    markup.add(button_admin, button_pro, button_free)
    markup.add(button_back)
    return markup


# Обработка выбора типа подписки
@bot.callback_query_handler(func=lambda call: call.data.startswith("subscription_"))
def choose_subscription(call):
    subscription_type = call.data.split("_")[1]
    bot.send_message(call.message.chat.id, "Введите ID пользователя, которому нужно выдать подписку.")
    bot.register_next_step_handler(call.message, get_user_id_to_give, subscription_type)


# Ввод ID пользователя для выдачи подписки
def get_user_id_to_give(message, subscription_type):
    user_id_to_give = message.text
    bot.send_message(message.chat.id, "Введите срок действия подписки (в виде y-год m-месяц d-дни h-часов m-минут).")
    bot.register_next_step_handler(message, get_subscription_duration, user_id_to_give, subscription_type)


# Ввод срока действия подписки
def get_subscription_duration(message, user_id_to_give, subscription_type):
    duration = message.text.strip()
    try:
        # Определяем начальные значения для времени
        years, months, days, hours, minutes = 0, 0, 0, 0, 0

        # Используем регулярное выражение для извлечения чисел и единиц времени
        import re
        duration_parts = re.findall(r'(\d+)([ymdHM])', duration)

        for number, unit in duration_parts:
            number = int(number)
            if unit == 'y':
                years = number
            elif unit == 'm':
                months = number
            elif unit == 'd':
                days = number
            elif unit == 'h':
                hours = number
            elif unit == 'M':
                minutes = number

        # Рассчитываем дату окончания подписки
        expiry_date = datetime.now() + relativedelta(years=years, months=months, days=days, hours=hours,
                                                     minutes=minutes)
        formatted_end_date = expiry_date.strftime('%Y-%m-%d %H:%M:%S')

        if subscription_type not in ["Admin", "Pro", "Free"]:
            bot.send_message(message.chat.id, "Неверный тип подписки.")
            return

        # Обновляем данные подписки
        subscriptions[user_id_to_give] = {
            "subscription": {
                "type": subscription_type,
                "end": formatted_end_date
            }
        }
        save_subscriptions(subscriptions)

        bot.send_message(message.chat.id,
                         f"Подписка {subscription_type} выдана пользователю {user_id_to_give} до {formatted_end_date}.")
        bot.send_message(user_id_to_give, f"Вам выдана подписка {subscription_type} до {formatted_end_date}.")

    except ValueError:
        bot.send_message(message.chat.id, "Ошибка при вводе срока подписки. Попробуйте еще раз.")
        bot.register_next_step_handler(message, get_subscription_duration, user_id_to_give, subscription_type)

    # Открываем меню аккаунта
    my_account(message)

# Обработка нажатия на кнопку Снять подписку
@bot.callback_query_handler(func=lambda call: call.data == "remove_subscription")
def remove_subscription(call):
    bot.send_message(call.message.chat.id, "Введите ID пользователя, для которого нужно снять подписку.")
    bot.register_next_step_handler(call.message, get_user_id_to_remove)


# Ввод ID пользователя для снятия подписки
def get_user_id_to_remove(message):
    user_id_to_remove = message.text
    bot.send_message(message.chat.id, "Введите причину снятия подписки.")
    bot.register_next_step_handler(message, remove_subscription_reason, user_id_to_remove)


# Ввод причины снятия подписки
def remove_subscription_reason(message, user_id_to_remove):
    reason = message.text
    if user_id_to_remove in subscriptions:
        del subscriptions[user_id_to_remove]
        save_subscriptions(subscriptions)
        bot.send_message(message.chat.id,
                         f"Подписка для пользователя {user_id_to_remove} успешно снята. Причина: {reason}.")
        # Уведомление пользователю
        bot.send_message(user_id_to_remove, f"Ваша подписка была отменена. Причина: {reason}.")
    else:
        bot.send_message(message.chat.id, f"Пользователь с ID {user_id_to_remove} не найден.")
    # Открываем меню аккаунта
    my_account(message)

# Клавиатура для выбора типа подписки
def subscription_types_markup():
    markup = types.InlineKeyboardMarkup()
    button_admin = types.InlineKeyboardButton(text="Admin", callback_data="subscription_Admin")
    button_pro = types.InlineKeyboardButton(text="Pro", callback_data="subscription_Pro")
    button_free = types.InlineKeyboardButton(text="Free", callback_data="subscription_Free")
    button_back = types.InlineKeyboardButton(text="◀️ Назад", callback_data="my_account")
    markup.add(button_admin, button_pro, button_free)
    markup.add(button_back)
    return markup


# Обработка нажатия на кнопку Назад из меню "Выдать подписку"
@bot.callback_query_handler(func=lambda call: call.data == "my_account")
def back_from_manage_subscription(call):
    my_account(call)

# Для обработки вызовов из других функций, где нет объекта call
def some_other_function(message):
    # Пример использования
    my_account(message)  # Убедитесь, что message имеет свойство chat.id

# Обработка нажатия на кнопку Пополнить
@bot.callback_query_handler(func=lambda call: call.data == "top_up")
def top_up(call):
    bot.send_message(call.message.chat.id, "Функция пополнения баланса временно недоступна. Обратитесь в поддержку за пополнением баланса.")

def get_top_up_amount(message):
    try:
        amount = float(message.text)
        user_id = str(message.from_user.id)

        if user_id in balances:
            balances[user_id] += amount
        else:
            balances[user_id] = amount

        with open(BALANCE_FILE, 'w') as file:
            for uid, balance in balances.items():
                file.write(f"{uid}:{balance}\n")

        bot.send_message(message.chat.id, f"Ваш баланс пополнен на {amount}₽. Текущий баланс: {balances[user_id]}₽")
    except ValueError:
        bot.send_message(message.chat.id, "Сумма должна быть числом. Попробуйте снова.")
        bot.register_next_step_handler(message, get_top_up_amount)


def notify_users():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r') as file:
            lines = file.readlines()

        for line in lines:
            queue_number, user_id, chat_id, spam_message, count = line.strip().split('|')
            if int(queue_number) == 0:
                bot.send_message(user_id, "Ваша очередь 0, спам был начат.")


if __name__ == '__main__':
    save_subscriptions(subscriptions)

    reset_daily_limits()

    notify_users()

    bot.infinity_polling()
