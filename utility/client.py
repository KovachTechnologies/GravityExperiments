import socket

SERVER_HOST = "192.168.1.10" 
SERVER_PORT = 5001
SEND_TIMEOUT_S = 2.0


def send_measurement(epoch, value, timestamp=None, host=SERVER_HOST, port=SERVER_PORT):
    if timestamp is None:
        line = f"{value}\n"
    else:
        line = f"{epoch},{timestamp},{value}\n"

    payload = line.encode("ascii", errors="replace")
    with socket.create_connection((host, port), timeout=SEND_TIMEOUT_S) as sock:
        sock.sendall(payload)
