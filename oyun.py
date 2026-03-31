"""
factory_escape.py
══════════════════════════════════════════════════════════════════════════
FRAGMENTIA Engine  ·  Level Module  v1.0
"INDUSTRIAL ESCAPE: INFINITE FACTORY"

  Standalone  →  python factory_escape.py
  Engine call →  from factory_escape import run
               →  result = run(level_idx, screen, clock, save_mgr, player_ctx)
               →  result ∈ {"completed", "died", "quit"}
══════════════════════════════════════════════════════════════════════════
"""
from __future__ import annotations

import math
import random
import sys
import pygame
from typing import List, Optional, Tuple

# ── graceful shared_player import ─────────────────────────────────────────
try:
    from shared_player import SharedPlayer as _ExtPlayer          # type: ignore
    _USE_EXT = True
except ImportError:
    _USE_EXT = False
    _ExtPlayer = None

# ══════════════════════════════════════════════════════════════════════════
# §1  CONSTANTS & COLOUR PALETTE
# ══════════════════════════════════════════════════════════════════════════
SW, SH = 1280, 720
TARGET_FPS = 60
LEVEL_SEED  = 7391           # deterministic geometry

GRAV             = 1420.0    # px/s²  gravity
TERM_VEL         = 920.0     # px/s   terminal velocity (downward)
AUTO_SCROLL_BASE =  90.0     # px/s   camera creep
CONV_PUSH        = 160.0     # px/s   conveyor belt rightward force
WORLD_W          = 12_500    # total world width (px)

PHASE_CAM_X  = (0.0, 2_100.0, 4_700.0, 7_400.0)   # cam_x thresholds
EXIT_DOOR_X  = 11_300.0

# ── Colour palette – Siberpunk Industrial ─────────────────────────────────
BG_TOP    = (  7,   5,   2);  BG_BOT    = ( 28,  14,   4)
SOOT      = ( 20,  16,  12);  D_STEEL   = ( 34,  36,  40)
STEEL     = ( 68,  74,  82);  LT_STEEL  = (110, 116, 124)
RUST      = (202,  70,   0);  RUST_DK   = (108,  34,   0)
SULFUR    = (195, 164,  10)
NEON_RED  = (255,  20,  20);  NEON_ORG  = (255, 108,   0)
NEON_YEL  = (255, 204,   6)
LASER_C   = (255,   0,  52);  DRONE_C   = ( 48, 160, 196)
DEVOUR_C  = (160,  14,   0);  WARN_C    = (255, 170,   0)
WHITE     = (255, 255, 255);  HP_C      = ( 42, 214,  72)
STAM_C    = ( 52, 134, 255);  CYAN      = (  0, 236, 206)
ALARM_C   = (200,   0,   0)

# ── Kurumsal Kimlik / Corporate Identity ──────────────────────────────────
CORP_PRIMARY   = ( 18,  90, 160)   # Şirket ana rengi – derin endüstriyel mavi
CORP_SECONDARY = (220, 140,   0)   # Vurgu rengi – altın sarısı
CORP_DARK      = (  8,  20,  40)   # Koyu arka plan
CORP_LIGHT     = (200, 215, 230)   # Açık metin / levha rengi
CORP_NAME      = "FRAGMENTIA INDUSTRIES"
CORP_SLOGAN    = "PRECISION · POWER · PROGRESS"

# ── Fabrika Bölge Tanımları / Functional Zones ────────────────────────────
# (başlangıç_x, bitiş_x, Türkçe ad, İngilizce ad, zemin rengi, aksent rengi)
FACTORY_ZONES = [
    (    0,  2100, "HAMMADDE GİRİŞİ",   "RAW MATERIALS",    ( 55, 38, 14), (200, 130,  30)),
    ( 2100,  4700, "BİRİNCİL İŞLEM",    "PRIMARY PROCESS",  ( 14, 30,  55), ( 30, 100, 200)),
    ( 4700,  7400, "MONTAJ HATTI",       "ASSEMBLY LINE",    ( 14, 50,  20), ( 30, 180,  70)),
    ( 7400, 10000, "KALİTE KONTROL",     "QUALITY CONTROL",  ( 50, 14,  50), (180,  40, 180)),
    (10000, 13000, "SEVKİYAT / ÇIKIŞ",  "DISPATCH / EXIT",  ( 50, 50,  14), (200, 200,  30)),
]

# ── Güvenlik İşaret Renkleri / Safety Colour Codes ────────────────────────
SAFE_WALK   = ( 30, 180,  50)   # Yeşil – yürüyüş yolu
FORKLIFT_Y  = (220, 190,   0)   # Sarı – forklift yolu
DANGER_RED  = (200,  30,  10)   # Kırmızı – tehlike bölgesi
SAFE_ZONE_C = ( 20, 140,  60)   # Koyu yeşil – güvenli alan köşebent
FLOOR_GRID  = ( 40,  36,  30)   # Zemin ızgara rengi

# ══════════════════════════════════════════════════════════════════════════
# §2  UTILITIES
# ══════════════════════════════════════════════════════════════════════════
def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t

def clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))

def screen_x(wx: float, cam_x: float) -> int:
    return int(wx - cam_x)

def visible(wx: float, cam_x: float, margin: float = 120.0) -> bool:
    sx = wx - cam_x
    return -margin <= sx <= SW + margin

# ══════════════════════════════════════════════════════════════════════════
# §3  PARTICLE SYSTEM  (zero-GC pool)
# ══════════════════════════════════════════════════════════════════════════
class Particle:
    __slots__ = ("wx","y","vx","vy","life","max_life","r","col","grav")

    def __init__(self):
        self.wx = self.y = self.vx = self.vy = 0.0
        self.life = self.max_life = 1.0
        self.r = 3; self.col = WHITE; self.grav = 200.0

    def reset(self, wx, y, vx, vy, life, r, col, grav=200.0):
        self.wx=wx; self.y=y; self.vx=vx; self.vy=vy
        self.life=life; self.max_life=life; self.r=r; self.col=col; self.grav=grav

    def update(self, dt: float) -> bool:
        self.vy += self.grav * dt
        self.wx += self.vx * dt
        self.y  += self.vy * dt
        self.life -= dt
        return self.life > 0.0

    def draw(self, surf: pygame.Surface, cam_x: float):
        sx = int(self.wx - cam_x)
        sy = int(self.y)
        if -16 <= sx <= SW+16 and -16 <= sy <= SH+16:
            t = max(0.0, self.life / self.max_life)
            r = max(1, int(self.r * t))
            c = (int(self.col[0]*t), int(self.col[1]*t), int(self.col[2]*t))
            pygame.draw.circle(surf, c, (sx, sy), r)


class ParticleSystem:
    CAPACITY = 800

    def __init__(self):
        self._pool   = [Particle() for _ in range(self.CAPACITY)]
        self._active: List[Particle] = []

    def emit(self, wx, y, vx, vy, life, r, col, grav=200.0):
        if self._pool:
            p = self._pool.pop()
            p.reset(wx, y, vx, vy, life, r, col, grav)
            self._active.append(p)

    def burst(self, wx, y, n, speed, life, r, col, grav=200.0):
        for _ in range(n):
            a = random.uniform(0, math.tau)
            s = random.uniform(speed*0.4, speed)
            self.emit(wx, y, math.cos(a)*s, math.sin(a)*s, life, r, col, grav)

    def sparks(self, wx, y, n=8):
        """Orange sparks burst"""
        self.burst(wx, y, n, 180, 0.7, random.randint(2,4), NEON_ORG, 350.0)

    def smoke(self, wx, y, n=4):
        """Smoke puff"""
        for _ in range(n):
            self.emit(wx + random.uniform(-12,12), y,
                      random.uniform(-20,20), random.uniform(-60,-20),
                      random.uniform(0.8,1.6), random.randint(4,8), SOOT, -30.0)

    def update(self, dt: float):
        alive, dead = [], []
        for p in self._active:
            if p.update(dt): alive.append(p)
            else: dead.append(p)
        self._active = alive
        self._pool.extend(dead)

    def draw(self, surf: pygame.Surface, cam_x: float):
        for p in self._active:
            p.draw(surf, cam_x)


# ══════════════════════════════════════════════════════════════════════════
# §4  SCREEN EFFECTS  (shake + colour flash, no allocations on update)
# ══════════════════════════════════════════════════════════════════════════
class ScreenFX:
    def __init__(self):
        self._shake_amp = 0.0;  self._shake_t   = 0.0
        self._flash_col = (0,0,0); self._flash_t = 0.0; self._flash_dur = 0.0
        self._overlay   = pygame.Surface((SW, SH), pygame.SRCALPHA)

    def shake(self, amp: float = 8.0, dur: float = 0.30):
        self._shake_amp = max(self._shake_amp, amp)
        self._shake_t   = max(self._shake_t,   dur)

    def flash(self, col, dur: float = 0.25):
        self._flash_col = col; self._flash_t = dur; self._flash_dur = dur

    def update(self, dt: float):
        if self._shake_t > 0:
            self._shake_amp = lerp(self._shake_amp, 0, dt * 8)
            self._shake_t   = max(0.0, self._shake_t - dt)
        self._flash_t = max(0.0, self._flash_t - dt)

    def get_offset(self) -> Tuple[int, int]:
        if self._shake_t <= 0: return 0, 0
        amp = self._shake_amp
        return (int(random.uniform(-amp, amp)), int(random.uniform(-amp*0.5, amp*0.5)))

    def draw_overlay(self, surf: pygame.Surface):
        if self._flash_t > 0 and self._flash_dur > 0:
            alpha = int(170 * (self._flash_t / self._flash_dur))
            self._overlay.fill((*self._flash_col, alpha))
            surf.blit(self._overlay, (0, 0))



# ══════════════════════════════════════════════════════════════════════════
# §4b  FONKSIYONEL BÖLGE YÖNETİCİSİ / Functional Zone Manager
# ══════════════════════════════════════════════════════════════════════════

def get_zone(wx: float) -> int:
    """Verilen dünya x koordinatının hangi fabrika bölgesinde olduğunu döndürür."""
    for i, (zx0, zx1, *_) in enumerate(FACTORY_ZONES):
        if zx0 <= wx < zx1:
            return i
    return len(FACTORY_ZONES) - 1


