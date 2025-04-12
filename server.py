#!/usr/bin/env python3
"""
server.py – Центральный сервер, обеспечивающий туннелирование трафика.

Запускает два сервера:
  1. Сервер регистрации сервисов (порт 8888):
     Устройства, находящиеся за NAT, подключаются сюда для регистрации.
  2. Сервер внешних клиентов (порт 1080):
     Внешний клиент сначала отправляет 36‑байтный идентификатор сервиса,
     после чего весь трафик (например, SOCKS5‑рукопожатие, запрос и далее)
     пересылается к соответствующему зарегистрированному сервису.
"""

import asyncio

# Глобальный словарь зарегистрированных сервисов.
# Ключ – service_id (строка), значение – (reader, writer)
registered_services = {}

async def forward_data(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    """
    Пересылает данные от reader к writer до закрытия соединения.
    """
    try:
        while True:
            data = await reader.read(4096)
            if not data:
                break
            writer.write(data)
            await writer.drain()
    except Exception as e:
        print(f"[forward_data] Ошибка: {e}")
    finally:
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass

async def handle_external_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    """
    Обрабатывает подключения внешних клиентов.
    Первый шаг – чтение ровно 36 байт с идентификатором сервиса.
    Если он найден, запускается двунаправленная пересылка данных между
    внешним клиентом и зарегистрированным сервисом (с учетом дальнейшей обработки SOCKS5).
    """
    client_addr = writer.get_extra_info('peername')
    try:
        # Ожидаем ровно 36 байт – идентификатор сервиса
        service_id_data = await reader.readexactly(36)
        service_id = service_id_data.decode('utf-8').strip()
        print(f"[External] {client_addr} запрашивает подключение к сервису с ID: {service_id}")

        if service_id not in registered_services:
            err_msg = "Invalid service id\n".encode('utf-8')
            writer.write(err_msg)
            await writer.drain()
            writer.close()
            return

        # Получаем установленное ранее соединение с клиент-сервером
        service_reader, service_writer = registered_services[service_id]
        print(f"[External] Туннель установлен между {client_addr} и сервисом {service_id}")

        # Пересылаем данные между внешним клиентом и клиент-сервером (SOCKS5 будет обрабатываться на клиент-сервере)
        await asyncio.gather(
            forward_data(reader, service_writer),
            forward_data(service_reader, writer)
        )
    except asyncio.IncompleteReadError:
        print(f"[External] Оборвано соединение с клиентом {client_addr}")
    except Exception as e:
        print(f"[External] Ошибка с клиентом {client_addr}: {e}")
    finally:
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass

async def register_service(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    """
    Обрабатывает регистрацию сервисов.
    При подключении генерируется уникальный ID, сохраняется привязка ID → (reader, writer)
    и ID отправляется клиенту.
    Далее соединение используется для туннелирования (обработка SOCKS5 на стороне клиента).
    """
    client_addr = writer.get_extra_info('peername')
    import uuid
    service_id = str(uuid.uuid4())
    registered_services[service_id] = (reader, writer)
    print(f"[Register] Сервис с {client_addr} зарегистрирован под ID: {service_id}")

    try:
        # Отправляем ID для дальнейших подключений
        writer.write(service_id.encode('utf-8'))
        await writer.drain()

        # Держим соединение открытым.
        while True:
            await asyncio.sleep(1)
            # Здесь можно добавить heartbeat или другое управление соединением.
    except Exception as e:
        print(f"[Register] Ошибка сервиса {service_id}: {e}")
    finally:
        print(f"[Register] Сервис {service_id} отключился")
        registered_services.pop(service_id, None)
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass

async def main():
    # Сервер для внешних клиентов (порт 1080)
    external_server = await asyncio.start_server(handle_external_client, '0.0.0.0', 1080)
    # Сервер регистрации сервисов (порт 8888)
    registration_server = await asyncio.start_server(register_service, '0.0.0.0', 8888)

    print("Сервер запущен:")
    print(" - Регистрация сервисов: порт 8888")
    print(" - Подключения клиентов: порт 1080")

    async with external_server, registration_server:
        await asyncio.gather(
            external_server.serve_forever(),
            registration_server.serve_forever()
        )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Сервер остановлен")
