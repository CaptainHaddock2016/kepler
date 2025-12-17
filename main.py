# ==============================
# MPOS (Microprocessor OS) Boot Script
# ==============================
MACHINE_NAME = "machine"

# Level 1 - Hardware Initialization
import displayio
import supervisor
import storage
from adafruit_display_text import label
from terminalio import FONT, Terminal

# --- Initialize Display ---
display = supervisor.runtime.display
DISPROOT = displayio.Group()
text = "Starting..."
text_area = label.Label(FONT, text=text)
text_area.x = (display.width // 2) - (text_area.bounding_box[2] // 2)
text_area.y = (display.height // 2) - (text_area.bounding_box[3] // 2)
DISPROOT.append(text_area)
display.refresh()
display.root_group = DISPROOT
display.auto_refresh = False
display.refresh()

import usb_cdc

# --- Remount SD safely ---
try:
    storage.remount("/sd", False, disable_concurrent_write_protection=True)
    usb_cdc.enable(console=True, data=True)
except Exception:
    pass

# --- Boot Splash ---

# Level 2 - Display Library Initialization
import helpers

# --- Initialize Terminal ---
font_bb = FONT.get_bounding_box()
screen_size = (display.width // font_bb[0], display.height // font_bb[1])
char_size = FONT.get_bounding_box()
screen_size = (display.width // char_size[0], display.height // char_size[1])

terminal_palette = displayio.Palette(2)
terminal_palette[0] = 0x000000
terminal_palette[1] = 0x33FF33

terminal_area = displayio.TileGrid(
    bitmap=FONT.bitmap,
    width=screen_size[0],
    height=screen_size[1],
    tile_width=char_size[0],
    tile_height=char_size[1],
    pixel_shader=terminal_palette,
)

DISPROOT.pop()
terminal = Terminal(terminal_area, FONT)
DISPROOT.append(terminal_area)
display.refresh()

helpers.KERNEL_TERMINAL = terminal
helpers.KERNEL_TILEGRID = terminal_area
helpers.CURRENT_TERMINAL = terminal
helpers.CURRENT_TILEGRID = terminal_area
helpers.display = display

print = helpers.print
printf = helpers.printf
input = helpers.input

# Level 3 - Peripheral Initialization

printf(f"[ INFO ] Loading drivers...")
from adafruit_esp32spi import adafruit_esp32spi
import adafruit_connection_manager
import adafruit_requests
from mem import mem
#from adafruit_atecc.adafruit_atecc import ATECC
from digitalio import DigitalInOut
import board
import time
#from adafruit_fruitjam.peripherals import Peripherals
#from adafruit_tlv320 import DEBOUNCE_32MS, BTN_DEBOUNCE_16MS
#import alarm

#pin_alarm = alarm.pin.PinAlarm(board.D7, False)

printf(f"[OK] Hardware drivers initalized")


def hang():
    while True:
        time.sleep(1)

WAKE_CLK_FREQ = 100000
i2c = board.STEMMA_I2C()
helpers.i2c = i2c
try:
    import fsio
    import kernel
    import os
except ImportError:
    printf(f"[FATAL] Disk drive not found. Insert and restart.")
    hang()
printf(f"[OK] Disk drive initialized")

skipCrypto = True

# Config file
#import json
#CONFIG_FILE = "sd/dev/config.json"
#if not fsio.exists(CONFIG_FILE, k=True):
#    with open(CONFIG_FILE, "w") as f:
#        f.write(json.dumps({
#            "tz_offset": 0,
#        }))

#from adafruit_atecc.adafruit_atecc import ATECC
#
#atecc = ATECC(helpers.i2c)
#atecc._debug = True
#
#atecc.wakeup()
#t = bytearray(64)
#atecc.gen_key(t, slot_num=0, private_key=True)
#print(t)

if not skipCrypto:
    printf(f"[ INFO ] Loading cryptographic libraries...")
    from secureCore import ChaCha20Poly1305
    from ellipticcurve.privateKey import PrivateKey
    import ellipticcurve.curve as curve
    import hmac

    printf(f"[OK] Cryptographic libraries loaded")

    #atecc._debug = True

# --- Optional Peripherals setup ---
skip = False
skipWIFI = False
if not skip:
    #peripherals = Peripherals(safe_volume_limit=20)
    #printf(f"[OK] Display initialized")
#
    #peripherals.audio.stop()
#
    #peripherals.dac.set_headset_detect(
    #enable=True,
    #detect_debounce=DEBOUNCE_32MS,
    #button_debounce=BTN_DEBOUNCE_16MS
    #)

    # Create standard directories if missing
    DRV_DIRS = ["bin", "dev", "lib", "media", "root", "srv", "tmp", "usr", "var"]
    for directory in DRV_DIRS:
        if not fsio.exists(directory):
            fsio.mkdir(directory)
            printf(f"[ INFO ] Created dir: {directory}")
    if not fsio.exists("root/home"):
        fsio.mkdir("root/home")
        printf(f"[ INFO ] Created dir: root/home")

    if not skipWIFI:
        # Wi-Fi connection
        printf("[ INFO ] Connecting Wi-Fi...")
        esp32_cs, esp32_ready, esp32_reset = map(DigitalInOut, [board.ESP_CS, board.ESP_BUSY, board.ESP_RESET])
        spi = board.SPI()
        esp = adafruit_esp32spi.ESP_SPIcontrol(spi, esp32_cs, esp32_ready, esp32_reset)

        pool = adafruit_connection_manager.get_radio_socketpool(esp)
        ssl_context = adafruit_connection_manager.get_radio_ssl_context(esp)
        requests = adafruit_requests.Session(pool, ssl_context)

        helpers.requests = requests

        mem.write("$esp", esp)
        mem.write("$socketpool", pool)
        mem.write("$sslcontext", ssl_context)
        mem.write("$requests", requests)

        retries = 0
        while not esp.is_connected and retries < 3:
            try:
                esp.connect_AP(os.getenv("WIFI_SSID"), os.getenv("WIFI_PASSWORD"))
            except OSError as e:
                esp.connect_AP(os.getenv("WIFI_SECONDARY_SSID"), os.getenv("WIFI_SECONDARY_PASSWORD"))
                printf("Retrying Wi-Fi:", e)
                continue
            retries += 1

        if not esp.is_connected:
            printf(f"[WARNING] Could not connect to Wi-Fi. Check settings.")

        else:
            printf(f"Connected: {esp.ap_info.ssid} | RSSI: {esp.ap_info.rssi}")
            
            import adafruit_ntp
            import rtc

            ntp = adafruit_ntp.NTP(pool, cache_seconds=3600)
            rtc.RTC().datetime = ntp.datetime
            printf(f"[OK] Wi-Fi connected and time synchronized")
        #esp.disconnect()

# --- Command executor ---
def exe(cmd):
    """Execute shell command."""
    global shellcwd
    args = cmd.split(" ")
    program = args[0]

    # Built-in commands
    if program == "shutdown":
        # Deep sleep until one of the alarm goes off. Then restart the program.
        #alarm.exit_and_deep_sleep_until_alarms(pin_alarm)
        pass
    elif program == "cd":
        cwdDelta = shellcwd.join("".join(args[1:]))
        if fsio.isDir(cwdDelta):
            shellcwd = cwdDelta
        else:
            printf("Directory not found.")
    elif program == "cls":
        helpers.cls()
    else:
        out = None
        try:
            out = kernel.exe(program, args, shellcwd)
        except:
            try:
                out = kernel.runProgram(program)
            except kernel.CommandNotFoundError:
                print(f"'{program}' is not recognized as an internal or external command.")
        if out:
            printf(out)

# ==============================
# Main Command Loop
# ==============================
shellcwd = fsio.Path("/root/home/")

while True:
    cmd = input(f"root@{MACHINE_NAME}:{shellcwd.pstr()}$ ")
    if cmd.strip():
        exe(cmd)
