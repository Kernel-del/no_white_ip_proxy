#!/usr/bin/env python3
import socket
import threading
import select
import time

def start_socks5_server(listen_host, listen_port):
    """
    Запускает минимальный SOCKS5-сервер, поддерживающий команду CONNECT.
    """
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # Разрешаем повторное использование адреса
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
    except Exception as e:
        print("SO_REUSEPORT не поддерживается:", e)

    try:
        server.bind((listen_host, listen_port))
    except OSError as e:
        print(f"Ошибка при привязке к {listen_host}:{listen_port} - {e}")
        return
    server.listen(5)
    print(f"SOCKS5 сервер запущен, слушает {listen_host}:{listen_port}")

    while True:
        client_sock, client_addr = server.accept()
        print(f"Получено подключение к SOCKS5 от {client_addr}")
        threading.Thread(target=handle_socks5_client, args=(client_sock,), daemon=True).start()

def handle_socks5_client(client):
    """
    Обрабатывает рукопожатие SOCKS5 и осуществляет проксирование данных.
    """
    try:
        greeting = client.recv(262)
        if not greeting:
            client.close()
            return
        client.sendall(b'\x05\x00')
        request = client.recv(4)
        if len(request) < 4:
            client.close()
            return
        ver, cmd, _, atyp = request[0], request[1], request[2], request[3]
        if ver != 5 or cmd != 1:  # поддерживаем только CONNECT
            client.close()
            return

        # Определяем адрес назначения
        if atyp == 1:  # IPv4
            addr = socket.inet_ntoa(client.recv(4))
        elif atyp == 3:  # доменное имя
            domain_length = client.recv(1)[0]
            addr = client.recv(domain_length).decode()
        elif atyp == 4:  # IPv6
            addr = socket.inet_ntop(socket.AF_INET6, client.recv(16))
        else:
            client.close()
            return

        port = int.from_bytes(client.recv(2), 'big')
        print(f"Запрос на подключение к {addr}:{port}")
        remote = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        remote.connect((addr, port))
        reply = b'\x05\x00\x00\x01' + socket.inet_aton("0.0.0.0") + (0).to_bytes(2, 'big')
        client.sendall(reply)
        relay_sockets(client, remote)
    except Exception as e:
        print("Ошибка в SOCKS5 обработчике:", e)
    finally:
        client.close()

def relay_sockets(sock1, sock2):
    """
    Передаёт данные в обе стороны между sock1 и sock2 с помощью select.
    """
    sockets = [sock1, sock2]
    try:
        while True:
            readable, _, _ = select.select(sockets, [], [])
            for s in readable:
                data = s.recv(4096)
                if not data:
                    return
                if s is sock1:
                    sock2.sendall(data)
                else:
                    sock1.sendall(data)
    except Exception as e:
        print("Ошибка при передаче данных:", e)
    finally:
        sock1.close()
        sock2.close()

def heartbeat(sock, interval=30):
    """
    Периодически отправляет heartbeat-сообщение через открытое соединение,
    чтобы провайдер не закрыл порт из-за неактивности.
    """
    while True:
        try:
            # Можно отправлять любой небольшой сигнал, например 'ping'
            sock.sendall(b'ping')
            # Не обязательно ждать ответа; если нужно – добавить обработку.
        except Exception as e:
            print("Ошибка при отправке heartbeat:", e)
            break
        time.sleep(interval)

def main():
    """
    Логика работы CPS с heartbeat:
      1. Устанавливаем исходящее соединение с SCOP и получаем внешний адрес.
      2. Запускаем отдельный поток, который каждые interval секунд отправляет сигнал.
      3. (Опционально) Запускаем SOCKS5-сервер, если планируется принимать входящие подключения.
         Если используется единичное соединение и требуется мультиплексирование – нужно доработать протокол.
    """
    scop_host = "100.125.120.106"  # замените на реальный адрес SCOP-сервера
    scop_port = 9000

    # Устанавливаем исходящее соединение с SCOP
    cps_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        cps_socket.connect((scop_host, scop_port))
    except Exception as e:
        print("Ошибка подключения к SCOP:", e)
        return

    internal_ip, internal_port = cps_socket.getsockname()
    response = cps_socket.recv(1024).decode().strip()
    try:
        external_ip, external_port = response.split(":")
        external_port = int(external_port)
    except Exception as e:
        print("Ошибка при разборе данных от SCOP:", e)
        cps_socket.close()
        return

    print(f"Внутренний адрес CPS: {internal_ip}:{internal_port}")
    print(f"Внешний адрес (как видит SCOP): {external_ip}:{external_port}")

    # Запускаем поток для heartbeat на SCOP-соединении
    hb_thread = threading.Thread(target=heartbeat, args=(cps_socket,), daemon=True)
    hb_thread.start()
    print("Heartbeat запущен – периодическая отправка сигналов для поддержания порта.")

    # Если требуется запустить SOCKS5-сервер на том же порту, надо реализовать мультиплексирование.
    # Либо можно после этого закрыть cps_socket и запустить отдельный сервер, но NAT mapping может быть потерян.
    # Для демонстрации ниже приведён запуск SOCKS5-сервера на порту, отличном от internal_port.
    alt_port = internal_port + 1  # пример выбора другого порта
    socks_thread = threading.Thread(target=start_socks5_server, args=(internal_ip, alt_port), daemon=True)
    socks_thread.start()
    print(f"SOCKS5-сервер запущен на {internal_ip}:{alt_port}")

    # Основной поток остаётся активным, например, ожидание событий.
    while True:
        time.sleep(1)

if __name__ == '__main__':
    main()
