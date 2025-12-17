from adafruit_usb_host_mouse import find_and_init_boot_mouse
import dang
import time

mouse = find_and_init_boot_mouse("/mouse_cursor.bmp")

group.append(mouse.tilegrid)

while True:
    # update mouse
    pressed_btns = mouse.update()
    refresh()
    time.sleep(0.016)