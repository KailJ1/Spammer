from telethon import TelegramClient, errors
from telethon.tl.functions.contacts import UnblockRequest
from telethon.tl.functions.messages import DeleteHistoryRequest
from telethon.tl.functions.contacts import BlockRequest
import asyncio
import os
import random

API_ID = '26727292'  # замените на ваш API ID
API_HASH = 'aa47f020555b710b98dc04367aad53c2'  # замените на ваш API Hash
SESSION_FOLDER = 'sessions/'  # папка для хранения сессий
DEFAULT_PHONE = "123"  # номер телефона по умолчанию


async def send_message(client, chat_id, message):
    try:
        await client.send_message(chat_id, message)
        print(f"Сообщение отправлено в чат {chat_id}")
        return True
    except errors.FloodWaitError as e:
        print(f"Ошибка при отправке сообщения: Too many requests. Ждем {e.seconds} секунд.")
        await asyncio.sleep(e.seconds)
        return False
    except Exception as e:
        print(f"Ошибка при отправке сообщения: {e}")
        return False


async def delete_chat(client, chat_id):
    try:
        await client(DeleteHistoryRequest(peer=chat_id, max_id=0))
        print(f"Чат с {chat_id} удален для текущего аккаунта")
    except Exception as e:
        print(f"Ошибка при удалении чата: {e}")


async def block_user(client, user_id):
    try:
        await client(BlockRequest(user_id))
        print(f"Пользователь {user_id} заблокирован")
    except Exception as e:
        print(f"Ошибка при блокировке пользователя: {e}")


async def process_request(request):
    # Преобразуем значения из строки в нужные типы данных
    queue_number = int(request[0])
    user_id = request[1]
    target = request[2]
    message = request[3]
    total_messages = int(request[4])

    chat_id = target if target.startswith("@") or target.isnumeric() else None

    if chat_id is None:
        print(f"Некорректный target: {target}")
        return

    sessions = [os.path.join(SESSION_FOLDER, session) for session in os.listdir(SESSION_FOLDER)]
    messages_sent = 0

    while messages_sent < total_messages:
        random.shuffle(sessions)
        for session in sessions:
            if messages_sent >= total_messages:
                break

            client = TelegramClient(session, API_ID, API_HASH)
            try:
                await asyncio.wait_for(client.start(phone=lambda: DEFAULT_PHONE), timeout=5)
            except (asyncio.TimeoutError, errors.FloodWaitError) as e:
                print(f"Ошибка подключения к сессии {session}: {e}")
                continue
            except Exception as e:
                print(f"Ошибка при старте клиента для сессии {session}: {e}")
                continue

            try:
                success = await send_message(client, chat_id, message)
                if success:
                    messages_sent += 1
                    print(f"Отправлено сообщений: {messages_sent} из {total_messages}")
                    await delete_chat(client, chat_id)
                    await block_user(client, chat_id)
            except Exception as e:
                print(f"Ошибка во время операций с сессией {session}: {e}")
            finally:
                await client.disconnect()

        if messages_sent < total_messages:
            print("Не удалось отправить нужное количество сообщений, повторяем цикл...")

    print(f"Всего сообщений отправлено: {messages_sent}")


async def main():
    while True:
        # Считываем запросы из файла
        with open('data.txt', 'r') as file:
            requests = [line.strip().split('|') for line in file]

        # Сортируем запросы по номеру очереди
        requests.sort(key=lambda x: int(x[0]))

        if not requests:
            print("Нет запросов для обработки.")
            break

        # Обрабатываем все запросы последовательно
        for request in requests:
            await process_request(request)

        # Удаляем обработанные строки из файла и обновляем номера очереди
        with open('data.txt', 'r') as file:
            lines = file.readlines()

        # Оставляем только те строки, которые не равны обработанным запросам
        new_lines = []
        for line in lines:
            parts = line.strip().split('|')
            if parts not in requests:
                # Обновляем номера очереди только для оставшихся строк
                if int(parts[0]) > int(requests[0][0]):
                    parts[0] = str(int(parts[0]) - 1)
                new_lines.append('|'.join(parts) + '\n')

        # Перезаписываем файл с обновленным содержимым
        with open('data.txt', 'w') as file:
            file.writelines(new_lines)


if __name__ == "__main__":
    asyncio.run(main())
