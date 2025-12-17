from adafruit_display_text import label
from adafruit_display_shapes.rect import Rect
from .base import Widget, font

class ListBox(Widget):
    def __init__(self, rel_x, rel_y, width, height, options, parent_window=None):
        self.items = options
        self.selected_index = 0
        self.scroll_offset = 0
        super().__init__(rel_x, rel_y, width, height, parent_window)
        self.draw()
        self.attach()

    def draw(self):
        box = Rect(0, 0, self.width, self.height, outline=0x000000, fill=0xFFFFFF)
        self.group.append(box)
        self.labels = []
        for i, item in enumerate(self.items):
            item_label = label.Label(font, text=str(item), color=0x000000)
            item_label.x = 2
            item_label.y = 8 + i * 10
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
            relative_y = y - self.abs_y
            index = relative_y // 10
            self.select(index)