class ZoneManager:
    """
    Fabrika bölgelerini çizer:
    - Bölge zemin renkleri (epoksi zemin / industrial flooring)
    - Güvenlik zemin çizgileri (safety marking)
    - Forklift yolları
    - Bölge sınır levhaları ve corporate branding
    - İş istasyonu köşebentleri (workstation corners)
    """

    def __init__(self):
        # Kurumsal logo yüzeyleri (önceden oluştur)
        self._logo_surf = self._make_logo()
        self._zone_sep_xs: List[float] = [z[1] for z in FACTORY_ZONES[:-1]]

    @staticmethod
    def _make_logo() -> pygame.Surface:
        """Kare kurumsal logo plakası."""
        w, h = 180, 52
        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        surf.fill((*CORP_DARK, 220))
        pygame.draw.rect(surf, CORP_PRIMARY, (0, 0, w, h), 2)
        pygame.draw.rect(surf, CORP_SECONDARY, (4, 4, w-8, 4))
        pygame.draw.rect(surf, CORP_SECONDARY, (4, h-8, w-8, 4))
        try:
            f1 = pygame.font.SysFont("Consolas,monospace", 12, bold=True)
            f2 = pygame.font.SysFont("Consolas,monospace", 9)
            t1 = f1.render(CORP_NAME, True, CORP_LIGHT)
            t2 = f2.render(CORP_SLOGAN, True, CORP_SECONDARY)
            surf.blit(t1, (w//2 - t1.get_width()//2, 12))
            surf.blit(t2, (w//2 - t2.get_width()//2, 30))
        except Exception:
            pass
        return surf

    def get_current_zone_info(self, cam_x: float) -> Tuple[int, str, str, tuple]:
        """Kameranın ortasındaki bölge bilgilerini döndürür."""
        wx = cam_x + SW // 2
        z  = get_zone(wx)
        _, _, tr_name, en_name, _, accent = FACTORY_ZONES[z]
        return z, tr_name, en_name, accent

    def draw_floor(self, surf: pygame.Surface, cam_x: float, tick: float):
        """
        Zemin katmanı: bölge rengi, ızgara, güvenlik çizgileri.
        GROUND_Y = 570 referansı.
        """
        GROUND_Y = 570
        floor_h   = 30     # platform yüksekliği
        strip_y   = GROUND_Y + floor_h   # zemin alt sınırı (ekranın altı)

        # ── 1) Bölge zemin boyaları (epoksi / industrial flooring) ──────────
        for i, (zx0, zx1, *_, floor_col, accent) in enumerate(FACTORY_ZONES):
            sx0 = int(zx0 - cam_x)
            sx1 = int(zx1 - cam_x)
            if sx1 < 0 or sx0 > SW: continue
            sx0 = max(0, sx0); sx1 = min(SW, sx1)
            # Bölge zemin rengi şeridi (zemin platformunun altı)
            zone_surf = pygame.Surface((sx1 - sx0, SH - strip_y + 30), pygame.SRCALPHA)
            zone_surf.fill((*floor_col, 80))
            surf.blit(zone_surf, (sx0, strip_y - 30))

        # ── 2) Zemin ızgarası (grid / industrial flooring pattern) ───────────
        grid_off  = int(cam_x * 1.0) % 40   # parallax = 1.0 (zemin)
        for xi in range(-1, SW // 40 + 2):
            gx = xi * 40 - grid_off
            pygame.draw.line(surf, FLOOR_GRID,
                             (gx, GROUND_Y + floor_h),
                             (gx, SH), 1)
        pygame.draw.line(surf, FLOOR_GRID,
                         (0, GROUND_Y + floor_h),
                         (SW, GROUND_Y + floor_h), 1)

        # ── 3) Güvenlik yürüyüş yolu (yeşil şerit – safe walking path) ──────
        walk_y  = GROUND_Y - 4
        dash_off = int(cam_x * 1.0) % 60
        for xi in range(-1, SW // 60 + 2):
            dx = xi * 60 - dash_off
            pygame.draw.line(surf, SAFE_WALK,
                             (dx, walk_y), (dx + 30, walk_y), 2)

        # ── 4) Forklift yolu (sarı çift çizgi) – orta boşluklarda ───────────
        fork_y  = GROUND_Y - 18
        pygame.draw.line(surf, FORKLIFT_Y, (0, fork_y),   (SW, fork_y),   1)
        pygame.draw.line(surf, FORKLIFT_Y, (0, fork_y+4), (SW, fork_y+4), 1)
        # Yön okları
        arrow_off = int(cam_x * 1.0) % 120
        for xi in range(-1, SW // 120 + 2):
            ax = xi * 120 + 60 - arrow_off
            pts = [(ax-8, fork_y+2), (ax+8, fork_y+2), (ax+14, fork_y+6),
                   (ax+8, fork_y+10), (ax-8, fork_y+10)]
            if len(pts) >= 3:
                pygame.draw.polygon(surf, FORKLIFT_Y, pts, 1)

    def draw_zone_separators(self, surf: pygame.Surface, cam_x: float, tick: float):
        """Bölge geçiş levhaları ve dikey çizgiler."""
        try:
            f_big  = pygame.font.SysFont("Consolas,monospace", 13, bold=True)
            f_small = pygame.font.SysFont("Consolas,monospace", 10)
        except Exception:
            return

        for i, sep_wx in enumerate(self._zone_sep_xs):
            sx = int(sep_wx - cam_x)
            if not (-20 <= sx <= SW + 20): continue

            # Dikey bölge sınır çizgisi
            pygame.draw.line(surf, CORP_SECONDARY, (sx, 0), (sx, SH), 2)

            # Bölge isim tabelası (sol ve sağ)
            for side, zone_i in ((-1, i), (1, i+1)):
                if not (0 <= zone_i < len(FACTORY_ZONES)): continue
                _, _, tr_name, en_name, _, accent = FACTORY_ZONES[zone_i]
                tab_x = sx + side * 8 if side == 1 else sx - 200 - 8
                tab_x = max(4, min(SW - 204, tab_x))

                # Tabela arka planı
                pygame.draw.rect(surf, (*CORP_DARK, 200) if False else CORP_DARK,
                                 (tab_x, 60, 200, 42))
                pygame.draw.rect(surf, tuple(int(c*0.8) for c in accent),
                                 (tab_x, 60, 200, 42), 1)
                pygame.draw.rect(surf, accent, (tab_x, 60, 200, 3))

                t1 = f_big.render(tr_name, True, CORP_LIGHT)
                t2 = f_small.render(en_name, True, tuple(int(c*0.7) for c in accent))
                surf.blit(t1, (tab_x + 6, 65))
                surf.blit(t2, (tab_x + 6, 83))

    def draw_workstation_markers(self, surf: pygame.Surface, cam_x: float,
                                  platforms: list):
        """
        İş İstasyonu Tasarımı: yakın platformların etrafına yeşil köşebent çiz.
        Workstation corners around clustered platforms.
        """
        CORNER = 10
        for p in platforms:
            if p.conveyor: continue            # sadece sabit platformlar
            sx = screen_x(p.wx, cam_x)
            sy = int(p.wy)
            if not (-60 <= sx <= SW + 60): continue
            col = SAFE_ZONE_C
            # Sol üst köşe
            pygame.draw.line(surf, col, (sx - 4, sy - CORNER), (sx - 4, sy), 2)
            pygame.draw.line(surf, col, (sx - 4, sy - CORNER), (sx - 4 + CORNER, sy - CORNER), 2)
            # Sağ üst köşe
            pygame.draw.line(surf, col, (sx + p.w + 4, sy - CORNER), (sx + p.w + 4, sy), 2)
            pygame.draw.line(surf, col, (sx + p.w + 4 - CORNER, sy - CORNER), (sx + p.w + 4, sy - CORNER), 2)

    def draw_danger_zones(self, surf: pygame.Surface, cam_x: float,
                           crushers: list, tick: float):
        """
        Presler etrafında kırmızı uyarı taraması (hatch) ve çizgileri.
        Safety marking around crushers.
        """
        for cr in crushers:
            sx = screen_x(cr.wx - cr.W // 2 - 8, cam_x)
            if not (-cr.W - 40 <= sx <= SW + 40): continue
            zone_w = cr.W + 16
            zone_y = int(cr.target_y) - 6
            # Çapraz tarama (hatch) – tehlike bölgesi
            hatch_surf = pygame.Surface((zone_w, 20), pygame.SRCALPHA)
            pulse = 0.5 + 0.5 * math.sin(tick * 6)
            alpha = int(80 * pulse) if cr.state in ("warning", "dropping") else 40
            for xi in range(0, zone_w + 20, 8):
                pygame.draw.line(hatch_surf, (*DANGER_RED, alpha),
                                 (xi, 0), (xi - 20, 20), 2)
            surf.blit(hatch_surf, (sx, zone_y))
            # Çerçeve
            pygame.draw.rect(surf, DANGER_RED,
                             (sx, zone_y, zone_w, 20), 1)

    def draw_corp_logos(self, surf: pygame.Surface, cam_x: float):
        """
        Kurumsal kimlik: duvarlara logo yerleştir.
        Corporate identity branding on factory walls.
        """
        logo_w = self._logo_surf.get_width()
        # Her 900 px'de bir logo (parallax 0.6)
        for i in range(WORLD_W // 900 + 2):
            wx = i * 900 + 60
            sx = int(wx - cam_x * 0.6) - logo_w // 2
            if -logo_w <= sx <= SW:
                surf.blit(self._logo_surf, (sx, 120))


# ══════════════════════════════════════════════════════════════════════════
# §4c  YÜKSEK TAVAN AYDINLATMASI / High-Bay Industrial Lighting
# ══════════════════════════════════════════════════════════════════════════
class HighBayLight:
    """
    Tavandan sarkan endüstriyel aydınlatma armatürü.
    High-bay lighting fixture hanging from ceiling.
    """
    __slots__ = ("wx", "zone", "on", "_flicker_t", "_flicker_on")

    def __init__(self, wx: float):
        self.wx       = wx
        self.zone     = get_zone(wx)
        self.on       = True
        self._flicker_t  = random.uniform(4.0, 20.0)
        self._flicker_on = True

    def update(self, dt: float):
        self._flicker_t -= dt
        if self._flicker_t <= 0:
            self._flicker_on = not self._flicker_on
            self._flicker_t  = random.uniform(0.04, 0.15) if not self._flicker_on \
                               else random.uniform(5.0, 25.0)

    def draw(self, surf: pygame.Surface, cam_x: float, tick: float):
        sx = int(self.wx - cam_x)
        if not (-80 <= sx <= SW + 80): return

        _, _, _, _, _, accent = FACTORY_ZONES[self.zone]

        # Askı kablo
        pygame.draw.line(surf, D_STEEL, (sx, 14), (sx, 38), 2)

        # Armatür gövdesi
        pygame.draw.rect(surf, D_STEEL,  (sx - 24, 38, 48, 12))
        pygame.draw.rect(surf, STEEL,    (sx - 22, 39, 44, 10), 1)
        # Reflektör
        pts = [(sx - 24, 50), (sx + 24, 50), (sx + 16, 66), (sx - 16, 66)]
        pygame.draw.polygon(surf, LT_STEEL, pts)
        pygame.draw.polygon(surf, D_STEEL, pts, 1)

        # Işık konisi (flicker destekli)
        if self._flicker_on:
            cone_h    = 160
            cone_half = 80
            pulse     = 0.82 + 0.18 * math.sin(tick * 0.7 + self.wx * 0.003)
            alpha     = int(38 * pulse)
            cone_surf = pygame.Surface((cone_half * 2, cone_h), pygame.SRCALPHA)
            # İki renk: bölgeye özel aksent + sarı beyaz
            r = min(255, int(accent[0] * 0.4 + 220 * 0.6))
            g = min(255, int(accent[1] * 0.4 + 200 * 0.6))
            b = min(255, int(accent[2] * 0.2 + 160 * 0.6))
            pts_c = [(0, 0), (cone_half * 2, 0), (cone_half + cone_half//2, cone_h),
                     (cone_half - cone_half//2, cone_h)]
            pygame.draw.polygon(cone_surf, (r, g, b, alpha), pts_c)
            surf.blit(cone_surf, (sx - cone_half, 66))

            # Lamba yüzü
            pygame.draw.rect(surf, (r, g, b), (sx - 14, 50, 28, 14))
        else:
            # Yanmıyor – kırmızı ikaz göstergesi
            pygame.draw.circle(surf, (100, 0, 0), (sx, 44), 4)


# ══════════════════════════════════════════════════════════════════════════
# §4d  HVAC SİSTEMLERİ / HVAC Units
# ══════════════════════════════════════════════════════════════════════════
class HVACUnit:
    """
    Tavana monte HVAC / havalandırma ünitesi.
    Ceiling-mounted HVAC unit with animated fan and airflow particles.
    """
    __slots__ = ("wx", "wy", "W", "H", "_fan_angle", "_puff_t", "zone")

    def __init__(self, wx: float, wy: float = 28):
        self.wx   = wx
        self.wy   = wy
        self.W    = 64
        self.H    = 28
        self._fan_angle = random.uniform(0, math.tau)
        self._puff_t    = random.uniform(0.3, 1.2)
        self.zone = get_zone(wx)

    def update(self, dt: float, particles: "ParticleSystem"):
        self._fan_angle += dt * 6.0
        self._puff_t -= dt
        if self._puff_t <= 0:
            self._puff_t = random.uniform(0.4, 0.9)
            # Soğuk hava akımı partikülleri (aşağı doğru)
            for _ in range(3):
                particles.emit(
                    self.wx + random.uniform(-10, 10),
                    self.wy + self.H + 4,
                    random.uniform(-12, 12),
                    random.uniform(20, 55),
                    random.uniform(0.6, 1.2),
                    random.randint(2, 5),
                    (180, 230, 255),
                    -15.0)   # negatif yerçekimi → yavaş yükselen hava

    def draw(self, surf: pygame.Surface, cam_x: float, tick: float):
        sx = int(self.wx - cam_x)
        if not (-80 <= sx <= SW + 80): return
        sy = int(self.wy)

        # Gövde
        pygame.draw.rect(surf, D_STEEL,  (sx - self.W//2, sy, self.W, self.H))
        pygame.draw.rect(surf, STEEL,    (sx - self.W//2, sy, self.W, self.H), 1)
        # Izgara çizgileri (ön panel)
        for gi in range(4):
            gx = sx - self.W//2 + 8 + gi * 14
            pygame.draw.line(surf, LT_STEEL, (gx, sy + 4), (gx, sy + self.H - 4), 1)
        # Fan (dönen)
        for fi in range(3):
            fa = self._fan_angle + fi * (math.tau / 3)
            fx = int(sx + math.cos(fa) * 10)
            fy = int(sy + self.H//2 + math.sin(fa) * 5)
            pygame.draw.line(surf, LT_STEEL, (sx, sy + self.H//2), (fx, fy), 2)
        pygame.draw.circle(surf, RUST, (sx, sy + self.H//2), 3)
        # İkaz ışığı (yeşil – çalışıyor)
        gc = (0, 180, 80) if int(tick * 2) % 2 == 0 else (0, 80, 30)
        pygame.draw.circle(surf, gc, (sx + self.W//2 - 8, sy + 6), 3)
        # HVAC etiketi
        try:
            f = pygame.font.SysFont("Consolas", 8)
            t = f.render("HVAC", True, LT_STEEL)
            surf.blit(t, (sx - t.get_width()//2, sy + self.H + 2))
        except Exception:
            pass


# ══════════════════════════════════════════════════════════════════════════
# §4e  SANDWICH PANEL DUVAR / Wall Panelling
# ══════════════════════════════════════════════════════════════════════════
class WallPanel:
    """
    Fabrika arka duvarında sandviç panel görsel efekti.
    Sandwich panel / acoustic wall panel visual.
    """
    __slots__ = ("wx", "wy", "W", "H", "col_face", "col_edge", "is_acoustic")

    def __init__(self, wx: float, wy: float, W: int = 80, H: int = 160,
                 is_acoustic: bool = False):
        self.wx = wx; self.wy = wy
        self.W  = W;  self.H  = H
        z       = get_zone(wx)
        _, _, _, _, floor_col, accent = FACTORY_ZONES[z]
        self.col_face  = (max(20, floor_col[0]+10),
                          max(20, floor_col[1]+10),
                          max(20, floor_col[2]+10))
        self.col_edge  = (min(255, accent[0]//3),
                          min(255, accent[1]//3),
                          min(255, accent[2]//3))
        self.is_acoustic = is_acoustic

    def draw(self, surf: pygame.Surface, cam_x: float):
        sx = int(self.wx - cam_x * 0.55)   # parallax 0.55
        if not (-self.W - 10 <= sx <= SW + 10): return
        sy = int(self.wy)
        # Panel gövdesi
        pygame.draw.rect(surf, self.col_face, (sx, sy, self.W, self.H))
        pygame.draw.rect(surf, self.col_edge, (sx, sy, self.W, self.H), 1)
        # Panel birleşim çizgileri (yatay)
        for ri in range(1, self.H // 40):
            pygame.draw.line(surf, self.col_edge,
                             (sx, sy + ri * 40), (sx + self.W, sy + ri * 40), 1)
        # Cıvata noktaları
        for ry in range(0, self.H // 40 + 1):
            for cx2 in (sx + 6, sx + self.W - 6):
                cy2 = sy + ry * 40 + 4
                pygame.draw.circle(surf, LT_STEEL, (cx2, cy2), 2)
        if self.is_acoustic:
            # Akustik panel – noktalı desen (emici yüzey)
            for ry in range(6, self.H - 6, 10):
                for rcx in range(sx + 10, sx + self.W - 6, 10):
                    pygame.draw.circle(surf, tuple(max(0, c-15) for c in self.col_face),
                                       (rcx, sy + ry), 2)



# ── Arka plan dişlisi ─────────────────────────────────────────────────────
class BgGear:
    """Dönen arka plan dişlisi."""
    __slots__ = ("wx","y","radius","teeth","speed","parallax","angle","col_inner","col_outer")

    def __init__(self, wx, y, radius, teeth, speed, parallax, col_outer=None, col_inner=None):
        self.wx = wx; self.y = y
        self.radius = radius; self.teeth = teeth
        self.speed = speed; self.parallax = parallax
        self.angle = random.uniform(0, math.tau)
        self.col_outer = col_outer or D_STEEL
        self.col_inner = col_inner or STEEL

    def update(self, dt: float):
        self.angle += self.speed * dt

    def draw(self, surf: pygame.Surface, cam_x: float):
        sx = int(self.wx - cam_x * self.parallax)
        if sx + self.radius < -10 or sx - self.radius > SW + 10:
            return
        sy = int(self.y)
        r_out = self.radius
        r_in  = int(self.radius * 0.68)
        n = self.teeth
        pts = []
        for i in range(n * 2):
            a  = self.angle + i * math.pi / n
            r  = r_out if i % 2 == 0 else r_in
            pts.append((int(sx + math.cos(a) * r), int(sy + math.sin(a) * r)))
        if len(pts) >= 3:
            pygame.draw.polygon(surf, self.col_outer, pts)
            pygame.draw.polygon(surf, self.col_inner, pts, 1)
        # Göbek
        hub_r = max(3, int(self.radius * 0.22))
        pygame.draw.circle(surf, RUST_DK, (sx, sy), hub_r)
        pygame.draw.circle(surf, LT_STEEL, (sx, sy), max(1, hub_r - 2), 1)
        # Spoke'lar
        for i in range(4):
            a = self.angle + i * math.pi / 2
            ex = int(sx + math.cos(a) * r_in * 0.85)
            ey = int(sy + math.sin(a) * r_in * 0.85)
            pygame.draw.line(surf, self.col_inner, (sx, sy), (ex, ey), 1)


# ── Arka plan ürünü ───────────────────────────────────────────────────────
class BgProduct:
    """Konveyör bandı üzerinde hareket eden arka plan ürünü."""
    __slots__ = ("wx","y","speed","parallax","shape","w","h","active","color","crushed","crush_t")
    SHAPES = ("box", "cylinder", "crate", "barrel")

    def __init__(self, wx, y, speed, parallax, shape=None):
        self.wx = wx; self.y = y
        self.speed = speed; self.parallax = parallax
        self.shape = shape or random.choice(self.SHAPES)
        self.w = {"box":16,"cylinder":14,"crate":20,"barrel":14}[self.shape]
        self.h = {"box":14,"cylinder":18,"crate":18,"barrel":20}[self.shape]
        self.active = True
        self.color = random.choice([RUST, SULFUR, (80,100,80), LT_STEEL])
        self.crushed = False
        self.crush_t  = 0.0

    def crush(self):
        self.crushed = True; self.crush_t = 0.0

    def update(self, dt: float):
        if not self.crushed:
            self.wx += self.speed * dt
        else:
            self.crush_t += dt
        if self.wx > WORLD_W + 300 or self.crush_t > 2.5:
            self.active = False

    def draw(self, surf: pygame.Surface, cam_x: float):
        sx = int(self.wx - cam_x * self.parallax)
        if not (-60 <= sx <= SW + 60):
            return
        sy = int(self.y)
        if self.crushed:
            # Ezilmiş: yassı elips
            t = min(1.0, self.crush_t * 4)
            eh = max(2, int(self.h * (1.0 - t * 0.7)))
            ew = self.w + int(self.w * t * 0.8)
            col = (min(255, self.color[0]+40), max(0,self.color[1]-20), 0)
            pygame.draw.ellipse(surf, col, (sx - ew//2, sy - eh, ew, eh))
            # Sıvı sıçrama efekti
            for _ in range(2):
                ox = random.randint(-ew, ew)
                pygame.draw.circle(surf, col, (sx + ox, sy - eh//2), random.randint(1,3))
            return
        if self.shape == "box":
            pygame.draw.rect(surf, self.color, (sx, sy - self.h, self.w, self.h))
            pygame.draw.rect(surf, tuple(max(0,c-40) for c in self.color),
                             (sx, sy - self.h, self.w, self.h), 1)
            # Haç çizgisi (kutu kapağı)
            pygame.draw.line(surf, tuple(max(0,c-60) for c in self.color),
                             (sx, sy - self.h//2), (sx + self.w, sy - self.h//2), 1)
        elif self.shape == "cylinder":
            pygame.draw.rect(surf, self.color, (sx, sy - self.h + 4, self.w, self.h - 4))
            pygame.draw.ellipse(surf, tuple(min(255,c+30) for c in self.color),
                                (sx, sy - self.h, self.w, 8))
            pygame.draw.ellipse(surf, tuple(max(0,c-20) for c in self.color),
                                (sx, sy - 8, self.w, 8))
        elif self.shape == "crate":
            pygame.draw.rect(surf, self.color, (sx, sy - self.h, self.w, self.h))
            for cx2 in range(sx, sx+self.w, 6):
                pygame.draw.line(surf, tuple(max(0,c-50) for c in self.color),
                                 (cx2, sy-self.h), (cx2, sy), 1)
            pygame.draw.rect(surf, tuple(max(0,c-40) for c in self.color),
                             (sx, sy-self.h, self.w, self.h), 1)
        elif self.shape == "barrel":
            pygame.draw.rect(surf, self.color, (sx+2, sy-self.h+4, self.w-4, self.h-8))
            pygame.draw.ellipse(surf, tuple(min(255,c+20) for c in self.color),
                                (sx, sy-self.h, self.w, 8))
            pygame.draw.ellipse(surf, tuple(max(0,c-20) for c in self.color),
                                (sx, sy-12, self.w, 8))
            for bp in (sy-self.h//3, sy-2*self.h//3):
                pygame.draw.line(surf, tuple(max(0,c-60) for c in self.color),
                                 (sx, bp), (sx+self.w, bp), 1)


# ── Arka plan pres makinası ───────────────────────────────────────────────
class BgPress:
    """Konveyör üstünde ürünleri ezen arka plan pres makinası."""
    __slots__ = ("wx","y_surf","parallax","W","H","press_y",
                 "state","t","period","_spawn_prd")

    def __init__(self, wx: float, y_surf: float, parallax: float):
        self.wx = wx; self.y_surf = y_surf
        self.parallax = parallax
        self.W = 58; self.H = 36
        self.press_y = y_surf - 90
        self.state = "up"
        self.t = 0.0
        self.period = random.uniform(2.2, 4.5)
        self._spawn_prd = False

    def update(self, dt: float) -> bool:
        """True döndürürse o karede ürün ezildi."""
        self.t += dt
        crushed = False
        if self.state == "up":
            if self.t >= self.period - 0.7:
                self.state = "warn"; self.t = 0.0
        elif self.state == "warn":
            if self.t >= 0.7:
                self.state = "drop"; self.t = 0.0
        elif self.state == "drop":
            target = self.y_surf - self.H
            self.press_y = min(target, self.press_y + 650 * dt)
            if self.press_y >= target:
                self.press_y = target
                self.state = "hold"; self.t = 0.0; crushed = True
        elif self.state == "hold":
            if self.t >= 0.28:
                self.state = "retract"; self.t = 0.0
        elif self.state == "retract":
            retracted = self.y_surf - 90
            self.press_y = max(retracted, self.press_y - 320 * dt)
            if self.press_y <= retracted:
                self.press_y = retracted
                self.state = "up"; self.t = 0.0
        return crushed

    def is_active_zone_x(self) -> Tuple[float, float]:
        return (self.wx - self.W//2, self.wx + self.W//2)

    def draw(self, surf: pygame.Surface, cam_x: float, tick: float):
        sx = int(self.wx - cam_x * self.parallax)
        if not (-120 <= sx <= SW + 120):
            return
        sy_surf = int(self.y_surf)

        # Uyarı ışıkları (warn durumunda)
        if self.state == "warn":
            wa = 0.5 + 0.5 * math.sin(tick * 20)
            wc = (int(255*wa), int(80*wa), 0)
            pygame.draw.rect(surf, wc, (sx - self.W//2, sy_surf - self.H - 6, self.W, 4))

        # Piston kolu
        rod_top = sy_surf - 110
        rod_bot = int(self.press_y)
        if rod_bot > rod_top:
            pygame.draw.rect(surf, STEEL, (sx - 7, rod_top, 14, rod_bot - rod_top))
            pygame.draw.rect(surf, D_STEEL, (sx - 5, rod_top, 10, rod_bot - rod_top))

        # Pres gövdesi
        py = int(self.press_y)
        pygame.draw.rect(surf, RUST_DK, (sx - self.W//2, py, self.W, self.H))
        pygame.draw.rect(surf, RUST,    (sx - self.W//2 + 3, py + 3, self.W - 6, self.H - 6))
        # Çizgiler
        for i in range(3):
            cl = WARN_C if i % 2 == 0 else NEON_RED
            pygame.draw.rect(surf, cl, (sx - self.W//2, py + i*(self.H//3), self.W, self.H//3 - 1))
        # Alt dişler
        tw = 9
        for i in range(self.W // tw):
            tx = sx - self.W//2 + i * tw
            pty = py + self.H
            pts = [(tx, pty), (tx + tw//2, pty+11), (tx + tw, pty)]
            pygame.draw.polygon(surf, D_STEEL, pts)

        # Hold/ezme ışığı
        if self.state in ("hold", "drop"):
            for r2 in (self.W//2 + 3, self.W//2):
                gs = pygame.Surface((r2*2, r2*2), pygame.SRCALPHA)
                pygame.draw.ellipse(gs, (*NEON_RED, 45), (0,0,r2*2,r2*2))
                surf.blit(gs, (sx - r2, py + self.H//2 - r2))
            # Ezilmiş ürün kalıntısı
            pygame.draw.ellipse(surf, NEON_ORG,
                (sx - self.W//2 + 6, sy_surf - 5, self.W - 12, 5))


# ── Arka plan dönüşüm makinası ────────────────────────────────────────────
class BgMachine:
    """Ürünü alıp farklı bir ürün çıkaran dönüşüm makinası."""
    __slots__ = ("wx","y","parallax","W","H","anim_t","out_t","out_period",
                 "_gear_angle","_belt_offset")

    def __init__(self, wx: float, y: float, parallax: float):
        self.wx = wx; self.y = y
        self.parallax = parallax
        self.W = 90; self.H = 70
        self.anim_t = random.uniform(0, math.tau)
        self.out_t = random.uniform(0, 3.0)
        self.out_period = random.uniform(2.5, 5.0)
        self._gear_angle = random.uniform(0, math.tau)
        self._belt_offset = 0.0

    def update(self, dt: float, tick: float = 0.0) -> bool:
        """True döndürürse çıkış ürünü üretildi."""
        self.anim_t += dt * 3.0
        self._gear_angle += dt * 2.2
        self._belt_offset = (self._belt_offset + dt * 40) % 16
        self.out_t += dt
        if self.out_t >= self.out_period:
            self.out_t = 0.0
            return True
        return False

    def draw(self, surf: pygame.Surface, cam_x: float, tick: float):
        sx = int(self.wx - cam_x * self.parallax)
        if not (-150 <= sx <= SW + 150):
            return
        sy = int(self.y)

        # Gövde
        pygame.draw.rect(surf, D_STEEL,  (sx, sy - self.H, self.W, self.H))
        pygame.draw.rect(surf, STEEL,    (sx + 4, sy - self.H + 4, self.W-8, self.H-8))
        pygame.draw.rect(surf, LT_STEEL, (sx, sy - self.H, self.W, self.H), 1)

        # Üst dişli çark (büyük)
        gcx = sx + self.W//2
        gcy = sy - self.H + 18
        r = 13
        n = 10
        pts = []
        for i in range(n*2):
            a = self._gear_angle + i * math.pi / n
            r2 = r if i%2==0 else int(r*0.7)
            pts.append((int(gcx + math.cos(a)*r2), int(gcy + math.sin(a)*r2)))
        if pts: pygame.draw.polygon(surf, RUST, pts)
        pygame.draw.circle(surf, D_STEEL, (gcx, gcy), 4)

        # Yanda küçük dişliler
        for (ox, sign) in ((-22, 1), (22, -1)):
            r3 = 7; n3 = 6
            pts2 = []
            for i in range(n3*2):
                a = self._gear_angle * sign + i * math.pi / n3
                r4 = r3 if i%2==0 else int(r3*0.65)
                pts2.append((int(gcx+ox + math.cos(a)*r4), int(gcy + math.sin(a)*r4)))
            if pts2: pygame.draw.polygon(surf, RUST_DK, pts2)

        # Giriş hunisi (sol)
        pygame.draw.polygon(surf, STEEL, [
            (sx-22, sy-self.H+16), (sx, sy-self.H+28),
            (sx, sy-self.H+38),    (sx-22, sy-self.H+26)
        ])
        pygame.draw.line(surf, LT_STEEL, (sx-22, sy-self.H+16), (sx-22, sy-self.H+26), 1)

        # Çıkış kanalı (sağ)
        pygame.draw.polygon(surf, SULFUR, [
            (sx+self.W, sy-self.H+28),   (sx+self.W+22, sy-self.H+18),
            (sx+self.W+22, sy-self.H+28), (sx+self.W, sy-self.H+38)
        ])
        pygame.draw.line(surf, (180,140,0), (sx+self.W+22, sy-self.H+18), (sx+self.W+22, sy-self.H+28), 1)

        # İç konveyör bandı animasyonu
        band_y = sy - self.H//2
        for bx in range(sx+6, sx+self.W-6, 16):
            bx2 = int(bx + self._belt_offset) % (self.W - 12) + sx + 6
            pygame.draw.line(surf, D_STEEL, (bx2, band_y-3), (bx2, band_y+3), 2)

        # Aktif ışık göstergesi
        pulse = 0.5 + 0.5 * math.sin(tick * 4 + self.wx * 0.01)
        gc = (0, int(140*pulse + 60), 0)
        pygame.draw.circle(surf, gc, (sx + self.W - 9, sy - self.H + 9), 5)
        pygame.draw.circle(surf, (220,220,220), (sx + self.W - 9, sy - self.H + 9), 2)

        # Duman bacası etkisi (makinadan yukarı çıkan ısı dalgası)
        for i in range(2):
            ht = tick * 1.5 + i * 1.1
            hx = sx + 10 + i*20 + int(math.sin(ht)*4)
            hy = sy - self.H - int((ht % 1.0) * 30)
            col_h = (int(30 + 20*math.sin(ht)), int(20+10*math.sin(ht)), 10)
            pygame.draw.circle(surf, col_h, (hx, hy), 3)


# ── Duman bulutu ──────────────────────────────────────────────────────────
class BgSmokePuff:
    """Baca veya makinadan çıkan duman bulutu."""
    __slots__ = ("wx","y","vx","vy","life","max_life","r","parallax")

    def __init__(self, wx, y, parallax):
        self.wx = wx; self.y = y
        self.vx = random.uniform(-8, 8)
        self.vy = random.uniform(-25, -10)
        self.life = random.uniform(1.5, 3.5)
        self.max_life = self.life
        self.r = random.randint(6, 16)
        self.parallax = parallax

    def update(self, dt):
        self.wx += self.vx * dt
        self.y  += self.vy * dt
        self.vy *= 0.97
        self.r = min(self.r + int(dt * 4), 28)
        self.life -= dt
        return self.life > 0

    def draw(self, surf, cam_x):
        sx = int(self.wx - cam_x * self.parallax)
        if not (-60 <= sx <= SW+60): return
        t = max(0.0, self.life / self.max_life)
        alpha = int(60 * t)
        gs = pygame.Surface((self.r*2, self.r*2), pygame.SRCALPHA)
        c = int(lerp(20, 50, 1.0-t))
        pygame.draw.circle(gs, (c, c, c, alpha), (self.r, self.r), self.r)
        surf.blit(gs, (sx - self.r, int(self.y) - self.r))


# ── Ana Background sınıfı ────────────────────────────────────────────────
class Background:
    """
    ══════════════════════════════════════════════════════════
    ENDÜSTRIYEL DÜZEN  /  Industrial Layout  (Lean Line Flow)
    ══════════════════════════════════════════════════════════
    Gerçek fabrika tasarım prensiplerine dayalı arka plan:

    1. YAPISAL BAY SISTEMI  — 140 px aralıklı kolon/kiriş ızgarası
       (Gerçek hayat karşılığı: 10–12 m montaj hattı bay aralığı)

    2. OVERHEAD CRANE RAYLI — Ağır ekipman için tavan köprü vinci kirişi

    3. BÖLGEYE ÖZEL BORU HATLARI — Her bölgenin renk kodlu fayda boruları
       (Sarı=basınçlı hava, Kırmızı=hidrolik, Mavi=soğutma suyu,
        Yeşil=temiz hava, Kahverengi=hammadde)

    4. KABLO TEPSİLERİ — Rastgele sarkan kablo yerine düzenli tray sistemi

    5. RAFLI DEPOLAMA — Her bölge girişinde/çıkışında palet rafları

    6. BÖLGE MAKİNELERİ — Her bölgeye özel ekipman tipi:
       Z0=Besleyici/Hopper, Z1=CNC/Torna, Z2=Montaj Hücresi,
       Z3=Muayene Tezgahı, Z4=Paketleme/Sevkiyat

    7. ANA KONVEYÖR HATTI — Tam uzunluklu sürekli konveyör
       (Hammaddeden sevkiyata kesintisiz akış)

    8. İKİNCİL KONVEYÖR — Ara katman malzeme besleme hattı

    9. ARAÇ YOLU — Forklift / AGV için zemin takip hattı
    ══════════════════════════════════════════════════════════
    """

    # ── Bölgeye göre boru renk kodları ───────────────────────────────────
    # (zone_idx → [(pipe_color, pipe_y_offset, pipe_label)])
    ZONE_PIPES = [
        # Zone 0: Hammadde — Kahverengi boru (bulk malzeme taşıma)
        [((100, 60, 20), 80,  "BULK"),  ((60, 40, 10), 96, "")],
        # Zone 1: Birincil İşlem — Kırmızı (yüksek basınç hidrolik)
        [((160, 20, 20), 80,  "HYD"),   ((80, 10, 10), 96, "")],
        # Zone 2: Montaj — Mavi (pnömatik alet besleme)
        [((20, 80, 160), 80,  "AIR"),   ((10, 40, 80), 96, "")],
        # Zone 3: Kalite Kontrol — Yeşil (temiz basınçlı hava)
        [((20, 120, 40), 80,  "CLEAN"), ((10, 60, 20), 96, "")],
        # Zone 4: Sevkiyat — Sarı (paketleme yardımcı)
        [((160, 140, 0), 80,  "PKG"),   ((80, 70, 0), 96, "")],
    ]

    # ── Bay aralığı (endüstriyel kolon ızgarası) ─────────────────────────
    BAY_W = 140    # px  (~10m ölçek)

    def __init__(self):
        rng = random.Random(LEVEL_SEED + 1)

        # ── Uzak sanayi binası cephesi (parallax 0.10) ────────────────────
        # Düzenli pencere+çatı profili — tek büyük endüstriyel bina bloğu
        self._far_building_h = 200
        self._far_window_cols = WORLD_W // 40   # her 40px'de bir pencere sütunu

        # ── Bölge başlarında baca/silo (sadece bölge geçişlerinde) ─────────
        self._chimneys: List[Tuple[float, float, float]] = []
        for z_idx, (zx0, zx1, *_) in enumerate(FACTORY_ZONES):
            # Bölge başında: silo
            h = 180 + z_idx * 20
            w = 28 + z_idx * 4
            self._chimneys.append((zx0 + 120, h, w))
            # Bölge ortasında: egzoz bacası
            mid = (zx0 + zx1) / 2
            self._chimneys.append((mid, 120 + z_idx*10, 18))

        # ── Yapısal kolon pozisyonları (bay ızgarası) ─────────────────────
        self._columns: List[float] = list(range(0, WORLD_W + self.BAY_W, self.BAY_W))

        # ── Overhead crane rayı kirişi (parallax 0.38) ────────────────────
        # Ağır imalat bölgeleri için — Z1 ve Z2'de (x: 2100–7400)
        self._crane_rail_zones = [(2100, 7400)]

        # ── Bölgeye özel arka plan makineleri ────────────────────────────
        self._machines: List[BgMachine] = []
        zone_machine_step = {
            0: 520,   # Hammadde: seyrek besleyici
            1: 380,   # Birincil işlem: sık CNC
            2: 320,   # Montaj: çok sık hücre
            3: 450,   # Kalite: orta sıklık muayene
            4: 500,   # Sevkiyat: paketleme
        }
        for z_idx, (zx0, zx1, *_) in enumerate(FACTORY_ZONES):
            step = zone_machine_step.get(z_idx, 420)
            mx = zx0 + 200.0
            while mx < zx1 - 200:
                my = SH - 82     # ana hat yüksekliği
                self._machines.append(BgMachine(mx, my, 0.52))
                mx += step + rng.uniform(-40, 40)

        # ── Dişliler — sadece makine yakınında, düzenli aralıkta ──────────
        # (rastgele değil, makine başına 1-2 dişli)
        self._mid_gears: List[BgGear] = []
        for mach in self._machines:
            # Her makinenin üstüne bir dişli çifti
            for offset in (-38, 38):
                r  = rng.randint(16, 36)
                nt = rng.choice([8, 10, 12])
                spd = 1.2 * (1 if offset > 0 else -1)
                gy  = mach.y - mach.H - r - 4
                co  = D_STEEL if rng.random() > 0.3 else RUST_DK
                ci  = STEEL   if co == D_STEEL else RUST
                self._mid_gears.append(
                    BgGear(mach.wx + offset, gy, r, nt, spd, 0.52, co, ci))

        # Birbirine temas eden dişli çiftleri (gerçekçi mekanizma)
        self._far_gears: List[BgGear] = []
        gx_f = 300.0
        while gx_f < WORLD_W:
            r1 = rng.randint(30, 60)
            r2 = rng.randint(20, 40)
            nt1 = rng.choice([12, 16, 20])
            nt2 = rng.choice([8, 10, 12])
            gy_f = rng.choice([SH * 0.35, SH * 0.50, SH * 0.60])
            spd1 = 0.4 * rng.choice([-1, 1])
            # İkinci dişli ters döner (gerçekçi)
            spd2 = -spd1 * (r1 / r2)
            self._far_gears.append(
                BgGear(gx_f,      gy_f, r1, nt1, spd1, 0.18, D_STEEL, STEEL))
            self._far_gears.append(
                BgGear(gx_f + r1 + r2, gy_f, r2, nt2, spd2, 0.18, RUST_DK, RUST))
            gx_f += rng.uniform(600, 1200)   # her 600–1200px'de bir mekanizma

        # ── Ana Konveyör Hattı (hammaddeden sevkiyata tam uzunluk) ─────────
        # Bölge başlarında kısa kesintiler (bölge geçiş kapıları)
        self._bg_conveyors: List[Tuple[float,float,float,float,float]] = []
        conv_y_main = SH - 82      # Ana hat: zemin seviyesi
        conv_y_feed = SH - 162     # İkincil besleme hattı
        self._prod_rng = random.Random(LEVEL_SEED + 77)

        for z_idx, (zx0, zx1, *_) in enumerate(FACTORY_ZONES):
            seg_len = (zx1 - zx0) - 60    # bölge geçiş boşluğu: 60px
            # Ana konveyör segmenti
            self._bg_conveyors.append(
                (conv_y_main, zx0 + 30, seg_len, 75.0, 0.52))
            # İkincil besleme hattı (biraz daha yavaş)
            if z_idx < 4:
                feed_len = seg_len * 0.6
                self._bg_conveyors.append(
                    (conv_y_feed, zx0 + 30 + seg_len * 0.2, feed_len, 55.0, 0.52))

        # ── Arka plan pres makinaları (Z0 ve Z1 bölgelerinde) ─────────────
        self._presses: List[BgPress] = []
        for z_idx in (0, 1):
            zx0, zx1 = FACTORY_ZONES[z_idx][:2]
            px2 = zx0 + 400.0
            while px2 < zx1 - 300:
                self._presses.append(BgPress(px2, conv_y_main, 0.52))
                px2 += rng.uniform(900, 1600)

        # ── Hareketli ürünler ─────────────────────────────────────────────
        self._products: List[BgProduct] = []
        self._prod_spawn_t: List[float] = []
        for (by, bx2, blen, bspd, bpar) in self._bg_conveyors:
            self._prod_spawn_t.append(self._prod_rng.uniform(0.3, 2.5))
            ox = bx2
            while ox < bx2 + blen - 30:
                p = BgProduct(ox, by, bspd * 0.9, bpar)
                self._products.append(p)
                ox += self._prod_rng.uniform(40, 90)

        # ── Rafli depolama (palet raf) — bölge girişleri ve çıkışlarında ──
        # (wx, wy, n_shelf, n_col, zone_idx)
        self._storage_racks: List[Tuple[float, float, int, int, int]] = []
        for z_idx, (zx0, zx1, *_) in enumerate(FACTORY_ZONES):
            # Bölge girişi: girdi deposu
            self._storage_racks.append((zx0 + 60, SH - 240, 3, 4, z_idx))
            # Bölge çıkışı: WIP (ara stok) deposu
            if z_idx < 4:
                self._storage_racks.append((zx1 - 280, SH - 200, 2, 4, z_idx))

        # ── Düzenli kablo tepsisi (kablo trayı — rastgele değil) ─────────
        # Yatay tray: parallax 0.38, sabit yükseklik
        self._cable_tray_y = 108   # tavandan aşağı
        # Tray üzerindeki kablo sayısı bölgeye göre değişir

        # ── Duman bulutları ───────────────────────────────────────────────
        self._smoke: List[BgSmokePuff] = []
        self._smoke_t = 0.0

        # ── Kıvılcımlar (sadece makine çalışma noktaları) ─────────────────
        self._sparks: List[Tuple[float,float,float,float,float]] = []
        self._spark_t = 0.0

        # ── Konveyör animasyon ─────────────────────────────────────────────
        self._belt_anim = 0.0

    # ── Güncelleme ─────────────────────────────────────────────────────────
    def update(self, dt: float, tick: float, cam_x: float):
        for g in self._far_gears: g.update(dt)
        for g in self._mid_gears:  g.update(dt)

        for p in self._products: p.update(dt)
        self._products = [p for p in self._products if p.active]

        for i, (by, bx2, blen, bspd, bpar) in enumerate(self._bg_conveyors):
            self._prod_spawn_t[i] -= dt
            if self._prod_spawn_t[i] <= 0:
                sx_rel = bx2 - cam_x * bpar
                if sx_rel < SW + 200:
                    p = BgProduct(bx2, by, bspd * 0.9, bpar)
                    self._products.append(p)
                self._prod_spawn_t[i] = self._prod_rng.uniform(1.2, 3.5)

        for press in self._presses:
            crushed = press.update(dt)
            if crushed:
                px_lo, px_hi = press.is_active_zone_x()
                for p in self._products:
                    if not p.crushed and abs(p.y - press.y_surf) < 20:
                        if px_lo <= p.wx <= px_hi:
                            p.crush()

        for mach in self._machines:
            emit = mach.update(dt, tick)
            if emit:
                p = BgProduct(mach.wx + mach.W + 24, mach.y, 70, mach.parallax,
                              random.choice(["box","cylinder","crate","barrel"]))
                self._products.append(p)

        # Duman — sadece bölge bacalarından
        self._smoke_t -= dt
        if self._smoke_t <= 0:
            self._smoke_t = random.uniform(0.4, 1.2)
            for (cwx, ch, cw2) in self._chimneys:
                if abs(cwx - cam_x * 0.12 - SW//2) < SW:
                    self._smoke.append(BgSmokePuff(cwx + cw2/2, SH - ch - 20, 0.12))
            for mach in self._machines:
                sx_rel = mach.wx - cam_x * mach.parallax
                if -200 <= sx_rel <= SW + 200 and random.random() < 0.3:
                    self._smoke.append(BgSmokePuff(mach.wx + 10, mach.y - mach.H - 5, mach.parallax))
        self._smoke = [s for s in self._smoke if s.update(dt)]

        # Kıvılcımlar — sadece birbirine temas eden dişliler
        self._spark_t -= dt
        if self._spark_t <= 0:
            self._spark_t = random.uniform(0.2, 0.6)
            for i in range(0, len(self._far_gears) - 1, 2):
                g1 = self._far_gears[i]
                g2 = self._far_gears[i+1]
                sx1 = g1.wx - cam_x * g1.parallax
                if not (0 <= sx1 <= SW): continue
                dist = math.hypot(g1.wx - g2.wx, g1.y - g2.y)
                gap  = dist - g1.radius - g2.radius
                if abs(gap) < 8:
                    mx2 = (g1.wx + g2.wx) / 2
                    my2 = (g1.y  + g2.y ) / 2
                    for _ in range(4):
                        a = random.uniform(0, math.tau)
                        spd2 = random.uniform(40, 100)
                        self._sparks.append((mx2, my2,
                                            math.cos(a)*spd2, math.sin(a)*spd2,
                                            random.uniform(0.2, 0.5)))

        new_sparks = []
        for (swx, sy2, svx, svy, slife) in self._sparks:
            nlife = slife - dt
            if nlife > 0:
                new_sparks.append((swx + svx*dt, sy2 + svy*dt, svx, svy, nlife))
        self._sparks = new_sparks

        self._belt_anim = (self._belt_anim + dt * 55) % 18

    # ── Çizim ─────────────────────────────────────────────────────────────
    def draw(self, surf: pygame.Surface, cam_x: float, tick: float):

        # ═══════════════════════════════════════════════════════════
        # KATMAN 1 — DEGRADE ARKA PLAN (karanlık sanayi gökyüzü)
        # ═══════════════════════════════════════════════════════════
        step = SH // 8
        for i in range(8):
            t = i / 7.0
            c = (int(lerp(BG_TOP[0], BG_BOT[0], t)),
                 int(lerp(BG_TOP[1], BG_BOT[1], t)),
                 int(lerp(BG_TOP[2], BG_BOT[2], t)))
            pygame.draw.rect(surf, c, (0, i*step, SW, step+2))

        # ═══════════════════════════════════════════════════════════
        # KATMAN 2 — UZAK BİNA CAMPESİ  (parallax 0.10)
        # Düzenli çatı profili + pencere ızgarası
        # ═══════════════════════════════════════════════════════════
        bh = self._far_building_h
        bx_off = int(-cam_x * 0.10)
        # Bina ana gövdesi
        pygame.draw.rect(surf, (12, 9, 7),
                         (0, SH - bh - 10, SW, bh + 10))
        # Çatı dişlisi (sawtooth roofline — fabrika çatısı)
        for ci in range(0, SW + 40, 40):
            bx_c = ci + bx_off % 40
            pts = [(bx_c, SH - bh - 10),
                   (bx_c + 20, SH - bh - 24),
                   (bx_c + 40, SH - bh - 10)]
            if len(pts) == 3:
                pygame.draw.polygon(surf, (16, 12, 9), pts)
        # Düzenli pencere ızgarası
        col_pitch = 40
        row_pitch = 28
        col_off   = bx_off % col_pitch
        for ri in range(bh // row_pitch):
            wy2 = SH - bh + 10 + ri * row_pitch
            for ci2 in range(-1, SW // col_pitch + 2):
                wx2 = ci2 * col_pitch + col_off
                # Pencerenin yanıp yanmadığı
                flicker = 0.5 + 0.5 * math.sin(
                    tick * 0.9 + (ci2 * 0.37 + ri * 0.19) * 3.1)
                lit = ((ci2 * 3 + ri * 7 + int(cam_x * 0.001)) % 5 != 0)
                if lit:
                    wc = (int(55 * flicker), int(38 * flicker), 0)
                    pygame.draw.rect(surf, wc, (wx2 + 4, wy2 + 4, 14, 12))
                else:
                    pygame.draw.rect(surf, (8, 7, 6),  (wx2 + 4, wy2 + 4, 14, 12))

        # ═══════════════════════════════════════════════════════════
        # KATMAN 3 — BACA / SİLO SİLÜETLERİ  (parallax 0.12)
        # ═══════════════════════════════════════════════════════════
        for (cwx, ch, cw2) in self._chimneys:
            csx = int(cwx - cam_x * 0.12)
            if not (-80 <= csx <= SW + 80): continue
            # Gövde (silindirik baca)
            body_y = int(SH - ch - 14)
            pygame.draw.rect(surf, (16, 11, 8),
                             (csx - int(cw2//2), body_y, int(cw2), int(ch)+14))
            # Çember halkaları
            for ri in range(0, int(ch), 35):
                pygame.draw.ellipse(surf, (22, 16, 10),
                                    (csx - int(cw2//2) - 2, body_y + ri, int(cw2)+4, 8))
            # Ağız (toroidal ring)
            pygame.draw.ellipse(surf, (28, 20, 12),
                                (csx - int(cw2//2) - 4, body_y - 6, int(cw2)+8, 12))
            # Kızıl kor ağzı
            pulse_c = 0.6 + 0.4 * math.sin(tick * 1.5 + cwx * 0.007)
            rc = (int(50*pulse_c), int(22*pulse_c), 0)
            pygame.draw.circle(surf, rc,
                               (csx, body_y), int(cw2//2 - 2))

        # ═══════════════════════════════════════════════════════════
        # KATMAN 4 — UZAK DİŞLİ MEKANİZMALARI  (parallax 0.18)
        # Birbirine temas eden çiftler halinde (gerçekçi mekanizma)
        # ═══════════════════════════════════════════════════════════
        for g in self._far_gears:
            sx = int(g.wx - cam_x * g.parallax)
            if -g.radius - 10 <= sx <= SW + g.radius + 10:
                g.draw(surf, cam_x)

        # ═══════════════════════════════════════════════════════════
        # KATMAN 5 — YAPISAL KOLONLAR  (parallax 0.38)
        # Bay ızgarası — fabrika iskelet sistemi
        # ═══════════════════════════════════════════════════════════
        for col_wx in self._columns:
            sx = int(col_wx - cam_x * 0.38)
            if not (-20 <= sx <= SW + 20): continue
            # Kolon gövdesi (I-profil)
            pygame.draw.rect(surf, (22, 20, 18), (sx - 6, 14, 12, SH - 40))
            pygame.draw.rect(surf, (34, 30, 26), (sx - 4, 14, 8, SH - 40))
            pygame.draw.rect(surf, D_STEEL, (sx - 2, 14, 4, SH - 40))
            # Taban plakası
            pygame.draw.rect(surf, (30, 28, 24), (sx - 10, SH - 44, 20, 8))
            # Kolon başlığı (tavan bağlantısı)
            pygame.draw.rect(surf, (30, 28, 24), (sx - 10, 14, 20, 8))
            # Çapraz destekler (çerçeve) — her iki bayda bir
            bay_i = round(col_wx / self.BAY_W)
            if bay_i % 2 == 0:
                next_wx = col_wx + self.BAY_W
                nsx = int(next_wx - cam_x * 0.38)
                # X-brace
                pygame.draw.line(surf, (28, 25, 22),
                                 (sx, SH//3), (nsx, SH * 2//3), 1)
                pygame.draw.line(surf, (28, 25, 22),
                                 (nsx, SH//3), (sx, SH * 2//3), 1)

        # ═══════════════════════════════════════════════════════════
        # KATMAN 6 — OVERHEAD CRANE RAYLI (parallax 0.38)
        # Ağır imalat bölgesi (Z1–Z2) tavan köprü vinci
        # ═══════════════════════════════════════════════════════════
        crane_y = 28
        for (cx0, cx1) in self._crane_rail_zones:
            sx0 = int(cx0 - cam_x * 0.38)
            sx1 = int(cx1 - cam_x * 0.38)
            if sx1 < -20 or sx0 > SW + 20: continue
            sx0c = max(-20, sx0); sx1c = min(SW+20, sx1)
            # Ray profili (I-kesit)
            pygame.draw.rect(surf, (40, 36, 32),
                             (sx0c, crane_y, sx1c - sx0c, 12))
            pygame.draw.rect(surf, STEEL,
                             (sx0c, crane_y + 4, sx1c - sx0c, 4))
            # Ray bağlantı askıları — her kolona
            for col_wx in self._columns:
                if cx0 <= col_wx <= cx1:
                    csx2 = int(col_wx - cam_x * 0.38)
                    if sx0c <= csx2 <= sx1c:
                        pygame.draw.rect(surf, D_STEEL,
                                         (csx2 - 3, 0, 6, crane_y))

        # ═══════════════════════════════════════════════════════════
        # KATMAN 7 — KABLO TEPSİSİ  (parallax 0.38)
        # Düzenli yatay kablo trayı — her bölgede kendi renk paketi
        # ═══════════════════════════════════════════════════════════
        tray_y = self._cable_tray_y
        # Tray gövdesi (tam uzunluk)
        tray_sx0 = int(0 - cam_x * 0.38)
        tray_sx1 = int(WORLD_W - cam_x * 0.38)
        pygame.draw.rect(surf, (32, 28, 24),
                         (max(0, tray_sx0), tray_y, min(SW, tray_sx1 - tray_sx0), 14))
        pygame.draw.rect(surf, (44, 40, 36),
                         (max(0, tray_sx0), tray_y + 2, min(SW, tray_sx1 - tray_sx0), 2))
        # Tray destek pabuçları — kolonlara monte
        for col_wx in self._columns:
            tsx = int(col_wx - cam_x * 0.38)
            if 0 <= tsx <= SW:
                pygame.draw.rect(surf, STEEL, (tsx - 8, tray_y - 4, 16, 4))
        # Bölgeye göre renk kodlu kablo çizgileri (tray içinde)
        for z_idx, (zx0, zx1, *_) in enumerate(FACTORY_ZONES):
            pipe_defs = self.ZONE_PIPES[z_idx]
            for k, (pcol, _, _) in enumerate(pipe_defs):
                wsxz0 = int(zx0 - cam_x * 0.38)
                wsxz1 = int(zx1 - cam_x * 0.38)
                if wsxz1 < 0 or wsxz0 > SW: continue
                cx0c = max(0, wsxz0); cx1c = min(SW, wsxz1)
                if cx1c > cx0c:
                    pygame.draw.line(surf, pcol,
                                     (cx0c, tray_y + 5 + k * 3),
                                     (cx1c, tray_y + 5 + k * 3), 2)

        # ═══════════════════════════════════════════════════════════
        # KATMAN 8 — BÖLGEYE ÖZEL BORU HATLARI  (parallax 0.35)
        # Her bölgenin renk kodlu fayda boruları
        # ═══════════════════════════════════════════════════════════
        for z_idx, (zx0, zx1, *_) in enumerate(FACTORY_ZONES):
            pipe_defs = self.ZONE_PIPES[z_idx]
            for (pcol, pipe_y_off, label) in pipe_defs:
                py = pipe_y_off
                psxz0 = int(zx0 - cam_x * 0.35)
                psxz1 = int(zx1 - cam_x * 0.35)
                if psxz1 < -10 or psxz0 > SW + 10: continue
                px0 = max(-10, psxz0); px1 = min(SW + 10, psxz1)
                # Boru dış yüzey
                pygame.draw.line(surf, tuple(max(0, c//3) for c in pcol),
                                 (px0, py), (px1, py), 9)
                # Boru orta çizgi
                pygame.draw.line(surf, pcol, (px0, py), (px1, py), 5)
                # Boru iç parlaklık
                pygame.draw.line(surf, tuple(min(255, c + 40) for c in pcol),
                                 (px0, py), (px1, py), 2)
                # Flanş halkalar (kolonlara denk gelir)
                for col_wx in self._columns:
                    if zx0 <= col_wx <= zx1:
                        fsx = int(col_wx - cam_x * 0.35)
                        if 0 <= fsx <= SW:
                            pygame.draw.rect(surf, STEEL, (fsx - 3, py - 5, 6, 10))
                # Boru etiketi (bölge girişinde)
                if label and abs(psxz0 - 0) < 600 and px0 > 0:
                    try:
                        f_lbl = pygame.font.SysFont("Consolas", 8)
                        t_lbl = f_lbl.render(label, True, pcol)
                        surf.blit(t_lbl, (px0 + 4, py - 8))
                    except Exception:
                        pass
                # Dikey düşümler (boru + kolonların kesişiminde)
                for col_wx in self._columns:
                    if not (zx0 < col_wx < zx1): continue
                    if int(col_wx / self.BAY_W) % 3 != z_idx % 3: continue
                    vsx = int(col_wx - cam_x * 0.35)
                    if not (0 <= vsx <= SW): continue
                    pygame.draw.line(surf, tuple(max(0, c//2) for c in pcol),
                                     (vsx, py), (vsx, py + 60), 4)
                    pygame.draw.line(surf, pcol,
                                     (vsx, py), (vsx, py + 60), 2)
                    # Vana
                    pygame.draw.rect(surf, LT_STEEL,
                                     (vsx - 5, py + 24, 10, 10))
                    pygame.draw.circle(surf, STEEL, (vsx, py + 29), 3)

        # ═══════════════════════════════════════════════════════════
        # KATMAN 9 — RAFLİ DEPOLAMA  (parallax 0.52)
        # Bölge girişlerinde ve çıkışlarında palet rafları
        # ═══════════════════════════════════════════════════════════
        for (rwx, rwy, n_shelf, n_col, z_idx) in self._storage_racks:
            rsx = int(rwx - cam_x * 0.52)
            if not (-200 <= rsx <= SW + 60): continue
            _, _, _, _, _, z_accent = FACTORY_ZONES[z_idx]
            col_w = 22
            shelf_h = 30
            total_w  = n_col * col_w
            total_h  = n_shelf * shelf_h

            # Raf ana gövdesi
            pygame.draw.rect(surf, (24, 20, 16),
                             (rsx, int(rwy), total_w, total_h))
            # Dikey kolonlar
            for ci in range(n_col + 1):
                cx3 = rsx + ci * col_w
                pygame.draw.rect(surf, D_STEEL, (cx3 - 1, int(rwy), 3, total_h))
            # Yatay raflar
            for ri in range(n_shelf + 1):
                ry3 = int(rwy) + ri * shelf_h
                pygame.draw.rect(surf, STEEL, (rsx, ry3, total_w, 2))
            # Raf içerik (ürün kutuları)
            for ri in range(n_shelf):
                for ci in range(n_col):
                    cx3 = rsx + ci * col_w + 3
                    ry3 = int(rwy) + ri * shelf_h + 5
                    box_h = shelf_h - 10
                    col3 = tuple(min(255, int(c * 0.5 + 40)) for c in z_accent)
                    pygame.draw.rect(surf, col3, (cx3, ry3, col_w - 6, box_h))
            # Zemin palet tabanı
            pygame.draw.rect(surf, (34, 28, 20),
                             (rsx - 4, int(rwy) + total_h, total_w + 8, 8))

        # ═══════════════════════════════════════════════════════════
        # KATMAN 10 — MAKINE DİŞLİLERİ  (parallax 0.52, yakın plan)
        # ═══════════════════════════════════════════════════════════
        for g in self._mid_gears:
            sx = int(g.wx - cam_x * g.parallax)
            if -g.radius - 10 <= sx <= SW + g.radius + 10:
                g.draw(surf, cam_x)

        # ═══════════════════════════════════════════════════════════
        # KATMAN 11 — ANA KONVEYÖR & İKİNCİL BESLEME HATLARI  (par.0.52)
        # ═══════════════════════════════════════════════════════════
        ba = int(self._belt_anim)
        for seg_idx, (by, bx2, blen, bspd, bpar) in enumerate(self._bg_conveyors):
            sx0 = int(bx2       - cam_x * bpar)
            sx1 = int(bx2 + blen - cam_x * bpar)
            if sx1 < -10 or sx0 > SW + 10: continue
            sy2 = int(by)
            is_main = (by == int(SH - 82))

            # Bant yüzeyi — ana hat daha kalın
            belt_h = 12 if is_main else 8
            pygame.draw.rect(surf, (28, 24, 20), (sx0, sy2, sx1 - sx0, belt_h))

            # Bant çizgileri
            top_c = NEON_ORG if is_main else (80, 140, 80)
            pygame.draw.line(surf, top_c, (sx0, sy2), (sx1, sy2), 2 if is_main else 1)
            pygame.draw.line(surf, (38, 34, 28),
                             (sx0, sy2 + belt_h - 1), (sx1, sy2 + belt_h - 1), 1)

            # Bölücü çizgiler (hareketli)
            for bxi in range((sx0 - ba) % 18 + sx0, sx1, 18):
                pygame.draw.line(surf, (48, 43, 36),
                                 (bxi, sy2 + 2), (bxi, sy2 + belt_h - 2), 1)

            # Kasnaklar (bölge sınırlarına denk gelir)
            for ex in (sx0, sx1):
                r_k = 7 if is_main else 5
                pygame.draw.circle(surf, D_STEEL, (ex, sy2 + belt_h//2), r_k)
                pygame.draw.circle(surf, STEEL,   (ex, sy2 + belt_h//2), r_k - 3)

            # Ana hat altında destek kiriş
            if is_main:
                pygame.draw.rect(surf, (20, 18, 14),
                                 (sx0, sy2 + belt_h, sx1 - sx0, 6))

        # ═══════════════════════════════════════════════════════════
        # KATMAN 12 — ARKA PLAN PRESLER  (par.0.52)
        # ═══════════════════════════════════════════════════════════
        for press in self._presses:
            press.draw(surf, cam_x, tick)

        # ═══════════════════════════════════════════════════════════
        # KATMAN 13 — ARKA PLAN MAKİNELERİ  (par.0.52)
        # ═══════════════════════════════════════════════════════════
        for mach in self._machines:
            mach.draw(surf, cam_x, tick)

        # ═══════════════════════════════════════════════════════════
        # KATMAN 14 — HAREKETLİ ÜRÜNLER  (par.0.52)
        # ═══════════════════════════════════════════════════════════
        for p in self._products:
            p.draw(surf, cam_x)

        # ═══════════════════════════════════════════════════════════
        # KATMAN 15 — DIŞLİ KIVILCIMLARI
        # ═══════════════════════════════════════════════════════════
        for (swx, sy2, svx, svy, slife) in self._sparks:
            sx2 = int(swx - cam_x * 0.18)
            if 0 <= sx2 <= SW:
                t = max(0.0, slife / 0.5)
                col_s = (int(255*t), int(180*t*t), 0)
                pygame.draw.circle(surf, col_s, (sx2, int(sy2)),
                                   max(1, int(2*t)))

        # ═══════════════════════════════════════════════════════════
        # KATMAN 16 — DUMAN BULUTLARI
        # ═══════════════════════════════════════════════════════════
        for s in self._smoke:
            s.draw(surf, cam_x)

        # ═══════════════════════════════════════════════════════════
        # KATMAN 17 — ALT LAV PARILTISI
        # ═══════════════════════════════════════════════════════════
        glow_surf = pygame.Surface((SW, 90), pygame.SRCALPHA)
        pulse2 = 0.85 + 0.15 * math.sin(tick * 1.8)
        glow_surf.fill((int(80*pulse2), int(18*pulse2), 0, 55))
        surf.blit(glow_surf, (0, SH - 90))


# ══════════════════════════════════════════════════════════════════════════
# §6  MOCK PLAYER  (standalone fallback, replaces shared_player)
# ══════════════════════════════════════════════════════════════════════════
class MockPlayer:
    W, H = 28, 46

    # Physics tunables
    WALK_SPEED   = 230.0
    JUMP_VY      = -620.0
    DJUMP_VY     = -540.0
    DASH_SPEED   = 460.0
    DASH_DUR     = 0.16
    DASH_CD      = 1.25
    DASH_CHARGES = 3
    SLAM_VY      = 940.0
    ATK_RANGE    = 64.0
    ATK_CD       = 0.45
    INV_DUR      = 1.40

    def __init__(self, wx: float, wy: float):
        self.wx = wx;  self.wy = wy
        self.vx = 0.0; self.vy = 0.0
        self.on_ground   = False
        self.jumps_left  = 2
        self.facing      = 1           # 1=right, -1=left
        self.hp          = 3           # lives
        self.inv_t       = 0.0
        self.dash_cd     = 0.0
        self.dash_t      = 0.0
        self.dash_charges= self.DASH_CHARGES
        self.is_dashing  = False
        self.is_slamming = False
        self.slam_ready  = False       # can slam right now
        self.atk_t       = 0.0
        self.is_attacking= False
        self.atk_dur     = 0.18
        self.tick        = 0.0
        self.dead        = False
        # afterimage ring-buffer for dash trail
        self._trail: List[Tuple[float,float,float]] = []

    # ── rect helpers ──────────────────────────────────────────────────────
    @property
    def rect(self) -> pygame.Rect:
        return pygame.Rect(int(self.wx), int(self.wy), self.W, self.H)

    @property
    def cx(self): return self.wx + self.W / 2
    @property
    def cy(self): return self.wy + self.H / 2
    @property
    def feet_y(self): return self.wy + self.H

    # ── public interface (mirrors SharedPlayer API) ────────────────────────
    def take_damage(self, source: str = "env"):
        if self.inv_t > 0: return False
        self.hp -= 1
        self.inv_t = self.INV_DUR
        self.vx = -self.facing * 180
        self.vy = -240.0
        return True

    def is_alive(self): return self.hp > 0

    # ── input → intent (call from main loop with pygame key state) ────────
    def handle_input(self, keys):
        # Horizontal
        move = 0
        if keys[pygame.K_LEFT]  or keys[pygame.K_a]: move = -1
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]: move =  1
        if move != 0: self.facing = move

        # Jump
        if (keys[pygame.K_SPACE] or keys[pygame.K_UP] or keys[pygame.K_w]):
            self._try_jump()

        # Dash
        if keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT]:
            self._try_dash()

        # Slam
        if (keys[pygame.K_DOWN] or keys[pygame.K_s]) and not self.on_ground:
            self._try_slam()

        # Attack
        if keys[pygame.K_z] or keys[pygame.K_LCTRL]:
            self._try_attack()

        return move

    def _try_jump(self):
        if self.jumps_left > 0 and not self._jump_held:
            vy = self.JUMP_VY if self.jumps_left == 2 else self.DJUMP_VY
            self.vy = vy
            self.jumps_left -= 1
            self.on_ground = False
            self._jump_held = True

    def _try_dash(self):
        if not hasattr(self, "_dash_held"): self._dash_held = False
        if self._dash_held: return
        if self.dash_cd <= 0 and self.dash_charges > 0 and not self.is_dashing:
            self.is_dashing = True
            self.dash_t     = self.DASH_DUR
            self.dash_cd    = self.DASH_CD
            self.dash_charges -= 1
            self.vy = min(self.vy, 0)      # cancel downward momentum
            self._dash_held = True
            self._trail.clear()

    def _try_slam(self):
        if not self.is_slamming and self.slam_ready and not self.on_ground:
            self.is_slamming = True
            self.vy = self.SLAM_VY
            self.slam_ready = False

    def _try_attack(self):
        if not hasattr(self, "_atk_held"): self._atk_held = False
        if self._atk_held: return
        if self.atk_t <= 0:
            self.is_attacking = True
            self.atk_t = self.atk_dur
            self._atk_held = True

    # ── physics + collision update ─────────────────────────────────────────
    def update(self, dt: float, platforms: list, conv_speed_mult: float = 1.0):
        if not hasattr(self, "_jump_held"): self._jump_held = False
        if not hasattr(self, "_dash_held"): self._dash_held = False
        if not hasattr(self, "_atk_held"):  self._atk_held  = False

        self.tick += dt

        # Timers
        self.inv_t = max(0.0, self.inv_t - dt)
        self.dash_cd = max(0.0, self.dash_cd - dt)
        if self.dash_t > 0:
            self.dash_t = max(0.0, self.dash_t - dt)
            if self.dash_t <= 0:
                self.is_dashing = False
        if self.atk_t > 0:
            self.atk_t -= dt
            if self.atk_t <= 0: self.is_attacking = False
        if not self.is_dashing and self.dash_cd <= 0:
            self.dash_charges = min(self.DASH_CHARGES,
                                    self.dash_charges + dt / self.DASH_CD)

        # Reset jump/dash/atk held flags when keys released
        keys = pygame.key.get_pressed()
        if not (keys[pygame.K_SPACE] or keys[pygame.K_UP] or keys[pygame.K_w]):
            self._jump_held = False
        if not (keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT]):
            self._dash_held = False
        if not (keys[pygame.K_z] or keys[pygame.K_LCTRL]):
            self._atk_held = False

        # Read movement intent
        move = 0
        if keys[pygame.K_LEFT]  or keys[pygame.K_a]: move = -1
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]: move =  1
        if move: self.facing = move

        # Jump / slam / dash
        if keys[pygame.K_SPACE] or keys[pygame.K_UP] or keys[pygame.K_w]:
            self._try_jump()
        if keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT]:
            self._try_dash()
        if (keys[pygame.K_DOWN] or keys[pygame.K_s]) and not self.on_ground:
            self.slam_ready = True
            self._try_slam()
        else:
            if not self.is_slamming: self.slam_ready = True
        if keys[pygame.K_z] or keys[pygame.K_LCTRL]:
            self._try_attack()

        # Horizontal velocity
        if self.is_dashing:
            self.vx = self.facing * self.DASH_SPEED
            self._trail.append((self.wx, self.wy, self.tick))
            if len(self._trail) > 6: self._trail.pop(0)
        else:
            target_vx = move * self.WALK_SPEED
            accel = 1800.0 if self.on_ground else 900.0
            if move == 0: accel *= 2.5
            self.vx = lerp(self.vx, target_vx, min(1.0, accel * dt / self.WALK_SPEED))
            if not self.is_dashing and abs(self.vx) < 6: self.vx = 0.0

        # Gravity
        if not self.is_dashing:
            self.vy = min(self.vy + GRAV * dt, TERM_VEL)

        # Move & collide
        self.on_ground = False
        prev_wy = self.wy

        # Horizontal
        self.wx += self.vx * dt
        # Vertical
        self.wy += self.vy * dt

        # Platform collision
        conv_push_x = 0.0
        for plat in platforms:
            if not visible(plat.wx, 0, SW + plat.w): continue
            pr = plat.rect
            pr_top = plat.wy; pr_bot = plat.wy + plat.h
            pr_lft = plat.wx; pr_rgt = plat.wx + plat.w

            # Horizontal overlap check
            if not (self.wx + self.W > pr_lft and self.wx < pr_rgt): continue

            # Land on top
            if prev_wy + self.H <= pr_top + 4 and self.wy + self.H >= pr_top and self.vy >= 0:
                self.wy = pr_top - self.H
                self.vy = 0.0
                self.on_ground = True
                self.jumps_left = 2
                self.is_slamming = False
                self.slam_ready  = True
                if plat.conveyor:
                    spd = plat.conv_speed * conv_speed_mult
                    conv_push_x += plat.conv_dir * spd

            # Hit ceiling
            elif self.wy <= pr_bot and (prev_wy >= pr_bot - 4) and self.vy < 0:
                self.wy = pr_bot
                self.vy = 0.0

        # Apply conveyor
        if conv_push_x != 0:
            self.wx += conv_push_x * dt

        # Regen dash charges on ground
        if self.on_ground and not self.is_dashing:
            self.dash_charges = self.DASH_CHARGES

    def get_attack_rect(self) -> Optional[pygame.Rect]:
        if not self.is_attacking: return None
        off = self.facing * (self.W // 2 + 8)
        return pygame.Rect(int(self.cx + off - self.ATK_RANGE//2),
                           int(self.cy - 16), int(self.ATK_RANGE), 32)

    def draw(self, surf: pygame.Surface, cam_x: float):
        sx = screen_x(self.wx, cam_x)
        sy = int(self.wy)
        inv_flash = (self.inv_t > 0) and (int(self.tick * 12) % 2 == 0)
        if inv_flash: return

        # Dash trail afterimages
        for i, (twx, twy, _) in enumerate(self._trail):
            alpha_t = (i+1) / max(1, len(self._trail))
            tsx = screen_x(twx, cam_x)
            c = (int(DRONE_C[0]*alpha_t*0.5), int(DRONE_C[1]*alpha_t*0.5), int(DRONE_C[2]*alpha_t*0.5))
            pygame.draw.rect(surf, c, (tsx, int(twy), self.W, self.H), 1)

        # Slam glow
        if self.is_slamming:
            for r in (28, 20, 12):
                alpha_surf = pygame.Surface((r*2, r*2), pygame.SRCALPHA)
                pygame.draw.ellipse(alpha_surf, (*NEON_ORG, 60), (0, 0, r*2, r*2))
                surf.blit(alpha_surf, (sx + self.W//2 - r, sy + self.H - r//2))

        # Attack arc
        if self.is_attacking:
            ar = self.get_attack_rect()
            if ar:
                asx = ar.x - int(cam_x)
                glow = pygame.Surface((ar.width, ar.height), pygame.SRCALPHA)
                glow.fill((*SULFUR, 90))
                surf.blit(glow, (asx, ar.y))
                pygame.draw.rect(surf, SULFUR, (asx, ar.y, ar.width, ar.height), 1)

        # Body
        body_c = D_STEEL if not self.is_dashing else DRONE_C
        pygame.draw.rect(surf, body_c, (sx, sy+14, self.W, self.H-14))
        # Chest stripe
        pygame.draw.rect(surf, RUST, (sx+4, sy+20, self.W-8, 6))
        # Helmet
        pygame.draw.rect(surf, STEEL, (sx+1, sy+2, self.W-2, 16))
        # Visor
        visor_c = CYAN if not self.is_slamming else NEON_ORG
        pygame.draw.rect(surf, visor_c, (sx+3, sy+7, self.W-6, 6))
        # Visor glow
        pygame.draw.rect(surf, WHITE, (sx+5, sy+8, 4, 4))
        # Legs
        pygame.draw.rect(surf, RUST_DK, (sx+2, sy+self.H-10, 10, 10))
        pygame.draw.rect(surf, RUST_DK, (sx+self.W-12, sy+self.H-10, 10, 10))

        # Directional exhaust during dash
        if self.is_dashing:
            ex = sx - 6 * self.facing
            ey = sy + self.H // 2
            for i in range(3):
                r = 4 - i
                cx2 = ex - self.facing * i * 6
                pygame.draw.circle(surf, NEON_ORG if i==0 else RUST, (cx2, ey), r)


# ══════════════════════════════════════════════════════════════════════════
# §7  PLATFORM  (static + conveyor belt)
# ══════════════════════════════════════════════════════════════════════════
class Platform:
    def __init__(self, wx: float, wy: float, w: int, h: int = 24,
                 conveyor: bool = False, conv_dir: int = 1,
                 conv_speed: float = CONV_PUSH):
        self.wx = wx; self.wy = wy
        self.w = w;   self.h = h
        self.conveyor  = conveyor
        self.conv_dir  = conv_dir
        self.conv_speed = conv_speed

    @property
    def rect(self) -> pygame.Rect:
        return pygame.Rect(int(self.wx), int(self.wy), self.w, self.h)

    def draw(self, surf: pygame.Surface, cam_x: float, tick: float):
        sx = screen_x(self.wx, cam_x)
        if sx + self.w < -20 or sx > SW + 20: return
        r = pygame.Rect(sx, int(self.wy), self.w, self.h)

        # Base platform
        pygame.draw.rect(surf, D_STEEL, r)
        # Inner shadow
        if self.h > 12:
            pygame.draw.rect(surf, SOOT, (r.x+2, r.y+4, r.w-4, r.h-6))

        if self.conveyor:
            # Animated diagonal stripe pattern
            stripe_period = 32
            anim = int(tick * self.conv_speed * self.conv_dir * 0.3) % stripe_period
            surf.set_clip(r)
            for i in range(-2, self.w // stripe_period + 3):
                bx = sx + i * stripe_period + anim
                pts = [(bx,      int(self.wy)),
                       (bx+16,   int(self.wy)),
                       (bx+16-8, int(self.wy)+self.h),
                       (bx-8,    int(self.wy)+self.h)]
                pygame.draw.polygon(surf, (55, 50, 38), pts)
            surf.set_clip(None)
            # Direction arrow every 60px
            arrows = self.w // 60
            for i in range(arrows):
                ax = sx + 30 + i * 60
                ay = int(self.wy) + self.h // 2
                dw = 8 * self.conv_dir
                pygame.draw.polygon(surf, SULFUR,
                    [(ax, ay-3), (ax+dw, ay), (ax, ay+3)])
            # Glowing top edge
            pygame.draw.line(surf, NEON_ORG, (sx, int(self.wy)), (sx+self.w, int(self.wy)), 2)
        else:
            # Steel top edge
            pygame.draw.line(surf, LT_STEEL, (sx, int(self.wy)), (sx+self.w, int(self.wy)), 2)

        # Side rivets
        for i in range(0, self.h, 12):
            pygame.draw.circle(surf, STEEL, (sx+4, int(self.wy)+i+4), 2)
            pygame.draw.circle(surf, STEEL, (sx+self.w-4, int(self.wy)+i+4), 2)


# ══════════════════════════════════════════════════════════════════════════
# §8  CRUSHER  (pneumatic press, Phase 1+)
# ══════════════════════════════════════════════════════════════════════════
class Crusher:
    W = 90
    WARN_DUR  = 0.80
    HOLD_DUR  = 0.25
    RETRACT_DELAY = 0.60
    SPEED_DN  = 720.0
    SPEED_UP  = 320.0
    CEILING_Y = 0.0

    def __init__(self, wx: float, target_y: float, period: float,
                 phase_offset: float = 0.0, chaotic: bool = False):
        self.wx      = wx
        self.target_y = target_y
        self.period  = period
        self.offset  = phase_offset
        self.chaotic = chaotic
        self.cy_pos  = -self.CEILING_Y  # current y of crusher bottom
        self.state   = "waiting"  # waiting → warning → dropping → holding → retracting
        self.t       = phase_offset % period
        self._set_next()

    def _set_next(self):
        if self.chaotic:
            self.period = random.uniform(1.4, 3.8)
        self.t = 0.0

    @property
    def body_rect_world(self):
        H = 55
        return pygame.Rect(int(self.wx - self.W//2), int(self.cy_pos - H), self.W, H)

    def update(self, dt: float, chaotic: bool = False) -> bool:
        """Returns True if crusher bottom is in danger zone (crushing)."""
        if chaotic: self.chaotic = True
        self.t += dt
        crushing = False

        if self.state == "waiting":
            if self.t >= self.period - self.WARN_DUR:
                self.state = "warning"
                self.t = 0.0

        elif self.state == "warning":
            self.cy_pos = 0.0   # stays at ceiling
            if self.t >= self.WARN_DUR:
                self.state = "dropping"
                self.t = 0.0

        elif self.state == "dropping":
            self.cy_pos = min(self.target_y, self.cy_pos + self.SPEED_DN * dt)
            crushing = True
            if self.cy_pos >= self.target_y:
                self.cy_pos = self.target_y
                self.state  = "holding"
                self.t = 0.0

        elif self.state == "holding":
            crushing = True
            if self.t >= self.HOLD_DUR:
                self.state = "retracting"
                self.t = 0.0

        elif self.state == "retracting":
            self.cy_pos = max(-60.0, self.cy_pos - self.SPEED_UP * dt)
            if self.cy_pos <= -55.0:
                self.cy_pos = -55.0
                self.state = "waiting"
                self._set_next()

        return crushing

    def get_danger_rect(self) -> pygame.Rect:
        """Rect of the impact zone while dropping/holding."""
        br = self.body_rect_world
        return pygame.Rect(br.x + 4, br.bottom, br.w - 8, 16)

    def draw(self, surf: pygame.Surface, cam_x: float, tick: float):
        sx = screen_x(self.wx - self.W//2, cam_x)
        if sx + self.W < -20 or sx > SW + 20: return
        H = 55
        cy = int(self.cy_pos)
        body_y = cy - H

        # Shadow / warning indicator on ground
        if self.state in ("warning", "dropping"):
            warn_alpha = 0.5 + 0.5 * math.sin(tick * 14)
            for i, col in enumerate([(180, 0, 0), NEON_RED, WARN_C]):
                w2 = self.W - i*8
                x2 = sx + i*4
                y2 = int(self.target_y) - 4 + i*2
                pygame.draw.rect(surf, tuple(int(c*warn_alpha) for c in col),
                                 (x2, y2, w2, 4))

        # Piston rod from ceiling
        rod_x = sx + self.W // 2 - 6
        pygame.draw.rect(surf, STEEL, (rod_x, 0, 12, max(0, body_y + H//2)))

        # Body
        pygame.draw.rect(surf, RUST_DK, (sx, body_y, self.W, H))
        pygame.draw.rect(surf, RUST,    (sx+4, body_y+4, self.W-8, H-8))
        # Hazard stripes
        for i in range(4):
            col = WARN_C if i % 2 == 0 else NEON_RED
            pygame.draw.rect(surf, col, (sx, body_y + i*(H//4), self.W, H//4), 0
                             if i % 2 == 0 else 0)
            pygame.draw.rect(surf, col, (sx+6, body_y + i*(H//4)+2, self.W-12, H//4-4))

        # Serrated bottom teeth
        tooth_w = 12
        for i in range(self.W // tooth_w):
            tx = sx + i * tooth_w
            ty = cy
            pts = [(tx, ty), (tx + tooth_w//2, ty + 14), (tx + tooth_w, ty)]
            pygame.draw.polygon(surf, D_STEEL, pts)

        # Glow when holding/crushing
        if self.state in ("holding", "dropping"):
            for r in (self.W//2+4, self.W//2):
                glow = pygame.Surface((r*2, r*2), pygame.SRCALPHA)
                pygame.draw.ellipse(glow, (*NEON_RED, 50), (0, 0, r*2, r*2))
                surf.blit(glow, (sx + self.W//2 - r, cy - r//2))


# ══════════════════════════════════════════════════════════════════════════
# §9  BULLET  (object-pool reusable)
# ══════════════════════════════════════════════════════════════════════════
class Bullet:
    W, H = 8, 4
    SPEED = 340.0
    LIFE  = 3.5   # seconds until auto-expire

    def __init__(self):
        self.wx = 0.0; self.wy = 0.0
        self.dir = 1; self.active = False; self.t = 0.0

    def fire(self, wx, wy, direction: int):
        self.wx = wx; self.wy = wy
        self.dir = direction; self.active = True; self.t = 0.0

    def update(self, dt: float) -> bool:
        if not self.active: return False
        self.wx += self.dir * self.SPEED * dt
        self.t  += dt
        if self.t >= self.LIFE or self.wx < 0 or self.wx > WORLD_W:
            self.active = False
        return self.active

    @property
    def rect(self) -> pygame.Rect:
        return pygame.Rect(int(self.wx), int(self.wy - self.H//2), self.W, self.H)

    def draw(self, surf: pygame.Surface, cam_x: float):
        if not self.active: return
        sx = screen_x(self.wx, cam_x)
        if not (0 <= sx <= SW): return
        sy = int(self.wy)
        pygame.draw.rect(surf, DRONE_C, (sx-self.W//2, sy-self.H//2, self.W, self.H))
        pygame.draw.circle(surf, CYAN, (sx, sy), 3)


# ══════════════════════════════════════════════════════════════════════════
# §10 FACTORY DRONE  (object pool, Phase 2)
# ══════════════════════════════════════════════════════════════════════════
class FactoryDrone:
    W, H     = 36, 22
    SPEED    = 145.0
    FIRE_CD  = 2.2
    HP       = 2
    FLOAT_AMP = 14.0
    FLOAT_SPD = 2.4

    def __init__(self):
        self.wx = 0.0; self.wy = 0.0
        self.base_wy = 0.0
        self.dir = -1          # -1 = moves left
        self.fire_t = 0.0
        self.tick = 0.0
        self.hp = self.HP
        self.active = False

    def spawn(self, wx: float, wy: float, dir: int = -1):
        self.wx = wx; self.wy = wy; self.base_wy = wy
        self.dir = dir; self.hp = self.HP
        self.active = True; self.tick = random.uniform(0, math.tau)
        self.fire_t = random.uniform(0.5, self.FIRE_CD)

    def update(self, dt: float, player_cx: float, player_cy: float,
               bullets: list) -> bool:
        if not self.active: return False
        self.tick += dt
        self.fire_t -= dt

        # Patrol + approach
        dx = player_cx - (self.wx + self.W/2)
        if abs(dx) > 350:
            self.wx += self.dir * self.SPEED * dt
        else:
            # Strafe
            self.wx += math.cos(self.tick * 0.9) * self.SPEED * 0.4 * dt

        # Float bob
        self.wy = self.base_wy + math.sin(self.tick * self.FLOAT_SPD) * self.FLOAT_AMP

        # Shoot at player
        if self.fire_t <= 0:
            bdir = -1 if (self.wx + self.W/2) > player_cx else 1
            b = _get_bullet(bullets)
            if b: b.fire(self.wx + self.W//2, self.wy + self.H//2, bdir)
            self.fire_t = self.FIRE_CD

        # Out of world
        if self.wx < -200 or self.wx > WORLD_W + 200:
            self.active = False
        return self.active

    def hit(self) -> bool:
        self.hp -= 1
        if self.hp <= 0:
            self.active = False
            return True   # dead
        return False

    @property
    def rect(self) -> pygame.Rect:
        return pygame.Rect(int(self.wx), int(self.wy), self.W, self.H)

    def draw(self, surf: pygame.Surface, cam_x: float, tick: float):
        if not self.active: return
        sx = screen_x(self.wx, cam_x)
        if not (-50 <= sx <= SW+50): return
        sy = int(self.wy)

        # Body hex
        cx2, cy2 = sx + self.W//2, sy + self.H//2
        pts = [(cx2, sy), (sx+self.W, sy+self.H//3),
               (sx+self.W, sy+2*self.H//3), (cx2, sy+self.H),
               (sx, sy+2*self.H//3), (sx, sy+self.H//3)]
        pygame.draw.polygon(surf, D_STEEL, pts)
        pygame.draw.polygon(surf, DRONE_C, pts, 2)

        # Rotors
        rot_angle = tick * 6.0
        for ox in (-12, 12):
            rx, ry = cx2 + ox, sy - 6
            for i in range(2):
                a = rot_angle + i * math.pi
                ex = int(rx + math.cos(a) * 8)
                ey = int(ry + math.sin(a) * 3)
                pygame.draw.line(surf, LT_STEEL, (rx, ry), (ex, ey), 2)

        # Eye lens
        eye_c = NEON_RED if self.fire_t < 0.5 else CYAN
        pygame.draw.circle(surf, eye_c, (cx2, cy2), 5)
        pygame.draw.circle(surf, WHITE, (cx2-1, cy2-1), 2)

        # HP indicator
        if self.hp < self.HP:
            pygame.draw.rect(surf, NEON_RED, (sx+2, sy-8, self.W-4, 4))


def _get_bullet(pool: list) -> Optional[Bullet]:
    """Get an inactive bullet from pool (or None if pool exhausted)."""
    for b in pool:
        if not b.active: return b
    return None


def _get_drone(pool: list) -> Optional[FactoryDrone]:
    for d in pool:
        if not d.active: return d
    return None


# ══════════════════════════════════════════════════════════════════════════
# §11 LASER SCANNER  (Phase 3 stealth)
# ══════════════════════════════════════════════════════════════════════════
class LaserScanner:
    H = 4

    def __init__(self, wx: float, w: float, y_center: float,
                 y_range: float, speed: float, phase_off: float = 0.0):
        self.wx       = wx
        self.w        = w
        self.y_center = y_center
        self.y_range  = y_range
        self.speed    = speed
        self.phase    = phase_off
        self.wy       = y_center
        self.active   = True
        self.tick     = phase_off

    def update(self, dt: float):
        self.tick += dt
        self.wy = self.y_center + math.sin(self.tick * self.speed) * self.y_range

    @property
    def rect(self) -> pygame.Rect:
        return pygame.Rect(int(self.wx), int(self.wy) - self.H//2, int(self.w), self.H + 2)

    def collides_player(self, player) -> bool:
        pr = pygame.Rect(int(player.wx)+4, int(player.wy)+4, player.W-8, player.H-8)
        return pr.colliderect(self.rect)

    def draw(self, surf: pygame.Surface, cam_x: float, tick: float, alarmed: bool):
        sx = screen_x(self.wx, cam_x)
        if sx + self.w < -10 or sx > SW+10: return
        sy = int(self.wy)

        # Glow layers (widest to smallest)
        pulse = 0.7 + 0.3 * math.sin(tick * 8)
        for (thickness, col_t) in [(10, 0.25), (6, 0.5), (3, 0.85), (1, 1.0)]:
            c = (int(LASER_C[0]*col_t*pulse),
                 int(LASER_C[1]*col_t*pulse),
                 int(LASER_C[2]*col_t*pulse))
            pygame.draw.line(surf, c, (sx, sy), (sx + int(self.w), sy), thickness)

        # Emitter nodes
        for ex in (sx, sx + int(self.w)):
            pygame.draw.circle(surf, WARN_C, (ex, sy), 6)
            pygame.draw.circle(surf, WHITE,  (ex, sy), 3)

        # Alarm sweep dot
        if alarmed:
            sweep_x = sx + int((math.sin(tick*6)*0.5+0.5) * self.w)
            pygame.draw.circle(surf, NEON_RED, (sweep_x, sy), 5)


# ══════════════════════════════════════════════════════════════════════════
# §12 THE DEVOURER  (Phase 4 screen-edge pursuer)
# ══════════════════════════════════════════════════════════════════════════
class TheDevourer:
    W, H = 220, 240
    SPEED_BASE = 62.0

    def __init__(self, start_wx: float):
        self.wx    = start_wx
        self.tick  = 0.0
        self.speed = self.SPEED_BASE
        self.roar_t = 0.0   # roar effect timer

    def update(self, dt: float, cam_x: float):
        self.tick   += dt
        self.roar_t  = max(0.0, self.roar_t - dt)
        # Approaches screen left edge continuously
        target_x = cam_x - self.W * 0.4
        if self.wx < target_x:
            self.wx = min(target_x, self.wx + self.speed * dt)
        else:
            self.wx += self.speed * dt
        # Speed up over time
        self.speed = min(self.SPEED_BASE * 2.2, self.speed + 1.0 * dt)

    def roar(self):
        self.roar_t = 0.5

    @property
    def danger_rect(self) -> pygame.Rect:
        return pygame.Rect(int(self.wx + 20), 0, self.W - 20, SH)

    def collides_player(self, player) -> bool:
        pr = pygame.Rect(int(player.wx), int(player.wy), player.W, player.H)
        return pr.colliderect(self.danger_rect)

    def draw(self, surf: pygame.Surface, cam_x: float, tick: float):
        sx = screen_x(self.wx, cam_x)
        if sx + self.W < -20: return
        cy = SH // 2

        # Body pulse
        pulse = 1.0 + 0.06 * math.sin(tick * 4)
        W2 = int(self.W * pulse); H2 = int(self.H * pulse)
        bx = sx + (self.W - W2) // 2
        by = cy - H2 // 2

        # Outer glow
        for r in (H2//2 + 30, H2//2 + 18, H2//2 + 8):
            gs = pygame.Surface((r*2, r*2), pygame.SRCALPHA)
            alpha = max(0, int(60 * (1 - (r - H2//2)/35)))
            pygame.draw.ellipse(gs, (*DEVOUR_C, alpha), (0, 0, r*2, r*2))
            surf.blit(gs, (sx + W2//2 - r, cy - r))

        # Main body gear circle
        pygame.draw.ellipse(surf, RUST_DK, (bx, by, W2, H2))
        pygame.draw.ellipse(surf, DEVOUR_C, (bx, by, W2, H2), 3)

        # Rotating gear teeth
        n_teeth = 16
        r_outer = H2 // 2 + 14
        r_inner = H2 // 2 + 2
        gear_angle = tick * 2.0
        for i in range(n_teeth):
            a0 = gear_angle + i * (math.tau / n_teeth)
            a1 = a0 + (math.tau / n_teeth / 2)
            gx0 = sx + W2//2 + int(math.cos(a0) * r_outer)
            gy0 = cy        + int(math.sin(a0) * r_outer)
            gx1 = sx + W2//2 + int(math.cos(a0) * r_inner)
            gy1 = cy        + int(math.sin(a0) * r_inner)
            gx2 = sx + W2//2 + int(math.cos(a1) * r_inner)
            gy2 = cy        + int(math.sin(a1) * r_inner)
            gx3 = sx + W2//2 + int(math.cos(a1) * r_outer)
            gy3 = cy        + int(math.sin(a1) * r_outer)
            pygame.draw.polygon(surf, RUST, [(gx0,gy0),(gx1,gy1),(gx2,gy2),(gx3,gy3)])
            pygame.draw.polygon(surf, DEVOUR_C, [(gx0,gy0),(gx1,gy1),(gx2,gy2),(gx3,gy3)], 1)

        # Inner counter-rotating gears
        for (r_c, spd, off) in ((35, -3.5, 0.5), (20, 5.0, 1.2)):
            inner_angle = tick * spd + off
            for i in range(8):
                a = inner_angle + i * (math.tau / 8)
                ix = sx + W2//2 + int(math.cos(a) * r_c)
                iy = cy        + int(math.sin(a) * r_c)
                pygame.draw.circle(surf, RUST_DK, (ix, iy), 4)
                pygame.draw.circle(surf, NEON_ORG, (ix, iy), 2)

        # "Eye" / intake maw
        eye_pulse = 0.6 + 0.4 * math.sin(tick * 7)
        eye_r = int(30 * eye_pulse)
        pygame.draw.circle(surf, D_STEEL, (sx + W2//2, cy), eye_r)
        pygame.draw.circle(surf, (int(200*eye_pulse), 0, 0), (sx + W2//2, cy), eye_r-4)
        pygame.draw.circle(surf, NEON_RED, (sx + W2//2, cy), eye_r//3)

        # Roar shockwave
        if self.roar_t > 0:
            rs = self.roar_t / 0.5
            rr = int((1.0 - rs) * 200)
            if rr > 0:
                rs_surf = pygame.Surface((rr*2, rr*2), pygame.SRCALPHA)
                pygame.draw.ellipse(rs_surf, (*NEON_RED, int(80*rs)), (0,0,rr*2,rr*2))
                surf.blit(rs_surf, (sx + W2//2 - rr, cy - rr))


# ══════════════════════════════════════════════════════════════════════════
# §13 EXIT DOOR
# ══════════════════════════════════════════════════════════════════════════
class ExitDoor:
    W, H = 64, 100

    def __init__(self, wx: float, wy: float):
        self.wx = wx; self.wy = wy
        self.locked   = True
        self.open_t   = 0.0      # opening animation timer
        self.slam_zone = pygame.Rect(int(wx) - 30, int(wy) - 40, self.W + 60, 60)

    @property
    def rect(self) -> pygame.Rect:
        return pygame.Rect(int(self.wx), int(self.wy), self.W, self.H)

    def try_slam_open(self, player) -> bool:
        """Returns True if slam opens the door."""
        if not self.locked: return False
        pr = pygame.Rect(int(player.wx), int(player.wy), player.W, player.H)
        if player.is_slamming and pr.colliderect(self.slam_zone):
            self.locked = False
            self.open_t = 0.6
            return True
        return False

    def draw(self, surf: pygame.Surface, cam_x: float, tick: float):
        sx = screen_x(self.wx, cam_x)
        if not (-20 <= sx <= SW+20): return
        sy = int(self.wy)

        # Frame / surround
        pygame.draw.rect(surf, LT_STEEL, (sx-8, sy-8, self.W+16, self.H+8))
        pygame.draw.rect(surf, STEEL,    (sx-6, sy-6, self.W+12, self.H+4))

        if self.locked:
            # Door body
            pygame.draw.rect(surf, D_STEEL, (sx, sy, self.W, self.H))
            # Reinforcement bars
            for i in range(3):
                pygame.draw.rect(surf, STEEL, (sx+4, sy+8+i*28, self.W-8, 10))
            # Lock indicator (red)
            pygame.draw.circle(surf, NEON_RED, (sx+self.W//2, sy+self.H//2), 12)
            pygame.draw.circle(surf, WHITE,    (sx+self.W//2, sy+self.H//2), 6)
            # "SLAM TO OPEN" hint pulsing
            if int(tick * 3) % 2 == 0:
                pygame.draw.rect(surf, WARN_C, (sx-4, sy-30, self.W+8, 18))
        else:
            # Open — green glow
            open_frac = min(1.0, self.open_t / 0.6) if self.open_t > 0 else 1.0
            gap = int(self.W * open_frac)
            pygame.draw.rect(surf, (0, 30, 0), (sx, sy, self.W, self.H))
            for r in (40, 28, 16):
                gs = pygame.Surface((r*2, r*2), pygame.SRCALPHA)
                alpha = int(80 * (1 - r/42))
                pygame.draw.ellipse(gs, (0, 200, 80, alpha), (0,0,r*2,r*2))
                surf.blit(gs, (sx+self.W//2-r, sy+self.H//2-r))
            # Light beams from opening
            for i in range(5):
                bx = sx + self.W//2 + random.randint(-10, 10)
                pygame.draw.line(surf, (0, 200, 80),
                                 (bx, sy), (bx + random.randint(-20,20), sy-60), 1)


# ══════════════════════════════════════════════════════════════════════════
# §14 HUD
# ══════════════════════════════════════════════════════════════════════════
class HUD:
    PHASE_NAMES = ["PHASE I: CALIBRATION", "PHASE II: PURSUIT",
                   "PHASE III: DETECTION", "PHASE IV: DEVOURER"]
    PHASE_COLS  = [SULFUR, NEON_ORG, LASER_C, DEVOUR_C]

    def __init__(self):
        self._font_lg = pygame.font.SysFont("Consolas,monospace", 26, bold=True)
        self._font_sm = pygame.font.SysFont("Consolas,monospace", 16)
        self._font_xl = pygame.font.SysFont("Consolas,monospace", 52, bold=True)
        self._phase_flash_t = 0.0
        self._phase_shown   = 0
        self._msg: List[Tuple[str, float, tuple]] = []   # (text, ttl, col)

    def notify_phase(self, phase: int):
        self._phase_flash_t = 3.0
        self._phase_shown   = phase
        self.push_msg(self.PHASE_NAMES[phase], 3.0, self.PHASE_COLS[phase])

    def push_msg(self, text: str, ttl: float, col=WARN_C):
        self._msg.append([text, ttl, col])
        if len(self._msg) > 4: self._msg.pop(0)

    def update(self, dt: float):
        self._phase_flash_t = max(0.0, self._phase_flash_t - dt)
        self._msg = [[t, ttl-dt, c] for (t, ttl, c) in self._msg if ttl > dt]

    def draw(self, surf: pygame.Surface, player, phase: int, cam_x: float,
             alarmed: bool, devourer: Optional[TheDevourer], tick: float):
        # ── HP Lives ───
        for i in range(3):
            col = HP_C if i < player.hp else D_STEEL
            pygame.draw.rect(surf, col, (20 + i*28, 20, 22, 22))
            pygame.draw.rect(surf, LT_STEEL, (20 + i*28, 20, 22, 22), 1)

        # ── Dash charges ───
        charges = int(player.dash_charges)
        for i in range(MockPlayer.DASH_CHARGES):
            col = STAM_C if i < charges else D_STEEL
            pygame.draw.rect(surf, col, (20 + i*22, 50, 18, 8))
            pygame.draw.rect(surf, LT_STEEL, (20 + i*22, 50, 18, 8), 1)

        # ── Phase indicator ───
        pcol = self.PHASE_COLS[phase]
        ph_txt = self._font_sm.render(f"◈ {self.PHASE_NAMES[phase]}", True, pcol)
        surf.blit(ph_txt, (SW - ph_txt.get_width() - 18, 18))

        # ── Alarm banner ───
        if alarmed:
            a = 0.5 + 0.5 * math.sin(tick * 10)
            alarm_surf = pygame.Surface((SW, 44), pygame.SRCALPHA)
            alarm_surf.fill((180, 0, 0, int(120 * a)))
            surf.blit(alarm_surf, (0, SH//2 - 120))
            at = self._font_lg.render("⚠  ALARM — SECURITY BREACH  ⚠", True, NEON_RED)
            surf.blit(at, (SW//2 - at.get_width()//2, SH//2 - 118))

        # ── Phase-flash title ───
        if self._phase_flash_t > 0:
            alpha = min(1.0, self._phase_flash_t) * min(1.0, self._phase_flash_t * 3)
            pcol2 = self.PHASE_COLS[self._phase_shown]
            pt = self._font_xl.render(self.PHASE_NAMES[self._phase_shown], True, pcol2)
            ps = pygame.Surface((pt.get_width()+20, pt.get_height()+10), pygame.SRCALPHA)
            ps.fill((*SOOT, int(180*alpha)))
            ps.blit(pt, (10, 5))
            surf.blit(ps, (SW//2 - ps.get_width()//2, SH//2 - 60))

        # ── Devourer warning ───
        if devourer:
            dist_px = devourer.wx - cam_x + devourer.W
            if dist_px < 500:
                frac = max(0.0, 1.0 - dist_px / 500.0)
                pulse = 0.7 + 0.3 * math.sin(tick * 12 * frac + 1)
                dw = int(200 * frac)
                pygame.draw.rect(surf, tuple(int(c*pulse) for c in DEVOUR_C),
                                 (0, SH//2 - 10, dw, 20))
                dt2 = self._font_sm.render("THE DEVOURER", True,
                                           tuple(int(c*pulse) for c in NEON_RED))
                surf.blit(dt2, (10, SH//2 - 8))

        # ── Floating messages ───
        for i, (text, ttl, col) in enumerate(reversed(self._msg)):
            mt = self._font_sm.render(text, True, col)
            surf.blit(mt, (SW//2 - mt.get_width()//2, 90 + i*26))

        # ── Controls reminder (brief) ───
        ctrl = self._font_sm.render("ARROWS/WASD=MOVE  SPACE=JUMP  SHIFT=DASH  DOWN=SLAM  Z=ATK", True, STEEL)
        surf.blit(ctrl, (SW//2 - ctrl.get_width()//2, SH-24))


# ══════════════════════════════════════════════════════════════════════════
# §15 LEVEL GEOMETRY BUILDER
# ══════════════════════════════════════════════════════════════════════════
def _build_geometry() -> Tuple[list, list, list]:
    """
    Returns (platforms, crushers, laser_scanners).
    Deterministic via LEVEL_SEED.
    """
    rng = random.Random(LEVEL_SEED)

    platforms: List[Platform] = []
    crushers:  List[Crusher]  = []
    lasers:    List[LaserScanner] = []

    # ── Ground floor conveyor segments ────────────────────────────────────
    GROUND_Y = 570
    x = 0.0
    while x < WORLD_W - 400:
        w = rng.randint(180, 420)
        conv = rng.random() < 0.80    # 80% conveyor
        platforms.append(Platform(x, GROUND_Y, w, 30,
                                  conveyor=conv, conv_dir=1,
                                  conv_speed=CONV_PUSH))
        gap = rng.randint(28, 72)
        x += w + gap

    # ── Mid platforms (y ~ 430) ───────────────────────────────────────────
    x = 320.0
    while x < WORLD_W - 600:
        w = rng.randint(110, 260)
        conv = rng.random() < 0.40
        platforms.append(Platform(x, 430, w, 22,
                                  conveyor=conv, conv_dir=-1,
                                  conv_speed=CONV_PUSH * 0.7))
        x += w + rng.randint(100, 280)

    # ── High platforms (y ~ 300, Phase 2+) ───────────────────────────────
    x = 2400.0
    while x < WORLD_W - 800:
        w = rng.randint(90, 200)
        platforms.append(Platform(x, 300, w, 20, conveyor=False))
        x += w + rng.randint(160, 360)

    # ── Crushers (Phase 1 start: cam_x > 600) ────────────────────────────
    cx = 700.0
    while cx < WORLD_W - 1200:
        target_y = rng.choice([GROUND_Y, 430, 300]) + 15   # just above platform
        period   = rng.uniform(2.2, 5.0)
        offset   = rng.uniform(0, period)
        crushers.append(Crusher(cx, target_y, period, offset))
        cx += rng.randint(380, 720)

    # ── Laser scanners (Phase 3: cam_x > 4700) ───────────────────────────
    lx = 5200.0
    while lx < WORLD_W - 1500:
        y_center = rng.uniform(280, 490)
        y_range  = rng.uniform(30, 90)
        speed    = rng.uniform(1.2, 2.8)
        lw       = rng.uniform(300, 700)
        phase_off = rng.uniform(0, math.tau)
        lasers.append(LaserScanner(lx, lw, y_center, y_range, speed, phase_off))
        lx += rng.randint(400, 800)

    return platforms, crushers, lasers


# ══════════════════════════════════════════════════════════════════════════
# §16 FACTORY LEVEL  (main orchestrator)
# ══════════════════════════════════════════════════════════════════════════
class FactoryLevel:
    DRONE_POOL_SIZE  = 20
    BULLET_POOL_SIZE = 60
    SPAWN_CD_MIN = 2.5
    SPAWN_CD_MAX = 5.5

    def __init__(self, screen: pygame.Surface, clock: pygame.time.Clock,
                 player_ctx=None):
        self.screen = screen
        self.clock  = clock

        # Camera
        self.cam_x   = -100.0
        self.cam_spd = AUTO_SCROLL_BASE

        # Phase state
        self.phase        = 0
        self.prev_phase   = -1
        self.alarmed      = False
        self.alarm_t      = 0.0    # alarm duration
        self.chaotic      = False  # Phase 3 alarm effect on crushers

        # Time
        self.tick = 0.0

        # Subsystems
        self.particles = ParticleSystem()
        self.fx        = ScreenFX()
        self.bg        = Background()
        self.hud       = HUD()

        # Player
        if player_ctx is not None and _USE_EXT and isinstance(player_ctx, _ExtPlayer):
            self.player = player_ctx
            self.player.wx = 200.0
            self.player.wy = 520.0
        else:
            self.player = MockPlayer(200.0, 520.0)

        self.lives = 3   # level-level lives tracking for external player too
        self.respawn_t = 0.0

        # Level geometry
        self.platforms, self.crushers, self.lasers = _build_geometry()

        # ── Fonksiyonel Bölge Yöneticisi / Zone Manager ───────────────────
        self.zone_mgr = ZoneManager()

        # ── Yüksek Tavan Aydınlatması / High-Bay Lights ───────────────────
        # Her 160 px'de bir armatür (endüstriyel yüksek tavan aydınlatması)
        self.high_bay_lights: List[HighBayLight] = [
            HighBayLight(wx) for wx in range(120, WORLD_W, 160)
        ]

        # ── HVAC Üniteleri / HVAC Units ───────────────────────────────────
        # Her bölgede 4-6 HVAC ünitesi (bölge başlarında ve aralarında)
        self.hvac_units: List[HVACUnit] = [
            HVACUnit(wx) for wx in range(240, WORLD_W, 340)
        ]

        # ── Sandviç Panel Duvarlar / Wall Panels ──────────────────────────
        _wall_rng = random.Random(LEVEL_SEED + 99)
        self.wall_panels: List[WallPanel] = []
        wx2 = 80.0
        while wx2 < WORLD_W - 200:
            H2  = _wall_rng.randint(80, 200)
            W2  = _wall_rng.randint(60, 120)
            wy2 = _wall_rng.uniform(80, 250)
            acoustic = _wall_rng.random() < 0.30
            self.wall_panels.append(WallPanel(wx2, wy2, W2, H2, acoustic))
            wx2 += _wall_rng.uniform(150, 400)

        # Object pools
        self.drone_pool  = [FactoryDrone() for _ in range(self.DRONE_POOL_SIZE)]
        self.bullet_pool = [Bullet()       for _ in range(self.BULLET_POOL_SIZE)]
        self.active_drones: List[FactoryDrone] = []
        self.active_bullets: List[Bullet]      = []
        self.drone_spawn_t  = self.SPAWN_CD_MIN
        self.devourer: Optional[TheDevourer]    = None

        # Exit
        self.exit_door = ExitDoor(EXIT_DOOR_X, 468.0)

        # Result
        self.result: Optional[str] = None

        # Ambient spark emitter timer
        self._spark_t = 0.2

    # ── Phase management ──────────────────────────────────────────────────
    def _calc_phase(self) -> int:
        for i in range(len(PHASE_CAM_X)-1, -1, -1):
            if self.cam_x >= PHASE_CAM_X[i]:
                return i
        return 0

    def _on_phase_enter(self, phase: int):
        self.hud.notify_phase(phase)
        self.fx.flash(self.hud.PHASE_COLS[phase], 0.6)
        self.fx.shake(6.0, 0.5)
        if phase == 3:   # Phase IV – spawn Devourer
            self.devourer = TheDevourer(self.cam_x - 100)
            self.devourer.roar()
            self.fx.shake(14.0, 1.2)
            self.fx.flash(DEVOUR_C, 0.8)
            self.hud.push_msg("RUN. IT CANNOT BE STOPPED.", 4.0, NEON_RED)
        elif phase == 2:
            self.hud.push_msg("LASER GRIDS ACTIVE — STAY LOW", 3.5, LASER_C)
        elif phase == 1:
            self.hud.push_msg("DRONES DETECTED — ELIMINATE OR EVADE", 3.5, DRONE_C)

    # ── Player death / respawn ─────────────────────────────────────────────
    def _kill_player(self, cause: str = "env"):
        if self.respawn_t > 0: return    # already dead / respawning
        took_dmg = self.player.take_damage(cause)
        if not took_dmg: return
        self.lives = self.player.hp if hasattr(self.player, "hp") else self.lives - 1
        self.fx.flash(NEON_RED, 0.5)
        self.fx.shake(12.0, 0.6)
        self.particles.burst(self.player.cx, self.player.cy,
                             16, 220, 0.9, 5, NEON_RED)
        if self.lives <= 0 or (hasattr(self.player,"hp") and self.player.hp <= 0):
            self.result = "died"
        else:
            self.respawn_t = 1.2

    def _respawn(self):
        self.player.wx   = self.cam_x + 160
        self.player.wy   = 480.0
        self.player.vx   = 0.0
        self.player.vy   = 0.0
        if hasattr(self.player, "inv_t"):
            self.player.inv_t = 2.0

    # ── Drone spawning (Phase 2+) ─────────────────────────────────────────
    def _try_spawn_drone(self, dt: float):
        self.drone_spawn_t -= dt
        if self.drone_spawn_t > 0: return
        d = _get_drone(self.drone_pool)
        if d:
            spawn_wx = self.cam_x + SW + 60
            spawn_wy = random.uniform(260, 460)
            d.spawn(spawn_wx, spawn_wy, -1)
            self.active_drones.append(d)
        self.drone_spawn_t = random.uniform(self.SPAWN_CD_MIN, self.SPAWN_CD_MAX)

    # ── Collision checks ──────────────────────────────────────────────────
    def _check_crushers(self):
        for cr in self.crushers:
            if not visible(cr.wx, self.cam_x, 200): continue
            if cr.state not in ("dropping", "holding"): continue
            dr = cr.get_danger_rect()
            pr = pygame.Rect(int(self.player.wx), int(self.player.wy),
                             self.player.W, self.player.H)
            if pr.colliderect(dr):
                self._kill_player("crusher")
                self.fx.shake(16.0, 0.8)
                self.particles.burst(self.player.cx, self.player.cy,
                                     20, 180, 1.2, 6, WARN_C, 300.0)
                return

    def _check_bullets(self):
        pr = pygame.Rect(int(self.player.wx), int(self.player.wy),
                         self.player.W, self.player.H)
        for b in self.active_bullets:
            if not b.active: continue
            if pr.colliderect(b.rect):
                b.active = False
                self._kill_player("bullet")
                self.particles.sparks(b.wx, b.wy, 6)

    def _check_lasers(self):
        if self.alarmed: return    # already alarmed
        for ls in self.lasers:
            if not visible(ls.wx, self.cam_x, 50): continue
            if ls.collides_player(self.player):
                self.alarmed  = True
                self.alarm_t  = 8.0
                self.chaotic  = True
                self.cam_spd  = AUTO_SCROLL_BASE * 1.55
                self.fx.flash(ALARM_C, 0.8)
                self.fx.shake(8.0, 0.4)
                self.hud.push_msg("⚠ SECURITY BREACH — GRID ACCELERATING ⚠", 5.0, NEON_RED)
                break

    def _check_devourer(self):
        if not self.devourer: return
        if self.devourer.collides_player(self.player):
            self.player.hp = 0
            self.result = "died"

    def _check_exit(self):
        if self.exit_door.try_slam_open(self.player):
            self.fx.flash((0,220,80), 0.8)
            self.fx.shake(10.0, 0.5)
            self.particles.burst(self.player.cx, self.player.cy,
                                 24, 200, 1.4, 6, (0,220,80), 100.0)
            self.hud.push_msg("ESCAPE HATCH OPEN — GO GO GO", 3.0, (0,220,80))

        if (not self.exit_door.locked and
                self.player.wx > self.exit_door.wx + 20):
            self.result = "completed"

    def _check_player_oob(self):
        """Fell off left edge or into the pit."""
        if self.player.wx < self.cam_x - 80:
            self._kill_player("scroll")
        elif self.player.wy > SH + 60:
            self._kill_player("pit")

    # ── Attack vs drones ──────────────────────────────────────────────────
    def _check_player_attack(self):
        ar = self.player.get_attack_rect()
        if not ar: return
        for d in self.active_drones:
            if not d.active: continue
            if ar.colliderect(d.rect):
                died = d.hit()
                self.particles.sparks(d.wx + d.W//2, d.wy + d.H//2, 10)
                if died:
                    self.particles.burst(d.wx+d.W//2, d.wy+d.H//2,
                                         12, 160, 0.8, 5, DRONE_C, 200.0)

    # ── Main update ───────────────────────────────────────────────────────
    def update(self, dt: float, events: list) -> Optional[str]:
        if self.result: return self.result

        # Quit check
        for ev in events:
            if ev.type == pygame.QUIT:
                return "quit"
            if ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE:
                return "quit"

        self.tick += dt

        # Background animation update
        self.bg.update(dt, self.tick, self.cam_x)

        # Respawn timer
        if self.respawn_t > 0:
            self.respawn_t -= dt
            if self.respawn_t <= 0:
                self._respawn()
            return None

        # Auto-scroll camera
        self.cam_x += self.cam_spd * dt
        self.cam_x = max(0.0, self.cam_x)

        # Phase
        new_phase = self._calc_phase()
        if new_phase != self.prev_phase:
            self._on_phase_enter(new_phase)
            self.prev_phase = new_phase
        self.phase = new_phase

        # Alarm decay
        if self.alarmed:
            self.alarm_t -= dt
            if self.alarm_t <= 0:
                self.alarmed = False
                self.cam_spd = AUTO_SCROLL_BASE
                self.hud.push_msg("ALERT CLEARED", 2.0, SULFUR)

        # Player update
        conv_mult = 1.5 if self.alarmed else 1.0
        self.player.update(dt, self.platforms, conv_mult)

        # OOB check
        self._check_player_oob()
        if self.result: return self.result

        # Crushers
        for cr in self.crushers:
            if visible(cr.wx, self.cam_x, 300):
                is_crush = cr.update(dt, chaotic=self.chaotic)
                if is_crush:
                    # Ambient shake
                    if cr.state == "holding" and random.random() < dt * 8:
                        self.fx.shake(4.0, 0.1)
        self._check_crushers()
        if self.result: return self.result

        # Drones (Phase 2+)
        if self.phase >= 1:
            self._try_spawn_drone(dt)
            for d in self.active_drones:
                d.update(dt, self.player.cx, self.player.cy, self.bullet_pool)
            self.active_drones = [d for d in self.active_drones if d.active]

            for b in self.bullet_pool:
                b.update(dt)
            self._check_bullets()
            if self.result: return self.result

            self._check_player_attack()

        # Lasers (Phase 3+)
        if self.phase >= 2:
            for ls in self.lasers:
                if visible(ls.wx, self.cam_x, 100): ls.update(dt)
            self._check_lasers()
            if self.alarmed:
                self.fx.flash(ALARM_C, 0.05)

        # The Devourer (Phase 4)
        if self.phase >= 3:
            if self.devourer:
                self.devourer.update(dt, self.cam_x)
                # Periodic roar
                if int(self.tick * 3) % 20 == 0 and random.random() < dt * 4:
                    self.devourer.roar()
                    self.fx.shake(5.0, 0.2)
            self._check_devourer()
            if self.result: return self.result

        # Exit door
        self._check_exit()
        if self.result: return self.result

        # Ambient sparks from conveyor belt edges
        self._spark_t -= dt
        if self._spark_t <= 0:
            self._spark_t = random.uniform(0.06, 0.25)
            for p in self.platforms:
                if not visible(p.wx + p.w, self.cam_x, 50): continue
                if p.conveyor and random.random() < 0.3:
                    self.particles.emit(
                        p.wx + random.uniform(0, p.w),
                        p.wy,
                        random.uniform(-40, 40),
                        random.uniform(-120, -30),
                        random.uniform(0.3, 0.7),
                        random.randint(1, 3), NEON_ORG, 200.0)

        # Particles & FX
        self.particles.update(dt)
        self.fx.update(dt)
        self.hud.update(dt)

        # ── Yüksek Tavan Armatürleri / High-Bay Lights ────────────────────
        for light in self.high_bay_lights:
            if visible(light.wx, self.cam_x, 120):
                light.update(dt)

        # ── HVAC Güncellemesi ─────────────────────────────────────────────
        for hvac in self.hvac_units:
            if visible(hvac.wx, self.cam_x, 120):
                hvac.update(dt, self.particles)

        return None

    # ── Draw ──────────────────────────────────────────────────────────────
    def draw(self):
        surf = self.screen
        ox, oy = self.fx.get_offset()

        # Draw onto a temp surface for shake offset
        if ox or oy:
            world_surf = pygame.Surface((SW, SH))
            self._draw_world(world_surf)
            surf.blit(world_surf, (ox, oy))
        else:
            self._draw_world(surf)

        # Overlays always at (0,0)
        self.fx.draw_overlay(surf)
        self.hud.draw(surf, self.player, self.phase, self.cam_x,
                      self.alarmed, self.devourer, self.tick)

        # Death overlay
        if self.respawn_t > 0:
            a = min(200, int(200 * (1.0 - self.respawn_t / 1.2) * 2))
            ds = pygame.Surface((SW, SH), pygame.SRCALPHA)
            ds.fill((0, 0, 0, a))
            surf.blit(ds, (0, 0))

    def _draw_world(self, surf: pygame.Surface):
        # Background (parallax layers)
        self.bg.draw(surf, self.cam_x, self.tick)

        # ── Sandviç Panel Duvarlar / Wall Panels (arka plan katmanı) ─────
        for wp in self.wall_panels:
            if visible(wp.wx, self.cam_x * 0.55, wp.W + 30):
                wp.draw(surf, self.cam_x)

        # ── Kurumsal Kimlik / Corporate Branding (duvar logoları) ─────────
        self.zone_mgr.draw_corp_logos(surf, self.cam_x)

        # ── Bölge Zemin Renkleri & Güvenlik Çizgileri / Floor Markings ───
        self.zone_mgr.draw_floor(surf, self.cam_x, self.tick)

        # ── Yüksek Tavan Armatürleri / High-Bay Lighting ─────────────────
        for light in self.high_bay_lights:
            if visible(light.wx, self.cam_x, 120):
                light.draw(surf, self.cam_x, self.tick)

        # ── HVAC Üniteleri (tavan) / HVAC Ceiling Units ───────────────────
        for hvac in self.hvac_units:
            if visible(hvac.wx, self.cam_x, 80):
                hvac.draw(surf, self.cam_x, self.tick)

        # Pit lava at bottom
        pygame.draw.rect(surf, RUST_DK, (0, SH - 20, SW, 20))
        for i in range(0, SW, 6):
            h = 4 + int(3 * math.sin(self.tick * 3 + i * 0.1))
            pygame.draw.rect(surf, NEON_ORG, (i, SH - 20 - h, 4, h))

        # Ceiling pipes (tavan boru hattı – tesisat erişilebilirliği)
        pygame.draw.rect(surf, D_STEEL, (0, 0, SW, 14))
        for i in range(0, SW, 40):
            pygame.draw.rect(surf, STEEL, (i, 0, 24, 14))

        # ── İş İstasyonu Köşebentleri / Workstation Markers ─────────────
        self.zone_mgr.draw_workstation_markers(surf, self.cam_x, self.platforms)

        # ── Tehlike Bölgesi İşaretleri / Danger Zone Hatching ────────────
        self.zone_mgr.draw_danger_zones(surf, self.cam_x, self.crushers, self.tick)

        # Platforms
        for p in self.platforms:
            if visible(p.wx, self.cam_x, p.w + 50):
                p.draw(surf, self.cam_x, self.tick)

        # Crushers
        for cr in self.crushers:
            if visible(cr.wx, self.cam_x, cr.W + 60):
                cr.draw(surf, self.cam_x, self.tick)

        # Lasers
        for ls in self.lasers:
            if visible(ls.wx, self.cam_x, ls.w + 60):
                ls.draw(surf, self.cam_x, self.tick, self.alarmed)

        # Exit door
        if visible(self.exit_door.wx, self.cam_x, self.exit_door.W + 80):
            self.exit_door.draw(surf, self.cam_x, self.tick)
            # Label
            if abs(self.exit_door.wx - (self.cam_x + SW//2)) < 600:
                f = pygame.font.SysFont("Consolas", 14)
                lbl = f.render("EVACUATION HATCH  [SLAM TO OPEN]", True, WARN_C)
                esx = screen_x(self.exit_door.wx, self.cam_x)
                surf.blit(lbl, (esx - lbl.get_width()//2 + 32,
                                int(self.exit_door.wy) - 20))

        # Drones
        for d in self.active_drones:
            if visible(d.wx, self.cam_x, d.W + 40):
                d.draw(surf, self.cam_x, self.tick)

        # Bullets
        for b in self.bullet_pool:
            if b.active:
                b.draw(surf, self.cam_x)

        # Devourer
        if self.devourer:
            self.devourer.draw(surf, self.cam_x, self.tick)

        # Particles
        self.particles.draw(surf, self.cam_x)

        # Player
        self.player.draw(surf, self.cam_x)

        # ── Bölge Sınır Levhaları / Zone Separator Signs ─────────────────
        self.zone_mgr.draw_zone_separators(surf, self.cam_x, self.tick)

        # ── Mevcut Bölge Göstergesi / Current Zone HUD Indicator ─────────
        z_idx, tr_name, en_name, z_accent = \
            self.zone_mgr.get_current_zone_info(self.cam_x)
        try:
            fz = pygame.font.SysFont("Consolas,monospace", 12)
            zt = fz.render(f"BÖLGE {z_idx+1}/5 · {tr_name}", True, z_accent)
            surf.blit(zt, (SW//2 - zt.get_width()//2, SH - 82))
        except Exception:
            pass

        # Distance / progress bar
        prog = min(1.0, (self.cam_x / EXIT_DOOR_X))
        bar_w = SW - 80
        pygame.draw.rect(surf, D_STEEL, (40, SH - 46, bar_w, 8))
        # Bölge renkleriyle renklendirilmiş ilerleme çubuğu
        filled_w = int(bar_w * prog)
        if filled_w > 0:
            seg_w = bar_w // len(FACTORY_ZONES)
            for zi, (_, _, _, _, _, z_ac) in enumerate(FACTORY_ZONES):
                seg_x = 40 + zi * seg_w
                seg_fill = min(seg_w, max(0, filled_w - zi * seg_w))
                if seg_fill > 0:
                    pygame.draw.rect(surf, z_ac, (seg_x, SH - 46, seg_fill, 8))
        pygame.draw.rect(surf, LT_STEEL, (40, SH - 46, bar_w, 8), 1)
        f2 = pygame.font.SysFont("Consolas", 12)
        t2 = f2.render(f"FACTORY PROGRESS  {int(prog*100)}%", True, STEEL)
        surf.blit(t2, (40, SH - 60))




# ══════════════════════════════════════════════════════════════════════════
# §17 ENGINE-COMPATIBLE run() FUNCTION
# ══════════════════════════════════════════════════════════════════════════
def run(level_idx=0,
        screen_full: Optional[pygame.Surface] = None,
        clock_obj: Optional[pygame.time.Clock] = None,
        save_manager=None,
        player_ctx=None) -> str:
    """
    FRAGMENTIA engine entry point.
    Returns "completed" | "died" | "quit".
    """
    if not pygame.get_init():
        pygame.init()

    screen = screen_full or pygame.display.set_mode((SW, SH))
    clock  = clock_obj   or pygame.time.Clock()
    pygame.display.set_caption("FRAGMENTIA — Industrial Escape: Infinite Factory")

    level = FactoryLevel(screen, clock, player_ctx)

    # Brief intro flash
    level.fx.flash(BG_BOT, 1.2)
    level.hud.push_msg("INDUSTRIAL ESCAPE: INFINITE FACTORY", 4.0, RUST)
    level.hud.push_msg("SURVIVE THE FACTORY — REACH THE HATCH", 4.0, SULFUR)
    level.hud.push_msg(f"{CORP_NAME}  ·  {CORP_SLOGAN}", 5.0, CORP_SECONDARY)

    while True:
        dt = min(clock.tick(TARGET_FPS) / 1000.0, 0.05)  # cap at 50ms

        events = pygame.event.get()

        result = level.update(dt, events)
        if result:
            # Brief fade-out
            fade = pygame.Surface((SW, SH))
            for alpha in range(0, 255, 12):
                fade.fill((0, 0, 0))
                level.draw()
                fade.set_alpha(alpha)
                screen.blit(fade, (0, 0))
                pygame.display.flip()
                clock.tick(60)
            return result

        level.draw()
        pygame.display.flip()

    return "quit"


# ══════════════════════════════════════════════════════════════════════════
# §18 STANDALONE ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    pygame.init()
    pygame.display.set_caption("FRAGMENTIA — Industrial Escape: Infinite Factory")
    screen = pygame.display.set_mode((SW, SH))
    clock  = pygame.time.Clock()

    result = run(
        level_idx   = 0,
        screen_full = screen,
        clock_obj   = clock,
        save_manager= None,      # mock: no save state needed
        player_ctx  = None,      # mock: will use MockPlayer
    )

    # Post-level result screen
    font_xl = pygame.font.SysFont("Consolas,monospace", 56, bold=True)
    font_sm = pygame.font.SysFont("Consolas,monospace", 22)
    msgs = {
        "completed": ("ESCAPED", (42, 220, 80),    "You made it out."),
        "died":      ("CONSUMED", NEON_RED,          "The factory claimed you."),
        "quit":      ("ABORTED",  STEEL,             ""),
    }
    title_str, title_col, sub_str = msgs.get(result, ("—", WHITE, ""))
    screen.fill(BG_TOP)
    t1 = font_xl.render(title_str, True, title_col)
    t2 = font_sm.render(sub_str, True, STEEL)
    t3 = font_sm.render("Press any key to exit.", True, LT_STEEL)
    screen.blit(t1, (SW//2 - t1.get_width()//2, SH//2 - 70))
    screen.blit(t2, (SW//2 - t2.get_width()//2, SH//2 + 10))
    screen.blit(t3, (SW//2 - t3.get_width()//2, SH//2 + 50))
    pygame.display.flip()

    waiting = True
    while waiting:
        for ev in pygame.event.get():
            if ev.type in (pygame.QUIT, pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN):
                waiting = False
        clock.tick(30)

    pygame.quit()
    sys.exit(0)