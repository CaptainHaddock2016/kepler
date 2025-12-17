import displayio
from adafruit_display_text import label, wrap_text_to_lines
from terminalio import FONT
from adafruit_display_shapes.rect import Rect
from adafruit_display_shapes.line import Line
import panel.core       
import time
     
# UI widgets
# UI widgets can only be used within a Window. These do not use display x y coordinates.
# They are positioned relative to the window's client area.

# ─────────────────────────────────────────────
# UI WIDGET SYSTEM — dynamic coordinates
# ─────────────────────────────────────────────

font = panel.core.font
    
class Widget:
    """
    Base class for all UI widgets.
    Widgets use relative (window-local) coordinates.
    The GUI automatically recalculates display positions when windows move or resize.
    """
    def __init__(self, rel_x, rel_y, width, height, parent_window=None):
        self.rel_x = rel_x
        self.rel_y = rel_y
        self.width = width
        self.height = height
        self.parent_window = parent_window
        self.group = displayio.Group()
        if parent_window:
            parent_window.addWidget(self)

    # ── Derived absolute coordinates ───────────
    @property
    def abs_x(self):
        if not self.parent_window:
            return self.rel_x
        return self.parent_window.x + 1 + self.rel_x

    @property
    def abs_y(self):
        if not self.parent_window:
            return self.rel_y
        # Offset by title bar height (12 px)
        return self.parent_window.y + 12 + self.rel_y

    # ── Behavior methods ──────────────────────
    def attach(self):
        """Attach to the parent window’s display group."""
        if self.parent_window:
            self.parent_window.group.append(self.group)

    def addWidget(self, widget):
        widget.parent_window = self.parent_window
        self.group.append(widget.group)

    def update_position(self):
        """Recompute absolute position on screen."""
        self.group.x = self.abs_x
        self.group.y = self.abs_y

    def inBounds(self, x, y):
        """Hit test in display coordinates."""
        return self.abs_x <= x < self.abs_x + self.width and self.abs_y <= y < self.abs_y + self.height

    def draw(self):
        """Abstract: draw visuals."""
        raise NotImplementedError
    
    def destroy(self):
        """Remove from display."""
        if self.parent_window and self.group in self.parent_window.group:
            self.parent_window.group.remove(self.group)
    
class TextBox(Widget):
    def __init__(self, rel_x, rel_y, width=100, height=100, text="", parent_window=None):
        self.text = text
        self.textLineCutoff = width // 6
        super().__init__(rel_x, rel_y, width, height, parent_window)
        self.draw()
        self.attach()
    def draw(self):
        # Box with label inside
        box = Rect(0, 0, self.width, self.height, outline=0x000000, fill=0xFFFFFF)
        self.group.append(box)
        self.label = label.Label(font, text=self.text, color=0x000000)
        self.label.x = 0
        self.label.y = self.rel_y + 8  # Center vertically within widget height
        self.group.append(self.label)
        self.group.x = self.abs_x
        self.group.y = self.abs_y

    def on_key(self, k):
        # Simple text input handling
        c = ord(k)
        if c in (8, 127):
            self.label.text = self.label.text[:-1]
        elif c in (10, 13):  # Enter
            self.label.text += "\n"
        elif len(k) == 1 and 32 <= c <= 126:  # Printable characters
            if len(self.label.text.split("\n")[-1]) >= self.textLineCutoff:
                self.label.text += "\n"
            self.label.text += k
    
class Label(Widget):
    def __init__(self, rel_x, rel_y, text, parent_window=None):
        self._text = text
        width = len(text) * 6  # Approximate width for 6x8 font
        height = 8  # Font height
        super().__init__(rel_x, rel_y, width, height, parent_window)
        self.draw()
        self.attach()

    def draw(self):
        text = label.Label(font, text=self._text, color=0x000000)
        text.x = 0
        text.y = self.height // 2  # Center vertically within widget height
        self.group.append(text)
        self.group.x = self.abs_x
        self.group.y = self.abs_y

    @property
    def text(self):
        return self._text

    @text.setter
    def text(self, value):
        self._text = value
        self.group.pop()
        self.draw()

