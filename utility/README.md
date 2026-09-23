# Measurement stream: client.py and server.py

These two scripts move live readings off the measuring device and onto another computer on the same LAN. They use a raw TCP socket, not HTTP.

| File | Where it runs | Role |
|---|---|---|
| `client.py` | Measuring device | Snippet to drop into the existing Python acquisition script. Sends one ASCII line per sample. |
| `server.py` | Logging PC | Listens on a TCP port and appends every received line to `data.txt`. |

The copies checked in here as `tcp_client_snippet.py` / `tcp_server.py` are the same idea. Use the attached `client.py` / `server.py` values below (port **5001**, line format `epoch,timestamp,value`).

## What to configure

Both sides must agree on **IP and port**.

In `client.py`:

```python
SERVER_HOST = "192.168.1.10"   # LAN IP of the PC running server.py
SERVER_PORT = 5001             # must match the server
```

`192.168.1.10` is a placeholder. Replace it with the logging PC’s actual address (`ip -4 addr` on Linux, `ipconfig` on Windows). Do **not** use `127.0.0.1` unless client and server are on the same machine.

In `server.py` the defaults are:

```python
HOST = "0.0.0.0"   # accept connections from the LAN
PORT = 5001
OUT_FILE = Path("data.txt")
```

`0.0.0.0` is correct for a second computer. Override on the command line if needed:

```bash
python3 server.py --host 0.0.0.0 --port 5001 --out data.txt
```

Allow inbound TCP **5001** on the logging PC’s firewall.

## Measuring device: add client.py

`client.py` is not a standalone program. Copy its imports and `send_measurement()` into the Python script that already drives the scale.

After each reading is in hand:

```python
try:
    send_measurement(epoch, value, timestamp)
except OSError as exc:
    print(f"TCP send failed: {exc}")
```

Line format when `timestamp` is provided:

```
<epoch>,<timestamp>,<value>
```

If `timestamp` is omitted, only the value is sent:

```
<value>
```

Each call opens a short-lived TCP connection, writes one newline-terminated ASCII line, and closes. That is slower than a persistent socket but recovers cleanly if the link drops.

Start the server **before** the device starts sending.

## Logging PC: run server.py

On the computer that should collect the file:

```bash
python3 server.py
```

or with explicit options:

```bash
python3 server.py --host 0.0.0.0 --port 5001 --out data.txt
```

The process stays in the foreground and logs connects, writes, and disconnects. Each complete line is flushed to `data.txt` immediately. Stop it with Ctrl-C.

`data.txt` is created next to the server if it does not already exist. Later sessions append; they do not overwrite.

## Quick check

1. Start `server.py` on the logging PC.
2. From the measuring device (or any machine on the LAN), send one test line — either take a real sample with the patched acquisition script, or:

   ```bash
   python3 -c "from client import send_measurement; send_measurement(0, 12.3, 1710000000)"
   ```

3. Confirm a new line appeared in `data.txt` on the logging PC.

If nothing arrives: wrong `SERVER_HOST`, server not bound to `0.0.0.0`, port mismatch (client and server must both use 5001), or the firewall is blocking the port.
