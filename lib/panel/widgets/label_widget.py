from adafruit_display_text import label
from .base import Widget, font

class Label(Widget):
    def __init__(self, rel_x, rel_y, text, parent_window=None):
        self._text = text
        width = len(text) * 6
        height = 8
        super().__init__(rel_x, rel_y, width, height, parent_window)
        self.draw()
        self.attach()

    def draw(self):
        text_label = label.Label(font, text=self._text, color=0x000000)
        text_label.x = 0
        text_label.y = self.height // 2
        self.group.append(text_label)
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
