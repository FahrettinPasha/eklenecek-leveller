"""
=============================================================================
  GRINDER SURVIVAL LEVEL MODULE
  A standalone Pygame survival level designed to be plugged into a larger
  game project.

  INTEGRATION GUIDE:
  ------------------
  To run as a standalone demo:
      python grinder_level.py

  To integrate into an existing game:
      from grinder_level import SurvivalLevel
      level = SurvivalLevel(screen, clock)
      result = level.run()   # returns "win", "lose", or "quit"

  The SurvivalLevel.run() method returns a string result code that your
  main game can use to route to the next scene or level.
=============================================================================
"""

import pygame
import random
import math
import sys
from typing import Optional

# ─────────────────────────────────────────────
#  CONSTANTS  (tweak these to tune feel)
# ─────────────────────────────────────────────
SCREEN_W, SCREEN_H = 960, 640
FPS = 60
GRAVITY = 900            # px/s²
SURVIVAL_GOAL = 60       # seconds to survive for a win

# Colours
C_BG         = (18, 18, 24)
C_FLOOR      = (55, 50, 45)
C_PLATFORM   = (110, 90, 60)
C_PLAYER     = (80, 200, 120)
C_PLAYER_DMG = (220, 80,  80)
C_SMALL_ENEMY= (200, 60,  60)
C_HEAVY_ENEMY= (180, 100, 40)
C_EXPLO_ENEMY= (220, 200,  0)
C_JUNK       = (120, 120, 130)
C_GRINDER    = (60,  60,  70)
C_BLADE      = (200, 200, 220)
C_HUD_BG     = (0, 0, 0, 160)
C_WHITE      = (255, 255, 255)
C_ORANGE     = (255, 160,  40)
C_RED        = (220,  40,  40)
C_DARK_RED   = (140,  20,  20)
C_YELLOW     = (255, 230,  50)
C_SPARK      = (255, 200,  80)

# ─────────────────────────────────────────────
#  UTILITY
# ─────────────────────────────────────────────

def clamp(val, lo, hi):
    return max(lo, min(hi, val))


class ScreenShake:
    """Simple screen-shake effect via render offset."""
    def __init__(self):
        self.trauma  = 0.0    # 0–1
        self.offset  = (0, 0)

    def add(self, amount: float):
        self.trauma = clamp(self.trauma + amount, 0, 1)

    def update(self, dt: float):
        if self.trauma > 0:
            self.trauma = max(0, self.trauma - dt * 1.8)
            mag = self.trauma ** 2 * 20
            self.offset = (
                random.uniform(-mag, mag),
                random.uniform(-mag, mag),
            )
        else:
            self.offset = (0, 0)


class Particle:
    """Tiny visual spark / debris particle."""
    def __init__(self, x, y, colour, vx, vy, life=0.5, size=4):
        self.x, self.y = float(x), float(y)
        self.vx, self.vy = float(vx), float(vy)
        self.colour = colour
        self.life = life
        self.max_life = life
        self.size = size

    def update(self, dt):
        self.x  += self.vx * dt
        self.y  += self.vy * dt
        self.vy += GRAVITY * 0.4 * dt
        self.life -= dt

    def alive(self):
        return self.life > 0

    def draw(self, surf, offset=(0, 0)):
        alpha = self.life / self.max_life
        r, g, b = self.colour
        colour = (int(r * alpha), int(g * alpha), int(b * alpha))
        s = max(1, int(self.size * alpha))
        ox, oy = offset
        pygame.draw.circle(surf, colour,
                           (int(self.x + ox), int(self.y + oy)), s)


def spawn_particles(pool, x, y, colour, n=12, speed=120):
    for _ in range(n):
        angle = random.uniform(0, math.tau)
        spd   = random.uniform(speed * 0.4, speed)
        pool.append(Particle(x, y, colour,
                             math.cos(angle) * spd,
                             math.sin(angle) * spd,
                             life=random.uniform(0.3, 0.7)))


# ─────────────────────────────────────────────
#  PLAYER
# ─────────────────────────────────────────────

