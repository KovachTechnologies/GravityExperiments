# OpenMV real-time laser-spot analytics (aggregator mode)
# Conductive tape can split the beam into ~3 overlapping bright lobes.
# This script finds the brightest blobs, keeps the top 3, and streams
# each lobe's center of mass plus a pixel-weighted overall COM.
#
# Implements the READY / START / STOP handshake used by aggregator.py.
# Companion local-only logger: camera_local.py (does not change).

import sensor
import image
import time
import json
from pyb import USB_VCP

# ---------- Configuration ----------
BRIGHT_THRESH = (180, 255)    # lower bound may need to be higher so the
                              # connecting necks drop out and lobes separate
MIN_PIXELS = 30
MIN_AREA = 40
FRAMESIZE = sensor.QVGA       # or sensor.QQVGA for higher FPS
MAX_DOTS = 3                  # expect up to 3 lobes from the tape refraction
DEVICE_NAME = "camera"
READY_INTERVAL = 1.0          # seconds between READY lines while waiting
BAUD_NOTE = 115200            # host aggregator uses this baud (USB CDC ignores it)

# ---------- Hardware setup ----------
sensor.reset()
sensor.set_pixformat(sensor.GRAYSCALE)
sensor.set_framesize(FRAMESIZE)
sensor.skip_frames(time=2000)
sensor.set_auto_gain(False)      # critical for stable thresholds
sensor.set_auto_whitebal(False)
sensor.set_auto_exposure(False, exposure_us=10000)  # tune for your laser intensity

usb = USB_VCP()
# Avoid Ctrl-C interrupting the measurement loop; host uses STOP instead
try:
    usb.setinterrupt(-1)
except Exception:
    pass

# ---------- Serial helpers (USB VCP) ----------
def check_command():
    """
    Non-blocking read of one line from the USB virtual COM port.
    Returns the stripped line or None.
    """
    try:
        if usb.any():
            raw = usb.readline()
            if raw:
                return raw.decode("utf-8", errors="ignore").strip()
    except Exception:
        pass
    return None

def emit_json(obj):
    """Send one JSON line over USB serial."""
    try:
        line = json.dumps(obj, separators=(",", ":"))
        usb.write(line + "\n")
    except Exception:
        # Fallback to print if USB write fails
        print(json.dumps(obj, separators=(",", ":")))

def emit_ready():
    """Emit the self-identification heartbeat expected by aggregator.py."""
    try:
        usb.write(f"READY:{DEVICE_NAME}\n")
    except Exception:
        print(f"READY:{DEVICE_NAME}")

# ---------- Main state machine ----------
emit_ready()  # immediate first READY for fast discovery

while True:
    # ---------- Waiting for START ----------
    started = False
    last_ready = time.ticks_ms()
    while not started:
        cmd = check_command()
        if cmd == "START":
            started = True
            break
        elif cmd == "STOP":
            # ignore STOP while already idle
            pass
        # Periodic READY heartbeat
        now = time.ticks_ms()
        if time.ticks_diff(now, last_ready) >= int(READY_INTERVAL * 1000):
            emit_ready()
            last_ready = now
        time.sleep_ms(50)

    # ---------- Running (streaming) ----------
    start_ms = time.ticks_ms()
    running = True
    while running:
        # Check for STOP (or another START which restarts the timer)
        cmd = check_command()
        if cmd == "STOP":
            running = False
            break
        elif cmd == "START":
            start_ms = time.ticks_ms()  # reset device timer

        img = sensor.snapshot()

        # merge=False so that weakly-connected lobes stay separate when the
        # connecting neck falls below BRIGHT_THRESH.
        blobs = img.find_blobs(
            [BRIGHT_THRESH],
            pixels_threshold=MIN_PIXELS,
            area_threshold=MIN_AREA,
            merge=False,
            margin=0,
        )

        t_ms = time.ticks_diff(time.ticks_ms(), start_ms)

        if blobs:
            # Keep the largest blobs (the three bright lobes)
            blobs.sort(key=lambda b: b.pixels(), reverse=True)
            top = blobs[:MAX_DOTS]

            # Sort the selected lobes top-to-bottom by cy so the order is stable
            top.sort(key=lambda b: b.cy())

            # Pixel-weighted overall center of mass of the selected lobes
            total_pixels = sum(b.pixels() for b in top)
            if total_pixels > 0:
                overall_cx = sum(b.cx() * b.pixels() for b in top) / total_pixels
                overall_cy = sum(b.cy() * b.pixels() for b in top) / total_pixels
            else:
                overall_cx = overall_cy = 0.0

            # Build per-dot records (pad missing with null)
            dots = []
            for i in range(MAX_DOTS):
                if i < len(top):
                    b = top[i]
                    dots.append({
                        "cx": b.cx(),
                        "cy": b.cy(),
                        "area": b.area(),
                    })
                    # Draw for IDE preview
                    img.draw_rectangle(b.rect(), color=127)
                    img.draw_cross(b.cx(), b.cy(), color=255)
                else:
                    dots.append({"cx": None, "cy": None, "area": 0})

            # Overall COM cross
            img.draw_cross(int(overall_cx), int(overall_cy), color=200, size=8)

            record = {
                "t_ms": t_ms,
                "n_dots": len(top),
                "overall_cx": round(overall_cx, 2),
                "overall_cy": round(overall_cy, 2),
                "dot1_cx": dots[0]["cx"],
                "dot1_cy": dots[0]["cy"],
                "dot1_area": dots[0]["area"],
                "dot2_cx": dots[1]["cx"],
                "dot2_cy": dots[1]["cy"],
                "dot2_area": dots[1]["area"],
                "dot3_cx": dots[2]["cx"],
                "dot3_cy": dots[2]["cy"],
                "dot3_area": dots[2]["area"],
            }
        else:
            record = {
                "t_ms": t_ms,
                "n_dots": 0,
                "overall_cx": None,
                "overall_cy": None,
                "dot1_cx": None, "dot1_cy": None, "dot1_area": 0,
                "dot2_cx": None, "dot2_cy": None, "dot2_area": 0,
                "dot3_cx": None, "dot3_cy": None, "dot3_area": 0,
            }

        emit_json(record)

    # After STOP, fall back to the outer loop and resume READY heartbeats
    emit_ready()
