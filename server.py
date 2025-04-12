#!/usr/bin/env python3
import socket
import threading

def handle_client(conn, addr):
    """
    Обрабатывает соединение от CPS.
    Определяет внешний IP и порт (адрес, с которого пришёл запрос)
    и отправляет их обратно.
    """
    external_ip, external_port = addr[0], addr[1]
    response = f"{external_ip}:{external_port}"
    print(f"Получен запрос от {external_ip}:{external_port}, отправляю ответ: {response}")
    try:
        conn.sendall(response.encode())
        # Поддерживаем соединение открытым, пока CPS не разорвет его
        while True:
            data = conn.recv(1024)
            if not data:
                break
    except Exception as e:
        print("Ошибка в обработке соединения:", e)
    finally:
        conn.close()
        print(f"Соединение с {external_ip}:{external_port} закрыто")

def run_scop_server():
    host = ''  # слушаем на всех интерфейсах
    port = 9000
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind((host, port))
    server.listen(5)
    print(f"SCOP сервер запущен, слушает порт {port}")

    while True:
        conn, addr = server.accept()
        print(f"Установлено соединение от {addr}")
        threading.Thread(target=handle_client, args=(conn, addr), daemon=True).start()

if __name__ == '__main__':
    run_scop_server()
