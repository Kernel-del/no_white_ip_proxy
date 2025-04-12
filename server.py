# === scop_server.py ===
import socket


def scop_server(host='0.0.0.0', port=9000):
    print(f"[SCOP] UDP сервер на {host}:{port}")
    server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server.bind((host, port))

    clients = []

    while True:
        data, addr = server.recvfrom(1024)
        if addr not in clients:
            clients.append(addr)
            print(f"[SCOP] Новый клиент: {addr}")

        if len(clients) == 2:
            a, b = clients
            server.sendto(f"{b[0]}:{b[1]}".encode(), a)
            server.sendto(f"{a[0]}:{a[1]}".encode(), b)
            print(f"[SCOP] Адреса обменяны: {a} <-> {b}")
            clients.clear()


if __name__ == '__main__':
    scop_server()