class Button(Widget):
    """
    A clickable button widget with dynamic position tracking.
    Automatically updates its absolute coordinates when the window moves.
    """
    def __init__(self, rel_x, rel_y, width, height, text, parent_window, on_click=lambda: None):
        self._text = text
        self.usr_on_click = on_click
        super().__init__(rel_x, rel_y, width, height, parent_window)
        self.draw()

    def draw(self):
        self.group = displayio.Group(x=self.abs_x, y=self.abs_y)

        # Button rectangle
        rect = Rect(0, 0, self.width, self.height, outline=0x000000, fill=0xFFFFFF)
        
        # Centered text
        text = label.Label(font, text=self._text, color=0x000000)
        text.x = (self.width - text.bounding_box[2]) // 2
        text.y = (self.height // 2)
        
        self.group.append(rect)
        self.group.append(text)
        self.attach()

    def on_click(self, x, y):
        # change color on click
        if self.inBounds(x, y):
            self.group[0].fill = 0xCCCCCC  # Change button color to light gray
            panel.core.GUI.display.refresh()
            self.usr_on_click()
            time.sleep(0.1)  # Brief pause to show the color change
            self.group[0].fill = 0xFFFFFF  # Revert button color to

class ListBox(Widget):
    def __init__(self, rel_x, rel_y, width, height, options, parent_window=None):
        self.items = options
        self.selected_index = 0
        self.scroll_offset = 0
        super().__init__(rel_x, rel_y, width, height, parent_window)
        self.draw()
        self.attach()
    def draw(self):
        # Box with list of items
        box = Rect(0, 0, self.width, self.height, outline=0x000000, fill=0xFFFFFF)
        self.group.append(box)
        self.labels = []
        for i, item in enumerate(self.items):
            item_label = label.Label(font, text=str(item), color=0x000000)
            item_label.x = 2
            item_label.y = 8 + i * 10  # 10 px line height
            self.labels.append(item_label)
            self.group.append(item_label)
        self.group.x = self.abs_x
        self.group.y = self.abs_y
    def select(self, index):
        if 0 <= index < len(self.items):
            self.selected_index = index
            for i, lbl in enumerate(self.labels):
                lbl.color = 0xFF0000 if i == index else 0x000000
    def add_item(self, item):
        self.items.append(item)
        self.group.pop()
        self.draw()

    def on_click(self, x, y):
        if self.inBounds(x, y):
            # do not adjust for padding here, as rel_y is already relative to the widget
            relative_y = y - self.abs_y
            index = relative_y // 10  # Assuming 10 px line height
            self.select(index)

# Table. A listbox like widget with multiple columns.
class Table(Widget):
    def __init__(self, rel_x, rel_y, width, height, columns, data, parent_window=None):
        self.columns = columns  # List of column headers
        self.data = data  # List of rows
        self.scroll_offset = 0
        self.selected_index = None
        self.labels = {}
        super().__init__(rel_x, rel_y, width, height, parent_window)
        self.draw()
        self.attach()
        panel.core.GUI.focused_widget = self  # Auto-focus on creation

    def draw(self):
        # Clear any existing graphics
        self.group = displayio.Group()

        # Box with table of data
        box = Rect(self.abs_x, self.abs_y, self.width, self.height, outline=0x000000, fill=0xFFFFFF)
        self.group.append(box)

        col_width = self.width // len(self.columns)

        # Draw headers
        for i, col in enumerate(self.columns):
            col_label = label.Label(font, text=str(col), color=0x000000)
            col_label.x = self.abs_x + (i * col_width + 2)
            col_label.y = self.abs_y + 8
            self.group.append(col_label)

        # Header separator line
        line = Line(self.abs_x + 2, self.abs_y + 14, self.abs_x + self.width - 4, self.abs_y + 14, color=0x000000)
        self.group.append(line)

        # Determine how many rows fit
        self.num_visible = (self.height - 16) // 12

        # Draw visible rows
        self.labels = {}
        for row_index in range(self.num_visible):
            self.labels[row_index] = []
            if row_index + self.scroll_offset < len(self.data):
                row = self.data[row_index + self.scroll_offset]
            else:
                row = [""] * len(self.columns)
            for col_index, cell in enumerate(row):
                color = (
                    0xFF0000
                    if (row_index + self.scroll_offset) == self.selected_index
                    else 0x000000
                )
                cell_label = label.Label(font, text=str(cell), color=color)
                cell_label.x = self.abs_x + (col_index * col_width + 2)
                cell_label.y = self.abs_y + 22 + (row_index * 10)
                self.group.append(cell_label)
                self.labels[row_index].append(cell_label)

        # Scrollbar size based on total rows
        scrollWheelLength = min(self.height, (self.num_visible / max(len(self.data), 1)) * (self.height - 16))
        self.scrollRect = Rect(
            (self.abs_x + self.width) - 6,
            self.abs_y,
            6,
            int(scrollWheelLength),
            outline=0x000000,
            fill=0xFFFFFF,
        )
        self.group.append(self.scrollRect)

    def add_row(self, row):
        self.data.append(row)
        self.draw()

    def select(self, row_index):
        if 0 <= row_index < len(self.data):
            self.selected_index = row_index
            self.refresh_selection()

    def refresh_selection(self):
        """Updates label colors based on selection and scroll position."""
        for visible_row, lbls in self.labels.items():
            actual_index = self.scroll_offset + visible_row
            for lbl in lbls:
                if actual_index == self.selected_index:
                    lbl.color = 0xFF0000
                else:
                    lbl.color = 0x000000

    def on_click(self, x, y):
        if self.inBounds(x, y):
            if x >= self.abs_x + (self.width - 8):  # scrollbar click
                return
            relative_y = y - self.abs_y - 16
            index = relative_y // 10
            actual_index = self.scroll_offset + index
            self.select(actual_index)

    def on_scroll(self, offset):
        direction = -1 if offset > 0 else 1
        self.scroll_offset += direction
        self.scroll_offset = max(0, min(self.scroll_offset, max(len(self.data) - self.num_visible, 0)))

        # Update visible rows
        for visible_row in range(self.num_visible):
            actual_index = self.scroll_offset + visible_row
            if actual_index < len(self.data):
                row = self.data[actual_index]
                for col_index, cell in enumerate(row):
                    self.labels[visible_row][col_index].text = str(cell)
            else:
                for col_index in range(len(self.columns)):
                    self.labels[visible_row][col_index].text = ""

        # Update scrollbar position
        scroll_range = max(len(self.data) - self.num_visible, 0)
        if scroll_range > 0:
            self.scrollRect.y = self.abs_y + int(
                (self.scroll_offset / scroll_range) * (self.height - self.scrollRect.height)
            )
        else:
            self.scrollRect.y = self.abs_y

        # Update highlighting based on selection visibility
        if not (self.scroll_offset <= self.selected_index < self.scroll_offset + self.num_visible):
            # Selected row scrolled out of view — deselect visually but keep the index
            for lbls in self.labels.values():
                for lbl in lbls:
                    lbl.color = 0x000000
        else:
            self.refresh_selection()

# Text View
class TextView(Widget):
    def __init__(self, rel_x, rel_y, width, height, text="", parent_window=None):
        self.text = text
        self.wrapped_text = "\n".join(wrap_text_to_lines(text, width // 6))
        super().__init__(rel_x, rel_y, width, height, parent_window)
        self.draw()
        self.attach()
    def draw(self):
        # Box with label inside
        box = Rect(0, 0, self.width, self.height, outline=0x000000, fill=0xFFFFFF)
        self.group.append(box)
        self.label = label.Label(font, text=self.wrapped_text, color=0x000000)
        self.label.x = 0
        self.label.y = self.rel_y + 8  # Center vertically within widget height
        self.group.append(self.label)
        self.group.x = self.abs_x
        self.group.y = self.abs_y