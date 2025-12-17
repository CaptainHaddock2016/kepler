import displayio
from adafruit_display_text import label
from adafruit_display_shapes.rect import Rect
from adafruit_display_shapes.circle import Circle
from adafruit_bitmap_font import bitmap_font
import vectorio
import adafruit_usb_host_descriptors
import usb.core
import array
import adafruit_imageload
import supervisor
import sys
import time

font_file = "sd/dev/cp437-6x8a.pcf"

font = bitmap_font.load_font(font_file)
font.load_glyphs(b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*()-_=+[]{};:'\",.<>/?\\|`~ ")

GUI = None

class GUI:
    def __init__(self, display, terminal, input, print, kernel):
        global GUI

        self.display = display
        self.terminal = terminal
        self.input = input
        self.print = print
        self.kernel = kernel
        self.guiroot = displayio.Group()
        self.display.root_group = self.guiroot
        self.display.auto_refresh = False

        # Key buffer (simple FIFO). Bounded to avoid runaway memory use.
        self._key_buffer = []
        # store provided input source (can be a callable or None)
        self.input_source = input

        self.windows = []
        self.cursor = Cursor()
        self.guiroot.append(self.cursor.group)
        self.drawBackground()
        #self.drawTitleBar()

        self.currentDesktopIconX = 10
        self.currentDesktopIconY = 10

        # Add a time source and a timestamp for when the time label was last updated.
        # Use monotonic() if available to avoid issues with system clock changes.
        self._now = time.monotonic if hasattr(time, "monotonic") else time.time
        self._last_time_update = self._now()

        self.focus = None  # Currently focused window or widget
        self.focused_widget = None

        self._key_buffer = bytearray(256)   # small fixed ring buffer
        self._kb_head = 0
        self._kb_tail = 0
        self._read_buf = bytearray(64)      # bulk read buffer
        
        GUI = self

        self.display.refresh()

    def addWindow(self, window):
        self.windows.append(window)
        self.guiroot.append(window.group)
        self.guiroot.append(self.guiroot.pop(0))  # Ensure cursor is on top
        self.focus = window
        self.display.refresh()

    def addIcon(self, icon):
        # Draw desktop icon
        tg = icon.draw(x=self.currentDesktopIconX, y=self.currentDesktopIconY)
        self.guiroot.append(tg)
        self.currentDesktopIconX += 32  # Move x position for next icon
        if self.currentDesktopIconX + 32 > self.display.width:
            self.currentDesktopIconX = 10
            self.currentDesktopIconY += 32

    def drawTitleBar(self):
        # Macintosh-style menu bar
        self.guiroot.append(Rect(0, 0, self.display.width, 12, fill=0xffffff))
        # Add some menu text

    def drawBackground(self):

        bitmap, palette = adafruit_imageload.load("sd/dev/pattern1.bmp", bitmap=displayio.Bitmap, palette=displayio.Palette)

        # Show the bitmap
        # Get display dimensions
        screen_width = self.display.width
        screen_height = self.display.height

        # Get tile dimensions
        tile_width = bitmap.width
        tile_height = bitmap.height

        tile_grid = displayio.TileGrid(
            bitmap,
            pixel_shader=palette,
            width=screen_width // tile_width,   # number of tiles horizontally
            height=screen_height // tile_height,   # number of tiles vertically
            tile_width=tile_width,
            tile_height=tile_height,
        )

        # Display group
        self.guiroot.append(tile_grid)

        self.display.refresh()

    def fillAllColorsFast(self):
        bitmap = displayio.Bitmap(self.display.width, self.display.height, 256)
        palette = displayio.Palette(256)

        # Generate a simple grayscale palette for demonstration
        for i in range(256):
            palette[i] = (i << 16) | (i << 8) | i  # grayscale ramp

        tile_grid = displayio.TileGrid(bitmap, pixel_shader=palette)
        self.guiroot.append(tile_grid)

        # Loop through all 256 colors and fill the entire bitmap
        for i in range(256):
            for x in range(0, self.display.width):
                for y in range(0, self.display.height):
                    bitmap[x, y] = i


    def update(self):
        cursorRead = self.cursor.update()
        btn = cursorRead[0]
        if btn:
            if btn == "left":
                # Check windows in reverse order (topmost first)
                for window in reversed(self.windows):
                    # get the tip of the cursor
                    cursor_tip_y = self.cursor.y - 4
                    cursor_tip_x = self.cursor.x - 4
                    if window.inBounds(cursor_tip_x, cursor_tip_y):
                        self.focus = window
                        window.processClick(cursor_tip_x, cursor_tip_y)
                        break  # Stop after closing one window
        elif cursorRead[1]:
            # scroll wheel event (1 or -1)
            scroll_direction = cursorRead[1]
            for window in reversed(self.windows):
                if window.inBounds(self.cursor.x, self.cursor.y):
                    if self.focused_widget and hasattr(self.focused_widget, 'on_scroll'):
                        if callable(self.focused_widget.on_scroll):
                            self.focused_widget.on_scroll(scroll_direction)
        # Poll input early and aggressively

        # Drain and dispatch all buffered keys immediately to reduce perceived latency
        # Streamlined keyboard dispatch
        self.poll_keypresses()

        if self.focused_widget and hasattr(self.focused_widget, 'on_key'):
            keys = self.drain_keys()
            if keys:
                self.focused_widget.on_key(keys)

        # Redraw time/date in title bar
        # Efficient: only update every 60 seconds.
        #now = self._now()
        #if (now - self._last_time_update) >= 60:
        #    t = time.localtime()
        #    timestr = f"{t[3]:02}:{t[4]:02} {t[2]:02}/{t[1]:02}/{t[0]%100:02}"
        #    self.timeLabel.text = timestr
        #    self._last_time_update = now

        self.display.refresh()

    # New: keyboard buffer helpers
    def _kb_push(self, c):
        """Push one byte into the ring buffer, dropping oldest if full."""
        nxt = (self._kb_head + 1) % len(self._key_buffer)
        if nxt == self._kb_tail:  # buffer full, drop oldest
            self._kb_tail = (self._kb_tail + 1) % len(self._key_buffer)
        self._key_buffer[self._kb_head] = c
        self._kb_head = nxt

    def _kb_pop(self):
        """Pop one byte from ring buffer, or return None."""
        if self._kb_head == self._kb_tail:
            return None
        c = self._key_buffer[self._kb_tail]
        self._kb_tail = (self._kb_tail + 1) % len(self._key_buffer)
        return c

    def _kb_available(self):
        """Number of bytes available."""
        if self._kb_head >= self._kb_tail:
            return self._kb_head - self._kb_tail
        return len(self._key_buffer) - (self._kb_tail - self._kb_head)

    def poll_keypresses(self):
        """
        High-performance nonblocking serial poll.
        Reads in chunks into a preallocated buffer.
        """
        avail = supervisor.runtime.serial_bytes_available
        if not avail:
            return
        n = min(avail, len(self._read_buf))
        # read directly into buffer to minimize Python overhead
        data = sys.stdin.read(n)
        if not data:
            return
        for ch in data:
            self._kb_push(ord(ch) if isinstance(ch, str) else ch)

    def drain_keys(self):
        """Return all currently buffered keys as a single string."""
        if self._kb_head == self._kb_tail:
            return ""
        if self._kb_head > self._kb_tail:
            data = self._key_buffer[self._kb_tail:self._kb_head]
        else:
            data = self._key_buffer[self._kb_tail:] + self._key_buffer[:self._kb_head]
        self._kb_tail = self._kb_head
        return bytes(data).decode()
    


class Window:
    def __init__(self, x, y, width, height, title="Window"):

        assert GUI is not None, "GUI system not initialized"
        assert width > 20 and height > 20, "Window too small"
        assert x >= 0 and y >= 0, "Window position out of bounds"
        assert x + width <= GUI.display.width and y + height <= GUI.display.height, "Window exceeds display bounds"
        assert len(title) < (width // 8) - 10, "Title too long"

        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.title = title
        self.group = displayio.Group()
        self.drawWindow()

        self.isMaximized = False
        self.windowedWidth = width
        self.windowedHeight = height

        self.windowedx = x
        self.windowedy = y

        self.widgets = []

        GUI.addWindow(self)


    def drawWindow(self):
        # Background
        self.group.append(Rect(self.x, self.y, self.width, self.height, fill=0x00000))
        # Title bar
        self.group.append(Rect(self.x+1, self.y+1, self.width - 2, 10, fill=0xFFFFFF))
        # Content area
        self.group.append(Rect(self.x+1, self.y + 12, self.width-2, self.height-13, fill=0xFFFFFF))

        # Title text

        text = label.Label(font, text=self.title, color=0x000000, x=self.x, y=self.y+7)
        text.x = ((self.width - text.bounding_box[2]) // 2) + self.x

        self.group.append(text)

        # Traffic light buttons

        self.group.append(Circle(self.x + 6, self.y + 6, 2, fill=0xFF605C))  # Close button
        self.group.append(Circle(self.x + 14, self.y + 6, 2, fill=0xFFBD44)) # Minimize button
        self.group.append(Circle(self.x + 22, self.y + 6, 2, fill=0x00CA56)) # Maximize button

        # Application specific content

        #text = label.Label(font, text="Hi mom", color=0x000000, x=self.x + 3, y=self.y+18)

        #self.group.append(text)

    def addWidget(self, widget):
        widget.parent_window = self
        #widget.attach()
        self.widgets.append(widget)

    def translate(self, dx, dy):
        """
        Moves the window by (dx, dy) pixels.
        Automatically updates internal position and refreshes the display.
        """

        # New target position
        new_x = self.x + dx
        new_y = self.y + dy

        # Ensure we stay within display bounds
        if (
            new_x < 0
            or new_y < 0
            or new_x + self.width > GUI.display.width
            or new_y + self.height > GUI.display.height
        ):
            return  # Ignore movement if it would move window offscreen

        # Move all child layers within the window group
        for item in self.group:
            item.x += dx
            item.y += dy

        # Update stored position
        self.x = new_x
        self.y = new_y

        # Refresh display
        GUI.display.refresh()

    def inBounds(self, x, y):
        return self.x <= x < self.x + self.width and self.y <= y < self.y + self.height

    def processClick(self, x, y):
        """Process a click at (x, y) relative to the display coordinates."""

        # Process traffic light buttons
        if (self.x + 4) <= x <= (self.x + 8) and (self.y + 4) <= y <= (self.y + 8):
            # Close button clicked
            GUI.guiroot.remove(self.group)
            GUI.windows.remove(self)
            GUI.display.refresh()
            return "closed"
        elif (self.x + 12) <= x <= (self.x + 16) and (self.y + 4) <= y <= (self.y + 8):
            # Minimize button clicked
            # For simplicity, just hide the window
            self.group.hidden = True
            GUI.display.refresh()
            return "minimized"
        elif (self.x + 20) <= x <= (self.x + 24) and (self.y + 4) <= y <= (self.y + 8):
            # Maximize button clicked
            # For simplicity, just toggle between full screen and original size
            GUI.cursor.group.hidden = True
            if not self.isMaximized:
                # Maximizing Logic
                self.windowedHeight = self.height
                self.windowedWidth = self.width
                self.windowedx = self.x
                self.windowedy = self.y
                self.translate(-self.x, -self.y)  # Move to (0,0)
                self.width = GUI.display.width
                self.height = GUI.display.height
                self.group[0] = Rect(0, 0, self.width, self.height, fill=0x000000)
                self.group[1] = Rect(1, 1, self.width - 2, 10, fill=0xFFFFFF)
                self.group[2] = Rect(1, 12, self.width - 2, self.height - 13, fill=0xFFFFFF)
                self.group[3].x = (self.width - self.group[3].bounding_box[2]) // 2
                self.isMaximized = True
            else:
                print("minimizing")
                # Restore to original size (for simplicity, just a fixed size)
                self.width = self.windowedWidth
                self.height = self.windowedHeight
                self.group[0] = Rect(0, 0, self.width, self.height, fill=0x000000)
                self.group[1] = Rect(1, 1, self.width - 2, 10, fill=0xFFFFFF)
                self.group[2] = Rect(1, 12, self.width - 2, self.height - 13, fill=0xFFFFFF)
                self.group[3].x = (self.width - self.group[3].bounding_box[2]) // 2
                self.translate(self.windowedx, self.windowedy)
                self.isMaximized = False
            GUI.display.refresh()
            GUI.cursor.group.hidden = False
            return "maximized"

        # Process dragging if within title bar. Use a frame outline for smooth preview
        elif (self.y <= y <= self.y + 10) and not self.isMaximized:
            # Start dragging
            initial_mouse_x = x
            initial_mouse_y = y
            frame_x = self.x
            frame_y = self.y

            # Create a frame rectangle to show the drag outline
            frame = Rect(frame_x, frame_y, self.width, self.height, outline=0xFFFFFF)
            GUI.guiroot.append(frame)
            GUI.display.refresh()

            while True:
                m = GUI.cursor.readUSB()
                if m:
                    dx = int(m[0] * GUI.cursor.speedMultiplier)
                    dy = int(m[1] * GUI.cursor.speedMultiplier)
                    
                    if dx != 0 or dy != 0:
                        # Update cursor position
                        GUI.cursor.x += dx
                        GUI.cursor.y += dy
                        GUI.cursor.x = max(0, min(GUI.cursor.x, GUI.display.width - 1))
                        GUI.cursor.y = max(0, min(GUI.cursor.y, GUI.display.height - 1))
                        
                        # Calculate frame position based on cursor delta
                        frame_x += dx
                        frame_y += dy

                        # Clamp within display bounds
                        frame_x = max(0, min(frame_x, GUI.display.width - self.width))
                        frame_y = max(0, min(frame_y, GUI.display.height - self.height))

                        # Update frame position
                        frame.x = frame_x
                        frame.y = frame_y
                        GUI.cursor.draw()

                    # Check if left mouse button is released
                    if m[2] != "left":
                        break

            # Finalize window position
            self.translate(frame_x - self.x, frame_y - self.y)

            GUI.guiroot.remove(frame)
            GUI.display.refresh()
            return "moved"
        
        # Process widgets if any
        for item in self.widgets:
            if item.inBounds(x, y):
                self.focused_widget = item
                GUI.focused_widget = item
                if hasattr(item, 'on_click'):
                    if callable(item.on_click):
                        item.on_click(x, y)
                return
        self.focused_widget = None
        GUI.focused_widget = None

class Cursor:
    def __init__(self, x=320, y=240):
        self.x = int(x)
        self.y = int(y)
        self.firstDraw()

        self.speedMultiplier = 1

        self.BUTTONS = ["left", "right", "middle"]

        self.buf = array.array("b", [0] * 8)

        # scan for connected USB device and loop over any found
        for device in usb.core.find(find_all=True):
            # print device info
            print(f"{device.idVendor:04x}:{device.idProduct:04x}")
            print(device.manufacturer, device.product)
            print(device.serial_number)

            # try to find mouse endpoint on the current device.
            mouse_interface_index, mouse_endpoint_address = (
                adafruit_usb_host_descriptors.find_boot_mouse_endpoint(device)
            )
            if mouse_interface_index is not None and mouse_endpoint_address is not None:
                self.mouse = device
                print(
                    f"mouse interface: {mouse_interface_index} "
                    + f"endpoint_address: {hex(mouse_endpoint_address)}"
                )

                # detach the kernel driver if needed
                if self.mouse.is_kernel_driver_active(0):
                    self.mouse.detach_kernel_driver(0)

                # set configuration on the mouse so we can use it
                self.mouse.set_configuration()

                break

    def move(self, dx, dy):
        self.x += dx
        self.y += dy

        # Clamp within display bounds
        self.x = max(0, min(self.x, GUI.display.width - 1))
        self.y = max(0, min(self.y, GUI.display.height - 1))

        self.draw()

    def firstDraw(self):
        self.group = displayio.Group()

        # Palette: [outline, fill]
        palette = displayio.Palette(2)
        palette[0] = 0x000000  # Black outline
        palette[1] = 0xFFFFFF  # White fill

        # Define smaller pointer coordinates (roughly half of the full-size version)
        fill_points = [
            (0, 0),
            (0, 7),
            (1, 5),
            (4, 9),
            (4, 8),
            (3, 5),
            (5, 5)
        ]

        outline_points = [
            (-1, -1),
            (-1, 8),
            (1, 6),
            (4, 9),
            (5, 9),
            (4, 5),
            (6, 5)
        ]
        
        # Create the two polygons
        self.outline = vectorio.Polygon(points=outline_points, pixel_shader=palette, color_index=0, x=self.x, y=self.y)
        self.fill = vectorio.Polygon(points=fill_points, pixel_shader=palette, color_index=1, x=self.x, y=self.y)

        # Add both to group (outline first)
        self.group.append(self.outline)
        self.group.append(self.fill)

    def draw(self):
        # Update positions
        self.outline.x = int(self.x)
        self.outline.y = int(self.y)
        self.fill.x = int(self.x)
        self.fill.y = int(self.y)
        GUI.display.refresh()

    def readUSB(self):
        """Mouse event handler."""
        try:
            # attempt to read data from the mouse
            # 20ms timeout, so we don't block long if there
            # is no data
            self.mouse.read(0x82, self.buf, timeout=1)
        except usb.core.USBTimeoutError:
            # skip the rest of the loop if there is no data
            return

        # string with delta x, y values to print

        # loop over the button names
        btn = None
        for i, button in enumerate(self.BUTTONS):
            # check if each button is pressed using bitwise AND shifted
            # to the appropriate index for this button
            if self.buf[0] & (1 << i) != 0:
                # append the button name to the string to show if
                # it is being clicked.
                btn = button

        return self.buf[1], self.buf[2], self.buf[3], btn

    def update(self):
        m = self.readUSB()
        if m:
            self.move(int(m[0] * self.speedMultiplier), int(m[1] * self.speedMultiplier))
            if m[3]:
                return m[3], None
            elif m[2]:
                return None, m[2]
        return None, None
            
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

class Icon:
    def __init__(self, path):
        self.name = path.name
        self.path = path._kernel_path()
        # Load icon image and create display elements as needed
    def draw(self, x, y):
        image, palette = adafruit_imageload.load(
            f"{str(self.path)}/icon.png", bitmap=displayio.Bitmap, palette=displayio.Palette,
        )
        tile_grid = displayio.TileGrid(image, pixel_shader=palette, x=x, y=y)

        return tile_grid