#!/usr/bin/env python3
import socket
import threading
import time

def heartbeat_loop(sock, interval=30):
    while True:
        try:
            sock.sendall(b"ping")
            print("[HEARTBEAT] Отправлен ping")
        except Exception as e:
            print(f"[ERROR] Ошибка heartbeat: {e}")
            break
        time.sleep(interval)

def main():
    scop_host = "localhost"  # IP сервера
    scop_port = 9000

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((scop_host, scop_port))
        internal_ip, internal_port = sock.getsockname()
        print(f"[CONNECTED] Локальный адрес: {internal_ip}:{internal_port}")

        # Получаем внешний адрес
        response = sock.recv(1024).decode().strip()
        external_ip, external_port = response.split(":")
        print(f"[HANDSHAKE] Получен внешний адрес: {external_ip}:{external_port}")
    except Exception as e:
        print(f"[ERROR] Не удалось подключиться к SCOP: {e}")
        return

    # Запуск heartbeat потока
    threading.Thread(target=heartbeat_loop, args=(sock,), daemon=True).start()

    print("[READY] Соединение установлено, heartbeat активен.")
    try:
        while True:
            time.sleep(1)  # Просто держим клиент живым
    except KeyboardInterrupt:
        print("[STOP] Остановка клиента.")
        sock.close()

if __name__ == '__main__':
    main()
