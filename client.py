import socket
import threading
import time

# === SCOP Server ===
def scop_server(host='0.0.0.0', port=9999):
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

# === P2P Client ===
def parse_addr(addr_str):
    ip, port = addr_str.strip().split(':')
    return ip, int(port)

def punch_hole(sock, peer_addr):
    for _ in range(20):
        sock.sendto(b'ping', peer_addr)
        time.sleep(0.1)

def start_socks5_proxy(sock, peer_addr):
    def recv_loop():
        while True:
            try:
                data, _ = sock.recvfrom(4096)
                if data.startswith(b'SOCKS5:'):
                    content = data[7:]
                    remote.sendall(content)
                else:
                    print("[UDP]", data.decode(errors='ignore'))
            except Exception as e:
                print("[RECV ERROR]", e)
                break

    def send_loop():
        try:
            while True:
                data = remote.recv(4096)
                packet = b'SOCKS5:' + data
                sock.sendto(packet, peer_addr)
        except Exception as e:
            print("[SEND ERROR]", e)

    # SOCKS5 handshake (TCP локально)
    proxy = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    proxy.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    proxy.bind(('127.0.0.1', 1080))
    proxy.listen(1)
    print("[SOCKS5] Локальный SOCKS5 на 127.0.0.1:1080")

    while True:
        client, addr = proxy.accept()
        print(f"[SOCKS5] Клиент: {addr}")

        try:
            greeting = client.recv(262)
            client.sendall(b'\x05\x00')

            req = client.recv(4)
            if len(req) < 4 or req[1] != 1:
                client.close()
                continue

            atyp = req[3]
            if atyp == 1:
                dest_addr = socket.inet_ntoa(client.recv(4))
            elif atyp == 3:
                domain_len = client.recv(1)[0]
                dest_addr = client.recv(domain_len).decode()
            else:
                client.close()
                continue
            dest_port = int.from_bytes(client.recv(2), 'big')

            print(f"[SOCKS5] CONNECT {dest_addr}:{dest_port}")

            global remote
            remote = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            remote.connect((dest_addr, dest_port))

            reply = b'\x05\x00\x00\x01' + socket.inet_aton("0.0.0.0") + (0).to_bytes(2, 'big')
            client.sendall(reply)

            threading.Thread(target=recv_loop, daemon=True).start()
            threading.Thread(target=send_loop, daemon=True).start()

            while True:
                data = client.recv(4096)
                if not data:
                    break
                remote.sendall(data)
        except Exception as e:
            print("[SOCKS5 ERROR]", e)
        finally:
            client.close()
            remote.close()

# === Entry Point ===
if __name__ == '__main__':
    SCOP_HOST = 'YOUR_SCOP_IP_HERE'  # Заменить на IP SCOP-сервера
    SCOP_PORT = 9999

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(('0.0.0.0', 0))
    sock.sendto(b'hello', (SCOP_HOST, SCOP_PORT))
    print("[CLIENT] Жду адрес пира от SCOP...")

    data, _ = sock.recvfrom(1024)
    peer_ip, peer_port = parse_addr(data.decode())
    peer = (peer_ip, peer_port)
    print(f"[CLIENT] Адрес пира: {peer}")

    punch_hole(sock, peer)
    start_socks5_proxy(sock, peer)