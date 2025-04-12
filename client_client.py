#!/usr/bin/env python3
"""
local_proxy.py – Локальный TCP-прокси, создающий сервер на localhost:1080.
При входящем подключении он устанавливает соединение с центральным сервером,
отправляет фиксированный SERVICE_ID (36 символов) и туннелирует данные между
локальным клиентом и центральным сервером.

Схема работы:
  Пользователь/Приложение --> (localhost:1080) local_proxy.py -->
      центральный сервер (порта 1080) --> client_server.py (устройство за NAT)

Настройте:
  - CENTRAL_SERVER_HOST – IP центрального сервера.
  - CENTRAL_SERVER_PORT – порт (уже используется для подключения внешних клиентов).
  - SERVICE_ID – фиксированный идентификатор (полученный при регистрации client_server.py).
  - LISTEN_HOST и LISTEN_PORT – параметры локального сервера (как правило, '127.0.0.1' и 1080).
"""

import asyncio
import sys

# Настройки подключения к центральному серверу
CENTRAL_SERVER_HOST = 'localhost'  # Замените на IP вашего центрального сервера
CENTRAL_SERVER_PORT = 1080  # Порт для внешних клиентов на центральном сервере

# Параметры локального сервера
LISTEN_HOST = '127.0.0.1'
LISTEN_PORT = 1081

# Фиксированный SERVICE_ID, полученный от client_server.py
SERVICE_ID = "36b1a7fc-c6e2-41e5-bf81-0e93b8f28357"  # Должен быть ровно 36 символов

if len(SERVICE_ID) != 36:
    print("Ошибка: SERVICE_ID должен быть 36 символов (UUID).")
    sys.exit(1)


async def handle_client(local_reader: asyncio.StreamReader, local_writer: asyncio.StreamWriter):
    client_addr = local_writer.get_extra_info('peername')
    print(f"[Local Proxy] Новое подключение от {client_addr}")

    try:
        # Устанавливаем соединение с центральным сервером (порт 1080)
        remote_reader, remote_writer = await asyncio.open_connection(CENTRAL_SERVER_HOST, CENTRAL_SERVER_PORT)
        print(f"[Local Proxy] Соединение с сервером {CENTRAL_SERVER_HOST}:{CENTRAL_SERVER_PORT} установлено.")

        # Отправляем фиксированный SERVICE_ID (36 байт)
        remote_writer.write(SERVICE_ID.encode('utf-8'))
        await remote_writer.drain()

        # Функция для пересылки данных между двумя соединениями
        async def forward(src: asyncio.StreamReader, dst: asyncio.StreamWriter):
            try:
                while True:
                    data = await src.read(4096)
                    if not data:
                        break
                    dst.write(data)
                    await dst.drain()
            except Exception as e:
                print(f"[Local Proxy] Ошибка при пересылке: {e}")
            finally:
                dst.close()

        # Параллельно пересылаем данные в обоих направлениях
        await asyncio.gather(
            forward(local_reader, remote_writer),
            forward(remote_reader, local_writer)
        )
    except Exception as e:
        print(f"[Local Proxy] Ошибка: {e}")
    finally:
        local_writer.close()
        print(f"[Local Proxy] Соединение с {client_addr} закрыто.")


async def main():
    server = await asyncio.start_server(handle_client, LISTEN_HOST, LISTEN_PORT)
    addr = server.sockets[0].getsockname()
    print(f"[Local Proxy] Локальный сервер запущен и слушает {addr}")

    async with server:
        await server.serve_forever()


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[Local Proxy] Прокси остановлен.")
