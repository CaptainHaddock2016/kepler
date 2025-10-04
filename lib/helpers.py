import supervisor
import sys

terminal = None
display = None
_history = []

def print(*args, sep=" ", end="\n"):
    s = sep.join(str(a) for a in args)
    # Write only to the on-screen terminal; do NOT call builtin print
    terminal.write(s + end)
    display.refresh()

def input(prompt=""):
    global _history
    """Responsive line editor: arrows, history, backspace/delete, home/end, ctrl-keys."""
    buf = []
    cursor = 0
    hist_index = len(_history)

    # initial prompt
    terminal.write(prompt)
    display.refresh()

    def redraw():
        # Move to start of line, clear line, print prompt+buffer, then position cursor
        terminal.write("\x1b[1000D")  # to column 0
        terminal.write("\x1b[0K")     # clear whole line
        line = prompt + "".join(buf)
        terminal.write(line)
        # reposition after prompt+cursor
        terminal.write("\x1b[1000D")
        terminal.write("\x1b[{}C".format(len(prompt) + cursor))
        display.refresh()

    while True:
        while supervisor.runtime.serial_bytes_available:
            ch = sys.stdin.read(1)
            if not ch:
                continue
            code = ord(ch)

            # -------- ESCAPE SEQUENCES (arrows, home/end, delete) --------
            if code == 27:  # ESC
                seq = sys.stdin.read(1)
                if not seq:
                    # bare ESC, ignore
                    continue
                if seq == "[":
                    # read the next byte; some keys send extra tilde terminators
                    tail = sys.stdin.read(1)
                    if tail in ("A", "B", "C", "D", "H", "F"):
                        # classic ANSI
                        if tail == "D":  # Left
                            if cursor > 0:
                                cursor -= 1
                                redraw()
                        elif tail == "C":  # Right
                            if cursor < len(buf):
                                cursor += 1
                                redraw()
                        elif tail == "A":  # Up (history back)
                            if hist_index > 0:
                                hist_index -= 1
                                buf = list(_history[hist_index])
                                cursor = len(buf)
                                redraw()
                        elif tail == "B":  # Down (history forward)
                            if hist_index < len(_history) - 1:
                                hist_index += 1
                                buf = list(_history[hist_index])
                            else:
                                hist_index = len(_history)
                                buf = []
                            cursor = len(buf)
                            redraw()
                        elif tail == "H":  # Home
                            cursor = 0
                            redraw()
                        elif tail == "F":  # End
                            cursor = len(buf)
                            redraw()
                    elif tail in ("1", "3", "4", "7", "8"):
                        # Likely a multi-byte CSI like [3~ (Delete), [1~ (Home), [4~ (End)...
                        term = sys.stdin.read(1)  # usually '~'
                        if tail == "3" and term == "~":  # Delete
                            if cursor < len(buf):
                                del buf[cursor]
                                redraw()
                        elif tail in ("1", "7") and term == "~":  # Home
                            cursor = 0
                            redraw()
                        elif tail in ("4", "8") and term == "~":  # End
                            cursor = len(buf)
                            redraw()
                        else:
                            # unknown sequence, ignore
                            pass
                    else:
                        # swallow any stray sequence char
                        pass
                else:
                    # ESC <something else> — ignore
                    pass
                continue

            # -------- CONTROL KEYS --------
            if code in (8, 127):  # Backspace (BS or DEL-as-backspace)
                if cursor > 0:
                    del buf[cursor - 1]
                    cursor -= 1
                    redraw()
                continue

            if code in (10, 13):  # Enter
                terminal.write("\n")
                s = "".join(buf)
                if s:
                    _history.append(s)
                return s

            if code == 21:  # Ctrl-U: kill line (before cursor)
                if cursor > 0:
                    del buf[:cursor]
                    cursor = 0
                    redraw()
                continue

            if code == 1:  # Ctrl-A: Home
                cursor = 0
                redraw()
                continue

            if code == 5:  # Ctrl-E: End
                cursor = len(buf)
                redraw()
                continue

            # -------- PRINTABLE CHARACTERS --------
            # Only accept normal printable ASCII/UTF-8 bytes
            # (most firmware consoles deliver ASCII; this is fine)
            if 32 <= code <= 126 or code >= 160:
                buf.insert(cursor, ch)
                cursor += 1
                redraw()
                continue