import displayio
import panel.core

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

    @property
    def abs_x(self):
        if not self.parent_window:
            return self.rel_x
        return self.parent_window.x + 1 + self.rel_x

    @property
    def abs_y(self):
        if not self.parent_window:
            return self.rel_y
        return self.parent_window.y + 12 + self.rel_y  # Offset for title bar

    def attach(self):
        if self.parent_window:
            self.parent_window.group.append(self.group)

    def addWidget(self, widget):
        widget.parent_window = self.parent_window
        self.group.append(widget.group)

    def update_position(self):
        self.group.x = self.abs_x
        self.group.y = self.abs_y

    def inBounds(self, x, y):
        return self.abs_x <= x < self.abs_x + self.width and self.abs_y <= y < self.abs_y + self.height

    def draw(self):
        raise NotImplementedError

    def destroy(self):
        if self.parent_window and self.group in self.parent_window.group:
            self.parent_window.group.remove(self.group)
