#!/usr/bin/env python3
"""
client_server.py – Клиент-сервер, запускаемый на устройстве за NAT.
Подключается к центральному серверу (HOST:PORT нужно указать),
регистрируется и получает уникальный ID. После этого по установленному туннелю
обрабатывается стандартное SOCKS5‑рукопожатие:
  1. Принимается приветствие SOCKS5.
  2. Отправляется ответ (метод "нет аутентификации").
  3. Принимается запрос (CONNECT) с указанием целевого адреса и порта.
  4. Пробуется установление TCP-соединения с целевым адресом.
  5. Отправляется ответ SOCKS5.
  6. Запускается двунаправленный обмен данными между туннелированным соединением и целевым сервером.
"""

import asyncio
import sys
import struct

# Настройте адрес и порт центрального сервера для регистрации
CENTRAL_SERVER_HOST = 'localhost'    # Замените на IP центрального сервера
CENTRAL_SERVER_PORT = 8888

async def handle_socks_connection(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    """
    Обработка SOCKS5‑рукопожатия и подключения к цели.
    """
    peer = writer.get_extra_info('peername')
    print(f"[SOCKS] Туннель установлен, обработка SOCKS5 от {peer}")
    try:
        # 1. Получаем приветствие SOCKS5
        # Клиент посылает: VER, NMETHODS, METHODS...
        data = await reader.read(2)
        if len(data) < 2:
            raise Exception("Неполное приветствие")
        ver, nmethods = struct.unpack("!BB", data)
        methods = await reader.read(nmethods)
        print(f"[SOCKS] Приветствие: ver={ver}, nmethods={nmethods}, methods={methods.hex()}")

        # Отвечаем методом "нет аутентификации" (0x00)
        writer.write(struct.pack("!BB", 0x05, 0x00))
        await writer.drain()

        # 2. Получаем запрос
        # Формат запроса: VER, CMD, RSV, ATYP, DST.ADDR, DST.PORT
        header = await reader.readexactly(4)
        ver, cmd, rsv, atyp = struct.unpack("!BBBB", header)
        if ver != 0x05:
            raise Exception("Неверная версия SOCKS")
        if cmd != 0x01:  # поддерживаем только CONNECT
            # Отправляем ответ "Command not supported"
            writer.write(struct.pack("!BBBBIH", 0x05, 0x07, 0x00, 0x01, 0, 0))
            await writer.drain()
            raise Exception("Команда не поддерживается")

        # Читаем адрес в зависимости от ATYP
        if atyp == 0x01:  # IPv4
            addr_bytes = await reader.readexactly(4)
            address = ".".join(map(str, addr_bytes))
        elif atyp == 0x03:  # доменное имя
            domain_length = await reader.readexactly(1)
            domain_length = domain_length[0]
            addr_bytes = await reader.readexactly(domain_length)
            address = addr_bytes.decode('utf-8')
        elif atyp == 0x04:  # IPv6
            addr_bytes = await reader.readexactly(16)
            address = ":".join([addr_bytes[i:i+2].hex() for i in range(0, 16, 2)])
        else:
            raise Exception("ATYP не поддерживается")

        # Читаем порт (2 байта)
        port_bytes = await reader.readexactly(2)
        port = struct.unpack("!H", port_bytes)[0]

        print(f"[SOCKS] Запрошено соединение с {address}:{port}")

        # 3. Пытаемся установить соединение с целевым сервером
        try:
            target_reader, target_writer = await asyncio.open_connection(address, port)
        except Exception as e:
            print(f"[SOCKS] Не удалось подключиться к {address}:{port} – {e}")
            # Отправляем ответ с ошибкой (например, 0x04 - Host unreachable)
            reply = struct.pack("!BBBBIH", 0x05, 0x04, 0x00, 0x01, 0, 0)
            writer.write(reply)
            await writer.drain()
            writer.close()
            return

        # 4. Отправляем успешный ответ (REP=0x00)
        # Для простоты в качестве BND.ADDR/BND.PORT отправляем 0.0.0.0:0
        reply = struct.pack("!BBBBIH", 0x05, 0x00, 0x00, 0x01, 0, 0)
        writer.write(reply)
        await writer.drain()
        print(f"[SOCKS] Соединение с {address}:{port} установлено. Запущен туннель")

        # 5. Запускаем пересылку данных между клиентским (туннельным) соединением и целевым сервером
        await asyncio.gather(
            forward_data(reader, target_writer),
            forward_data(target_reader, writer)
        )
    except Exception as e:
        print(f"[SOCKS] Ошибка: {e}")
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass

async def forward_data(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    """
    Функция для пересылки данных, аналогична реализации на сервере.
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

async def run_service():
    """
    Подключается к центральному серверу для регистрации.
    После регистрации получает туннельное соединение, по которому
    будет обрабатываться SOCKS5‑рукопожатие.
    """
    try:
        print(f"[Client-Server] Подключение к центральному серверу {CENTRAL_SERVER_HOST}:{CENTRAL_SERVER_PORT}...")
        reader, writer = await asyncio.open_connection(CENTRAL_SERVER_HOST, CENTRAL_SERVER_PORT)
    except Exception as e:
        print(f"[Client-Server] Ошибка подключения к центральному серверу: {e}")
        sys.exit(1)

    try:
        # Получаем 36‑байтный ID
        service_id_bytes = await reader.readexactly(36)
        service_id = service_id_bytes.decode('utf-8').strip()
        print(f"[Client-Server] Сервис зарегистрирован. Ваш ID: {service_id}")
        print("[Client-Server] Ожидание входящих туннельных соединений для обработки SOCKS5...")
    except Exception as e:
        print(f"[Client-Server] Ошибка при регистрации: {e}")
        writer.close()
        await writer.wait_closed()
        sys.exit(1)

    # В данной реализации единственное соединение используется для SOCKS5.
    # Все данные, поступающие по туннелю, обрабатываются как SOCKS5‑сессия.
    await handle_socks_connection(reader, writer)

if __name__ == '__main__':
    try:
        asyncio.run(run_service())
    except KeyboardInterrupt:
        print("[Client-Server] Остановка сервиса")
