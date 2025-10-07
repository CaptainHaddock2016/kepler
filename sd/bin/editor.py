from dataclasses import dataclass

import fsio

try:  # CircuitPython-compatible minimal curses wrapper
    from adafruit_editor import dang as curses
except ImportError:  # pragma: no cover - fallback for host testing
    import curses  # type: ignore


USAGE = "Usage: editor <filename>"


def _load_buffer(path: fsio.Path):
    if not path.exists():
        return [""]
    contents = path.read("r")
    lines = contents.splitlines()
    return lines or [""]


def _write_buffer(path: fsio.Path, buffer):
    text = "\n".join(buffer)
    if buffer:
        text += "\n"
    bytes_written = len(text.encode("utf-8"))
    path.write(text)
    return bytes_written


def clamp(value, lower, upper):
    if value < lower:
        return lower
    if value > upper:
        return upper
    return value


class Buffer:
    def __init__(self, lines):
        self.lines = list(lines) or [""]

    def __len__(self):
        return len(self.lines)

    def __getitem__(self, index):
        return self.lines[index]

    @property
    def bottom(self):
        return len(self.lines) - 1

    def insert(self, cursor, string):
        row, col = cursor.row, cursor.col
        current = self.lines.pop(row)
        self.lines.insert(row, current[:col] + string + current[col:])

    def split(self, cursor):
        row, col = cursor.row, cursor.col
        current = self.lines.pop(row)
        self.lines.insert(row, current[:col])
        self.lines.insert(row + 1, current[col:])

    def delete(self, cursor):
        row, col = cursor.row, cursor.col
        if (row, col) < (self.bottom, len(self[row])):
            current = self.lines.pop(row)
            if col < len(current):
                self.lines.insert(row, current[:col] + current[col + 1 :])
            else:
                nextline = self.lines.pop(row)
                self.lines.insert(row, current + nextline)
        elif col < len(self[row]):
            current = self.lines.pop(row)
            self.lines.insert(row, current[:col] + current[col + 1 :])

    def delete_line(self, row):
        removed = self.lines.pop(row)
        if not self.lines:
            self.lines.append("")
        return removed


class Cursor:
    def __init__(self, row=0, col=0, col_hint=None):
        self.row = row
        self._col = col
        self._col_hint = col if col_hint is None else col_hint

    @property
    def col(self):
        return self._col

    @col.setter
    def col(self, value):
        self._col = value
        self._col_hint = value

    def _clamp_col(self, buffer):
        self._col = min(self._col_hint, len(buffer[self.row]))

    def up(self, buffer):
        if self.row > 0:
            self.row -= 1
            self._clamp_col(buffer)

    def down(self, buffer):
        if self.row < len(buffer) - 1:
            self.row += 1
            self._clamp_col(buffer)

    def left(self, buffer):
        if self.col > 0:
            self.col -= 1
        elif self.row > 0:
            self.row -= 1
            self.col = len(buffer[self.row])

    def right(self, buffer):
        if self.col < len(buffer[self.row]):
            self.col += 1
        elif self.row < len(buffer) - 1:
            self.row += 1
            self.col = 0

    def home(self, buffer):
        self.col = 0

    def end(self, buffer):
        self.col = len(buffer[self.row])


class Window:
    def __init__(self, n_rows, n_cols, row=0, col=0):
        self.n_rows = n_rows
        self.n_cols = n_cols
        self.row = row
        self.col = col

    @property
    def bottom(self):
        return self.row + self.n_rows - 1

    def up(self, cursor):
        if cursor.row < self.row:
            self.row = cursor.row

    def down(self, buffer, cursor):
        if cursor.row > self.bottom:
            max_row = max(len(buffer) - self.n_rows, 0)
            self.row = clamp(cursor.row - self.n_rows + 1, 0, max_row)

    def ensure_horizontal(self, cursor):
        if cursor.col < self.col:
            self.col = max(cursor.col - 5, 0)
        elif cursor.col >= self.col + self.n_cols:
            self.col = cursor.col - self.n_cols + 1

    def translate(self, cursor):
        return cursor.row - self.row, cursor.col - self.col


def move_left(window, buffer, cursor):
    cursor.left(buffer)
    window.up(cursor)
    window.ensure_horizontal(cursor)


def move_right(window, buffer, cursor):
    cursor.right(buffer)
    window.down(buffer, cursor)
    window.ensure_horizontal(cursor)


def move_up(window, buffer, cursor):
    cursor.up(buffer)
    window.up(cursor)
    window.ensure_horizontal(cursor)


def move_down(window, buffer, cursor):
    cursor.down(buffer)
    window.down(buffer, cursor)
    window.ensure_horizontal(cursor)


