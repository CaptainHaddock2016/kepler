#!/usr/bin/env python3

import math
import time
from adafruit_display_shapes.rect import Rect
from adafruit_display_shapes.circle import Circle
from adafruit_display_text.label import Label
from terminalio import FONT
from helpers import DISPLAY_WIDTH, DISPLAY_HEIGHT
import select
import sys

group = group
refresh = refresh

class Environment:
    def __init__(self,
                 x: int = 0,
                 y: int = 0,
                 width_px: int = DISPLAY_WIDTH,
                 height_px: int = DISPLAY_HEIGHT,
                 scale: float = 100.0,  # pixels per meter
                 gravity: float = -9.81,
                 drag_coeff: float = 0.002,
                 ground_height: float = 0.0,
                 ground_bounce: float = 0.7,
                 ground_friction: float = 0.8):

        self.x = x
        self.y = y
        self.width_px = width_px
        self.height_px = height_px
        self.scale = scale
        self.width_m = width_px / scale
        self.height_m = height_px / scale

        self.gravity = gravity
        self.drag_coeff = drag_coeff
        self.ground_y = ground_height
        self.ground_bounce = ground_bounce
        self.ground_friction = ground_friction

        self.objects = []

        group.append(Rect(x, y, width_px, height_px, outline=0xFFFFFF))

    def add(self, obj):
        self.objects.append(obj)

    def update(self, dt: float):
        for obj in self.objects:
            obj.ay = self.gravity
            obj.apply_quadratic_drag(self.drag_coeff)
            obj.update(dt)
            self._handle_bounds(obj)
            self._handle_ground(obj)

        self._handle_collisions()

        for obj in self.objects:
            obj.sync_shape(self.scale, self.height_m, self.x, self.y)


    def _handle_bounds(self, obj):
        r = obj.r

        if obj.x - r < 0:
            obj.x = r
            obj.vx = -obj.vx * 0.8
        elif obj.x + r > self.width_m:
            obj.x = self.width_m - r
            obj.vx = -obj.vx * 0.8

        if obj.y + r > self.height_m:
            obj.y = self.height_m - r
            obj.vy = -obj.vy * 0.8

    def _handle_ground(self, obj):
        r = obj.r
        if obj.y - r <= self.ground_y:
            obj.y = self.ground_y + r
            obj.vy = -obj.vy * self.ground_bounce
            obj.vx *= self.ground_friction

    def _handle_collisions(self):
        objs = self.objects
        n = len(objs)
        for i in range(n):
            a = objs[i]
            for j in range(i + 1, n):
                self._resolve_collision(a, objs[j])

    def _resolve_collision(self, a, b):
        dx, dy = b.x - a.x, b.y - a.y
        dist_sq = dx * dx + dy * dy
        min_dist = a.r + b.r

        if dist_sq < min_dist * min_dist and dist_sq > 0:
            dist = math.sqrt(dist_sq)
            nx, ny = dx / dist, dy / dist

            rvx, rvy = b.vx - a.vx, b.vy - a.vy
            vel_norm = rvx * nx + rvy * ny
            if vel_norm > 0:
                return  

            e = min(self.ground_bounce, 1.0)
            inv_mass_sum = 1 / a.mass + 1 / b.mass

            j = -(1 + e) * vel_norm / inv_mass_sum
            impulse_x, impulse_y = j * nx, j * ny

            a.vx -= impulse_x / a.mass
            a.vy -= impulse_y / a.mass
            b.vx += impulse_x / b.mass
            b.vy += impulse_y / b.mass

            correction = (min_dist - dist) / inv_mass_sum * 0.8
            a.x -= correction * nx / a.mass
            a.y -= correction * ny / a.mass
            b.x += correction * nx / b.mass
            b.y += correction * ny / b.mass

    def __str__(self):
        return "Environment"