class Player:
    WIDTH  = 30
    HEIGHT = 44
    SPEED  = 260      # px/s horizontal
    JUMP_V = -540     # px/s jump impulse
    MAX_HP = 100
    ATTACK_RANGE  = 55
    ATTACK_DAMAGE = 25
    ATTACK_COOLDOWN = 0.35   # seconds

    def __init__(self, x, y):
        self.x = float(x)
        self.y = float(y)
        self.vx = 0.0
        self.vy = 0.0
        self.hp = self.MAX_HP
        self.on_ground = False
        self.facing = 1          # 1 = right, -1 = left
        self.attack_timer = 0.0
        self.attacking = False
        self.attack_anim = 0.0   # 0–1 visual counter
        self.invincible = 0.0    # i-frames in seconds
        self.alive = True

    @property
    def rect(self):
        return pygame.Rect(int(self.x), int(self.y), self.WIDTH, self.HEIGHT)

    @property
    def centre(self):
        return (self.x + self.WIDTH / 2, self.y + self.HEIGHT / 2)

    def handle_input(self, keys, dt):
        """Process keyboard input – call once per frame."""
        dx = 0
        if keys[pygame.K_a] or keys[pygame.K_LEFT]:
            dx -= 1
            self.facing = -1
        if keys[pygame.K_d] or keys[pygame.K_RIGHT]:
            dx += 1
            self.facing = 1

        self.vx = dx * self.SPEED

        if (keys[pygame.K_SPACE] or keys[pygame.K_w] or keys[pygame.K_UP]) \
                and self.on_ground:
            self.vy = self.JUMP_V
            self.on_ground = False

        # Attack input (Z or J)
        if (keys[pygame.K_z] or keys[pygame.K_j]) \
                and self.attack_timer <= 0:
            self.attacking = True
            self.attack_anim = 1.0
            self.attack_timer = self.ATTACK_COOLDOWN

    def update(self, dt, platforms):
        """Physics + collision update."""
        if not self.alive:
            return

        self.attack_timer = max(0, self.attack_timer - dt)
        self.attack_anim  = max(0, self.attack_anim  - dt * 4)
        self.invincible   = max(0, self.invincible   - dt)

        # Gravity
        self.vy += GRAVITY * dt

        # Horizontal move
        self.x += self.vx * dt
        self.x  = clamp(self.x, 0, SCREEN_W - self.WIDTH)

        # Vertical move + platform collision
        self.y += self.vy * dt
        self.on_ground = False

        for plat in platforms:
            pr = self.rect
            if pr.colliderect(plat) and self.vy >= 0:
                if pr.bottom - plat.top < 28:  # landed from above
                    self.y = plat.top - self.HEIGHT
                    self.vy = 0
                    self.on_ground = True

        # Floor boundary (kill zone is handled by SurvivalLevel)
        self.y = min(self.y, SCREEN_H + 10)

        # Reset attack flag after one frame
        self.attacking = False

    def take_damage(self, amount):
        if self.invincible > 0:
            return
        self.hp -= amount
        self.invincible = 0.6
        if self.hp <= 0:
            self.hp = 0
            self.alive = False

    def get_attack_rect(self):
        """Returns the hitbox for the melee attack."""
        cx = self.x + self.WIDTH / 2 + self.facing * (self.ATTACK_RANGE / 2)
        cy = self.y + self.HEIGHT / 2
        return pygame.Rect(
            int(cx - self.ATTACK_RANGE / 2),
            int(cy - 20),
            self.ATTACK_RANGE,
            40
        )

    def draw(self, surf, offset=(0, 0)):
        if not self.alive:
            return
        ox, oy = offset
        x, y = int(self.x + ox), int(self.y + oy)

        # Flash white during invincibility
        body_colour = (230, 230, 230) \
            if (self.invincible > 0 and int(self.invincible * 12) % 2) \
            else C_PLAYER

        # Body
        pygame.draw.rect(surf, body_colour,
                         (x, y, self.WIDTH, self.HEIGHT), border_radius=4)

        # Eyes / direction indicator
        eye_x = x + (self.WIDTH // 2) + self.facing * 6
        eye_y = y + 10
        pygame.draw.circle(surf, (20, 20, 20), (eye_x, eye_y), 4)

        # Attack swing arc
        if self.attack_anim > 0:
            arc_x = int(self.x + self.WIDTH / 2 + ox)
            arc_y = int(self.y + self.HEIGHT / 2 + oy)
            arc_r = pygame.Rect(arc_x - 40, arc_y - 25, 80, 50)
            alpha = int(200 * self.attack_anim)
            pygame.draw.arc(surf, (*C_YELLOW, alpha), arc_r,
                            math.radians(0 if self.facing == 1 else 90),
                            math.radians(90 if self.facing == 1 else 180), 4)

        # Health bar
        bar_w = self.WIDTH + 10
        bar_x = x - 5
        bar_y = y - 12
        pygame.draw.rect(surf, C_DARK_RED, (bar_x, bar_y, bar_w, 6))
        hp_w = int(bar_w * (self.hp / self.MAX_HP))
        pygame.draw.rect(surf, C_PLAYER, (bar_x, bar_y, hp_w, 6))


# ─────────────────────────────────────────────
#  ENEMIES
# ─────────────────────────────────────────────

class Enemy:
    """Base enemy class – subclass for specific types."""
    WIDTH  = 26
    HEIGHT = 26
    COLOUR = C_SMALL_ENEMY
    CONTACT_DAMAGE = 10
    SPEED  = 80.0
    MAX_HP = 30
    SCORE  = 10

    def __init__(self, x, y):
        self.x = float(x)
        self.y = float(y)
        self.vy = 0.0
        self.vx = 0.0
        self.hp = self.MAX_HP
        self.alive = True
        self.on_ground = False
        self.angle = 0.0          # for spin animation

    @property
    def rect(self):
        return pygame.Rect(int(self.x), int(self.y), self.WIDTH, self.HEIGHT)

    @property
    def centre(self):
        return (self.x + self.WIDTH / 2, self.y + self.HEIGHT / 2)

    def update(self, dt, platforms, player_x):
        self.vy += GRAVITY * dt
        # Chase player horizontally
        cx = self.x + self.WIDTH / 2
        if player_x < cx:
            self.vx = -self.SPEED
        else:
            self.vx = self.SPEED

        self.x += self.vx * dt
        self.y += self.vy * dt
        self.on_ground = False
        self.angle += 90 * dt  # spin

        for plat in platforms:
            if self.rect.colliderect(plat) and self.vy >= 0:
                if self.rect.bottom - plat.top < 28:
                    self.y = plat.top - self.HEIGHT
                    self.vy = 0
                    self.on_ground = True

    def take_damage(self, amount):
        self.hp -= amount
        if self.hp <= 0:
            self.alive = False

    def draw(self, surf, offset=(0, 0)):
        ox, oy = offset
        cx = int(self.x + self.WIDTH / 2 + ox)
        cy = int(self.y + self.HEIGHT / 2 + oy)
        half = self.WIDTH // 2
        # Draw rotating square
        pts = []
        for i in range(4):
            a = math.radians(self.angle + i * 90)
            pts.append((cx + math.cos(a) * half, cy + math.sin(a) * half))
        pygame.draw.polygon(surf, self.COLOUR, pts)
        # Health bar
        bar_w = self.WIDTH
        bar_x = int(self.x + ox)
        bar_y = int(self.y + oy) - 8
        pygame.draw.rect(surf, C_DARK_RED, (bar_x, bar_y, bar_w, 4))
        pygame.draw.rect(surf, C_RED,
                         (bar_x, bar_y, int(bar_w * self.hp / self.MAX_HP), 4))


class SmallEnemy(Enemy):
    """Fast, weak. Zips around erratically."""
    WIDTH  = 22
    HEIGHT = 22
    COLOUR = (220, 70, 70)
    SPEED  = 140.0
    MAX_HP = 20
    CONTACT_DAMAGE = 8
    SCORE  = 10

    def update(self, dt, platforms, player_x):
        # Erratic horizontal jitter
        if random.random() < 0.02:
            self.vx += random.uniform(-60, 60)
        super().update(dt, platforms, player_x)


class HeavyEnemy(Enemy):
    """Slow, tanky. Stomps toward the player."""
    WIDTH  = 38
    HEIGHT = 38
    COLOUR = (170, 100, 50)
    SPEED  = 45.0
    MAX_HP = 100
    CONTACT_DAMAGE = 20
    SCORE  = 30

    def draw(self, surf, offset=(0, 0)):
        ox, oy = offset
        x, y = int(self.x + ox), int(self.y + oy)
        pygame.draw.rect(surf, self.COLOUR,
                         (x, y, self.WIDTH, self.HEIGHT), border_radius=3)
        # bolts
        for bx, by in [(5, 5), (self.WIDTH - 10, 5),
                       (5, self.HEIGHT - 10), (self.WIDTH - 10, self.HEIGHT - 10)]:
            pygame.draw.circle(surf, (200, 200, 210), (x + bx, y + by), 4)
        # hp bar
        bar_w = self.WIDTH
        pygame.draw.rect(surf, C_DARK_RED, (x, y - 8, bar_w, 5))
        pygame.draw.rect(surf, C_ORANGE,
                         (x, y - 8, int(bar_w * self.hp / self.MAX_HP), 5))


class ExplosiveEnemy(Enemy):
    """Runs at the player and detonates."""
    WIDTH  = 28
    HEIGHT = 28
    COLOUR = (230, 210, 30)
    SPEED  = 110.0
    MAX_HP = 25
    CONTACT_DAMAGE = 0     # dealt by explosion instead
    EXPLODE_DAMAGE = 55
    EXPLODE_RADIUS = 90
    SCORE  = 20
    FUSE   = 0.0           # counts up; explodes at 1.0

    def __init__(self, x, y):
        super().__init__(x, y)
        self.fuse = 0.0
        self.exploded = False

    def update(self, dt, platforms, player_x):
        self.fuse += dt * 0.6
        super().update(dt, platforms, player_x)

    def draw(self, surf, offset=(0, 0)):
        ox, oy = offset
        cx = int(self.x + self.WIDTH / 2 + ox)
        cy = int(self.y + self.HEIGHT / 2 + oy)
        # pulsing glow
        pulse = int(abs(math.sin(self.fuse * 6)) * 40)
        colour = (min(255, 200 + pulse), min(255, 180 + pulse), 20)
        pygame.draw.circle(surf, colour, (cx, cy), self.WIDTH // 2)
        # X mark
        pygame.draw.line(surf, (40, 40, 40),
                         (cx - 7, cy - 7), (cx + 7, cy + 7), 3)
        pygame.draw.line(surf, (40, 40, 40),
                         (cx + 7, cy - 7), (cx - 7, cy + 7), 3)
        # hp bar
        bar_w = self.WIDTH
        bx = int(self.x + ox)
        by = int(self.y + oy) - 8
        pygame.draw.rect(surf, C_DARK_RED, (bx, by, bar_w, 4))
        pygame.draw.rect(surf, C_YELLOW,
                         (bx, by, int(bar_w * self.hp / self.MAX_HP), 4))


# ─────────────────────────────────────────────
#  JUNK OBJECTS  (environmental hazard)
# ─────────────────────────────────────────────

class JunkObject:
    """Falling debris – purely environmental hazard."""
    SHAPES   = ["barrel", "panel", "gear"]
    DAMAGE   = 15
    BASE_SPD = 180

    def __init__(self, x, speed_mult=1.0):
        self.x = float(x)
        self.y = float(-40)
        self.vy = self.BASE_SPD * speed_mult * random.uniform(0.8, 1.4)
        self.shape = random.choice(self.SHAPES)
        self.size  = random.randint(18, 32)
        self.angle = random.uniform(0, 360)
        self.spin  = random.uniform(-180, 180)
        self.alive = True

    @property
    def rect(self):
        s = self.size
        return pygame.Rect(int(self.x - s), int(self.y - s), s * 2, s * 2)

    def update(self, dt):
        self.y     += self.vy * dt
        self.angle += self.spin * dt
        if self.y > SCREEN_H + 60:
            self.alive = False

    def draw(self, surf, offset=(0, 0)):
        ox, oy = offset
        cx = int(self.x + ox)
        cy = int(self.y + oy)
        s  = self.size
        a  = math.radians(self.angle)

        if self.shape == "barrel":
            # Rotated rectangle
            pts = [
                (cx + math.cos(a + d) * s,
                 cy + math.sin(a + d) * s)
                for d in [0.4, math.pi - 0.4, math.pi + 0.4, -0.4]
            ]
            pygame.draw.polygon(surf, C_JUNK, pts)
            pygame.draw.polygon(surf, (80, 80, 90), pts, 2)

        elif self.shape == "panel":
            pts = [
                (cx + math.cos(a + i * math.pi / 2) * s,
                 cy + math.sin(a + i * math.pi / 2) * s)
                for i in range(4)
            ]
            pygame.draw.polygon(surf, (90, 90, 100), pts)
            pygame.draw.polygon(surf, (140, 140, 150), pts, 2)

        else:  # gear
            for i in range(8):
                tooth_a = a + i * math.tau / 8
                inner = s * 0.55
                outer = s
                x1 = cx + math.cos(tooth_a - 0.2) * inner
                y1 = cy + math.sin(tooth_a - 0.2) * inner
                x2 = cx + math.cos(tooth_a) * outer
                y2 = cy + math.sin(tooth_a) * outer
                x3 = cx + math.cos(tooth_a + 0.2) * outer
                y3 = cy + math.sin(tooth_a + 0.2) * outer
                x4 = cx + math.cos(tooth_a + 0.4) * inner
                y4 = cy + math.sin(tooth_a + 0.4) * inner
                pygame.draw.polygon(surf, C_JUNK,
                                    [(x1, y1), (x2, y2), (x3, y3), (x4, y4)])
            pygame.draw.circle(surf, (60, 60, 70), (cx, cy), int(s * 0.3))


# ─────────────────────────────────────────────
#  GRINDER MACHINE
# ─────────────────────────────────────────────

class GrinderMachine:
    """
    Industrial grinder – left or right side of the arena.
    Deals continuous damage while active to anything touching it.
    """
    WIDTH  = 120
    HEIGHT = 180
    DAMAGE_PER_SEC = 80

    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.active = False
        self.blade_angle = 0.0
        self.rumble = 0.0   # visual shake offset
        self.activation_progress = 0.0  # 0 → 1 during startup animation

    @property
    def rect(self):
        return pygame.Rect(self.x, self.y, self.WIDTH, self.HEIGHT)

    @property
    def danger_zone(self):
        """Inner zone that deals damage."""
        padding = 10
        return pygame.Rect(
            self.x + padding, self.y + padding,
            self.WIDTH - padding * 2, self.HEIGHT - padding * 2
        )

    def activate(self):
        self.active = True

    def update(self, dt):
        if self.active:
            speed = 220 * self.activation_progress
            self.blade_angle += speed * dt
            self.activation_progress = min(1.0,
                                           self.activation_progress + dt * 0.8)
            self.rumble = random.uniform(-2, 2) if self.activation_progress < 1 else 0

    def draw(self, surf, offset=(0, 0)):
        ox, oy = offset
        rx = int(self.x + ox + self.rumble)
        ry = int(self.y + oy + self.rumble)

        # Housing body
        pygame.draw.rect(surf, C_GRINDER,
                         (rx, ry, self.WIDTH, self.HEIGHT), border_radius=6)
        pygame.draw.rect(surf, (40, 40, 50),
                         (rx, ry, self.WIDTH, self.HEIGHT), 3, border_radius=6)

        # Warning stripes at top
        stripe_h = 22
        for i in range(6):
            col = (200, 180, 0) if i % 2 == 0 else (30, 30, 30)
            pygame.draw.rect(surf, col,
                             (rx + i * (self.WIDTH // 6), ry,
                              self.WIDTH // 6, stripe_h))

        # Blade rotor in the centre
        cx = rx + self.WIDTH  // 2
        cy = ry + self.HEIGHT // 2 + 15
        rotor_r = 42

        pygame.draw.circle(surf, (35, 35, 45), (cx, cy), rotor_r)
        pygame.draw.circle(surf, (50, 50, 60), (cx, cy), rotor_r, 3)

        if self.active:
            num_blades = 6
            for i in range(num_blades):
                a = math.radians(self.blade_angle + i * (360 / num_blades))
                tip_x = cx + math.cos(a) * rotor_r
                tip_y = cy + math.sin(a) * rotor_r
                mid_x = cx + math.cos(a + 0.3) * (rotor_r * 0.5)
                mid_y = cy + math.sin(a + 0.3) * (rotor_r * 0.5)
                pygame.draw.polygon(surf, C_BLADE,
                                    [(cx, cy), (tip_x, tip_y),
                                     (mid_x, mid_y)])
            # Sparks
            if random.random() < 0.3:
                sa = random.uniform(0, math.tau)
                sx = cx + math.cos(sa) * rotor_r
                sy = cy + math.sin(sa) * rotor_r
                pygame.draw.circle(surf, C_SPARK, (int(sx), int(sy)),
                                   random.randint(2, 5))
        else:
            # Idle – just draw static blades
            for i in range(6):
                a = math.radians(i * 60)
                ex = cx + math.cos(a) * rotor_r
                ey = cy + math.sin(a) * rotor_r
                pygame.draw.line(surf, (80, 80, 90), (cx, cy),
                                 (int(ex), int(ey)), 5)

        pygame.draw.circle(surf, (80, 80, 100), (cx, cy), 10)

        # "DANGER" label
        font = pygame.font.SysFont("monospace", 11, bold=True)
        label = font.render("GRINDER", True, (220, 30, 30))
        surf.blit(label, (rx + self.WIDTH // 2 - label.get_width() // 2,
                          ry + self.HEIGHT - 28))


# ─────────────────────────────────────────────
#  SPAWNER
# ─────────────────────────────────────────────

class Spawner:
    """
    Controls when and what enemies / junk fall into the arena.
    Respects difficulty parameters set by DifficultyManager.
    """
    def __init__(self):
        self.enemy_timer    = 0.0
        self.junk_timer     = 0.0
        self.enemy_interval = 3.0   # seconds between enemy spawns
        self.junk_interval  = 2.0   # seconds between junk spawns

    def update(self, dt, enemies, junks, diff):
        """
        diff: a DifficultyManager instance with current parameters.
        enemies / junks: lists to append new entities to.
        """
        self.enemy_timer += dt
        self.junk_timer  += dt

        # Enemy spawn
        if self.enemy_timer >= diff.enemy_interval:
            self.enemy_timer = 0.0
            for _ in range(diff.simultaneous_enemies):
                self._spawn_enemy(enemies, diff)

        # Junk spawn
        if self.junk_timer >= diff.junk_interval:
            self.junk_timer = 0.0
            for _ in range(random.randint(1, diff.junk_burst)):
                x = random.randint(80, SCREEN_W - 80)
                junks.append(JunkObject(x, speed_mult=diff.junk_speed))

    def _spawn_enemy(self, enemies, diff):
        x = random.randint(50, SCREEN_W - 50)
        roll = random.random()

        if diff.level >= 4 and roll < 0.15:
            e = ExplosiveEnemy(x, -30)
        elif diff.level >= 2 and roll < 0.30:
            e = HeavyEnemy(x, -50)
        else:
            e = SmallEnemy(x, -20)

        # Apply difficulty speed multiplier
        e.SPEED = type(e).SPEED * diff.enemy_speed_mult
        enemies.append(e)


# ─────────────────────────────────────────────
#  DIFFICULTY MANAGER
# ─────────────────────────────────────────────

class DifficultyManager:
    """
    Escalates challenge over the survival timer duration.
    Call update() every frame; read parameters to tune spawning.
    """
    MAX_LEVEL = 8
    LEVEL_INTERVAL = 8.0  # seconds per difficulty level

    def __init__(self):
        self.level              = 1
        self.elapsed            = 0.0
        self.enemy_interval     = 3.5
        self.enemy_speed_mult   = 1.0
        self.simultaneous_enemies = 1
        self.junk_interval      = 2.5
        self.junk_speed         = 1.0
        self.junk_burst         = 1

    def update(self, dt):
        self.elapsed += dt
        new_level = int(self.elapsed / self.LEVEL_INTERVAL) + 1
        new_level = min(new_level, self.MAX_LEVEL)

        if new_level != self.level:
            self.level = new_level
            self._recalculate()

    def _recalculate(self):
        lvl = self.level
        self.enemy_interval       = max(0.6, 3.5  - lvl * 0.38)
        self.enemy_speed_mult     = 1.0 + lvl * 0.18
        self.simultaneous_enemies = 1 + (lvl // 3)
        self.junk_interval        = max(0.4, 2.5  - lvl * 0.25)
        self.junk_speed           = 1.0 + lvl * 0.15
        self.junk_burst           = 1 + (lvl // 4)


# ─────────────────────────────────────────────
#  SURVIVAL LEVEL  – Main Controller
# ─────────────────────────────────────────────

class SurvivalLevel:
    """
    Top-level level controller.

    Usage (standalone):
        pygame.init()
        screen = pygame.display.set_mode((960, 640))
        clock  = pygame.time.Clock()
        level  = SurvivalLevel(screen, clock)
        result = level.run()

    Usage (inside a larger game):
        result = SurvivalLevel(screen, clock).run()
        if   result == "win":  game.go_to_next_level()
        elif result == "lose": game.show_game_over()
    """

    # ── Cinematic state machine ──
    STATE_DROP      = "drop"        # player falling
    STATE_CINEMATIC = "cinematic"   # camera pans to grinder
    STATE_ACTIVATE  = "activate"    # grinder startup
    STATE_SURVIVAL  = "survival"    # main gameplay
    STATE_WIN       = "win"
    STATE_LOSE      = "lose"

    # ── Platform layout ──
    PLATFORMS = [
        pygame.Rect(180,  480, 600, 28),   # main centre platform
        pygame.Rect(40,   380, 160,  18),  # left ledge
        pygame.Rect(760,  380, 160,  18),  # right ledge
        pygame.Rect(340,  310, 140,  16),  # upper mid
        pygame.Rect(0,    620, SCREEN_W, 20),  # floor
    ]

    def __init__(self, screen: pygame.Surface, clock: pygame.time.Clock):
        self.screen = screen
        self.clock  = clock
        self.font_large  = pygame.font.SysFont("monospace", 42, bold=True)
        self.font_medium = pygame.font.SysFont("monospace", 24, bold=True)
        self.font_small  = pygame.font.SysFont("monospace", 16)

        # Entities
        self.player  = Player(SCREEN_W // 2 - 15, -60)
        self.enemies: list[Enemy]  = []
        self.junks:   list[JunkObject] = []
        self.particles: list[Particle] = []

        # Two grinders, one per side wall
        self.grinders = [
            GrinderMachine(10,   SCREEN_H - 260),
            GrinderMachine(SCREEN_W - GrinderMachine.WIDTH - 10,
                           SCREEN_H - 260),
        ]

        self.spawner    = Spawner()
        self.difficulty = DifficultyManager()
        self.shake      = ScreenShake()

        # State tracking
        self.state         = self.STATE_DROP
        self.state_timer   = 0.0
        self.survival_time = 0.0
        self.score         = 0

        # Cinematic tracking
        self.cinematic_target = None  # grinder to pan toward
        self.cam_x = 0.0
        self.cam_y = 0.0

    # ──────────────────────────
    #  MAIN LOOP
    # ──────────────────────────

    def run(self) -> str:
        """
        Blocking game loop. Returns "win", "lose", or "quit".
        """
        while True:
            dt = self.clock.tick(FPS) / 1000.0
            dt = min(dt, 0.05)   # cap delta time to avoid spiral of death

            result = self._handle_events()
            if result:
                return result

            self._update(dt)
            self._draw()
            pygame.display.flip()

            if self.state in (self.STATE_WIN, self.STATE_LOSE):
                # Show end screen for 3 seconds then return result
                self.state_timer += dt
                if self.state_timer > 3.0:
                    return self.state   # "win" or "lose"

    def _handle_events(self) -> Optional[str]:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return "quit"
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    return "quit"
        return None

    # ──────────────────────────
    #  UPDATE
    # ──────────────────────────

    def _update(self, dt: float):
        self.shake.update(dt)

        if self.state == self.STATE_DROP:
            self._update_drop(dt)
        elif self.state == self.STATE_CINEMATIC:
            self._update_cinematic(dt)
        elif self.state == self.STATE_ACTIVATE:
            self._update_activate(dt)
        elif self.state == self.STATE_SURVIVAL:
            self._update_survival(dt)

    def _update_drop(self, dt):
        """Player free-falls onto the platform."""
        self.player.vy += GRAVITY * dt
        self.player.y  += self.player.vy * dt

        for plat in self.PLATFORMS:
            if self.player.rect.colliderect(plat) and self.player.vy >= 0:
                if self.player.rect.bottom - plat.top < 28:
                    self.player.y = plat.top - self.player.HEIGHT
                    self.player.vy = 0
                    self.player.on_ground = True
                    self.shake.add(0.5)
                    spawn_particles(self.particles,
                                    self.player.x + 15,
                                    self.player.y + self.player.HEIGHT,
                                    C_PLATFORM, n=16, speed=90)
                    self.state = self.STATE_CINEMATIC
                    self.state_timer = 0.0
                    return

    def _update_cinematic(self, dt):
        """Camera slowly drifts toward a grinder, then triggers activation."""
        self.state_timer += dt

        # Drift camera toward the left grinder
        target_x = -(self.grinders[0].x - SCREEN_W // 4)
        target_y = -(self.grinders[0].y - SCREEN_H // 3)
        self.cam_x += (target_x - self.cam_x) * dt * 1.2
        self.cam_y += (target_y - self.cam_y) * dt * 1.2

        if self.state_timer > 2.2:
            # Return camera to origin
            self.cam_x += (0 - self.cam_x) * dt * 3
            self.cam_y += (0 - self.cam_y) * dt * 3

        if self.state_timer > 3.0:
            self.cam_x, self.cam_y = 0, 0
            self.state = self.STATE_ACTIVATE
            self.state_timer = 0.0

    def _update_activate(self, dt):
        """Grinders start up with a shake."""
        self.state_timer += dt

        if self.state_timer > 0.3 and not self.grinders[0].active:
            for g in self.grinders:
                g.activate()
            self.shake.add(0.9)

        for g in self.grinders:
            g.update(dt)

        if self.state_timer > 2.0:
            self.state = self.STATE_SURVIVAL
            self.state_timer = 0.0

    def _update_survival(self, dt):
        """Full gameplay loop."""
        self.survival_time += dt
        self.difficulty.update(dt)

        keys = pygame.key.get_pressed()
        self.player.handle_input(keys, dt)
        self.player.update(dt, self.PLATFORMS)

        # Check player fell off floor
        if self.player.y > SCREEN_H + 40:
            self.player.alive = False

        # Grinder update & damage
        for g in self.grinders:
            g.update(dt)
            if g.active and self.player.alive \
                    and self.player.rect.colliderect(g.danger_zone):
                self.player.take_damage(g.DAMAGE_PER_SEC * dt)
                spawn_particles(self.particles,
                                *self.player.centre, C_SPARK, n=3, speed=100)
                self.shake.add(0.05)

        # Enemy update
        for e in self.enemies:
            e.update(dt, self.PLATFORMS, self.player.x)

            # Grinder kills enemies too
            for g in self.grinders:
                if g.active and e.alive and e.rect.colliderect(g.danger_zone):
                    e.take_damage(g.DAMAGE_PER_SEC * dt)

        # Junk update
        for j in self.junks:
            j.update(dt)

        # ── Collision: Player ↔ Enemy contact ──
        atk_rect = self.player.get_attack_rect()
        for e in self.enemies:
            if not e.alive:
                continue
            if self.player.alive and \
                    self.player.rect.colliderect(e.rect):
                self.player.take_damage(e.CONTACT_DAMAGE * dt * 2)
                self.shake.add(0.15)

            # Melee attack
            if self.player.attacking and \
                    atk_rect.colliderect(e.rect):
                e.take_damage(self.player.ATTACK_DAMAGE)
                spawn_particles(self.particles, *e.centre,
                                C_ORANGE, n=8, speed=80)

        # ── Explosive enemy detonation ──
        for e in self.enemies:
            if isinstance(e, ExplosiveEnemy) and e.alive and e.fuse >= 1.0:
                e.alive = False
                self._explode(e)

        # ── Collision: Player ↔ Junk ──
        for j in self.junks:
            if not j.alive:
                continue
            if self.player.alive and \
                    self.player.rect.colliderect(j.rect):
                self.player.take_damage(j.DAMAGE)
                j.alive = False
                spawn_particles(self.particles,
                                j.x, j.y, C_JUNK, n=10, speed=70)
                self.shake.add(0.2)

        # Spawn new entities
        self.spawner.update(dt, self.enemies, self.junks, self.difficulty)

        # Collect particles
        for p in self.particles:
            p.update(dt)

        # Score dead enemies
        for e in self.enemies:
            if not e.alive:
                self.score += type(e).SCORE

        # Prune dead entities
        self.enemies   = [e for e in self.enemies   if e.alive]
        self.junks     = [j for j in self.junks     if j.alive]
        self.particles = [p for p in self.particles if p.alive()]

        # ── Win / Lose check ──
        if not self.player.alive:
            self.state       = self.STATE_LOSE
            self.state_timer = 0.0
            self.shake.add(1.0)
        elif self.survival_time >= SURVIVAL_GOAL:
            self.state       = self.STATE_WIN
            self.state_timer = 0.0

    def _explode(self, e: ExplosiveEnemy):
        """Handle explosion: area damage + visual."""
        spawn_particles(self.particles, *e.centre, C_ORANGE, n=30, speed=160)
        spawn_particles(self.particles, *e.centre, C_RED,    n=15, speed=100)
        self.shake.add(0.7)

        ex, ey = e.centre
        if self.player.alive:
            px, py = self.player.centre
            dist = math.hypot(px - ex, py - ey)
            if dist <= e.EXPLODE_RADIUS:
                falloff = 1.0 - (dist / e.EXPLODE_RADIUS)
                self.player.take_damage(e.EXPLODE_DAMAGE * falloff)

        # Chain damage to other enemies
        for other in self.enemies:
            if other is e or not other.alive:
                continue
            ox, oy = other.centre
            dist = math.hypot(ox - ex, oy - ey)
            if dist <= e.EXPLODE_RADIUS:
                other.take_damage(30)

    # ──────────────────────────
    #  DRAW
    # ──────────────────────────

    def _draw(self):
        self.screen.fill(C_BG)
        off = self.shake.offset

        # If cinematic, apply camera pan
        cam = (off[0] + self.cam_x, off[1] + self.cam_y)

        # Background grid for industrial feel
        self._draw_bg(cam)

        # Platforms
        for plat in self.PLATFORMS:
            pygame.draw.rect(self.screen, C_PLATFORM,
                             plat.move(int(cam[0]), int(cam[1])),
                             border_radius=3)
            pygame.draw.rect(self.screen, (80, 65, 40),
                             plat.move(int(cam[0]), int(cam[1])), 2,
                             border_radius=3)

        # Grinders
        for g in self.grinders:
            g.draw(self.screen, cam)

        # Junk
        for j in self.junks:
            j.draw(self.screen, cam)

        # Enemies
        for e in self.enemies:
            e.draw(self.screen, cam)

        # Particles
        for p in self.particles:
            p.draw(self.screen, cam)

        # Player
        self.player.draw(self.screen, cam)

        # HUD (no camera offset – always screen-space)
        self._draw_hud()

        # Cinematic letterbox
        if self.state in (self.STATE_DROP, self.STATE_CINEMATIC,
                          self.STATE_ACTIVATE):
            self._draw_letterbox()

        # Overlay states
        if self.state == self.STATE_CINEMATIC and self.state_timer < 2.5:
            self._draw_cinematic_text()

        if self.state == self.STATE_WIN:
            self._draw_end_screen("SURVIVED!", C_YELLOW)
        elif self.state == self.STATE_LOSE:
            self._draw_end_screen("YOU DIED", C_RED)

    def _draw_bg(self, cam):
        """Faint industrial grid background."""
        grid = 60
        for gx in range(0, SCREEN_W, grid):
            pygame.draw.line(self.screen, (28, 28, 36),
                             (gx + int(cam[0]) % grid, 0),
                             (gx + int(cam[0]) % grid, SCREEN_H))
        for gy in range(0, SCREEN_H, grid):
            pygame.draw.line(self.screen, (28, 28, 36),
                             (0, gy + int(cam[1]) % grid),
                             (SCREEN_W, gy + int(cam[1]) % grid))

    def _draw_hud(self):
        """Survival timer, health bar, score, difficulty level."""
        # Semi-transparent top bar
        hud_surf = pygame.Surface((SCREEN_W, 54), pygame.SRCALPHA)
        hud_surf.fill((0, 0, 0, 140))
        self.screen.blit(hud_surf, (0, 0))

        # Survival timer
        if self.state == self.STATE_SURVIVAL:
            remaining = max(0, SURVIVAL_GOAL - self.survival_time)
            timer_col = C_RED if remaining < 15 else C_WHITE
            timer_txt = self.font_medium.render(
                f"SURVIVE: {int(remaining):02d}s", True, timer_col)
            self.screen.blit(timer_txt, (SCREEN_W // 2 - timer_txt.get_width() // 2, 14))

        # Health bar
        bar_w = 200
        bar_x, bar_y = 14, 14
        pygame.draw.rect(self.screen, C_DARK_RED, (bar_x, bar_y, bar_w, 22),
                         border_radius=4)
        hp_w = int(bar_w * (self.player.hp / self.player.MAX_HP))
        hp_col = C_RED if self.player.hp < 30 else \
                 C_ORANGE if self.player.hp < 60 else C_PLAYER
        pygame.draw.rect(self.screen, hp_col,
                         (bar_x, bar_y, hp_w, 22), border_radius=4)
        hp_lbl = self.font_small.render(
            f"HP {self.player.hp}/{self.player.MAX_HP}", True, C_WHITE)
        self.screen.blit(hp_lbl, (bar_x + 6, bar_y + 4))

        # Score
        sc_txt = self.font_small.render(f"SCORE: {self.score}", True, C_WHITE)
        self.screen.blit(sc_txt, (SCREEN_W - sc_txt.get_width() - 14, 14))

        # Difficulty level
        dlvl = self.font_small.render(
            f"THREAT LVL {self.difficulty.level}", True, C_ORANGE)
        self.screen.blit(dlvl, (SCREEN_W - dlvl.get_width() - 14, 34))

        # Controls hint (survival phase only)
        if self.state == self.STATE_SURVIVAL:
            hint = self.font_small.render(
                "WASD/Arrows: Move   Space/W: Jump   Z/J: Attack", True, (80, 80, 90))
            self.screen.blit(hint, (SCREEN_W // 2 - hint.get_width() // 2,
                                    SCREEN_H - 22))

    def _draw_letterbox(self):
        bar_h = 48
        pygame.draw.rect(self.screen, (0, 0, 0), (0, 0, SCREEN_W, bar_h))
        pygame.draw.rect(self.screen, (0, 0, 0),
                         (0, SCREEN_H - bar_h, SCREEN_W, bar_h))

    def _draw_cinematic_text(self):
        alpha = min(1.0, self.state_timer / 0.5)
        col   = (int(220 * alpha), int(80 * alpha), int(40 * alpha))
        msg   = self.font_medium.render("THE GRINDER AWAKENS...", True, col)
        self.screen.blit(msg,
                         (SCREEN_W // 2 - msg.get_width() // 2, SCREEN_H // 2 - 12))

    def _draw_end_screen(self, message, colour):
        overlay = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 170))
        self.screen.blit(overlay, (0, 0))

        txt = self.font_large.render(message, True, colour)
        self.screen.blit(txt,
                         (SCREEN_W // 2 - txt.get_width() // 2,
                          SCREEN_H // 2 - 40))

        sub_col = C_WHITE if message == "SURVIVED!" else (180, 60, 60)
        sub_txt = self.font_medium.render(
            f"Score: {self.score}  |  Time: {int(self.survival_time)}s",
            True, sub_col)
        self.screen.blit(sub_txt,
                         (SCREEN_W // 2 - sub_txt.get_width() // 2,
                          SCREEN_H // 2 + 20))


# ─────────────────────────────────────────────
#  STANDALONE ENTRY POINT
# ─────────────────────────────────────────────

def main():
    pygame.init()
    pygame.display.set_caption("GRINDER SURVIVAL – Standalone Demo")
    screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
    clock  = pygame.time.Clock()

    # Title / start screen
    font_big = pygame.font.SysFont("monospace", 44, bold=True)
    font_med = pygame.font.SysFont("monospace", 22)
    waiting  = True
    blink    = 0.0

    while waiting:
        dt = clock.tick(FPS) / 1000.0
        blink += dt
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit(); sys.exit()
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    pygame.quit(); sys.exit()
                else:
                    waiting = False

        screen.fill((10, 10, 14))
        # Animated background lines
        for i in range(0, SCREEN_W, 60):
            pygame.draw.line(screen, (25, 25, 30), (i, 0), (i, SCREEN_H))
        for i in range(0, SCREEN_H, 60):
            pygame.draw.line(screen, (25, 25, 30), (0, i), (SCREEN_W, i))

        title = font_big.render("⚙  GRINDER SURVIVAL  ⚙", True, (220, 80, 30))
        screen.blit(title, (SCREEN_W // 2 - title.get_width() // 2, 200))

        sub = font_med.render("Survive 60 seconds in the scrap arena", True, (140, 140, 150))
        screen.blit(sub, (SCREEN_W // 2 - sub.get_width() // 2, 270))

        ctrls = [
            "WASD / Arrows – Move & Jump",
            "Z or J – Melee Attack",
            "ESC – Quit",
        ]
        for i, line in enumerate(ctrls):
            t = font_med.render(line, True, (100, 160, 100))
            screen.blit(t, (SCREEN_W // 2 - t.get_width() // 2, 340 + i * 34))

        if int(blink * 2) % 2 == 0:
            start = font_med.render("Press any key to begin", True, (200, 200, 80))
            screen.blit(start, (SCREEN_W // 2 - start.get_width() // 2, 480))

        pygame.display.flip()

    # Run the level
    level  = SurvivalLevel(screen, clock)
    result = level.run()

    # Result screen
    font_end = pygame.font.SysFont("monospace", 36, bold=True)
    font_sub = pygame.font.SysFont("monospace", 22)
    end_waiting = True
    end_blink   = 0.0

    while end_waiting:
        dt = clock.tick(FPS) / 1000.0
        end_blink += dt
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                end_waiting = False
            if event.type == pygame.KEYDOWN:
                end_waiting = False

        screen.fill((8, 8, 12))
        msg_col = (255, 220, 50) if result == "win" else (220, 50, 50)
        msg_txt = "MISSION COMPLETE" if result == "win" else \
                  "MISSION FAILED" if result == "lose" else "ABORTED"
        m = font_end.render(msg_txt, True, msg_col)
        screen.blit(m, (SCREEN_W // 2 - m.get_width() // 2, 260))

        if int(end_blink * 2) % 2 == 0:
            s = font_sub.render("Press any key to exit", True, (140, 140, 140))
            screen.blit(s, (SCREEN_W // 2 - s.get_width() // 2, 360))

        pygame.display.flip()

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()