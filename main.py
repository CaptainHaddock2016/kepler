# ==============================
# MPOS (Microprocessor OS) Boot Script
# ==============================
MACHINE_NAME = "machine"

# --- Imports ---
import board
import time
import ansi
import asyncio
import displayio
import supervisor
import storage
from digitalio import DigitalInOut
from adafruit_display_text import label
from terminalio import FONT
from adafruit_color_terminal import ColorTerminal
from adafruit_fruitjam.peripherals import Peripherals
from adafruit_esp32spi import adafruit_esp32spi
import adafruit_connection_manager
import adafruit_requests
from mem import mem
import helpers
import usb_cdc
from adafruit_editor import editor, picker

print = helpers.print
input = helpers.input

# --- Initialize Display ---
display = supervisor.runtime.display
DISPROOT = displayio.Group()
display.root_group = DISPROOT
display.auto_refresh = False
display.refresh()

# --- Remount SD safely ---
try:
    storage.remount("/sd", False, disable_concurrent_write_protection=True)
    usb_cdc.enable(console=True, data=True)
except Exception:
    pass

# --- Boot Splash ---
text = "Starting..."
text_area = label.Label(FONT, text=text)
text_area.x = (display.width // 2) - (text_area.bounding_box[2] // 2)
text_area.y = (display.height // 2) - (text_area.bounding_box[3] // 2)
DISPROOT.append(text_area)
display.refresh()

# --- Initialize Terminal ---
font_bb = FONT.get_bounding_box()
screen_size = (display.width // font_bb[0], display.height // font_bb[1])
terminal = ColorTerminal(FONT, screen_size[0], screen_size[1])
DISPROOT.append(terminal.tilegrid)
display.refresh()

helpers.terminal = terminal
helpers.display = display

# --- Low-latency print override ---

# --- Filesystem check ---
try:
    import fsio
except ImportError:
    print(f"[{ansi.red} FATAL {ansi.reset}] Disk drive not found. Insert and restart.")
    while True:
        time.sleep(1)
print(f"[{ansi.green} OK {ansi.reset}] Disk drive initialized")

# --- Optional Peripherals setup ---
skip = True
if not skip:
    peripherals = Peripherals(safe_volume_limit=20)
    print(f"[{ansi.green} OK {ansi.reset}] Display initialized")

    peripherals.dac.headphone_output = False
    peripherals.dac.speaker_output = True
    peripherals.dac.configure_clocks(sample_rate=44000, bit_depth=16)
    peripherals.volume = 18
    peripherals.audio.stop()

    # Create standard directories if missing
    DRV_DIRS = ["bin", "dev", "lib", "media", "root", "srv", "tmp", "usr", "var"]
    for directory in DRV_DIRS:
        if not fsio.exists(directory):
            fsio.mkdir(directory)
            print(f"[ INFO ] Created dir: {directory}")
    if not fsio.exists("root/home"):
        fsio.mkdir("root/home")
        print(f"[ INFO ] Created dir: root/home")

    # Wi-Fi connection
    print("[ INFO ] Connecting Wi-Fi...")
    esp32_cs, esp32_ready, esp32_reset = map(DigitalInOut, [board.ESP_CS, board.ESP_BUSY, board.ESP_RESET])
    spi = board.SPI()
    esp = adafruit_esp32spi.ESP_SPIcontrol(spi, esp32_cs, esp32_ready, esp32_reset)

    pool = adafruit_connection_manager.get_radio_socketpool(esp)
    ssl_context = adafruit_connection_manager.get_radio_ssl_context(esp)
    requests = adafruit_requests.Session(pool, ssl_context)

    mem.write("$esp", esp)
    mem.write("$socketpool", pool)
    mem.write("$sslcontext", ssl_context)
    mem.write("$requests", requests)

    while not esp.is_connected:
        try:
            esp.connect_AP("DanielsNet", "hcpkff9833")
        except OSError as e:
            print("Retrying Wi-Fi:", e)
            continue
    print(f"Connected: {esp.ap_info.ssid} | RSSI: {esp.ap_info.rssi}")
    print("IP:", esp.ipv4_address)
    #print("Ping google.com:", esp.ping("google.com"), "ms")

# ==============================
# Shell Command System
# ==============================
PATH = ["/bin"]
_history = []

filename = picker.pick_file()

# --- Command finder ---
def findCommand(program, cwd):
    """Find command in cwd or PATH."""
    for ext in (".py", ".mpy"):
        p = cwd.join(f"{program}{ext}")
        if fsio.exists(str(p)):
            return p
        for dir in PATH:
            test = fsio.Path(f"{dir}/{program}{ext}")
            if fsio.exists(test):
                return test
    return None

cursor = 0

# --- Command executor ---
async def exe(cmd):
    """Execute shell command."""
    global shellcwd
    args = cmd.split(" ")
    program = args[0]

    # Built-in commands
    if program == "cd":
        cwdDelta = shellcwd.join("".join(args[1:]))
        if fsio.isDir(cwdDelta):
            shellcwd = cwdDelta
        else:
            print("Directory not found.")
    elif program == "cls":
        print("\x1b[2J\x1b[H", end="")
    else:
        progPath = findCommand(program, shellcwd)
        if progPath:
            ns = {"print": print, "input": input}
            exec(progPath.read(), ns)
            try:
                out = await ns.get("main", lambda *_: None)(args, shellcwd)
            except:
                out = ns.get("main", lambda *_: None)(args, shellcwd)
            if out:
                print(out)
        else:
            print(f"'{program}' is not recognized as an internal or external command.")

# ==============================
# Main Command Loop
# ==============================
shellcwd = fsio.Path("/root/home/")

async def cmdloop():
    """Main shell loop."""
    while True:
        cmd = input(f"root@{MACHINE_NAME}:{shellcwd.pstr()}$ ")
        if cmd.strip():
            await exe(cmd)
        print()
        await asyncio.sleep(0)

async def main():
    await cmdloop()

# --- Run main loop ---
asyncio.run(main())
