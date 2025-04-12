#!/usr/bin/env python3
import socket
import threading

def handle_client(conn, addr):
    external_ip, external_port = addr
    response = f"{external_ip}:{external_port}"
    print(f"[HANDSHAKE] От {external_ip}:{external_port}, отправляю: {response}")

    try:
        conn.sendall(response.encode())
        while True:
            data = conn.recv(1024)
            if not data:
                print(f"[DISCONNECT] {external_ip}:{external_port} отключился.")
                break
            print(f"[HEARTBEAT] от {external_ip}:{external_port}: {data.decode(errors='ignore')}")
    except Exception as e:
        print(f"[ERROR] Ошибка в соединении с {external_ip}:{external_port} — {e}")
    finally:
        conn.close()
        print(f"[CLOSE] Соединение закрыто с {external_ip}:{external_port}")

def run_scop_server():
    host = ''
    port = 9000
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind((host, port))
    server.listen(5)
    print(f"[START] SCOP сервер слушает порт {port}")

    while True:
        conn, addr = server.accept()
        print(f"[CONNECT] Новое соединение от {addr}")
        threading.Thread(target=handle_client, args=(conn, addr), daemon=True).start()

if __name__ == '__main__':
    run_scop_server()
