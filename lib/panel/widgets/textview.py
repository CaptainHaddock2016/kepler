from adafruit_display_text import label, wrap_text_to_lines
from adafruit_display_shapes.rect import Rect
from .base import Widget, font

class TextView(Widget):
    def __init__(self, rel_x, rel_y, width, height, text="", parent_window=None):
        self.text = text
        self.wrapped_text = "\n".join(wrap_text_to_lines(text, width // 6))
        super().__init__(rel_x, rel_y, width, height, parent_window)
        self.draw()
        self.attach()

    def draw(self):
        box = Rect(0, 0, self.width, self.height, outline=0x000000, fill=0xFFFFFF)
        self.group.append(box)
        self.label = label.Label(font, text=self.wrapped_text, color=0x000000)
        self.label.x = 0
        self.label.y = self.rel_y + 8
        self.group.append(self.label)
        self.group.x = self.abs_x
        self.group.y = self.abs_y
