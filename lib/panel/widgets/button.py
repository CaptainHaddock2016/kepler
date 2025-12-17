import time
from adafruit_display_text import label
from adafruit_display_shapes.rect import Rect
import panel.core
from .base import Widget, font
import displayio

class Button(Widget):
    def __init__(self, rel_x, rel_y, width, height, text, parent_window, on_click=lambda: None):
        self._text = text
        self.usr_on_click = on_click
        super().__init__(rel_x, rel_y, width, height, parent_window)
        self.draw()

    def draw(self):
        self.group = displayio.Group(x=self.abs_x, y=self.abs_y)
        rect = Rect(0, 0, self.width, self.height, outline=0x000000, fill=0xFFFFFF)
        text_label = label.Label(font, text=self._text, color=0x000000)
        text_label.x = (self.width - text_label.bounding_box[2]) // 2
        text_label.y = self.height // 2
        self.group.append(rect)
        self.group.append(text_label)
        self.attach()

    def on_click(self, x, y):
        if self.inBounds(x, y):
            self.group[0].fill = 0xCCCCCC
            panel.core.GUI.display.refresh()
            self.usr_on_click()
            time.sleep(0.1)
            self.group[0].fill = 0xFFFFFF
