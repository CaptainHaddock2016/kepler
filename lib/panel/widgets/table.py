from .base import Widget, font
import panel.core
import displayio
from adafruit_display_shapes.rect import Rect
from adafruit_display_shapes.line import Line
from adafruit_display_text import label

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