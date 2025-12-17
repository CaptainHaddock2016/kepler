import supervisor, sys, displayio, select as sel
from terminalio import FONT, Terminal
from time import sleep

_display = supervisor.runtime.display
_builtin_print = print

# --- Constants --------------------------------------------------------------
char_w, char_h = FONT.get_bounding_box()
SCR_W = _display.width // char_w
SCR_H = _display.height // char_h

DISPLAY_WIDTH = _display.width
DISPLAY_HEIGHT = _display.height

MAX_CHARS_WIDTH = SCR_W
MAX_LINES = SCR_H

terminal_palette = displayio.Palette(2)
terminal_palette[0] = 0x000000
terminal_palette[1] = 0xFFFFFF

_history = []

# --- Terminal objects -------------------------------------------------------
KERNEL_TERMINAL = None          # Always exists
KERNEL_TILEGRID = None

CURRENT_TERMINAL = None         # The one all I/O uses
CURRENT_TILEGRID = None


# --- Utilities --------------------------------------------------------------
def _tw(s):
    """Write to the CURRENT terminal only."""
    if CURRENT_TERMINAL:
        CURRENT_TERMINAL.write(s)


# --- ANSI helpers -----------------------------------------------------------
def cursor_home(): _tw("\x1b[H")
def clear_entire_line(): _tw("\x1b[2K")
def clear_display(): _tw("\x1b[2J")

def move_cursor(r, c): _tw(f"\x1b[{r};{c}H")
def set_attributes(*attrs): _tw(f"\x1b[{';'.join(str(a) for a in attrs)}m")
def set_title(title): _tw(f"\x1b]0;{title}\x1b\\")


# --- print wrappers ---------------------------------------------------------
def print(*args, sep=" ", end="\n", flush=False):
    s = sep.join(str(a) for a in args)
    _tw(s + end)
    _builtin_print(s, end=end)
    if flush:
        _display.refresh()

def printf(*args, sep=" ", end="\n"):
    print(*args, sep=sep, end=end, flush=True)


# --- Create a new terminal and make it CURRENT ------------------------------
def newTerminal():
    global CURRENT_TERMINAL, CURRENT_TILEGRID

    area = displayio.TileGrid(
        bitmap=FONT.bitmap,
        width=SCR_W,
        height=SCR_H,
        tile_width=char_w,
        tile_height=char_h,
        pixel_shader=terminal_palette,
    )

    term = Terminal(area, FONT)

    # Replace display root content with this terminal
    if _display.root_group:
        old = _display.root_group.pop(0)
    _display.root_group.append(area)

    CURRENT_TERMINAL = term
    CURRENT_TILEGRID = area
    return term


# --- Initialize kernel terminal --------------------------------------------
def init_kernel_terminal():
    global KERNEL_TERMINAL, KERNEL_TILEGRID, CURRENT_TERMINAL, CURRENT_TILEGRID
    term = newTerminal()
    KERNEL_TERMINAL = term
    KERNEL_TILEGRID = CURRENT_TILEGRID
    CURRENT_TERMINAL = term
    CURRENT_TILEGRID = KERNEL_TILEGRID


# --- Optimized Input Handler ------------------------------------------------
def input(prompt=""):
    global _history

    buf = []
    cursor = 0
    hist_index = len(_history)

    _tw(prompt)
    _display.refresh()

    def redraw():
        _tw("\r\x1b[2K")
        visible = "".join(buf)
        if len(visible) > MAX_CHARS_WIDTH:
            visible = visible[-MAX_CHARS_WIDTH:]
        _tw(prompt + visible)

    while True:
        while supervisor.runtime.serial_bytes_available:
            ch = sys.stdin.read(1)
            code = ord(ch)

            # ENTER
            if code in (10, 13):
                _tw("\n")
                s = "".join(buf)
                if s:
                    _history.append(s)
                _display.refresh()
                return s

            # BACKSPACE
            if code in (8, 127):
                if cursor > 0:
                    cursor -= 1
                    buf.pop(cursor)
                    redraw()
                continue

            # ESC sequences
            if code == 27:
                nxt = sys.stdin.read(1)
                if nxt == "[":
                    tail = sys.stdin.read(1)

                    if tail == "D" and cursor > 0:  # LEFT
                        cursor -= 1
                    elif tail == "C" and cursor < len(buf):  # RIGHT
                        cursor += 1
                    elif tail == "A" and hist_index > 0:  # UP
                        hist_index -= 1
                        buf = list(_history[hist_index])
                        cursor = len(buf)
                    elif tail == "B":  # DOWN
                        if hist_index < len(_history)-1:
                            hist_index += 1
                            buf = list(_history[hist_index])
                        else:
                            hist_index = len(_history)
                            buf = []
                        cursor = len(buf)
                    redraw()
                continue

            # Printable characters
            if 32 <= code <= 126 or code >= 160:
                buf.insert(cursor, ch)
                cursor += 1
                redraw()

        _display.refresh()


# --- SELECT MENU ------------------------------------------------------------
def select(options, prompt="Select: "):
    global CURRENT_TERMINAL, CURRENT_TILEGRID

    n = len(options)
    index = 0

    # Save old terminal + tilegrid
    OLD_TERMINAL = CURRENT_TERMINAL
    OLD_TILEGRID = CURRENT_TILEGRID

    # Create temporary fullscreen terminal
    newTerminal()

    start_row = MAX_LINES - (n + 1)

    poll = sel.poll()
    poll.register(sys.stdin, sel.POLLIN)

    def move(r, c):
        _tw(f"\x1b[{r};{c}H")

    def redraw():
        move(start_row, 1)
        _tw(prompt)
        r = start_row + 1
        for i, o in enumerate(options):
            move(r, 1)
            if i == index:
                _tw(f"> {o}   ")
            else:
                _tw(f"  {o}   ")
            r += 1

    redraw()
    _display.refresh()

    # Menu loop
    while True:
        if not poll.poll(10):
            continue

        ch = sys.stdin.read(1)
        if ch == "\x1b":   # ESC prefix
            seq = sys.stdin.read(2)
            if seq == "[A":  # UP
                index = max(0, index - 1)
                redraw()
            elif seq == "[B":  # DOWN
                index = min(n - 1, index + 1)
                redraw()
            _display.refresh()
            continue

        if ch in ("\n", "\r"):
            # Restore old tilegrid
            if _display.root_group:
                _display.root_group.pop(0)
            _display.root_group.append(OLD_TILEGRID)

            # Restore current terminal
            CURRENT_TERMINAL = OLD_TERMINAL
            CURRENT_TILEGRID = OLD_TILEGRID

            _display.refresh()
            return options[index]

def cls():
    printf("\n" * (MAX_LINES - 1))

def pause():
    printf("Press any key to continue . . .")
    while True:
        if supervisor.runtime.serial_bytes_available:
            ch = sys.stdin.read(1)
            return
        sleep(0.1)