@dataclass
class EditorState:
    buffer: Buffer
    cursor: Cursor
    window: Window
    filename: str
    dirty: bool = False
    mode: str = "NORMAL"
    status: str = ""
    pending: str = ""
    command: str = ""
    command_mode: bool = False
    should_quit: bool = False

    def clamp_cursor(self):
        self.cursor.row = clamp(self.cursor.row, 0, self.buffer.bottom)
        line_len = len(self.buffer[self.cursor.row])
        self.cursor.col = clamp(self.cursor.col, 0, line_len)
        self.window.up(self.cursor)
        self.window.down(self.buffer, self.cursor)
        self.window.ensure_horizontal(self.cursor)


def _render_editor(stdscr, state: EditorState):
    window = state.window
    buffer = state.buffer
    stdscr.erase()

    for screen_row in range(window.n_rows):
        file_row = window.row + screen_row
        if file_row <= buffer.bottom:
            line = buffer[file_row]
            segment = line[window.col : window.col + window.n_cols]
            if window.col > 0 and segment:
                segment = "«" + segment[1:]
            if len(line) - window.col > window.n_cols:
                segment = segment[:-1] + "»" if segment else "»"
        else:
            segment = "~"
        stdscr.addstr(screen_row, 0, segment.ljust(window.n_cols))

    status_row = curses.LINES - 1
    if state.command_mode:
        prompt = ":" + state.command
        line = prompt.ljust(window.n_cols)
        stdscr.addstr(status_row, 0, line)
        stdscr.move(status_row, len(prompt))
        return

    mode_label = "-- INSERT --" if state.mode == "INSERT" else "-- NORMAL --"
    dirty_mark = " +" if state.dirty else ""
    info = f"{mode_label} {state.filename}{dirty_mark}"
    if state.status:
        info += f" | {state.status}"
    line = info[: window.n_cols].ljust(window.n_cols)
    stdscr.addstr(status_row, 0, line)

    row, col = window.translate(state.cursor)
    row = clamp(row, 0, window.n_rows - 1)
    col = clamp(col, 0, window.n_cols - 1)
    stdscr.move(row, col)


def _handle_command(state: EditorState, key, path: fsio.Path):
    if key in ("\x1b",):
        state.command_mode = False
        state.command = ""
        state.status = ""
        return

    if key in ("\n", "\r"):
        command = state.command.strip()
        force = command.endswith("!")
        if force:
            command = command[:-1]
        if command in ("w", "write"):
            bytes_written = _write_buffer(path, state.buffer.lines)
            state.dirty = False
            state.status = f"written {bytes_written} bytes"
        elif command in ("q", "quit"):
            if state.dirty and not force:
                state.status = "No write since last change (add ! to override)"
            else:
                state.should_quit = True
        elif command in ("wq", "x", "writequit", "xit"):
            bytes_written = _write_buffer(path, state.buffer.lines)
            state.dirty = False
            state.status = f"written {bytes_written} bytes"
            state.should_quit = True
        elif command in ("q!", "quit!"):
            state.should_quit = True
        else:
            state.status = f"Not an editor command: {state.command}"
        state.command_mode = False
        state.command = ""
        return

    if key in ("\x7f", "KEY_BACKSPACE"):
        state.command = state.command[:-1]
        return

    if len(key) == 1 and " " <= key <= "~":
        state.command += key


def _handle_insert(state: EditorState, key):
    buffer = state.buffer
    cursor = state.cursor
    window = state.window

    if key == "\x1b":
        if cursor.col > 0:
            cursor.col -= 1
        state.mode = "NORMAL"
        state.status = ""
        state.pending = ""
        window.ensure_horizontal(cursor)
        return

    if key in ("\n", "\r"):
        buffer.split(cursor)
        cursor.row += 1
        cursor.col = 0
        window.down(buffer, cursor)
        window.ensure_horizontal(cursor)
        state.dirty = True
        return

    if key in ("\x7f", "KEY_BACKSPACE"):
        if (cursor.row, cursor.col) > (0, 0):
            move_left(window, buffer, cursor)
            buffer.delete(cursor)
            state.dirty = True
        return

    if key in ("KEY_DELETE", "\x04"):
        buffer.delete(cursor)
        state.dirty = True
        state.clamp_cursor()
        return

    if key in (
        "KEY_LEFT",
        "KEY_RIGHT",
        "KEY_UP",
        "KEY_DOWN",
        "KEY_HOME",
        "KEY_END",
        "KEY_PGUP",
        "KEY_PGDN",
    ):
        if key == "KEY_LEFT":
            move_left(window, buffer, cursor)
        elif key == "KEY_RIGHT":
            move_right(window, buffer, cursor)
        elif key == "KEY_UP":
            move_up(window, buffer, cursor)
        elif key == "KEY_DOWN":
            move_down(window, buffer, cursor)
        elif key == "KEY_HOME":
            cursor.home(buffer)
            window.ensure_horizontal(cursor)
        elif key == "KEY_END":
            cursor.end(buffer)
            window.ensure_horizontal(cursor)
        elif key == "KEY_PGUP":
            for _ in range(window.n_rows):
                move_up(window, buffer, cursor)
        elif key == "KEY_PGDN":
            for _ in range(window.n_rows):
                move_down(window, buffer, cursor)
        return

    if len(key) == 1 and " " <= key <= "~":
        buffer.insert(cursor, key)
        move_right(window, buffer, cursor)
        state.dirty = True


