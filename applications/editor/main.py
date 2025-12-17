import displayio
from terminalio import FONT, Terminal
import helpers
from tilepalettemapper import TilePaletteMapper
from helpers import MAX_CHARS_WIDTH, MAX_LINES
import dang as curses

class Window:
    def __init__(self, n_rows, n_cols, row=0, col=0):
        self.n_rows = n_rows
        self.n_cols = n_cols
        self.row = row
        self.col = col

    @property
    def bottom(self):
        return self.row + self.n_rows - 1

    def up(self, cursor):  # pylint: disable=invalid-name
        if cursor.row == self.row - 1 and self.row > 0:
            self.row -= 1

    def down(self, buffer, cursor):
        if cursor.row == self.bottom + 1 and self.bottom < len(buffer) - 1:
            self.row += 1

    def horizontal_scroll(self, cursor, left_margin=5, right_margin=2):
        n_pages = cursor.col // (self.n_cols - right_margin)
        self.col = max(n_pages * self.n_cols - right_margin - left_margin, 0)

    def translate(self, cursor):
        return cursor.row - self.row, cursor.col - self.col


def editor(stdscr, terminal_tilegrid, on_save=""):
    class MockCursor:
        def __init__(self, row, col):
            self.row = row
            self.col = col
            
    window = Window(terminal_tilegrid.height - 1, terminal_tilegrid.width)  # -1 for status line
    stdscr.erase()
    img = [None] * (window.n_rows + 1)  # +1 for status line
    status_message_row = terminal_tilegrid.height - 1
    cursor_row, cursor_col = 0, 0
    status_changed = False

    # Store lines of text
    lines = [""]

    cursor = MockCursor(cursor_row, cursor_col)

    def setline(row, line):
        if img[row] == line:
            return
        img[row] = line
        line += " " * (window.n_cols - len(line) - 1)
        stdscr.addstr(row, 0, line)

    def get_user_input(prompt_text):
        """Prompt the user for input on the status line and return the entered string."""
        stdscr.addstr(status_message_row, 0, prompt_text + (" "*(window.n_cols - len(prompt_text) - 1)))
        helpers._display.refresh()
        user_input = ""
        while True:
            k = stdscr.getkey()
            if k is not None:
                if k in ("\n", "\r"):
                    break
                elif k in {"KEY_BACKSPACE", "\x7f", "\x08"}:
                    if len(user_input) > 0:
                        user_input = user_input[:-1]
                        stdscr.addstr(status_message_row, len(prompt_text) + 1, user_input + " ")
                        stdscr.move(status_message_row, len(prompt_text) + 1 + len(user_input))
                elif len(k) == 1 and " " <= k <= "~":
                    user_input += k
                    stdscr.addstr(status_message_row, len(prompt_text) + 1, user_input)
                helpers._display.refresh()
        return user_input.strip() or "output.txt"

    setline(status_message_row, " (mnt RO ^W) | ^R Run | ^O Open | ^F Find | ^G GoTo | ^C quit ")
    helpers._display.refresh()

    while True:
        # Create a mock cursor object for window methods
        
        
        k = stdscr.getkey()
        if k is not None:
            if status_changed:
                setline(status_message_row, " (mnt RO ^W) | ^S Save | ^O Open | ^F Find | ^G GoTo | ^C quit ")
                status_changed = False

            old_cursor_pos = (cursor_col, cursor_row)
            old_window_pos = (window.col, window.row)
            
            if len(k) == 1 and " " <= k <= "~":
                # Insert character at cursor position
                lines[cursor_row] = lines[cursor_row][:cursor_col] + k + lines[cursor_row][cursor_col:]
                cursor_col += 1
            elif k == "\n":
                # Split line at cursor position
                current_line = lines[cursor_row]
                lines[cursor_row] = current_line[:cursor_col]
                lines.insert(cursor_row + 1, current_line[cursor_col:])
                cursor_row += 1
                cursor_col = 0
            elif k in {"KEY_BACKSPACE", "\x7f", "\x08"}:
                if cursor_col > 0:
                    # Delete character before cursor
                    lines[cursor_row] = lines[cursor_row][:cursor_col - 1] + lines[cursor_row][cursor_col:]
                    cursor_col -= 1
                elif cursor_row > 0:
                    # Join with previous line
                    cursor_col = len(lines[cursor_row - 1])
                    lines[cursor_row - 1] += lines[cursor_row]
                    lines.pop(cursor_row)
                    cursor_row -= 1
            elif k == "KEY_LEFT":
                if cursor_col > 0:
                    cursor_col -= 1
                elif cursor_row > 0:
                    cursor_row -= 1
                    cursor_col = len(lines[cursor_row])
            elif k == "KEY_RIGHT":
                if cursor_col < len(lines[cursor_row]):
                    cursor_col += 1
                elif cursor_row < len(lines) - 1:
                    cursor_row += 1
                    cursor_col = 0
            elif k == "KEY_UP":
                if cursor_row > 0:
                    cursor_row -= 1
                    cursor_col = min(cursor_col, len(lines[cursor_row]))
            elif k == "KEY_DOWN":
                if cursor_row < len(lines) - 1:
                    cursor_row += 1
                    cursor_col = min(cursor_col, len(lines[cursor_row]))
            elif k == "\x13":  # Ctrl+S
                closing_input = get_user_input(on_save)
                return closing_input
                #try:
                #    with open(f"sd/{filename}", "w") as f:
                #        f.write("\n".join(lines))
                #    setline(status_message_row, f"File saved in {filename}")
                #except Exception as e:
                #    setline(status_message_row, f"Error saving file: {e}")
                #status_changed = True
            elif k == "\x06":  # Ctrl-F
                search_term = get_user_input("Find:")
                found = False
                for i, line in enumerate(lines):
                    col = line.find(search_term)
                    if col != -1:
                        cursor_row, cursor_col = i, col
                        found = True
                        break
                if found:
                    setline(status_message_row, f"Found '{search_term}'")
                else:
                    setline(status_message_row, f"'{search_term}' not found")
                status_changed = True
            elif k == "\x07":  # Ctrl+G
                line_str = get_user_input("Go to line:")
                try:
                    target = int(line_str) - 1
                    if 0 <= target < len(lines):
                        cursor_row = target
                        cursor_col = min(cursor_col, len(lines[cursor_row]))
                        setline(status_message_row, f"Moved to line {target + 1}")
                    else:
                        setline(status_message_row, "Line out of range")
                except ValueError:
                    setline(status_message_row, "Invalid line number")
                status_changed = True



            # Update cursor position for window methods
            cursor.col = cursor_col
            cursor.row = cursor_row
            
            # Trigger vertical scrolling
            window.up(cursor)
            window.down(lines, cursor)
            
            # Trigger horizontal scrolling
            window.horizontal_scroll(cursor)
            
            # Render all visible lines
            for row in range(window.n_rows):
                buffer_row = window.row + row
                if buffer_row < len(lines):
                    line = lines[buffer_row]
                    # Apply horizontal scroll
                    visible_line = line[window.col:]
                    if window.col > 0:
                        visible_line = "«" + visible_line[1:]  # Add scroll indicator
                    if len(visible_line) > window.n_cols - 1:
                        visible_line = visible_line[:window.n_cols - 2] + "»"  # Add right indicator
                    setline(row, visible_line)
            
            # Only update pixel shader if screen position actually changed
            old_screen_col = old_cursor_pos[0] - old_window_pos[0]
            old_screen_row = old_cursor_pos[1] - old_window_pos[1]
            new_screen_col = cursor_col - window.col
            new_screen_row = cursor_row - window.row
            
            if (old_screen_col != new_screen_col or old_screen_row != new_screen_row):
                # Make sure old position is within bounds
                if (0 <= old_screen_col < window.n_cols and 0 <= old_screen_row < window.n_rows):
                    terminal_tilegrid.pixel_shader[old_screen_col, old_screen_row] = [0, 1]
                # Make sure new position is within bounds
                if (0 <= new_screen_col < window.n_cols and 0 <= new_screen_row < window.n_rows):
                    terminal_tilegrid.pixel_shader[new_screen_col, new_screen_row] = [1, 0]
            
            helpers._display.refresh()

def get(on_save=""):
    highlight_palette = displayio.Palette(3)
    highlight_palette[0] = 0x000000
    highlight_palette[1] = 0xFFFFFF
    highlight_palette[2] = 0xC9C9C9

    tpm = TilePaletteMapper(highlight_palette, 2)

    area = displayio.TileGrid(
            bitmap=FONT.bitmap,
            width=helpers.SCR_W,
            height=helpers.SCR_H,
            tile_width=helpers.char_w,
            tile_height=helpers.char_h,
            pixel_shader=tpm,
        )

    for x in range(MAX_CHARS_WIDTH):
        tpm[x,MAX_LINES-1] = [2,0]

    term = Terminal(area, FONT)

    helpers._display.root_group.append(area)

    try:
        result = curses.custom_terminal_wrapper(term, editor, area, on_save)
    except KeyboardInterrupt:
        return None, None

    helpers._display.root_group.pop(-1)
    helpers._display.refresh()

    return result

get()
