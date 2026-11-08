# OpenMV real-time laser-spot analytics (local file logging)
# Identical multi-dot center-of-mass logic to camera.py, but writes
# CSV lines to a local file instead of streaming over serial.
#
# Conductive tape can split the beam into ~3 overlapping bright lobes.
# This script finds the brightest blobs, keeps the top 3, and logs
# each lobe's center of mass plus a pixel-weighted overall COM.

import sensor
import image
import time

# ---------- Configuration ----------
BRIGHT_THRESH = (180, 255)    # lower bound may need to be higher so the
                              # connecting necks drop out and lobes separate
MIN_PIXELS = 30
MIN_AREA = 40
FRAMESIZE = sensor.QVGA       # or sensor.QQVGA for higher FPS
MAX_DOTS = 3                  # expect up to 3 lobes from the tape refraction
LOG_FILE = "beam_local.csv"   # written to the OpenMV filesystem (or SD card root)

# ---------- Hardware setup ----------
sensor.reset()
sensor.set_pixformat(sensor.GRAYSCALE)
sensor.set_framesize(FRAMESIZE)
sensor.skip_frames(time=2000)
sensor.set_auto_gain(False)      # critical for stable thresholds
sensor.set_auto_whitebal(False)
sensor.set_auto_exposure(False, exposure_us=10000)  # tune for your laser intensity

clock = time.clock()
start_ms = time.ticks_ms()

# Open log file (overwrite on each run). Use "a" if you want to append.
log = open(LOG_FILE, "w")
header = ("t_ms,n_dots,overall_cx,overall_cy,"
          "dot1_cx,dot1_cy,dot1_area,"
          "dot2_cx,dot2_cy,dot2_area,"
          "dot3_cx,dot3_cy,dot3_area")
log.write(header + "\n")
log.flush()

def write_line(line):
    """Write one telemetry line to the local file."""
    log.write(line + "\n")
    # Flush occasionally so data survives an unexpected reset
    if time.ticks_ms() % 500 < 50:
        log.flush()

while True:
    clock.tick()
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

        # Build the fixed-width output (pad missing dots with nan)
        parts = [str(t_ms), str(len(top)), f"{overall_cx:.2f}", f"{overall_cy:.2f}"]
        for i in range(MAX_DOTS):
            if i < len(top):
                b = top[i]
                parts.append(str(b.cx()))
                parts.append(str(b.cy()))
                parts.append(str(b.area()))
                # Draw for IDE preview
                img.draw_rectangle(b.rect(), color=127)
                img.draw_cross(b.cx(), b.cy(), color=255)
            else:
                parts.extend(["nan", "nan", "0"])

        # Overall COM cross (thicker / different color if desired)
        img.draw_cross(int(overall_cx), int(overall_cy), color=200, size=8)

        write_line(",".join(parts))
    else:
        write_line(f"{t_ms},0,nan,nan,nan,nan,0,nan,nan,0,nan,nan,0")

    # print(clock.fps())   # uncomment for FPS debug