class PhysicalObject:
    def __init__(self, shape, radius_m, x, y, vx=0.0, vy=0.0, mass=1.0):
        self.shape = shape
        self.x, self.y = x, y
        self.vx, self.vy = vx, vy
        self.ax, self.ay = 0.0, 0.0
        self.r = radius_m
        self.mass = mass
        group.append(shape)

    def sync_shape(self, scale, screen_height_m, x_offset_px=0, y_offset_px=0):
        self.shape.x = int((self.x - self.r) * scale) + x_offset_px
        self.shape.y = int((screen_height_m - (self.y + self.r)) * scale) + y_offset_px

    def apply_quadratic_drag(self, drag_coeff):
        speed_sq = self.vx**2 + self.vy**2
        if speed_sq > 0:
            speed = math.sqrt(speed_sq)
            drag = drag_coeff * speed
            self.ax -= drag * (self.vx / speed)
            self.ay -= drag * (self.vy / speed)

    def apply_force(self, fx, fy):
        self.ax += fx / self.mass
        self.ay += fy / self.mass

    def update(self, dt):
        self.vx += self.ax * dt
        self.vy += self.ay * dt
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.ax = self.ay = 0.0


class SphericalObject(PhysicalObject):
    def __init__(self, radius_m, x, y, vx, vy, mass, scale):
        shape = Circle(0, 0, int(radius_m * scale), fill=0xFFFFFF)
        super().__init__(shape, radius_m, x, y, vx, vy, mass)

    def __str__(self):
        return "SphericalObject"


class CuboidalObject(PhysicalObject):
    def __init__(self, width_m, height_m, x, y, vx, vy, mass, scale):
        shape = Rect(int(x * scale), int(y * scale),
                     int(width_m * scale), int(height_m * scale),
                     fill=0xFFFFFF)
        super().__init__(shape, width_m / 2, x, y, vx, vy, mass)

    def __str__(self):
        return "CuboidalObject"



class Explorer:
    def __init__(self, n_rows=10):
        self.entries = []
        self.labels = []
        self.n_rows = n_rows
        self.selected = 0

        # draw UI 
        group.append(Rect(0, 0, 121, DISPLAY_HEIGHT, fill=0x000000, outline=0xFFFFFF))
        group.append(Rect(120, 0, DISPLAY_WIDTH - 120, 21, fill=0x000000, outline=0xFFFFFF))

        self.poll = select.poll()
        self.poll.register(sys.stdin, select.POLLIN)

    def add_environment(self, env):
        self.entries.append((0, env))
        for obj in env.objects:
            self.entries.append((1, obj))
        self._render_labels()
        print(self.entries)

    def _render_labels(self):
        for i, (depth, obj) in enumerate(self.entries[:self.n_rows]):
            text = f" {'  ' * depth}{obj}"
            label = Label(FONT, text=text, color=0xFFFFFF, x=2, y=12 + i * 10)
            self.labels.append(label)
            group.append(label)
        self.labels[0].text = ">" + self.labels[0].text[1:]
    
    def update(self):
        if not self.poll.poll(10):
            return

        ch = sys.stdin.read(1)
        if ch == "\x1b":   # ESC prefix
            seq = sys.stdin.read(2)
            if seq == "[A":  # UP
                if self.selected > 0:
                    self.labels[self.selected].text = '  '*self.entries[self.selected][0] + " " + self.labels[self.selected].text.strip()[1:]
                    self.selected -= 1
                    self.labels[self.selected].text = '  '*self.entries[self.selected][0] + ">" + self.labels[self.selected].text.strip()
            elif seq == "[B":  # DOWN
                if self.selected + 1 < len(self.labels):
                    self.labels[self.selected].text = '  '*self.entries[self.selected][0] + " " + self.labels[self.selected].text.strip()[1:]
                    self.selected += 1
                    self.labels[self.selected].text = '  '*self.entries[self.selected][0] + ">" + self.labels[self.selected].text.strip()


exp = Explorer()

env = Environment(
    x=120,
    y=20,
    width_px=DISPLAY_WIDTH - 120,
    height_px=DISPLAY_HEIGHT - 20,
    scale=100,
    gravity=-9.81,
    drag_coeff=0.0001,
    ground_height=0.0,
    ground_bounce=0.8,
    ground_friction=0.6
)

sphere = SphericalObject(0.20, 1.0, 3.0, 3, 0, 1.0, env.scale)
cuboid = CuboidalObject(0.4, 0.4, 2.0, 5.0, -9, 0, 2.0, env.scale)

env.add(sphere)
env.add(cuboid)
exp.add_environment(env)


FRAME_DT = 0.016  # 60 fps
while True:
    exp.update()
    env.update(FRAME_DT)
    refresh()
    time.sleep(FRAME_DT)
