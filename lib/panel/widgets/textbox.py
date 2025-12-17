import displayio
from adafruit_display_text import label
from adafruit_display_shapes.rect import Rect
import time
import panel.core

font = panel.core.font


class TextBox:
    """
    Optimized Text Box with low-latency input handling and blinking cursor.
    Uses buffered text updates to avoid full display refresh on every keystroke.
    """

    CURSOR_BLINK_INTERVAL = 0.5  # seconds
    REFRESH_THROTTLE = 0.05      # minimum time between screen refreshes

    def __init__(self, rel_x, rel_y, width=120, height=80, text="", parent_window=None):
        self.rel_x = rel_x
        self.rel_y = rel_y
        self.width = width
        self.height = height
        self.parent_window = parent_window
        self.text = text
        self.cursor_visible = True
        self.last_blink_time = time.monotonic()
        self.last_refresh_time = 0
        self.textLineCutoff = width // 6

        # Create main group and background box
        self.group = displayio.Group()
        self.box = Rect(0, 0, width, height, outline=0x000000, fill=0xFFFFFF)
        self.group.append(self.box)

        # Text label (kept persistent — only text changes, no redraw)
        self.label = label.Label(font, text=self.text, color=0x000000)
        self.label.x = 2
        self.label.y = 8
        self.group.append(self.label)

        # Cursor as a small vertical bar (updated separately)
        self.cursor = Rect(0, 0, 2, 10, fill=0x000000)
        self.group.append(self.cursor)

        if parent_window:
            parent_window.addWidget(self)
            self.attach()

        self.update_cursor_position()
        self.last_text_update = 0
        panel.core.GUI.focused_widget = self  # Auto-focus on creation

    # --- Coordinates ---
    @property
    def abs_x(self):
        if not self.parent_window:
            return self.rel_x
        return self.parent_window.x + 1 + self.rel_x

    @property
    def abs_y(self):
        if not self.parent_window:
            return self.rel_y
        return self.parent_window.y + 12 + self.rel_y

    def attach(self):
        if self.parent_window:
            self.parent_window.group.append(self.group)

    def update_position(self):
        self.group.x = self.abs_x
        self.group.y = self.abs_y

    def inBounds(self, x, y):
        return self.abs_x <= x < self.abs_x + self.width and self.abs_y <= y < self.abs_y + self.height

    # --- Input Handling ---
    def on_key(self, ch):
        """Handle character input with minimal redraw overhead."""
        for k in ch:
            c = ord(k)
            changed = False

            if c in (8, 127):  # Backspace
                if self.text:
                    self.text = self.text[:-1]
                    changed = True
            elif c in (10, 13):  # Enter
                self.text += "\n"
                changed = True
            elif 32 <= c <= 126:  # Printable
                last_line = self.text.split("\n")[-1]
                if len(last_line) >= self.textLineCutoff:
                    self.text += "\n"
                self.text += k
                changed = True

            if changed:
                self.label.text = self.text
                self.update_cursor_position()

    # --- Cursor ---
    def update_cursor_position(self):
        """Compute cursor position without heavy operations."""
        lines = self.text.split("\n")
        current_line = lines[-1] if lines else ""
        cursor_x = (len(current_line) * 6) + 2
        cursor_y = len(lines) * 10 - 2
        cursor_y = min(cursor_y, self.height - 12)
        self.cursor.x = cursor_x
        self.cursor.y = cursor_y

    def update(self):
        """Blink cursor asynchronously (no full refresh)."""
        now = time.monotonic()
        if now - self.last_blink_time >= self.CURSOR_BLINK_INTERVAL:
            self.cursor_visible = not self.cursor_visible
            self.cursor.hidden = not self.cursor_visible
            self.last_blink_time = now
            # Only refresh cursor area (fast)
            panel.core.GUI.display.refresh(minimum_frames_per_second=0)

    def draw(self):
        self.group.x = self.abs_x
        self.group.y = self.abs_y
        self.group.hidden = False
