# OpenMV real-time laser-spot analytics
# Streams timestamped metrics over USB serial (or hardware UART).
# Matches the spirit of the prior beam-analysis experiment.

import sensor
import image
import time
from pyb import UART          # only needed for hardware UART path

# ---------- Configuration ----------
USE_HARDWARE_UART = False     # True = RS232 shield / external UART; False = USB VCP
BAUDRATE = 115200
BRIGHT_THRESH = (200, 255)    # grayscale low/high for near-white core (tune as needed)
MIN_PIXELS = 50
MIN_AREA = 100
FRAMESIZE = sensor.QVGA       # or sensor.QQVGA for higher FPS

# ---------- Hardware setup ----------
sensor.reset()
sensor.set_pixformat(sensor.GRAYSCALE)
sensor.set_framesize(FRAMESIZE)
sensor.skip_frames(time=2000)
sensor.set_auto_gain(False)      # critical for stable thresholds
sensor.set_auto_whitebal(False)
sensor.set_auto_exposure(False, exposure_us=10000)  # tune for your laser intensity

if USE_HARDWARE_UART:
    # UART 3 → P4 (TX), P5 (RX) on most OpenMV boards (matches RS232 shield)
    uart = UART(3, BAUDRATE, timeout_char=1000)
else:
    uart = None   # print() goes to the USB virtual COM port

clock = time.clock()
start_ms = time.ticks_ms()

def send(line):
    """Send one line of telemetry."""
    if uart:
        uart.write(line + "\n")
    else:
        print(line)

# Header (optional, once)
send("t_ms,cx,cy,cxf,cyf,area,pixels,density,rotation_deg,elongation,mean_int,edge_pixels")

while True:
    clock.tick()
    img = sensor.snapshot()

    # Optional light edge detection for a roughness proxy
    edge_count = 0
    # edges = img.copy().find_edges(image.EDGE_SIMPLE, threshold=(40, 80))
    # edge_count = edges.get_histogram().get_percentile(0.99).l_value()  # cheap proxy

    blobs = img.find_blobs(
        [BRIGHT_THRESH],
        pixels_threshold=MIN_PIXELS,
        area_threshold=MIN_AREA,
        merge=True,
        margin=2,
    )

    t_ms = time.ticks_diff(time.ticks_ms(), start_ms)

    if blobs:
        # largest blob = core
        b = max(blobs, key=lambda x: x.pixels())

        # Sub-pixel centroid (preferred for deflection tracking)
        cx = b.cx()
        cy = b.cy()
        cxf = getattr(b, "cxf", lambda: cx)()
        cyf = getattr(b, "cyf", lambda: cy)()

        # Intensity stats inside the blob (same thresholds)
        stats = img.get_statistics(roi=b.rect(), thresholds=[BRIGHT_THRESH])
        mean_int = stats.mean()

        line = (
            f"{t_ms},{cx},{cy},{cxf:.2f},{cyf:.2f},"
            f"{b.area()},{b.pixels()},{b.density():.3f},"
            f"{b.rotation()*57.3:.1f},{b.elongation():.3f},"
            f"{mean_int:.1f},{edge_count}"
        )
        send(line)

        # Optional drawing for IDE preview
        img.draw_rectangle(b.rect(), color=127)
        img.draw_cross(cx, cy, color=255)
    else:
        send(f"{t_ms},nan,nan,nan,nan,0,0,0,0,0,0,0")

    # print(clock.fps())   # uncomment for FPS debug