def _delete_line(state: EditorState):
    removed = state.buffer.delete_line(state.cursor.row)
    state.status = "1 line deleted"
    state.dirty = True
    state.cursor.row = clamp(state.cursor.row, 0, state.buffer.bottom)
    state.cursor.col = clamp(state.cursor.col, 0, len(state.buffer[state.cursor.row]))
    state.window.down(state.buffer, state.cursor)
    state.window.ensure_horizontal(state.cursor)
    return removed


def _handle_normal(state: EditorState, key):
    buffer = state.buffer
    cursor = state.cursor
    window = state.window

    if state.pending and key != "d":
        state.status = "d requires a motion"
        state.pending = ""

    if key == "\x1b":
        state.pending = ""
        state.status = ""
        return

    if key in ("h", "KEY_LEFT"):
        move_left(window, buffer, cursor)
        return
    if key in ("l", "KEY_RIGHT"):
        move_right(window, buffer, cursor)
        return
    if key in ("j", "KEY_DOWN"):
        move_down(window, buffer, cursor)
        return
    if key in ("k", "KEY_UP"):
        move_up(window, buffer, cursor)
        return
    if key in ("0", "KEY_HOME"):
        cursor.home(buffer)
        window.ensure_horizontal(cursor)
        return
    if key in ("$", "KEY_END"):
        cursor.end(buffer)
        window.ensure_horizontal(cursor)
        return
    if key == "KEY_PGUP":
        for _ in range(window.n_rows):
            move_up(window, buffer, cursor)
        return
    if key == "KEY_PGDN":
        for _ in range(window.n_rows):
            move_down(window, buffer, cursor)
        return
    if key == "i":
        state.mode = "INSERT"
        state.status = ""
        return
    if key == "a":
        move_right(window, buffer, cursor)
        state.mode = "INSERT"
        state.status = ""
        return
    if key == "A":
        cursor.end(buffer)
        window.ensure_horizontal(cursor)
        state.mode = "INSERT"
        state.status = ""
        return
    if key == "o":
        cursor.end(buffer)
        buffer.lines.insert(cursor.row + 1, "")
        cursor.row += 1
        cursor.col = 0
        window.down(buffer, cursor)
        window.ensure_horizontal(cursor)
        state.mode = "INSERT"
        state.dirty = True
        state.status = ""
        return
    if key == "O":
        buffer.lines.insert(cursor.row, "")
        cursor.col = 0
        window.up(cursor)
        window.ensure_horizontal(cursor)
        state.mode = "INSERT"
        state.dirty = True
        state.status = ""
        return
    if key == "x":
        buffer.delete(cursor)
        state.dirty = True
        state.status = ""
        state.clamp_cursor()
        return
    if key == ":":
        state.command_mode = True
        state.command = ""
        state.status = ""
        state.pending = ""
        return
    if key == "d":
        if state.pending == "d":
            _delete_line(state)
            state.pending = ""
        else:
            state.pending = "d"
        return


def _editor_loop(stdscr, path: fsio.Path, filename: str):
    lines = _load_buffer(path)
    buffer = Buffer(lines)
    window = Window(max(curses.LINES - 1, 1), max(curses.COLS, 1))
    cursor = Cursor()
    state = EditorState(buffer=buffer, cursor=cursor, window=window, filename=filename)

    while not state.should_quit:
        state.clamp_cursor()
        _render_editor(stdscr, state)
        key = stdscr.getkey()
        if state.command_mode:
            _handle_command(state, key, path)
        elif state.mode == "INSERT":
            _handle_insert(state, key)
        else:
            _handle_normal(state, key)

    return ""


def main(argv, cwd):
    args = argv[1:]
    if not args:
        return USAGE

    target = fsio.Path(cwd).resolve(args[0])

    if target.exists() and target.is_dir:
        return f"editor: '{target.pstr()}' is a directory"

    parent = target.parent
    if str(parent) and not parent.exists():
        return f"editor: directory '{parent.pstr()}' does not exist"

    filename = target.pstr()

    try:
        curses.wrapper(_editor_loop, target, filename)
    except KeyboardInterrupt:
        return ""

    return ""
