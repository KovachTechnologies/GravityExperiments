#!/usr/bin/python3

###########################################################################
#
# name          : tcp_server.py
#
# purpose       : receive measurement lines over TCP and append them to
#                 data.txt as ASCII
#
# usage         : python3 tcp_server.py
#                 python3 tcp_server.py --host 0.0.0.0 --port 5000 --out data.txt
#
# description   : Listens on a TCP port. Each incoming connection may send
#                 one or more newline-terminated ASCII messages. Every
#                 complete line is written to the output file immediately.
#
###########################################################################

import argparse
import socket
from datetime import datetime, timezone
from pathlib import Path


HOST = "0.0.0.0"
PORT = 5001
OUT_FILE = Path("data.txt")
RECV_SIZE = 4096


def log(msg):
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{now}Z] {msg}", flush=True)


def handle_client(conn, addr, out_path):
    peer = f"{addr[0]}:{addr[1]}"
    log(f"connected {peer}")
    buffer = ""
    try:
        with conn:
            while True:
                chunk = conn.recv(RECV_SIZE)
                if not chunk:
                    break
                buffer += chunk.decode("ascii", errors="replace")
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    line = line.rstrip("\r")
                    if not line:
                        continue
                    with open(out_path, "a", encoding="ascii", errors="replace") as f:
                        f.write(line + "\n")
                        f.flush()
                    log(f"wrote {len(line)} bytes from {peer}")
            leftover = buffer.strip("\r")
            if leftover:
                with open(out_path, "a", encoding="ascii", errors="replace") as f:
                    f.write(leftover + "\n")
                    f.flush()
                log(f"wrote trailing {len(leftover)} bytes from {peer}")
    except ConnectionResetError:
        log(f"reset by {peer}")
    finally:
        log(f"disconnected {peer}")


def serve(host, port, out_path):
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.touch(exist_ok=True)

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((host, port))
        server.listen(5)
        log(f"listening on {host}:{port} -> {out_path.resolve()}")
        while True:
            conn, addr = server.accept()
            handle_client(conn, addr, out_path)


def main():
    parser = argparse.ArgumentParser(description="TCP receiver that appends ASCII lines to a file")
    parser.add_argument("--host", default=HOST, help="bind address (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=PORT, help="bind port (default: 5000)")
    parser.add_argument("--out", default=str(OUT_FILE), help="output file (default: data.txt)")
    args = parser.parse_args()
    serve(args.host, args.port, args.out)


if __name__ == "__main__":
    main()
