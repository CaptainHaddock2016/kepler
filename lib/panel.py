import displayio
from adafruit_display_text import label
from terminalio import FONT
from adafruit_display_shapes.rect import Rect
import core       
     
# UI widgets
# UI widgets can only be used within a Window. These do not use display x y coordinates.
# They are positioned relative to the window's client area.

# ─────────────────────────────────────────────
# UI WIDGET SYSTEM — dynamic coordinates
# ─────────────────────────────────────────────

class LayoutManager:
    def __init__(self, parent_window):
        self.parent_window = parent_window
        self.widgets = []

    def add(self, widget):
        self.widgets.append(widget)
        self.parent_window.addWidget(widget)
        self.reflow()

    def reflow(self):
        """Abstract: compute layout positions."""
        raise NotImplementedError
    
class PackLayout(LayoutManager):
    def __init__(self, parent_window, orientation="vertical", padding=4, spacing=2):
        super().__init__(parent_window)
        self.orientation = orientation  # "vertical" or "horizontal"
        self.padding = padding
        self.spacing = spacing

    def reflow(self):
        if not self.widgets:
            return

        x, y = self.padding, self.padding
        for widget in self.widgets:
            widget.rel_x = x
            widget.rel_y = y
            widget.update_position()

            if self.orientation == "vertical":
                y += widget.height + self.spacing
            else:
                x += widget.width + self.spacing
    
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
    def __init__(self, rel_x, rel_y, width, height, label_text, parent_window, on_click=lambda: None):
        self.label_text = label_text
        self.on_click = on_click
        super().__init__(rel_x, rel_y, width, height, parent_window)
        self.draw()

    def draw(self):
        self.group = displayio.Group(x=self.abs_x, y=self.abs_y)

        # Button rectangle
        rect = Rect(0, 0, self.width, self.height, outline=0x000000, fill=0xFFFFFF)
        
        # Centered text
        text = label.Label(font, text=self.label_text, color=0x000000)
        text.x = (self.width - text.bounding_box[2]) // 2
        text.y = (self.height // 2)
        
        self.group.append(rect)
        self.group.append(text)
        self.attach()