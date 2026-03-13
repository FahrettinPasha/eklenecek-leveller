"""
DEAD FACTORY  —  Industrial Megafactory Escape  (v3 — Extended)
================================================================
Controls: A/D move  |  W/Space jump  |  K/F/Shift DASH  |  E interact  |  R restart  |  ESC quit

YENİLİKLER v3
──────────────
[YENİ-1]  Dünya genişliği 6400 → 9800 px. Oyun süresi yaklaşık iki katına çıktı.
[YENİ-2]  BÖLGE 6: SUNUCU ODASI. Üç terminal doğru sırayla hacklenmelidir (1→2→3).
           Yanlış sıra → tüm terminaller sıfır + elektrik şoku (hasar).
           Çıkıştaki demir kapı, dizi tamamlanana kadar açılmaz.
[YENİ-3]  BÖLGE 7: BAKIM TÜNELLERİ. Üç salınan mekanik kol (daha hızlı),
           altı buhar jetinin senkronize çift darbesi, üç yatay hareketli platform.
           Hayatta kalan bir NPC ek bilgi verir.
[YENİ-4]  BÖLGE 8: YÜK DEPOSU. Basınç plakası bulmacası — dört plak yüksek
           platformlarda karışık sırayla yerleştirilmiştir; 1→2→3→4 sırasıyla basılmalı.
           Yanlış sıra → elektrik + tam sıfırlama + hasar.
           Vincin taşıdığı hareketli platform giriş boşluğunu kapatır.
[YENİ-5]  E tuşu: bağlam duyarlı etkileşim (terminaller).
[YENİ-6]  Kapı sistemi: kilitli demir kapılar bulmaca çözülünce yukarı kayar.
[YENİ-7]  Güvenlik düzeyi artan bekçiler: Bölge 6 ve 8'de hız/görüş artırımı.
[YENİ-8]  Bölge özel arka planlar: sunucu rafları, kargo kasaları, vinç rayı.
"""

import pygame, sys, math, random

# ── SABITLER ────────────────────────────────────────────────────────────────────
SW, SH   = 1920, 1080
FPS      = 60
WW       = 9800          # v3: genişletildi (6400 → 9800)
WH       = 1200
GRAVITY  = 980.0
FLOOR    = 1020

# Palet — STEAMPUNK ORANGE/AMBER TEMA
BG       = ( 14,  8,  3)          # koyu kahverengi-siyah zemin
WHITE    = (235, 210, 165)         # sıcak krem/fildişi (soğuk beyaz yok)
CYAN     = (220, 155, 20)          # teal→altın sarısı (ana vurgu)
AMBER    = (255, 140,  0)          # canlı turuncu-amber
RED      = (190,  55, 15)          # pas kırmızısı
ORANGE   = (245, 110, 18)          # parlak turuncu
GRAY     = ( 90,  68, 40)          # sıcak kahverengi-gri
DGRAY    = ( 42,  28, 12)          # koyu deri kahve
LGRAY    = (168, 132, 88)          # açık bronz/ten
MGRAY    = ( 78,  56, 28)          # orta bronz-kahve
RUST     = (140,  70, 18)          # koyu pas/bakır
DRUST    = ( 72,  34,  6)          # çok koyu pas
LRUST    = (200, 110, 35)          # parlak bakır/çelik
YELLOW   = (255, 205, 30)          # sıcak altın sarısı
DGREEN   = ( 52,  40, 10)          # koyu bronz-zeytin (yeşil yok)
LGREEN   = (210, 170, 40)          # parlak altın-pirinç (yeşil→altın)
DARK_BG  = (  8,  4,  1)          # neredeyse siyah sepia
PANEL    = ( 28, 16,  5)           # koyu kahve panel
STRIPE_Y = (230, 145,  0)          # turuncu uyarı şeridi
STRIPE_B = ( 30, 18,  5)           # koyu şerit zemini
BLUE     = (175,  85, 15)          # mavi→koyu bakır-bronz
LBLUE    = (255, 175, 55)          # açık mavi→parlak sarı-turuncu

# Bölge sınırları
ZONE_CONV_X1   =  900
ZONE_CONV_X2   = 1924
ZONE_PATROL_X1 = 1960
ZONE_PATROL_X2 = 3050
ZONE_STEAM_X1  = 3050
ZONE_STEAM_X2  = 3950
ZONE_MACH_X1   = 3950
ZONE_MACH_X2   = 5200
# YENİ bölgeler
ZONE_SERVER_X1 = 5500
ZONE_SERVER_X2 = 7000
ZONE_MAINT_X1  = 7000
ZONE_MAINT_X2  = 8300
ZONE_LOAD_X1   = 8300
ZONE_LOAD_X2   = 9600
ZONE_EXIT_X    = 9640   # v3: güncellendi

_fsml = None

# ── KAMERA ──────────────────────────────────────────────────────────────────────
class Cam:
    def __init__(self):
        self.x=0.; self.y=0.; self.st=0.; self.si=0.
        self.sx=0; self.sy=0; self.sf=1.
    def update(self, dt, px, py, f):
        self.sf += (f - self.sf) * min(1., 4.*dt)
        tx = max(0., min(float(WW-SW), px - SW//2 + self.sf*165.))
        ty = max(0., min(float(WH-SH), py - SH//2 - 60))
        self.x += (tx - self.x) * min(1., 6.*dt)
        self.y += (ty - self.y) * min(1., 6.*dt)
        if self.st > 0:
            self.st -= dt
            i = int(self.si)
            self.sx = random.randint(-i, i)
            self.sy = random.randint(-i, i)
        else:
            self.sx = self.sy = 0
        self.x = max(0., min(float(WW-SW), self.x))
        self.y = max(0., min(float(WH-SH), self.y))
    def shake(self, i, d=.3):
        self.si = i; self.st = d
    @property
    def ox(self): return int(self.x) + self.sx
    @property
    def oy(self): return int(self.y) + self.sy

def resolve(rect, vy, plats):
    on = False
    for p in plats:
        if vy >= 0 and rect.colliderect(p):
            rect.bottom = p.top; vy = 0.; on = True
    return vy, on

# ── OYUNCU ──────────────────────────────────────────────────────────────────────
class Player:
    W=32; H=58; HP=5

    def __init__(self, x, y):
        self.rect = pygame.Rect(x, y, self.W, self.H)
        self.vx = 0.; self.vy = 0.; self.on = False; self.f = 1
        self.hp = self.HP
        self.hc = 0.
        self.dc = 0.
        self.dt = 0.
        self.alive = True
        self.conv_push = 0.
        self.death_landed = False

    def take_hit(self, cam):
        if self.hc > 0 or not self.alive: return
        self.hp = max(0, self.hp - 1)
        self.hc = .75
        cam.shake(7, .24)
        self.vx = -self.f * 180.
        self.vy = -120.
        if self.hp <= 0:
            self.alive = False
            self.hc = 0.
            self.dc = 0.; self.dt = 0.

    def update(self, dt, plats):
        for attr in ("hc", "dc", "dt"):
            v = getattr(self, attr)
            if v > 0: setattr(self, attr, max(0., v - dt))

        if self.alive:
            if self.dt > 0:
                self.vx = self.f * 490. + self.conv_push
            else:
                keys = pygame.key.get_pressed()
                mv = (keys[pygame.K_d] or keys[pygame.K_RIGHT]) - \
                     (keys[pygame.K_a] or keys[pygame.K_LEFT])
                if mv: self.f = mv
                self.vx = mv * 210. + self.conv_push
            keys = pygame.key.get_pressed()
            if (keys[pygame.K_w] or keys[pygame.K_UP] or keys[pygame.K_SPACE]) and self.on:
                self.vy = -490.; self.on = False
        else:
            self.vx *= max(0., 1 - dt * 5)
            if self.on and not self.death_landed:
                self.death_landed = True

        self.vy = min(self.vy + GRAVITY * dt, 1400)
        self.rect.x += int(self.vx * dt)
        self.rect.x = max(0, min(self.rect.x, WW - self.W))
        self.rect.y += int(self.vy * dt)
        self.vy, self.on = resolve(self.rect, self.vy, plats)
        self.conv_push = 0.

    def dash(self):
        if self.dc <= 0 and self.alive:
            self.dt = .14; self.dc = .70; self.vy = min(self.vy, 0)

    def is_dashing(self): return self.dt > 0

    def draw(self, surf, ox, oy):
        if self.alive and self.hc > 0 and int(self.hc * 12) % 2 == 0: return
        bx = self.rect.x - ox
        by = self.rect.y - oy

        if self.dt > 0:
            for i in range(1, 5):
                gs = pygame.Surface((self.W, self.H), pygame.SRCALPHA)
                gs.fill((*CYAN, max(0, 90 - i*24)))
                surf.blit(gs, (bx - self.f*i*15, by))
            for i in range(3):
                ly = by + 8 + i*12
                pygame.draw.line(surf, (*CYAN, max(0, 65 - i*22)),
                                 (bx - self.f*40, ly), (bx - self.f*18, ly), 1)

        body_col = RED if not self.alive else (WHITE if self.hc <= 0 else RED)

        pygame.draw.rect(surf, MGRAY, (bx+2,  by+30, 7, 10))
        pygame.draw.rect(surf, MGRAY, (bx+13, by+30, 7, 10))
        pygame.draw.rect(surf, body_col, (bx, by, self.W, self.H - 10))
        pygame.draw.rect(surf, CYAN, (bx+6, by+6, 10, 8))
        pygame.draw.rect(surf, CYAN, (bx+3, by-14, 16, 14))
        ex = bx + 14 if self.f > 0 else bx + 3
        pygame.draw.rect(surf, (180, 120, 20), (ex, by-10, 5, 3))

    def draw_hud(self, surf, game_t):
        for i in range(self.HP):
            c = RED if i < self.hp else (40, 18, 5)
            pygame.draw.rect(surf, c, (18 + i*38, 18, 30, 14))
            pygame.draw.rect(surf, (68, 26, 8), (18 + i*38, 18, 30, 14), 1)
        pygame.draw.rect(surf, LGRAY, (16, 16, self.HP*38+2, 16), 1)

        lbl = _fsml.render("DASH", True, LGRAY)
        surf.blit(lbl, (18, SH-58))
        bw = 160
        pygame.draw.rect(surf, (28, 16, 5), (18, SH-40, bw, 14))
        if self.dc > 0:
            filled = int(bw * (1. - self.dc / .70))
            pygame.draw.rect(surf, MGRAY, (18, SH-40, filled, 14))
            pygame.draw.rect(surf, LGRAY, (18, SH-40, bw, 14), 1)
        else:
            flash = int(game_t * 6) % 2 == 0
            pygame.draw.rect(surf, CYAN if flash else (155, 100, 10), (18, SH-40, bw, 14))
            pygame.draw.rect(surf, WHITE, (18, SH-40, bw, 14), 1)
            if _fsml:
                rd = _fsml.render("READY", True, WHITE)
                surf.blit(rd, (18 + bw//2 - rd.get_width()//2, SH-42))


# ── NPC ─────────────────────────────────────────────────────────────────────────
class NPC:
    W=32; H=58
    LINES = [
        "So... you finally woke up.",
        "Your weapons?  Sorry.",
        "The scrap grinder got them.",
        "The exit is east — keep moving.",
        "The guards haven't seen you.",
        "Dash past them.  Don't stop.",
    ]
    LINE_DURATION = 2.6

    def __init__(self, x, y):
        self.rect = pygame.Rect(x, y, self.W, self.H)
        self.active = False; self.done = False
        self.line_idx = 0; self.line_t = 0.

    def update(self, dt, px, py):
        if abs(px - self.rect.centerx) < 220 and not self.done:
            self.active = True
        if self.active and not self.done:
            self.line_t += dt
            if self.line_t >= self.LINE_DURATION:
                self.line_t = 0.; self.line_idx += 1
                if self.line_idx >= len(self.LINES):
                    self.done = True; self.active = False

    def draw(self, surf, ox, oy, font):
        bx = self.rect.x - ox
        by = self.rect.y - oy
        pygame.draw.rect(surf, DRUST, (bx+2,  by+30, 7, 10))
        pygame.draw.rect(surf, DRUST, (bx+13, by+30, 7, 10))
        pygame.draw.rect(surf, AMBER, (bx, by, self.W, self.H - 10))
        pygame.draw.rect(surf, (200, 115, 0), (bx+7, by+6, 8, 22))
        pygame.draw.rect(surf, DRUST, (bx, by+24, self.W, 5))
        pygame.draw.rect(surf, (172, 115, 12), (bx+3, by-14, 16, 14))
        pygame.draw.rect(surf, AMBER, (bx+8, by-10, 6, 4))

        if self.active and not self.done and self.line_idx < len(self.LINES):
            line = self.LINES[self.line_idx]
            txt = font.render(line, True, WHITE)
            bw2 = txt.get_width() + 22; bh2 = txt.get_height() + 14
            bx2 = bx - bw2//2 + self.W//2; by2 = by - bh2 - 28
            bg = pygame.Surface((bw2, bh2), pygame.SRCALPHA)
            bg.fill((0, 0, 0, 205)); surf.blit(bg, (bx2, by2))
            pygame.draw.rect(surf, AMBER, (bx2, by2, bw2, bh2), 2)
            surf.blit(txt, (bx2+11, by2+7))
            mx2 = bx + self.W//2
            pygame.draw.polygon(surf, AMBER,
                [(mx2, by-5), (bx2+bw2//2-6, by2+bh2), (bx2+bw2//2+6, by2+bh2)])
            for i in range(len(self.LINES)):
                c = AMBER if i <= self.line_idx else DGRAY
                pygame.draw.circle(surf, c, (bx2+9+i*12, by2+bh2+9), 3)


# ── BEKÇİ AI ────────────────────────────────────────────────────────────────────
class Guard:
    W=38; H=64
    VISION      = 420
    CHASE_RANGE = 560
    NOISE_RANGE = 240

    def __init__(self, x, y, px1, px2, speed_mult=1.0):
        self.rect = pygame.Rect(x, y, self.W, self.H)
        self.vy = 0.; self.f = 1
        self.home_x = float(x)
        self.patrol_x1 = px1; self.patrol_x2 = px2
        self.pd = 1
        self.pt = random.uniform(1.8, 3.2); self.ptimer = 0.
        self.state = "idle"; self.state_t = 0.
        self.attack_t = 0.
        self.alarm = False
        self.speed_mult = speed_mult
        # v3: genişletilmiş görüş alanı için isteğe bağlı parametre
        self.VISION      = int(295 * speed_mult)
        self.CHASE_RANGE = int(400 * speed_mult)
        self.NOISE_RANGE = int(170 * speed_mult)

    def _can_see(self, px, py):
        dx = px - self.rect.centerx; dy = py - self.rect.centery
        if math.hypot(dx, dy) > self.VISION: return False
        return self.f * dx > 0

    def go_suspicious(self):
        if self.state not in ("alert", "chasing"):
            self.state = "suspicious"; self.state_t = 0.

    def update(self, dt, player, plats, eq):
        self.vy += GRAVITY * dt; self.rect.y += int(self.vy * dt)
        self.vy, _ = resolve(self.rect, self.vy, plats)
        self.rect.x = max(self.patrol_x1, min(self.rect.x, self.patrol_x2 - self.W))
        self.state_t += dt

        px = player.rect.centerx; py = player.rect.centery
        dx = px - self.rect.centerx; dist = abs(dx)
        sees = self._can_see(px, py)
        dash_noise = player.is_dashing() and dist < self.NOISE_RANGE

        spd = self.speed_mult

        if self.state == "idle":
            self.ptimer += dt
            self.rect.x += int(self.pd * 62. * spd * dt); self.f = self.pd
            if self.ptimer > self.pt:
                self.pd *= -1; self.ptimer = 0.; self.pt = random.uniform(1.8, 3.2)
            if sees or dash_noise:
                self.state = "suspicious"; self.state_t = 0.

        elif self.state == "suspicious":
            self.f = 1 if dx > 0 else -1
            if self.state_t > 1.1:
                self.state = "alert"; self.state_t = 0.; self.alarm = True
            elif not sees and not dash_noise and self.state_t > 0.65:
                self.state = "idle"

        elif self.state == "alert":
            if self.state_t > 0.55:
                self.state = "chasing"; self.state_t = 0.

        elif self.state == "chasing":
            self.f = 1 if dx > 0 else -1
            self.rect.x += int(self.f * 168. * spd * dt)
            self.attack_t = max(0., self.attack_t - dt)
            if dist < 50 and abs(player.rect.centery - self.rect.centery) < self.H + 12:
                if self.attack_t <= 0:
                    eq.append({"t": "HIT"}); self.attack_t = 0.55
            if dist > self.CHASE_RANGE + 80 or self.state_t > 7.:
                self.state = "returning"; self.state_t = 0.

        elif self.state == "returning":
            dh = self.home_x - self.rect.x
            if abs(dh) > 10:
                self.f = 1 if dh > 0 else -1
                self.rect.x += int(self.f * 90. * spd * dt)
            else:
                self.alarm = False; self.state = "idle"; self.state_t = 0.

    def draw(self, surf, ox, oy, game_t):
        bx = self.rect.x - ox; by = self.rect.y - oy

        if self.state in ("alert", "chasing"):     body = (155, 22, 22)
        elif self.state == "suspicious":           body = (152, 98, 12)
        elif self.state == "returning":            body = DRUST
        else:                                      body = (52, 38, 22)

        leg_col = DRUST if self.state not in ("alert", "chasing") else (108, 16, 16)
        pygame.draw.rect(surf, leg_col, (bx+3,  by+34, 8, 10))
        pygame.draw.rect(surf, leg_col, (bx+15, by+34, 8, 10))
        pygame.draw.rect(surf, body, (bx, by, self.W, self.H-10))
        pygame.draw.rect(surf, DGRAY,  (bx+2,  by+4, 10, 15))
        pygame.draw.rect(surf, DGRAY,  (bx+14, by+4, 10, 15))
        pygame.draw.rect(surf, LGRAY,  (bx+2,  by+4, 10, 15), 1)
        pygame.draw.rect(surf, LGRAY,  (bx+14, by+4, 10, 15), 1)
        pygame.draw.rect(surf, MGRAY, (bx-4,          by+2, 7, 12))
        pygame.draw.rect(surf, MGRAY, (bx+self.W-3,   by+2, 7, 12))
        pygame.draw.rect(surf, MGRAY, (bx+2, by-16, 22, 16))
        pygame.draw.rect(surf, DGRAY, (bx+4, by-14, 18, 10))
        ex = bx + 18 if self.f > 0 else bx + 4
        if self.state in ("alert", "chasing"):    ecol = RED
        elif self.state == "suspicious":          ecol = AMBER
        else:                                     ecol = (160, 110, 25)
        pygame.draw.rect(surf, ecol, (ex, by-11, 5, 4))

        if self.state in ("idle", "returning"):
            bk = bx if self.f > 0 else bx + self.W
            tip_x = bk - self.f * 9
            pygame.draw.polygon(surf, LGRAY,
                [(bk, by+8), (bk, by+20), (tip_x, by+14)])

        hx = bx + self.W//2; hy = by - 22
        if self.state == "suspicious":
            pygame.draw.polygon(surf, AMBER,
                [(hx, hy-10), (hx-6, hy), (hx+6, hy)])
            pygame.draw.rect(surf, AMBER, (hx-1, hy+3, 2, 4))
        elif self.state in ("alert", "chasing") and int(game_t*8) % 2 == 0:
            pygame.draw.circle(surf, RED,   (hx, hy), 7)
            pygame.draw.line(surf,   WHITE, (hx, hy-5), (hx, hy+1), 2)
            pygame.draw.circle(surf, WHITE, (hx, hy+3), 1)

        if self.alarm and int(game_t*7) % 2 == 0:
            pygame.draw.rect(surf, AMBER, (bx-3, by-3, self.W+6, self.H+6), 2)


# ── KONVEYÖR BANDI ──────────────────────────────────────────────────────────────
class ConveyorBelt:
    """
    Gerçekçi endüstriyel konveyör bandı — üçüncü kez, tamamen sıfırdan.

    Görsel katmanlar (arka → ön):
      1.  Destek ayakları  (aralıklı, taban plakası + cıvata)
      2.  Alt çerçeve kirişi  (I-profil, takviye nervürleriyle)
      3.  Dönüş bandı  (alt, iki tambur arasında sarkık parabolik yay)
      4.  Sol/sağ tambur  (dış çelik halka, iç lastik, dönen mil kolları, yatak)
      5.  Üst bant yüzeyi  (koyu lastik + kaymayan kayan dişler/cleats)
      6.  Yan kılavuz rayı  (L-profil, koruyucu flanş)
      7.  Toz / hurda parçacıkları

    Fizik:
      • self.rect.top  = belt üst yüzeyi  (resolve() buraya oturtur)
      • conv_push sadece gerçekten bant yüzeyinde duruluyorken uygulanır
    """
    # ── boyut sabitleri ─────────────────────────────────────────────────────────
    DRUM_R    = 13    # tambur yarıçapı  (px)
    BELT_T    =  7    # bant et kalınlığı görsel (px)
    CLEAT_SP  = 15    # dişler arası adım (dünya px)
    CLEAT_H   =  5    # diş yüksekliği (px)
    CLEAT_W   =  4    # diş eni (px)
    FRAME_TH  =  7    # alt kiriş yüksekliği (px)
    LEG_W     =  9    # ayak eni (px)
    LEG_SP    = 70    # ayaklar arası açıklık (px)
    PART_INT  = 0.14  # parçacık spawn aralığı (s)
    N_SPOKES  =  4    # tambur kol sayısı

    def __init__(self, x, y, w, speed):
        self.bx     = x          # belt dünya sol X
        self.by     = y          # belt üst yüzeyi Y  (oyuncu ayağı burada)
        self.bw     = w
        self.speed  = speed      # px/s  (+= sağ, -= sol)
        # Fizik rect: top = belt yüzeyi
        self.rect   = pygame.Rect(x, y, w, self.DRUM_R * 2 + 6)
        self._scroll      = 0.0  # kümülatif scroll (dünya px)
        self._drum_angle  = 0.0  # tambur açısı (rad)
        self._spawn_acc   = 0.0
        self.particles    = []

    # ── güncelle ────────────────────────────────────────────────────────────────
    def update(self, dt, player):
        # Scroll ve tambur açısı
        self._scroll     += self.speed * dt
        self._drum_angle += (self.speed * dt) / self.DRUM_R  # arc = r*θ

        # Parçacık üretimi — birikimli zamanlayıcı (dt spike'a karşı güvenli)
        self._spawn_acc += dt
        while self._spawn_acc >= self.PART_INT:
            self._spawn_acc -= self.PART_INT
            spx = random.uniform(self.bx + 18, self.bx + self.bw - 18)
            vx  = self.speed * 0.38 + random.uniform(-22, 22)
            self.particles.append({
                "x":  float(spx),
                "y":  float(self.by),
                "vx": vx,
                "vy": random.uniform(-45, -115),
                "w":  random.randint(2, 11), "h": random.randint(2, 6),
                "rot": random.uniform(0, 360),
                "rs":  random.uniform(-190, 190),
                "col": random.choice([RUST, DRUST, GRAY, DGRAY, (58, 46, 36)]),
                "life": random.uniform(0.35, 1.0), "t": 0.0,
            })

        for p in self.particles:
            p["t"]   += dt
            p["vy"]  += GRAVITY * dt * 0.26
            p["x"]   += p["vx"] * dt
            p["y"]   += p["vy"] * dt
            p["rot"] += p["rs"] * dt
        self.particles = [p for p in self.particles
                          if p["t"] < p["life"] and p["y"] < WH + 50]

        # Oyuncu itişi — sadece bant yüzeyine tam oturunca
        pr = player.rect
        on_belt = (pr.bottom >= self.by and
                   pr.bottom <= self.by + 16 and
                   pr.right  >  self.bx + 8 and
                   pr.left   <  self.bx + self.bw - 8 and
                   player.vy >= 0)
        if on_belt:
            player.conv_push += self.speed

    # ── çiz ─────────────────────────────────────────────────────────────────────
    def draw(self, surf, ox, oy, game_t):
        sx  = self.bx - ox   # belt sol kenarı (ekran)
        sy  = self.by - oy   # belt üst yüzeyi (ekran)
        sw  = self.bw

        if sx + sw < -120 or sx > SW + 120:
            return

        dr      = self.DRUM_R
        drum_cy = sy + dr        # tambur merkezi Y (ekran)
        drum_lx = sx + dr        # sol tambur X
        drum_rx = sx + sw - dr   # sağ tambur X
        floor_y = int(FLOOR - oy)

        # ── 1. Destek ayakları ────────────────────────────────────────────────
        leg_top_y  = int(drum_cy + dr + self.FRAME_TH)
        leg_bot_y  = floor_y + 6
        leg_h      = leg_bot_y - leg_top_y

        for leg_wx in range(int(self.bx + dr + 14),
                            int(self.bx + self.bw - dr - 10),
                            self.LEG_SP):
            lx = leg_wx - ox
            if not (-self.LEG_W * 3 < lx < SW + self.LEG_W * 3):
                continue
            # Ayak gövdesi
            pygame.draw.rect(surf, DGRAY,
                (int(lx) - self.LEG_W // 2, leg_top_y, self.LEG_W, leg_h))
            # Öne bakan yüzey parlaması
            pygame.draw.line(surf, MGRAY,
                (int(lx) - self.LEG_W // 2, leg_top_y),
                (int(lx) - self.LEG_W // 2, leg_bot_y), 1)
            # Taban plakası + cıvatalar
            pygame.draw.rect(surf, MGRAY,
                (int(lx) - self.LEG_W - 2, floor_y - 2, self.LEG_W * 2 + 4, 6))
            for blt in (-self.LEG_W + 1, self.LEG_W - 1):
                pygame.draw.circle(surf, LGRAY,
                    (int(lx) + blt, floor_y + 1), 2)

        # ── 2. Alt çerçeve kirişi (I-profil) ─────────────────────────────────
        kx1      = int(drum_lx - dr + 3)
        kx2      = int(drum_rx + dr - 3)
        kw       = kx2 - kx1
        k_top_y  = int(drum_cy + dr)
        # Gövde
        pygame.draw.rect(surf, (44, 28, 10), (kx1, k_top_y, kw, self.FRAME_TH))
        # Üst flanş
        pygame.draw.line(surf, MGRAY, (kx1 - 3, k_top_y),     (kx2 + 3, k_top_y),     2)
        # Alt flanş
        pygame.draw.line(surf, MGRAY, (kx1 - 3, k_top_y + self.FRAME_TH),
                                       (kx2 + 3, k_top_y + self.FRAME_TH), 2)
        # Takviye nervürleri
        for nrv in range(kx1 + 18, kx2 - 4, 26):
            pygame.draw.line(surf, (66, 44, 18),
                (nrv, k_top_y + 1), (nrv, k_top_y + self.FRAME_TH - 1), 1)

        # ── 3. Dönüş bandı (alt, sarkık parabolik yay) ───────────────────────
        rb_y0   = int(drum_cy + dr - 2)   # yay başlangıç / bitiş Y
        rb_sag  = 6                        # orta noktada sarkma (px)
        rb_x1   = int(drum_lx)
        rb_x2   = int(drum_rx)
        rb_w    = rb_x2 - rb_x1
        if rb_w > 0:
            step = max(2, rb_w // 45)
            for ti in range(0, rb_w, step):
                t       = ti / rb_w
                sag     = int(rb_sag * 4 * t * (1.0 - t))
                cur_y   = rb_y0 + sag
                seg_w   = min(step + 1, rb_w - ti)
                # Bant eti
                pygame.draw.rect(surf, (25, 20, 15),
                    (rb_x1 + ti, cur_y, seg_w, 6))
            # Üst kenar çizgisi (dönüş bandı profili)
            for ti in range(0, rb_w - step, step):
                t1  = ti / rb_w;        sag1 = int(rb_sag * 4 * t1 * (1 - t1))
                t2  = (ti + step) / rb_w; sag2 = int(rb_sag * 4 * t2 * (1 - t2))
                pygame.draw.line(surf, (48, 38, 28),
                    (rb_x1 + ti, rb_y0 + sag1),
                    (rb_x1 + ti + step, rb_y0 + sag2), 1)

        # ── 4. Tambur gövdeleri ──────────────────────────────────────────────
        for dcx in (drum_lx, drum_rx):
            dxi = int(dcx); dyi = int(drum_cy)

            # Gölge
            gs = pygame.Surface((dr * 2 + 8, dr * 2 + 8), pygame.SRCALPHA)
            pygame.draw.circle(gs, (0, 0, 0, 44), (dr + 4, dr + 4), dr + 3)
            surf.blit(gs, (dxi - dr - 2, dyi - dr - 2))

            # Dış çelik halka
            pygame.draw.circle(surf, (52, 62, 70), (dxi, dyi), dr)
            pygame.draw.circle(surf, MGRAY,          (dxi, dyi), dr,     2)
            # Lastik yüzey tabakası (tambur dışı)
            pygame.draw.circle(surf, (34, 28, 20), (dxi, dyi), dr - 3)
            pygame.draw.circle(surf, (50, 40, 30), (dxi, dyi), dr - 3, 1)

            # Dönen mil kolları
            for i in range(self.N_SPOKES):
                angle = self._drum_angle + i * (math.pi / self.N_SPOKES)
                ex = dxi + int(math.cos(angle) * (dr - 5))
                ey = dyi + int(math.sin(angle) * (dr - 5))
                pygame.draw.line(surf, LGRAY, (dxi, dyi), (ex, ey), 1)

            # Yatak (bearing) plakası — tambur üstünde
            bw2 = 12
            pygame.draw.rect(surf, LGRAY,
                (dxi - bw2 // 2, dyi - dr - 3, bw2, 5))
            pygame.draw.rect(surf, MGRAY,
                (dxi - bw2 // 2, dyi - dr - 3, bw2, 5), 1)
            # Yatak cıvataları
            for blt in (-4, 4):
                pygame.draw.circle(surf, DGRAY, (dxi + blt, dyi - dr - 1), 2)

            # Mil merkezi
            pygame.draw.circle(surf, AMBER, (dxi, dyi), 5)
            pygame.draw.circle(surf, (180, 110, 0), (dxi, dyi), 3)
            pygame.draw.circle(surf, DRUST, (dxi, dyi), 1)

        # ── 5. Üst bant yüzeyi ───────────────────────────────────────────────
        bl = int(drum_lx)
        br = int(drum_rx)
        bw2 = br - bl
        bt  = sy            # bant üst
        bb  = sy + self.BELT_T  # bant alt (görsel)

        if bw2 > 4:
            # Kırpma alanı: sadece tambur arası
            old_clip = surf.get_clip()
            surf.set_clip(pygame.Rect(bl, bt - self.CLEAT_H - 1, bw2, self.CLEAT_H + self.BELT_T + 2))

            # Lastik gövde
            pygame.draw.rect(surf, (28, 22, 16), (bl, bt, bw2, self.BELT_T))

            # Bant üzeri yatay doku çizgileri (statik, hafif aşınma desen)
            for ty in range(bt + 1, bb, 2):
                pygame.draw.line(surf, (36, 28, 20), (bl, ty), (br, ty), 1)

            # Hareketli dişler (cleats) — scroll dünya koordinatında
            base_offset = self._scroll % self.CLEAT_SP
            if self.speed < 0:
                base_offset = (self.CLEAT_SP - ((-self._scroll) % self.CLEAT_SP)) % self.CLEAT_SP

            n = int(bw2 / self.CLEAT_SP) + 4
            for i in range(-1, n + 1):
                cx = bl + int(base_offset) + i * self.CLEAT_SP
                if cx < bl - self.CLEAT_SP or cx > br + self.CLEAT_SP:
                    continue
                # Diş gövdesi (lastik, biraz açık)
                pygame.draw.rect(surf, (62, 50, 36),
                    (cx, bt - self.CLEAT_H, self.CLEAT_W, self.CLEAT_H + 1))
                # Diş ön yüzü (daha açık — ışık etkisi)
                pygame.draw.line(surf, (88, 70, 50),
                    (cx, bt - self.CLEAT_H), (cx, bt), 1)
                # Diş üst kenarı parlak
                pygame.draw.line(surf, (110, 88, 62),
                    (cx, bt - self.CLEAT_H),
                    (cx + self.CLEAT_W - 1, bt - self.CLEAT_H), 1)

            # Bant alt profil çizgisi
            pygame.draw.line(surf, (46, 36, 26), (bl, bb), (br, bb), 1)

            surf.set_clip(old_clip)

        # ── 6. Yan kılavuz rayı (L-profil, her iki kenar) ────────────────────
        rail_h = 9
        rail_y = sy - rail_h
        rx1    = int(drum_lx - dr)
        rx2    = int(drum_rx + dr)
        rw2    = rx2 - rx1

        # Arka duvar (gövde)
        pygame.draw.rect(surf, DGRAY,  (rx1, rail_y, rw2, rail_h))
        # Üst flanş (yatay plaka)
        pygame.draw.line(surf, LGRAY,  (rx1, rail_y),     (rx2, rail_y),     2)
        # Alt flanş (bant kenarına oturur)
        pygame.draw.line(surf, MGRAY,  (rx1, rail_y + rail_h), (rx2, rail_y + rail_h), 1)
        # Kenar kapak plakaları
        for cap_x in (rx1 - 3, rx2 - 3):
            pygame.draw.rect(surf, MGRAY, (cap_x, rail_y - 1, 6, rail_h + 2))
            pygame.draw.rect(surf, LGRAY, (cap_x, rail_y - 1, 6, rail_h + 2), 1)

        # ── 7. Parçacıklar ────────────────────────────────────────────────────
        for p in self.particles:
            px2 = int(p["x"] - ox)
            py2 = int(p["y"] - oy)
            if not (-30 < px2 < SW + 30 and -50 < py2 < SH + 20):
                continue
            prog  = p["t"] / p["life"]
            alpha = int(210 * (1.0 - prog))
            pw    = max(1, p["w"])
            ph    = max(1, p["h"])
            ps    = pygame.Surface((pw, ph), pygame.SRCALPHA)
            pygame.draw.rect(ps, (*p["col"], alpha), (0, 0, pw, ph))
            rot = pygame.transform.rotate(ps, p["rot"])
            surf.blit(rot, (px2 - rot.get_width()  // 2,
                            py2 - rot.get_height() // 2))



# ── KARGO KUTUSU ───────────────────────────────────────────────────────────────
class CargoBox:
    W, H = 26, 20
    SKINS = [
        ((70, 44, 16),  (106, 68, 26),  "CARGO"),
        ((34, 52, 24),  ( 50, 76, 34),  " BIO "),
        ((46, 36, 18),  ( 70, 54, 28),  "FRAG."),
        ((60, 32, 12),  ( 88, 50, 18),  "CTRL "),
    ]

    def __init__(self, x, y, skin_idx=0):
        self.rect = pygame.Rect(int(x - self.W // 2), int(y - self.H), self.W, self.H)
        self.vx = 0.; self.vy = 0.; self.on_ground = False
        sk = self.SKINS[skin_idx % len(self.SKINS)]
        self.dark, self.lite, self.lbl = sk
        self.alive  = True
        self.dying  = False
        self.die_t  = 0.

    def kill(self):
        if not self.dying:
            self.dying = True
            self.vy = min(self.vy, -55.)

    def update(self, dt, plats):
        if self.dying:
            self.die_t += dt
            self.vy = min(self.vy + GRAVITY * dt, 900.)
            self.rect.y += int(self.vy * dt)
            if self.die_t > 0.5:
                self.alive = False
            return
        self.vy = min(self.vy + GRAVITY * dt, 900.)
        self.rect.x += int(self.vx * dt)
        self.rect.y += int(self.vy * dt)
        self.vy, self.on_ground = resolve(self.rect, self.vy, plats)

    def draw(self, surf, ox, oy, font):
        if not self.alive: return
        sx = self.rect.x - ox; sy = self.rect.y - oy
        if not (-40 < sx < SW + 40 and -40 < sy < SH + 30): return
        if self.dying:
            prog  = min(1., self.die_t / 0.5)
            alpha = int(255 * (1 - prog))
            sc    = max(0.12, 1.0 - prog * 0.72)
            w     = max(2, int(self.W * sc)); h = max(2, int(self.H * sc))
            s = pygame.Surface((w, h), pygame.SRCALPHA)
            pygame.draw.rect(s, (*self.dark, alpha), (0, 0, w, h))
            pygame.draw.rect(s, (*self.lite, alpha), (0, 0, w, h), 1)
            surf.blit(s, (sx + self.W // 2 - w // 2, sy + self.H // 2 - h // 2))
            return
        r = pygame.Rect(sx, sy, self.W, self.H)
        pygame.draw.rect(surf, self.dark, r)
        pygame.draw.rect(surf, self.lite, r, 2)
        pygame.draw.line(surf, self.lite, (sx + 2, sy + 2), (sx + self.W - 3, sy + self.H - 3), 1)
        pygame.draw.line(surf, self.lite, (sx + self.W - 3, sy + 2), (sx + 2, sy + self.H - 3), 1)
        mid_y = sy + self.H // 2
        pygame.draw.line(surf, self.lite, (sx, mid_y), (sx + self.W, mid_y), 1)
        if font:
            lbl = font.render(self.lbl, True, self.lite)
            surf.blit(lbl, (sx + self.W // 2 - lbl.get_width() // 2,
                            mid_y - lbl.get_height() // 2))


# ── ISLEME MAKINESI ─────────────────────────────────────────────────────────────
class ProcessingMachine:
    MW = 124; MH = 258

    def __init__(self, x):
        self.x = x; self.y = FLOOR - self.MH
        self.gear_a   = 0.; self.gear2_a  = 0.
        self.proc_t   = 0.; self.processing = False
        self.shake    = 0.
        self.sparks   = []; self.smoke = []

    def eat(self, box):
        box.kill()
        self.processing = True; self.proc_t = 0.; self.shake = 0.26
        cx = float(self.x + 24); cy = float(FLOOR - 88)
        for _ in range(28):
            a  = random.uniform(math.pi * 0.5, math.pi * 1.5)
            sp = random.uniform(55, 260)
            self.sparks.append({
                "x": cx, "y": cy,
                "vx": math.cos(a) * sp, "vy": math.sin(a) * sp - 75,
                "life": random.uniform(0.18, 0.58), "t": 0.,
                "col": random.choice([YELLOW, AMBER, ORANGE, (255, 88, 5)])
            })
        for _ in range(10):
            self.smoke.append({
                "x": float(self.x + self.MW // 2), "y": float(self.y + 12),
                "vx": random.uniform(-22, 22), "vy": random.uniform(-65, -120),
                "r": random.randint(5, 13), "life": random.uniform(0.55, 1.15), "t": 0.
            })

    def update(self, dt):
        rpm = 3.9 if self.processing else 1.1
        self.gear_a  += rpm * dt; self.gear2_a -= rpm * 0.62 * dt
        if self.processing:
            self.proc_t += dt
            if self.proc_t > 0.95: self.processing = False
        self.shake = max(0., self.shake - dt * 2.1)
        for s in self.sparks:
            s["t"] += dt; s["vy"] += GRAVITY * dt * 0.40
            s["x"] += s["vx"] * dt; s["y"] += s["vy"] * dt
            s["vx"] *= max(0., 1 - dt * 2.5)
        self.sparks = [s for s in self.sparks if s["t"] < s["life"]]
        for sm in self.smoke:
            sm["t"] += dt; sm["x"] += sm["vx"] * dt; sm["y"] += sm["vy"] * dt
            sm["r"]  = min(38, sm["r"] + int(sm["r"] * dt * 0.55))
            sm["vx"] *= max(0., 1 - dt * 0.65)
        self.smoke = [sm for sm in self.smoke if sm["t"] < sm["life"]]

    def draw(self, surf, ox, oy, game_t):
        bsx = self.x - ox; bsy = self.y - oy
        fsy = int(FLOOR - oy)
        if bsx + self.MW < -50 or bsx > SW + 50: return
        shx = (int(random.uniform(-2, 2)) if self.shake > 0.06 else 0)
        shy = (int(random.uniform(-1, 1)) if self.shake > 0.06 else 0)
        sx = int(bsx) + shx; sy = int(bsy) + shy

        # Duman
        for sm in self.smoke:
            smx = int(sm["x"] - ox) + shx; smy = int(sm["y"] - oy) + shy
            prog = sm["t"] / sm["life"]; a = int(95 * (1 - prog)); r = max(1, sm["r"])
            s = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
            pygame.draw.circle(s, (68, 68, 68, a), (r, r), r)
            surf.blit(s, (smx - r, smy - r))

        body_c = (18, 26, 34)
        if self.processing:
            pulse = abs(math.sin(game_t * 9)) * 0.38
            body_c = (min(255, int(18 * (1 + pulse * 1.3))), int(26 * (1 + pulse * 0.35)), 34)
        pygame.draw.rect(surf, body_c, (sx, sy, self.MW, self.MH))
        pygame.draw.rect(surf, MGRAY,  (sx, sy, self.MW, self.MH), 3)
        for rx in range(sx + 20, sx + self.MW - 4, 24):
            pygame.draw.line(surf, (44, 28, 10), (rx, sy + 6), (rx, sy + self.MH - 6), 1)
        for seam_dy in (62, 132, 192):
            sey = sy + seam_dy
            pygame.draw.line(surf, (44, 28, 10), (sx + 3, sey), (sx + self.MW - 3, sey), 2)
            for rx in range(sx + 8, sx + self.MW - 3, 14):
                pygame.draw.circle(surf, MGRAY, (rx, sey), 2)

        # Huni
        hp = [(sx-24, sy+2),(sx+self.MW+24, sy+2),(sx+self.MW-10, sy-46),(sx+10, sy-46)]
        pygame.draw.polygon(surf, (36, 22, 8), hp)
        pygame.draw.polygon(surf, MGRAY, hp, 2)
        pygame.draw.rect(surf, (18, 10, 3), (sx+12, sy-46, self.MW-24, 48))
        pygame.draw.rect(surf, RUST, (sx+12, sy-46, self.MW-24, 48), 1)
        for gx in range(sx + 18, sx + self.MW - 13, 12):
            pygame.draw.line(surf, (58, 36, 14), (gx, sy-44), (gx, sy-2), 1)

        # Gozlem penceresi
        pw_cx = sx + self.MW // 2; pw_cy = sy + 74; pw_r = 34
        pygame.draw.circle(surf, (18, 10, 3), (pw_cx, pw_cy), pw_r)
        pygame.draw.circle(surf, LGRAY,        (pw_cx, pw_cy), pw_r, 4)
        pygame.draw.circle(surf, MGRAY,        (pw_cx, pw_cy), pw_r+5, 2)
        for ci in range(8):
            ca = ci * (math.pi / 4)
            pygame.draw.circle(surf, AMBER,
                (pw_cx+int(math.cos(ca)*(pw_r+2)), pw_cy+int(math.sin(ca)*(pw_r+2))), 2)

        # Ana disli
        n_t=12; gr=pw_r-8; tooth_l=8
        for ti in range(n_t):
            a1 = self.gear_a + ti*(math.tau/n_t)
            tx=pw_cx+int(math.cos(a1)*(gr+tooth_l)); ty=pw_cy+int(math.sin(a1)*(gr+tooth_l))
            b1x=pw_cx+int(math.cos(a1-0.14)*gr); b1y=pw_cy+int(math.sin(a1-0.14)*gr)
            b2x=pw_cx+int(math.cos(a1+0.14)*gr); b2y=pw_cy+int(math.sin(a1+0.14)*gr)
            pygame.draw.polygon(surf, RUST,  [(tx,ty),(b1x,b1y),(b2x,b2y)])
            pygame.draw.polygon(surf, LRUST, [(tx,ty),(b1x,b1y),(b2x,b2y)], 1)
        pygame.draw.circle(surf, RUST,  (pw_cx, pw_cy), gr-1)
        pygame.draw.circle(surf, LRUST, (pw_cx, pw_cy), gr-1, 1)
        for ti in range(4):
            sa = self.gear_a + ti*(math.pi*0.5)
            ix=pw_cx+int(math.cos(sa)*(gr-5)); iy=pw_cy+int(math.sin(sa)*(gr-5))
            pygame.draw.line(surf, LRUST, (pw_cx,pw_cy), (ix,iy), 3)
        pygame.draw.circle(surf, AMBER, (pw_cx,pw_cy), 7)
        pygame.draw.circle(surf, (180,110,0), (pw_cx,pw_cy), 4)
        pygame.draw.circle(surf, DRUST, (pw_cx,pw_cy), 2)

        # Kucuk karsi disli
        sg_r=11; sg_cx=pw_cx+gr+sg_r-2; sg_cy=pw_cy-gr+8; n_t2=8
        for ti in range(n_t2):
            a1=self.gear2_a+ti*(math.tau/n_t2)
            tx2=sg_cx+int(math.cos(a1)*(sg_r+4)); ty2=sg_cy+int(math.sin(a1)*(sg_r+4))
            b1x=sg_cx+int(math.cos(a1-0.18)*sg_r); b1y=sg_cy+int(math.sin(a1-0.18)*sg_r)
            b2x=sg_cx+int(math.cos(a1+0.18)*sg_r); b2y=sg_cy+int(math.sin(a1+0.18)*sg_r)
            pygame.draw.polygon(surf, DGRAY, [(tx2,ty2),(b1x,b1y),(b2x,b2y)])
            pygame.draw.polygon(surf, MGRAY, [(tx2,ty2),(b1x,b1y),(b2x,b2y)], 1)
        pygame.draw.circle(surf, DGRAY, (sg_cx,sg_cy), sg_r)
        pygame.draw.circle(surf, MGRAY, (sg_cx,sg_cy), sg_r, 1)
        pygame.draw.circle(surf, LGRAY, (sg_cx,sg_cy), 3)

        glass = pygame.Surface((pw_r*2, pw_r*2), pygame.SRCALPHA)
        gc = (255,120,10,35) if self.processing else (120,80,20,20)
        pygame.draw.circle(glass, gc, (pw_r,pw_r), pw_r)
        surf.blit(glass, (pw_cx-pw_r, pw_cy-pw_r))
        pygame.draw.circle(surf, LGRAY, (pw_cx,pw_cy), pw_r, 1)

        # Kontrol paneli
        cp_x=sx+10; cp_y=sy+self.MH-100
        pygame.draw.rect(surf, PANEL, (cp_x, cp_y, 60, 54))
        pygame.draw.rect(surf, MGRAY, (cp_x, cp_y, 60, 54), 1)
        pygame.draw.rect(surf, DGRAY, (cp_x+2, cp_y+2, 56, 26))
        for li,(lxo,con,coff) in enumerate([(7,RED,(28,4,4)),(22,AMBER,(30,18,4)),(37,YELLOW,(40,28,4))]):
            is_on=((li==2 and not self.processing)or(li==0 and self.processing and int(game_t*6)%2==0)or(li==1 and self.processing))
            c=con if is_on else coff
            pygame.draw.circle(surf,c,(cp_x+lxo,cp_y+13),5)
            pygame.draw.circle(surf,LGRAY,(cp_x+lxo,cp_y+13),5,1)
            if is_on:
                g=pygame.Surface((16,16),pygame.SRCALPHA)
                pygame.draw.circle(g,(*c,52),(8,8),7)
                surf.blit(g,(cp_x+lxo-8,cp_y+5))
        pygame.draw.circle(surf,DGRAY,(cp_x+14,cp_y+38),10)
        pygame.draw.circle(surf,MGRAY,(cp_x+14,cp_y+38),10,1)
        for ti in range(7):
            ta=-math.pi*0.72+ti*(math.pi*1.44/6)
            pygame.draw.line(surf,LGRAY,(cp_x+14+int(math.cos(ta)*8),cp_y+38+int(math.sin(ta)*8)),(cp_x+14+int(math.cos(ta)*10),cp_y+38+int(math.sin(ta)*10)),1)
        na=game_t*2.4 if self.processing else math.pi*0.22
        pygame.draw.line(surf,RED,(cp_x+14,cp_y+38),(cp_x+14+int(math.cos(na)*7),cp_y+38+int(math.sin(na)*7)),2)
        pygame.draw.circle(surf,DGRAY,(cp_x+44,cp_y+38),9)
        pygame.draw.circle(surf,MGRAY,(cp_x+44,cp_y+38),9,1)
        ka=game_t*0.85+(math.pi*0.5 if self.processing else 0)
        pygame.draw.line(surf,AMBER,(cp_x+44,cp_y+38),(cp_x+44+int(math.cos(ka)*6),cp_y+38+int(math.sin(ka)*6)),2)

        # Giris acikligi
        belt_sy=int(FLOOR-46-oy); apt_h=30
        pygame.draw.rect(surf,(6,10,16),(sx-2,belt_sy-apt_h+6,20,apt_h))
        pygame.draw.rect(surf,MGRAY,(sx-2,belt_sy-apt_h+6,20,apt_h),1)
        for rly in (belt_sy, belt_sy-apt_h+6):
            pygame.draw.line(surf,MGRAY,(sx-36,rly),(sx+2,rly),2)

        # Cikis borusu
        pipe_y=sy+168
        pygame.draw.rect(surf,DGRAY,(sx+self.MW-1,pipe_y,48,22))
        pygame.draw.line(surf,MGRAY,(sx+self.MW-1,pipe_y),(sx+self.MW+47,pipe_y),2)
        pygame.draw.line(surf,(10,16,22),(sx+self.MW-1,pipe_y+22),(sx+self.MW+47,pipe_y+22),2)
        pygame.draw.rect(surf,RUST,(sx+self.MW+42,pipe_y-5,12,32))
        pygame.draw.rect(surf,LRUST,(sx+self.MW+42,pipe_y-5,12,32),1)
        if self.processing and int(game_t*6)%3==0:
            for _ in range(2):
                pygame.draw.circle(surf,RUST,(sx+self.MW+52,random.randint(pipe_y+5,pipe_y+17)),2)

        # Zemin civatalari
        for blt_x in range(sx+14,sx+self.MW,22):
            pygame.draw.rect(surf,MGRAY,(blt_x-5,fsy-9,10,11))
            pygame.draw.rect(surf,LGRAY,(blt_x-5,fsy-9,10,11),1)
            pygame.draw.circle(surf,DGRAY,(blt_x,fsy-4),3)
            pygame.draw.circle(surf,AMBER,(blt_x,fsy-4),1)

        if self.processing and int(game_t*5)%2==0 and _fsml:
            t=_fsml.render("PROCESSING...",True,AMBER)
            surf.blit(t,(sx+self.MW//2-t.get_width()//2,sy+152))

        # Kivilcimlar
        for sp in self.sparks:
            spx=int(sp["x"]-ox)+shx; spy=int(sp["y"]-oy)+shy
            if not (-10<spx<SW+10 and -60<spy<SH+10): continue
            prog=sp["t"]/sp["life"]; a=int(255*(1-prog)); r=max(1,int(3*(1-prog)))
            gs=pygame.Surface((r*2+2,r*2+2),pygame.SRCALPHA)
            pygame.draw.circle(gs,(*sp["col"],a),(r+1,r+1),r)
            surf.blit(gs,(spx-r-1,spy-r-1))


# ── KONVEYOR SISTEMI ─────────────────────────────────────────────────────────────
class ConveyorSystem:
    BELT_CFGS = [
        ( 900, FLOOR - 46, 380, +140.),
        (1285, FLOOR - 46, 325, +125.),
        (1615, FLOOR - 46, 305, +148.),
    ]
    MACHINE_X      = 1924
    SPAWN_INTERVAL = 2.8

    def __init__(self):
        self.belts   = [ConveyorBelt(x, y, w, spd)
                        for x, y, w, spd in self.BELT_CFGS]
        self.machine = ProcessingMachine(self.MACHINE_X)
        self.boxes   = []
        self._spawn_t = 1.5
        self._skin_i  = 0
        self.plat_rects = [pygame.Rect(x, y, w, 18)
                           for x, y, w, _ in self.BELT_CFGS]
        self._box_plats = self.plat_rects + [pygame.Rect(0, FLOOR, WW, 140)]

    def update(self, dt, player):
        for belt in self.belts:
            belt.update(dt, player)
        self.machine.update(dt)
        self._spawn_t += dt
        if self._spawn_t >= self.SPAWN_INTERVAL:
            self._spawn_t = 0.
            bx, by, _, spd = self.BELT_CFGS[0]
            box = CargoBox(bx + 34, by, self._skin_i % len(CargoBox.SKINS))
            self._skin_i += 1; box.vx = spd
            self.boxes.append(box)
        for box in self.boxes:
            box.update(dt, self._box_plats)
        for box in self.boxes:
            if box.dying or not box.on_ground: continue
            for bx, by, bw, spd in self.BELT_CFGS:
                on_this = (box.rect.right > bx+5 and box.rect.left < bx+bw-5
                           and abs(box.rect.bottom - by) < 10)
                if on_this:
                    box.vx = spd; break
        mach_x = self.MACHINE_X
        for box in self.boxes:
            if not box.dying and box.on_ground and box.rect.right >= mach_x - 2:
                self.machine.eat(box)
        self.boxes = [b for b in self.boxes if b.alive]

    def draw(self, surf, ox, oy, game_t):
        self._draw_transitions(surf, ox, oy)
        for belt in self.belts: belt.draw(surf, ox, oy, game_t)
        for box  in self.boxes: box.draw(surf, ox, oy, _fsml)
        self.machine.draw(surf, ox, oy, game_t)

    def _draw_transitions(self, surf, ox, oy):
        belt_sy = int(FLOOR - 46 - oy)
        for i in range(len(self.BELT_CFGS) - 1):
            bx_end  = self.BELT_CFGS[i][0]  + self.BELT_CFGS[i][2]
            bx_next = self.BELT_CFGS[i+1][0]
            ex = int(bx_end - ox); nx = int(bx_next - ox)
            gap = nx - ex
            if gap <= 0 or gap > 90: continue
            pygame.draw.rect(surf, (26,36,46), (ex-1, belt_sy-1, gap+2, 8))
            pygame.draw.line(surf, LGRAY, (ex, belt_sy), (nx, belt_sy), 2)
            pygame.draw.line(surf, MGRAY, (ex, belt_sy+6), (nx, belt_sy+6), 1)
            mid_x = (ex + nx) // 2
            pygame.draw.rect(surf, LGRAY,  (mid_x-5, belt_sy-4, 10, 13))
            pygame.draw.rect(surf, MGRAY,  (mid_x-5, belt_sy-4, 10, 13), 1)
            pygame.draw.circle(surf, AMBER, (mid_x, belt_sy+2), 3)
        last_end_x = int(self.BELT_CFGS[-1][0] + self.BELT_CFGS[-1][2] - ox)
        mach_x     = int(self.MACHINE_X - ox)
        if 0 < mach_x - last_end_x < 80:
            pygame.draw.line(surf, MGRAY,      (last_end_x, belt_sy), (mach_x, belt_sy), 2)
            pygame.draw.line(surf, (18,26,36), (last_end_x, belt_sy+6), (mach_x, belt_sy+6), 1)


# ── BUHAR JETİ ──────────────────────────────────────────────────────────────────
class SteamVent:
    BURST_DUR = 0.85; PAUSE_DUR = 2.2

    def __init__(self, x, y, burst_h=115):
        self.rect = pygame.Rect(x, y, 32, 16)
        self.burst_h = burst_h
        self.bursting = False; self.cycle_t = 0.; self.particles = []

    def update(self, dt):
        self.cycle_t += dt
        limit = self.BURST_DUR if self.bursting else self.PAUSE_DUR
        if self.cycle_t >= limit:
            self.cycle_t = 0.; self.bursting = not self.bursting
        if self.bursting:
            for _ in range(5):
                self.particles.append({
                    "x": float(self.rect.centerx) + random.uniform(-8, 8),
                    "y": float(self.rect.top),
                    "vx": random.uniform(-25, 25),
                    "vy": random.uniform(-175, -310),
                    "r": random.randint(5, 16),
                    "life": random.uniform(.3, .72), "t": 0.
                })
        for p in self.particles:
            p["t"] += dt; p["x"] += p["vx"]*dt; p["y"] += p["vy"]*dt
            p["vx"] *= max(0., 1-dt*2); p["vy"] *= max(0., 1-dt*1.4)
        self.particles = [p for p in self.particles if p["t"] < p["life"]]

    def hazard_rect(self):
        if self.bursting:
            return pygame.Rect(self.rect.x-6, self.rect.top-self.burst_h,
                               self.rect.w+12, self.burst_h)
        return None

    def draw(self, surf, ox, oy):
        dr = self.rect.move(-ox, -oy)
        if dr.x+dr.w < -60 or dr.x > SW+60: return
        pygame.draw.rect(surf, DGRAY, dr)
        pygame.draw.rect(surf, LGRAY, dr, 2)
        nw = 14
        pygame.draw.rect(surf, MGRAY, (dr.x+dr.w//2-nw//2, dr.y-6, nw, 8))
        pygame.draw.rect(surf, LGRAY, (dr.x+dr.w//2-nw//2, dr.y-6, nw, 8), 1)
        if not self.bursting and self.cycle_t > self.PAUSE_DUR*.65:
            prog = (self.cycle_t - self.PAUSE_DUR*.65) / (self.PAUSE_DUR*.35)
            a = int(40 * prog)
            g = pygame.Surface((self.rect.w+12, int(self.burst_h*prog*.4)), pygame.SRCALPHA)
            g.fill((210, 175, 130, a))
            surf.blit(g, (dr.x-6, dr.y - int(self.burst_h*prog*.4)))
        for p in self.particles:
            sx = int(p["x"]-ox); sy = int(p["y"]-oy)
            prog = p["t"]/p["life"]
            a = int(200*(1-prog)); r = max(1, int(p["r"]*(1-prog*.4)))
            s = pygame.Surface((r*2, r*2), pygame.SRCALPHA)
            pygame.draw.circle(s, (210, 178, 130, a), (r, r), r)
            surf.blit(s, (sx-r, sy-r))
        if self.bursting:
            g2 = pygame.Surface((44, self.burst_h), pygame.SRCALPHA)
            g2.fill((200, 155, 80, 14)); surf.blit(g2, (dr.x-6, dr.y-self.burst_h))
            pygame.draw.rect(surf, AMBER,
                (dr.x-6, dr.y-self.burst_h, self.rect.w+12, self.burst_h), 1)


# ── MEKANİK KOL ─────────────────────────────────────────────────────────────────
class MechArm:
    def __init__(self, pivot_x, pivot_y, arm_len=175, speed=1.4):
        self.px = float(pivot_x); self.py = float(pivot_y)
        self.length = arm_len
        self.phase = 0.; self.speed = speed

    def update(self, dt):
        self.phase += self.speed * dt

    def _angle(self):
        return math.pi*0.15 + (math.sin(self.phase)+1)/2 * math.pi*0.70

    def check_hit(self, prect):
        angle = self._angle()
        for s in range(9):
            t = s / 8
            sx = int(self.px + math.cos(angle)*self.length*t)
            sy = int(self.py + math.sin(angle)*self.length*t)
            if prect.collidepoint(sx, sy): return True
        return False

    def draw(self, surf, ox, oy, game_t):
        angle = self._angle()
        sx = int(self.px - ox); sy = int(self.py - oy)
        if not (-120 < sx < SW+120): return
        tx = int(self.px + math.cos(angle)*self.length - ox)
        ty = int(self.py + math.sin(angle)*self.length - oy)
        pygame.draw.line(surf, MGRAY, (sx, sy), (tx, ty), 12)
        pygame.draw.line(surf, LGRAY, (sx, sy), (tx, ty), 10)
        pygame.draw.line(surf, DGRAY, (sx, sy), (tx, ty), 8)
        for i in range(5):
            t1 = i/5; t2 = (i+.5)/5
            ax1 = int(self.px + math.cos(angle)*self.length*t1 - ox)
            ay1 = int(self.py + math.sin(angle)*self.length*t1 - oy)
            ax2 = int(self.px + math.cos(angle)*self.length*t2 - ox)
            ay2 = int(self.py + math.sin(angle)*self.length*t2 - oy)
            if i % 2 == 0:
                pygame.draw.line(surf, STRIPE_Y, (ax1, ay1), (ax2, ay2), 4)
        pygame.draw.circle(surf, LGRAY, (sx, sy), 10)
        pygame.draw.circle(surf, DGRAY, (sx, sy), 6)
        pygame.draw.circle(surf, RUST,  (tx, ty), 10)
        pygame.draw.circle(surf, LRUST, (tx, ty), 6)


# ── KIVILCIM YAYICI ─────────────────────────────────────────────────────────────
class SparkEmitter:
    def __init__(self, x, y):
        self.x = float(x); self.y = float(y)
        self.sparks = []; self.next = random.uniform(.4, 2.)

    def update(self, dt):
        self.next -= dt
        if self.next <= 0:
            self.next = random.uniform(.5, 2.1)
            for _ in range(random.randint(5, 18)):
                a = random.uniform(math.pi*.85, math.pi*1.95)
                sp = random.uniform(50, 230)
                self.sparks.append({
                    "x": self.x, "y": self.y,
                    "vx": math.cos(a)*sp, "vy": math.sin(a)*sp - 75,
                    "life": random.uniform(.18, .52), "t": 0.,
                    "col": random.choice([YELLOW, (255, 190, 42), (255, 138, 16)])
                })
        for s in self.sparks:
            s["t"] += dt; s["vx"] *= max(0., 1-dt*2.5)
            s["vy"] += GRAVITY*dt*.36
            s["x"] += s["vx"]*dt; s["y"] += s["vy"]*dt
        self.sparks = [s for s in self.sparks if s["t"] < s["life"]]

    def draw(self, surf, ox, oy):
        for s in self.sparks:
            sx = int(s["x"]-ox); sy = int(s["y"]-oy)
            if not (-10 < sx < SW+10 and -60 < sy < SH+30): continue
            prog = s["t"]/s["life"]
            a = max(0, int(255*(1-prog))); r = max(1, int(3*(1-prog)))
            gs = pygame.Surface((r*2+2, r*2+2), pygame.SRCALPHA)
            pygame.draw.circle(gs, (*s["col"], a), (r+1, r+1), r)
            surf.blit(gs, (sx-r-1, sy-r-1))


# ── DÜŞEN HURDA ─────────────────────────────────────────────────────────────────
class MachineFalling:
    def __init__(self, x1, x2):
        self.x1 = x1; self.x2 = x2; self.pieces = []; self.active = False
        self.spawn_t = 0.; self.cycle_t = 0.; self.raining = False
        self.next_rain = random.uniform(1.8, 3.2)

    def try_activate(self, px):
        if not self.active and px > self.x1 - 400: self.active = True

    def update(self, dt):
        if not self.active: return
        self.cycle_t += dt
        if not self.raining and self.cycle_t > self.next_rain:
            self.raining = True; self.cycle_t = 0.
        elif self.raining and self.cycle_t > 1.3:
            self.raining = False; self.cycle_t = 0.
            self.next_rain = random.uniform(1.8, 3.0)
        if self.raining:
            self.spawn_t += dt
            if self.spawn_t > 0.065:
                self.spawn_t = 0.
                self.pieces.append({
                    "x": float(random.uniform(self.x1, self.x2)), "y": -28.,
                    "w": random.randint(8, 38), "h": random.randint(5, 18),
                    "vy": random.uniform(235, 520),
                    "rot": random.uniform(0, 360), "rs": random.uniform(-195, 195),
                    "col": random.choice([RUST, DRUST, GRAY, DGRAY, LRUST, MGRAY]),
                    "alive": True
                })
        for p in self.pieces:
            p["y"] += p["vy"]*dt; p["rot"] += p["rs"]*dt
            if p["y"] > WH+80: p["alive"] = False
        self.pieces = [p for p in self.pieces if p["alive"]]

    def check_hit(self, prect):
        for p in self.pieces:
            if pygame.Rect(int(p["x"]-p["w"]//2), int(p["y"]-p["h"]//2),
                           p["w"], p["h"]).colliderect(prect): return True
        return False

    def draw(self, surf, ox, oy):
        for p in self.pieces:
            sx = int(p["x"]-ox); sy = int(p["y"]-oy)
            if not (-60 < sx < SW+60 and -60 < sy < SH+60): continue
            s = pygame.Surface((p["w"], p["h"]), pygame.SRCALPHA)
            pygame.draw.rect(s, p["col"], (0, 0, p["w"], p["h"]))
            pygame.draw.rect(s, LGRAY,    (0, 0, p["w"], p["h"]), 1)
            surf.blit(pygame.transform.rotate(s, p["rot"]%360),
                      (sx - p["w"]//2, sy - p["h"]//2))


# ── UYARI IŞIĞI ─────────────────────────────────────────────────────────────────
class WarningLight:
    def __init__(self, x, y, col=None):
        self.x = x; self.y = y; self.col = col or RED; self.active = False

    def draw(self, surf, ox, oy, game_t):
        sx = self.x - ox; sy = self.y - oy
        if not (-22 < sx < SW+22): return
        on = self.active and int(game_t*4) % 2 == 0
        if on:
            g = pygame.Surface((48, 48), pygame.SRCALPHA)
            pygame.draw.circle(g, (*self.col, 42), (24, 24), 22)
            surf.blit(g, (int(sx)-24, int(sy)-24))
            pygame.draw.circle(surf, self.col, (int(sx), int(sy)), 9)
        else:
            c = (32, 10, 10) if self.col == RED else (36, 28, 4)
            pygame.draw.circle(surf, c, (int(sx), int(sy)), 9)
        pygame.draw.circle(surf, LGRAY, (int(sx), int(sy)), 9, 2)


# ════════════════════════════════════════════════════════════════════════════════
# YENİ SINIFLAR — v3
# ════════════════════════════════════════════════════════════════════════════════

# ── DEMIR KAPI ──────────────────────────────────────────────────────────────────
class Gate:
    """Bulmaca tamamlanana kadar geçişi engelleyen kilitli kapı."""
    def __init__(self, x, h=210):
        self.x = float(x)
        self.h = h
        self.locked = True
        self.slide = 0.   # 0 = kapalı, 1 = tam açık

    def unlock(self):
        self.locked = False

    def update(self, dt):
        if not self.locked:
            self.slide = min(1., self.slide + dt * 1.1)

    def as_rect(self):
        """Çarpışma dikdörtgeni (yeterince açıksa None)."""
        shown_h = int(self.h * (1. - self.slide))
        if shown_h < 14: return None
        return pygame.Rect(int(self.x), FLOOR - shown_h, 32, shown_h)

    def draw(self, surf, ox, oy, game_t):
        sx = int(self.x - ox)
        if not (-80 < sx < SW + 80): return
        shown_h = int(self.h * (1. - self.slide))

        # Çerçeve (her zaman görünür)
        fy = FLOOR - self.h - oy
        pygame.draw.rect(surf, MGRAY, (sx - 6, fy, 8, self.h))
        pygame.draw.rect(surf, MGRAY, (sx + 30, fy, 8, self.h))
        pygame.draw.rect(surf, MGRAY, (sx - 6, fy - 10, 46, 10))
        pygame.draw.rect(surf, LGRAY, (sx - 6, fy - 10, 46, self.h + 10), 2)

        if shown_h > 4:
            sy = FLOOR - shown_h - oy
            pygame.draw.rect(surf, (60, 26, 6), (sx, sy, 32, shown_h))
            pygame.draw.rect(surf, LRUST, (sx, sy, 32, shown_h), 2)
            # Tehlike şeritleri
            for i in range(0, shown_h, 26):
                c = STRIPE_Y if (i // 26) % 2 == 0 else RUST
                pygame.draw.rect(surf, c, (sx + 2, sy + i, 28, min(13, shown_h - i)))
            # Kilit göstergesi
            lc = RED if self.locked else YELLOW
            if self.locked:
                blink = int(game_t * 3) % 2 == 0
                lc = RED if blink else (80, 0, 0)
            pygame.draw.circle(surf, lc, (sx + 16, sy + 16), 10)
            pygame.draw.circle(surf, (10, 10, 10), (sx + 16, sy + 16), 5)


# ── TERMİNAL ────────────────────────────────────────────────────────────────────
class BoilerValve:
    """
    Buhar kazanı vanası — E tuşuyla çevrilir.
    4 vana, girişteki renk şemasına göre doğru sırayla çevrilmeli.
    Renk sırası: KIRMIZI → SARI → TURUNCU → BEYAZ
    """
    W, H          = 60, 120
    PIPE_W        = 22
    INTERACT_DIST = 120
    COLOURS = [
        (RED,    "I",   (180, 25, 10)),
        (YELLOW, "II",  (155, 125, 5)),
        (ORANGE, "III", (160, 65, 8)),
        (WHITE,  "IV",  (140, 110, 70)),
    ]

    def __init__(self, x, y, seq_num):
        self.rect    = pygame.Rect(x - self.W//2, y - self.H, self.W, self.H)
        self.seq_num = seq_num           # 1-4
        self.turned  = False
        self.turn_t  = 0.               # animasyon
        self.err_t   = 0.
        self.steam_t = 0.               # hata buharı
        self.angle   = 0.               # vana kolu açısı (derece)
        self.particles = []

    def nearby(self, prect):
        return abs(prect.centerx - self.rect.centerx) < self.INTERACT_DIST

    def turn(self):
        self.turned = True; self.turn_t = 0.6
        # Çevrilince buhar efekti
        cx = float(self.rect.centerx); cy = float(self.rect.top - 10)
        for _ in range(18):
            a  = random.uniform(-math.pi*0.9, -math.pi*0.1)
            sp = random.uniform(40, 140)
            self.particles.append({
                "x": cx, "y": cy,
                "vx": math.cos(a)*sp, "vy": math.sin(a)*sp,
                "r": random.randint(5, 14),
                "life": random.uniform(.4, .9), "t": 0.
            })

    def trigger_error(self):
        self.err_t = 0.7; self.turned = False; self.turn_t = 0.
        self.angle = 0.
        # Büyük buhar patlaması
        cx = float(self.rect.centerx); cy = float(self.rect.top)
        for _ in range(32):
            a  = random.uniform(-math.pi, 0)
            sp = random.uniform(80, 280)
            self.particles.append({
                "x": cx, "y": cy,
                "vx": math.cos(a)*sp, "vy": math.sin(a)*sp,
                "r": random.randint(8, 20),
                "life": random.uniform(.5, 1.1), "t": 0.
            })

    def reset(self):
        self.turned  = False; self.turn_t = 0.
        self.err_t   = 0.;    self.angle  = 0.

    def update(self, dt):
        if self.turn_t > 0: self.turn_t = max(0., self.turn_t - dt)
        if self.err_t  > 0: self.err_t  = max(0., self.err_t  - dt)
        # Kol dönüş animasyonu
        target = 90. if self.turned else 0.
        self.angle += (target - self.angle) * min(1., dt * 8.)
        # Parçacıklar
        for p in self.particles:
            p["t"] += dt; p["x"] += p["vx"]*dt; p["y"] += p["vy"]*dt
            p["vx"] *= max(0., 1 - dt*1.8); p["vy"] *= max(0., 1 - dt*1.2)
        self.particles = [p for p in self.particles if p["t"] < p["life"]]

    def draw(self, surf, ox, oy, font, game_t, show_hint):
        sx = self.rect.x - ox; sy = self.rect.y - oy
        if not (-120 < sx < SW + 120): return
        cx = sx + self.W // 2

        col, label, dark = self.COLOURS[self.seq_num - 1]
        if self.err_t > 0:
            col = RED; dark = (100, 10, 5)

        # ── Buhar parçacıkları ──
        for p in self.particles:
            px2 = int(p["x"] - ox); py2 = int(p["y"] - oy)
            prog = p["t"] / p["life"]
            a = int(190 * (1 - prog)); r = max(1, int(p["r"] * (1 - prog * .3)))
            s = pygame.Surface((r*2, r*2), pygame.SRCALPHA)
            pygame.draw.circle(s, (215, 175, 115, a), (r, r), r)
            surf.blit(s, (px2 - r, py2 - r))

        # ── Zemine gömülü boru gövdesi ──
        pipe_top = sy + self.H - 72
        pw = self.PIPE_W
        pygame.draw.rect(surf, MGRAY, (cx - pw//2, pipe_top, pw, 72))
        pygame.draw.rect(surf, LGRAY, (cx - pw//2, pipe_top, pw, 72), 2)
        for fy in (pipe_top + 12, pipe_top + 38, pipe_top + 58):
            pygame.draw.rect(surf, LGRAY, (cx - pw//2 - 8, fy, pw + 16, 9))
            pygame.draw.rect(surf, MGRAY, (cx - pw//2 - 8, fy, pw + 16, 9), 1)
            for bx2 in (-pw//2 - 5, pw//2 + 3):
                pygame.draw.circle(surf, DGRAY, (cx + bx2, fy + 4), 3)

        # ── Ana vana gövdesi (büyük, belirgin) ──
        body_h = self.H - 72
        body_col = dark if self.turned else DGRAY
        if self.err_t > 0 and int(self.err_t * 10) % 2 == 0:
            body_col = (90, 15, 5)
        # Gölge efekti
        shadow = pygame.Surface((self.W + 8, body_h + 8), pygame.SRCALPHA)
        shadow.fill((0, 0, 0, 60))
        surf.blit(shadow, (sx + 4, sy + 4))
        pygame.draw.rect(surf, body_col, (sx, sy, self.W, body_h))
        pygame.draw.rect(surf, LRUST,   (sx, sy, self.W, body_h), 3)
        # Kabartma detay çizgileri
        for ry in range(sy + 8, sy + body_h - 6, 14):
            pygame.draw.line(surf, (dark[0]//2, dark[1]//2, dark[2]//2) if self.turned else (50, 30, 10),
                             (sx + 4, ry), (sx + self.W - 4, ry), 1)

        # ── Büyük renk göstergesi dairesi (ana tanımlayıcı) ──
        ind_r   = 22
        ind_cy  = sy + body_h // 2
        ind_col = col if not self.turned else tuple(min(255, v + 80) for v in col)
        # Dış hale (etkileşim alanı belirgin olsun)
        if show_hint and not self.turned:
            pulse = abs(math.sin(game_t * 4))
            halo = pygame.Surface((ind_r*4, ind_r*4), pygame.SRCALPHA)
            pygame.draw.circle(halo, (*col, int(50 + 50*pulse)), (ind_r*2, ind_r*2), ind_r*2)
            surf.blit(halo, (cx - ind_r*2, ind_cy - ind_r*2))
        if self.turned:
            glow = pygame.Surface((ind_r*4, ind_r*4), pygame.SRCALPHA)
            pygame.draw.circle(glow, (*ind_col, 70), (ind_r*2, ind_r*2), ind_r*2)
            surf.blit(glow, (cx - ind_r*2, ind_cy - ind_r*2))
        pygame.draw.circle(surf, (20, 10, 3),  (cx, ind_cy), ind_r + 4)
        pygame.draw.circle(surf, LRUST,        (cx, ind_cy), ind_r + 4, 2)
        pygame.draw.circle(surf, ind_col,      (cx, ind_cy), ind_r)
        pygame.draw.circle(surf, tuple(min(255, v + 50) for v in ind_col), (cx - 6, ind_cy - 6), ind_r//3)

        # ── Büyük vana kolu (çok belirgin) ──
        hand_cy = sy + 14
        rad = math.radians(self.angle - 90)
        arm = 26
        kx1 = cx + int(math.cos(rad) * arm)
        ky1 = hand_cy + int(math.sin(rad) * arm)
        kx2 = cx - int(math.cos(rad) * arm)
        ky2 = hand_cy - int(math.sin(rad) * arm)
        pygame.draw.line(surf, LGRAY, (kx1, ky1), (kx2, ky2), 10)
        pygame.draw.line(surf, MGRAY, (kx1, ky1), (kx2, ky2),  6)
        # Kol uçları (T-vana eli)
        for ex, ey in ((kx1, ky1), (kx2, ky2)):
            pygame.draw.circle(surf, LGRAY, (ex, ey), 7)
            pygame.draw.circle(surf, MGRAY, (ex, ey), 7, 2)
        pygame.draw.circle(surf, AMBER, (cx, hand_cy), 10)
        pygame.draw.circle(surf, DRUST, (cx, hand_cy), 5)

        # ── Manometre (büyük, okunabilir) ──
        gx = sx + self.W + 14; gy = sy + 18
        pygame.draw.circle(surf, DGRAY, (gx, gy), 16)
        pygame.draw.circle(surf, LRUST, (gx, gy), 16, 2)
        pygame.draw.circle(surf, (18, 10, 3), (gx, gy), 13)
        needle_a = math.radians(-130 + (self.angle / 90.) * 110)
        nx = gx + int(math.cos(needle_a) * 10)
        ny = gy + int(math.sin(needle_a) * 10)
        pygame.draw.line(surf, RED if not self.turned else AMBER, (gx, gy), (nx, ny), 2)
        pygame.draw.circle(surf, LGRAY, (gx, gy), 3)

        # ── Roman rakamı etiketi (büyük, belirgin) ──
        if font:
            lbl_surf = font.render(label, True, YELLOW if self.turned else WHITE)
            surf.blit(lbl_surf, (sx + self.W//2 - lbl_surf.get_width()//2, sy + body_h + 4))

        # ── Etkileşim ipucu (büyük, animasyonlu) ──
        if show_hint and not self.turned and font:
            pulse2 = abs(math.sin(game_t * 3.5))
            # Arka panel
            hint_txt = font.render("[ E ]  ÇEVİR", True, AMBER)
            hw = hint_txt.get_width() + 24; hh = hint_txt.get_height() + 12
            hint_bg = pygame.Surface((hw, hh), pygame.SRCALPHA)
            hint_bg.fill((10, 5, 0, int(180 + 50 * pulse2)))
            surf.blit(hint_bg, (cx - hw//2, sy - hh - 12))
            pygame.draw.rect(surf, AMBER, (cx - hw//2, sy - hh - 12, hw, hh), 2)
            surf.blit(hint_txt, (cx - hint_txt.get_width()//2, sy - hint_txt.get_height() - 18))
            # Aşağı ok göstergesi
            ax = cx; ay = sy - 8
            pygame.draw.polygon(surf, AMBER, [(ax-8, ay-10), (ax+8, ay-10), (ax, ay)])


def _draw_valve_schema(surf, ox, oy, valve_next, total, game_t):
    """Bölge girişinde vana renk şeması tabelası — hangi sırayla çevirileceğini gösterir."""
    wx = ZONE_SERVER_X1 + 80; wy = FLOOR - 320
    sx = wx - ox; sy = wy - oy
    if not (-300 < sx < SW + 300): return
    bw = 360; bh = 140
    # Panel gölgesi
    shadow = pygame.Surface((bw + 8, bh + 8), pygame.SRCALPHA)
    shadow.fill((0, 0, 0, 80))
    surf.blit(shadow, (sx + 4, sy + 4))
    # Panel arka planı
    pygame.draw.rect(surf, (26, 14, 4), (sx, sy, bw, bh))
    pygame.draw.rect(surf, LRUST,       (sx, sy, bw, bh), 3)
    pygame.draw.rect(surf, RUST,        (sx, sy, bw, 24))
    if _fsml:
        t = _fsml.render("▶  BASINÇ VANA SIRASI  ◀", True, (220, 165, 55))
        surf.blit(t, (sx + bw//2 - t.get_width()//2, sy + 4))
    # 4 renk yuvası
    labels = ["I", "II", "III", "IV"]
    cols   = [RED, YELLOW, ORANGE, WHITE]
    for i in range(total):
        cx2 = sx + 44 + i * 80; cy2 = sy + 82
        done   = (i + 1) < valve_next
        active = (i + 1) == valve_next
        c = cols[i]
        # Aktif hale
        if active:
            pulse = abs(math.sin(game_t * 4))
            halo = pygame.Surface((80, 80), pygame.SRCALPHA)
            pygame.draw.circle(halo, (*c, int(40 + 40*pulse)), (40, 40), 38)
            surf.blit(halo, (cx2 - 40, cy2 - 40))
        # Çerçeve ve iç renk
        border_c = AMBER if active else (MGRAY if done else DGRAY)
        border_w = 3 if active else 2
        pygame.draw.circle(surf, (30, 16, 5), (cx2, cy2), 28)
        pygame.draw.circle(surf, border_c,    (cx2, cy2), 28, border_w)
        inner = c if active else ((100, 80, 30) if done else (40, 24, 8))
        pygame.draw.circle(surf, inner, (cx2, cy2), 22)
        # Tamamlandı işareti
        if done:
            pygame.draw.line(surf, AMBER, (cx2-9, cy2+1), (cx2-3, cy2+8), 3)
            pygame.draw.line(surf, AMBER, (cx2-3, cy2+8), (cx2+9, cy2-7), 3)
        # Roman rakamı etiketi
        if _fsml:
            lbl = _fsml.render(labels[i], True, WHITE if active else LGRAY)
            surf.blit(lbl, (cx2 - lbl.get_width()//2, sy + 116))
        # Ok bağlantısı
        if i < total - 1:
            ax = cx2 + 28; ay = cy2
            pygame.draw.line(surf, MGRAY, (ax, ay), (ax + 22, ay), 2)
            pygame.draw.polygon(surf, MGRAY, [(ax+22, ay-5), (ax+22, ay+5), (ax+30, ay)])


# ── BASINÇ PLAKASI ──────────────────────────────────────────────────────────────
class PressurePlate:
    """
    Platform üzerinde bulunan, üstüne basıldığında tetiklenen renkli plaka.
    Bulmacada belirli bir sırayla basılmalıdır.
    """
    W, H = 90, 18

    def __init__(self, x, y, colour, order_num):
        self.rect = pygame.Rect(x, y, self.W, self.H)
        self.colour = colour
        self.order_num = order_num
        self.pressed = False
        self.err_t = 0.

    def check_press(self, prect, player_on):
        """Oyuncu platformun üstüne ayak bastığında tetiklenir."""
        if not player_on: return False
        return (abs(prect.bottom - self.rect.top) <= 10 and
                prect.right > self.rect.left + 6 and
                prect.left  < self.rect.right - 6)

    def trigger_error(self):
        self.err_t = 0.55

    def reset(self):
        self.pressed = False; self.err_t = 0.

    def update(self, dt):
        if self.err_t > 0: self.err_t = max(0., self.err_t - dt)

    def draw(self, surf, ox, oy, font):
        sx = self.rect.x - ox; sy = self.rect.y - oy
        if not (-100 < sx < SW + 100): return
        cx = sx + self.W // 2

        # Platform altlığı (daha kalın, belirgin)
        pygame.draw.rect(surf, DGRAY, (sx - 6, sy, self.W + 12, self.H + 8))
        pygame.draw.rect(surf, MGRAY, (sx - 6, sy, self.W + 12, self.H + 8), 1)

        # Plaka rengi
        c = self.colour
        if self.err_t > 0:
            c = RED
        elif self.pressed:
            c = tuple(min(255, v + 90) for v in c)

        pygame.draw.rect(surf, c, (sx, sy, self.W, self.H))
        pygame.draw.rect(surf, WHITE, (sx, sy, self.W, self.H), 3)

        # Plaka iç çizgileri (tekstür)
        for lx in range(sx + 10, sx + self.W - 4, 14):
            pygame.draw.line(surf, tuple(max(0, v - 40) for v in c), (lx, sy + 2), (lx, sy + self.H - 2), 1)

        # Sıra numarası etiketi — büyük ve belirgin kutu içinde
        if font:
            label_str = str(self.order_num)
            label = font.render(label_str, True, WHITE)
            lw = label.get_width() + 16; lh = label.get_height() + 8
            lbg = pygame.Surface((lw, lh), pygame.SRCALPHA)
            lbg.fill((10, 5, 0, 200))
            surf.blit(lbg, (cx - lw//2, sy - lh - 6))
            pygame.draw.rect(surf, c, (cx - lw//2, sy - lh - 6, lw, lh), 2)
            surf.blit(label, (cx - label.get_width()//2, sy - label.get_height() - 10))

        # Onay ışığı (basılınca — büyük parlak daire)
        if self.pressed:
            glow = pygame.Surface((40, 40), pygame.SRCALPHA)
            pygame.draw.circle(glow, (*YELLOW, 90), (20, 20), 18)
            surf.blit(glow, (cx - 20, sy - 6))
            pygame.draw.circle(surf, YELLOW, (cx, sy + self.H//2), 8)
            pygame.draw.circle(surf, WHITE,  (cx, sy + self.H//2), 4)


# ── HAREKETLİ PLATFORM ──────────────────────────────────────────────────────────
class MovingPlatform:
    """İki nokta arasında sinüs hareketiyle salınan platform."""
    def __init__(self, x, y, w, h, axis, dist, speed, phase=0.):
        self._ox = float(x); self._oy = float(y)
        self.w = w; self.h = h
        self.axis = axis    # 'x' veya 'y'
        self.dist = dist
        self.speed = speed
        self.phase = phase
        self.rect = pygame.Rect(x, y, w, h)
        self._prev_x = float(x); self._prev_y = float(y)

    def update(self, dt, player):
        self._prev_x = float(self.rect.x)
        self._prev_y = float(self.rect.y)
        self.phase += self.speed * dt
        t = (math.sin(self.phase) + 1) / 2  # 0..1

        if self.axis == 'x':
            nx = int(self._ox + t * self.dist)
            dx = nx - self.rect.x
            self.rect.x = nx
            # Oyuncuyu platform birlikte taşır
            on_plat = (player.rect.bottom >= self.rect.top and
                       player.rect.bottom <= self.rect.top + 20 and
                       player.rect.right > self.rect.left + 4 and
                       player.rect.left  < self.rect.right - 4)
            if on_plat:
                player.rect.x += dx
                player.rect.x = max(0, min(player.rect.x, WW - player.W))
        else:  # 'y'
            ny = int(self._oy + t * self.dist)
            self.rect.y = ny

    def as_plat_rect(self):
        return self.rect

    def draw(self, surf, ox, oy):
        dr = self.rect.move(-ox, -oy)
        if dr.x + dr.w < -60 or dr.x > SW + 60: return
        pygame.draw.rect(surf, MGRAY, dr)
        pygame.draw.line(surf, CYAN,  (dr.x, dr.y), (dr.x + dr.w, dr.y), 3)
        pygame.draw.line(surf, LGRAY, (dr.x, dr.y), (dr.x, dr.y + dr.h), 1)
        pygame.draw.line(surf, LGRAY, (dr.x+dr.w-1, dr.y), (dr.x+dr.w-1, dr.y + dr.h), 1)
        # Yön okları
        cx = dr.x + dr.w // 2; cy = dr.y + dr.h // 2
        if self.axis == 'x':
            pygame.draw.polygon(surf, LGRAY, [(cx-12,cy),(cx-6,cy-4),(cx-6,cy+4)])
            pygame.draw.polygon(surf, LGRAY, [(cx+12,cy),(cx+6,cy-4),(cx+6,cy+4)])
        else:
            pygame.draw.polygon(surf, LGRAY, [(cx,cy-10),(cx-4,cy-4),(cx+4,cy-4)])
            pygame.draw.polygon(surf, LGRAY, [(cx,cy+10),(cx-4,cy+4),(cx+4,cy+4)])


# ════════════════════════════════════════════════════════════════════════════════
# ÇEVRE ÇİZİM FONKSİYONLARI
# ════════════════════════════════════════════════════════════════════════════════

def draw_plat(surf, r, ox, oy, col=None):
    dr = r.move(-ox, -oy)
    if dr.x+dr.w < -80 or dr.x > SW+80 or dr.y+dr.h < -80 or dr.y > SH+80: return
    c = col or DGRAY
    pygame.draw.rect(surf, c, dr)
    pygame.draw.line(surf, LGRAY,      (dr.x, dr.y),    (dr.x+dr.w, dr.y),    3)
    pygame.draw.line(surf, GRAY,       (dr.x, dr.y),    (dr.x,     dr.y+dr.h),1)
    pygame.draw.line(surf, (22, 12, 4),(dr.x, dr.y+dr.h),(dr.x+dr.w,dr.y+dr.h),2)
    if dr.h > 12:
        for iy in range(6, dr.h, 10):
            pygame.draw.line(surf, (38, 24, 8), (dr.x+2, dr.y+iy), (dr.x+dr.w-2, dr.y+iy), 1)


def _hazard_stripes(surf, x1, x2, y, ox, oy, stripe_w=36):
    sx1 = x1-ox; sx2 = x2-ox; sy = y-oy
    if sx2 < 0 or sx1 > SW: return
    sx1 = max(sx1, 0); sx2 = min(sx2, SW)
    for bx in range(int(sx1)//stripe_w*stripe_w, int(sx2)+stripe_w, stripe_w):
        if bx > sx2: break
        col = STRIPE_Y if (bx//stripe_w) % 2 == 0 else STRIPE_B
        pygame.draw.rect(surf, col, (bx, sy, stripe_w, 8))


def _wall_panels(surf, ox, oy):
    panel_h = 200; panel_y = FLOOR - panel_h
    for wx in range(0, WW, 88):
        sx = wx - ox; sy = panel_y - oy
        if sx+88 < -10 or sx > SW+10: continue
        pygame.draw.rect(surf, PANEL, (sx, sy, 86, panel_h))
        pygame.draw.line(surf, MGRAY, (sx,    sy), (sx,    sy+panel_h), 1)
        pygame.draw.line(surf, DGRAY, (sx+86, sy), (sx+86, sy+panel_h), 1)
        for rib in range(sy+8, sy+panel_h, 24):
            pygame.draw.line(surf, (38, 24, 10), (sx+2, rib), (sx+84, rib), 1)
    pygame.draw.rect(surf, MGRAY, (0-ox, panel_y-oy, WW, 6))
    pygame.draw.line(surf, LGRAY, (-ox, panel_y-oy), (WW-ox, panel_y-oy), 2)


def _ceiling_pipes(surf, ox, oy):
    for py, ph, col, seg in [
        (28,  24, DGRAY,         340),
        (66,  16, MGRAY,         260),
        (108, 12, (38, 24, 10),  320),
    ]:
        sy = py - oy
        if sy > SH or sy+ph < -10: continue
        for wx in range(0, WW, seg):
            sx = wx - ox
            if sx+seg < -10 or sx > SW+10: continue
            pygame.draw.rect(surf, col, (sx, sy, seg-4, ph))
            pygame.draw.line(surf, LGRAY, (sx, sy), (sx+seg-4, sy), 2)
            pygame.draw.rect(surf, LGRAY, (sx+seg-10, sy-3, 10, ph+6))
        for wx in range(0, WW, seg*5):
            sx = wx - ox + seg*2
            if not (-30 < sx < SW+30): continue
            pygame.draw.rect(surf, MGRAY, (sx, sy-6, 22, ph+12))
            pygame.draw.rect(surf, LGRAY, (sx, sy-6, 22, ph+12), 1)


def _machine_silhouettes(surf, ox, oy):
    machines = [
        (848,  FLOOR-188, 122, 188),
        (1868, FLOOR-242, 142, 242),
        (3018, FLOOR-202, 132, 202),
        (3908, FLOOR-262, 152, 262),
        (5168, FLOOR-182, 102, 182),
    ]
    for mx, my, mw, mh in machines:
        sx = mx - ox; sy = my - oy
        if sx+mw < -20 or sx > SW+20: continue
        pygame.draw.rect(surf, (20, 12, 4), (sx, sy, mw, mh))
        pygame.draw.rect(surf, MGRAY,        (sx, sy, mw, mh), 2)
        for iy in range(sy+16, sy+mh, 24):
            pygame.draw.line(surf, (42, 28, 12), (sx+4, iy), (sx+mw-4, iy), 1)
        pygame.draw.circle(surf, DRUST, (sx+mw//2, sy+8), 6)
        for gx in range(sx+8, sx+mw-8, 10):
            pygame.draw.rect(surf, DGRAY, (gx, sy+mh-30, 6, 22))


def _scrap_piles(surf, ox, oy):
    piles = [(140,FLOOR),(500,FLOOR),(1645,FLOOR),(2100,FLOOR),
             (3480,FLOOR),(4180,FLOOR),(4780,FLOOR),
             (5700,FLOOR),(6300,FLOOR),(7200,FLOOR),(7900,FLOOR),
             (8500,FLOOR),(9100,FLOOR)]
    rng = random.Random(42)
    for px, py in piles:
        sx = px - ox; sy = py - oy
        if not (-120 < sx < SW+120): continue
        for i in range(rng.randint(6, 14)):
            bx = sx - 55 + i*9
            bh = rng.randint(6, 28); bw = rng.randint(8, 22)
            by = sy - bh
            col = rng.choice([RUST, DRUST, DGRAY, MGRAY])
            pygame.draw.rect(surf, col,  (bx, by, bw, bh))
            pygame.draw.rect(surf, LGRAY,(bx, by, bw, bh), 1)


def _factory_doors(surf, ox, oy):
    for dx in [ZONE_CONV_X1, ZONE_PATROL_X1, ZONE_STEAM_X1, ZONE_MACH_X1,
               ZONE_SERVER_X1, ZONE_MAINT_X1, ZONE_LOAD_X1]:
        sx = dx - ox; sy = FLOOR - oy - 182
        if not (-80 < sx < SW+80): continue
        pygame.draw.rect(surf, MGRAY, (sx-8,  sy,    12, 182))
        pygame.draw.rect(surf, MGRAY, (sx+50, sy,    12, 182))
        pygame.draw.rect(surf, MGRAY, (sx-8,  sy-10, 70,  12))
        pygame.draw.rect(surf, LGRAY, (sx-8,  sy,    70, 182), 2)
        for panel in range(3):
            py = sy + panel*60
            pygame.draw.rect(surf, DGRAY, (sx,   py, 50, 58))
            pygame.draw.rect(surf, MGRAY, (sx,   py, 50, 58), 1)
            pygame.draw.line(surf, (32, 20, 8),(sx+2,py+8), (sx+48,py+8),  1)
            pygame.draw.line(surf, (32, 20, 8),(sx+2,py+28),(sx+48,py+28), 1)


def _boiler_pipes(surf, ox, oy, game_t):
    """Bölge 6 arka planı — büyük kazan boruları ve buhar hatları."""
    # Ana yatay ana boru hattı
    pipe_y = FLOOR - 290
    x1s = ZONE_SERVER_X1 - ox; x2s = ZONE_SERVER_X2 - ox
    if not (x2s < -20 or x1s > SW + 20):
        pygame.draw.rect(surf, MGRAY,  (max(x1s, 0), pipe_y, min(x2s, SW) - max(x1s, 0), 28))
        pygame.draw.rect(surf, LGRAY,  (max(x1s, 0), pipe_y, min(x2s, SW) - max(x1s, 0), 28), 2)
        pygame.draw.line(surf, (66, 44, 18), (max(x1s,0), pipe_y+8), (min(x2s,SW), pipe_y+8), 1)

    # Düşey branşman boruları + kazanlar
    boiler_xs = [ZONE_SERVER_X1+200, ZONE_SERVER_X1+560, ZONE_SERVER_X1+920, ZONE_SERVER_X1+1260]
    for bx in boiler_xs:
        sx = bx - ox; sy = pipe_y - oy
        if not (-120 < sx < SW + 120): continue
        # Düşey boru
        pygame.draw.rect(surf, DGRAY, (sx - 10, int(sy + oy) - oy, 20, FLOOR - pipe_y))
        pygame.draw.rect(surf, MGRAY, (sx - 10, int(sy + oy) - oy, 20, FLOOR - pipe_y), 1)
        # Kazan silindiri
        bw2 = 68; bh2 = 110; bsy = FLOOR - oy - bh2 - 20
        pygame.draw.rect(surf, (24, 14, 4), (sx - bw2//2, bsy, bw2, bh2))
        pygame.draw.rect(surf, RUST,        (sx - bw2//2, bsy, bw2, bh2), 2)
        # Yatay çember kaynak hatları
        for ry2 in range(bsy + 15, bsy + bh2 - 10, 22):
            pygame.draw.line(surf, LRUST, (sx - bw2//2 + 2, ry2), (sx + bw2//2 - 2, ry2), 1)
            for rx2 in (sx - bw2//2 + 6, sx + bw2//2 - 6):
                pygame.draw.circle(surf, MGRAY, (rx2, ry2), 2)
        # Kazan gözlem camı
        pulse = abs(math.sin(game_t * 1.4 + bx * 0.001)) * 0.5
        gc2 = (int(80 + pulse * 120), int(40 + pulse * 60), 10)
        pygame.draw.circle(surf, gc2, (sx, bsy + 28), 14)
        pygame.draw.circle(surf, LGRAY, (sx, bsy + 28), 14, 2)
        # Sıcaklık göstergesi tüp
        pygame.draw.rect(surf, DGRAY, (sx + bw2//2 + 2, bsy + 10, 8, 55))
        pygame.draw.rect(surf, LGRAY, (sx + bw2//2 + 2, bsy + 10, 8, 55), 1)
        fill_h = int(20 + pulse * 30)
        pygame.draw.rect(surf, AMBER, (sx + bw2//2 + 3, bsy + 10 + 55 - fill_h, 6, fill_h))


def _cargo_crates(surf, ox, oy):
    """[YENİ] Kargo kasaları — Bölge 8 arka planı."""
    crate_defs = [
        (ZONE_LOAD_X1 + 55,  FLOOR - 88,  72, 82),
        (ZONE_LOAD_X1 + 155, FLOOR - 145, 72, 135),
        (ZONE_LOAD_X1 + 275, FLOOR - 88,  72, 82),
        (ZONE_LOAD_X1 + 800, FLOOR - 145, 84, 135),
        (ZONE_LOAD_X1 + 900, FLOOR - 88,  72, 82),
        (ZONE_LOAD_X2 - 210, FLOOR - 88,  84, 82),
        (ZONE_LOAD_X2 - 110, FLOOR - 145, 84, 135),
    ]
    for cx, cy, cw, ch in crate_defs:
        sx = cx - ox; sy = cy - oy
        if not (-110 < sx < SW + 110): continue
        pygame.draw.rect(surf, (38, 22, 8), (sx, sy, cw, ch))
        pygame.draw.rect(surf, LRUST, (sx, sy, cw, ch), 2)
        pygame.draw.line(surf, (58, 36, 14), (sx, sy),    (sx+cw, sy+ch), 1)
        pygame.draw.line(surf, (58, 36, 14), (sx+cw, sy), (sx, sy+ch),    1)
        pygame.draw.rect(surf, AMBER, (sx+cw//2-18, sy+ch//2-10, 36, 18))
        pygame.draw.rect(surf, DRUST, (sx+cw//2-18, sy+ch//2-10, 36, 18), 1)


def _crane_rail(surf, ox, oy):
    """[YENİ] Yük deposu vinç rayı."""
    x1 = ZONE_LOAD_X1 - ox; x2 = ZONE_LOAD_X2 - ox; sy = 72 - oy
    if x2 < 0 or x1 > SW: return
    cx1 = max(x1, -6); cx2 = min(x2, SW + 6)
    pygame.draw.rect(surf, MGRAY, (cx1, sy, cx2 - cx1, 26))
    pygame.draw.rect(surf, LGRAY, (cx1, sy, cx2 - cx1, 26), 2)
    for rx in range(int(ZONE_LOAD_X1), int(ZONE_LOAD_X2), 90):
        tsx = rx - ox
        if 0 <= tsx <= SW:
            pygame.draw.rect(surf, DGRAY, (tsx - 4, sy + 26, 8, 44))
            pygame.draw.rect(surf, MGRAY, (tsx - 4, sy + 26, 8, 44), 1)


def draw_industrial_bg(surf, ox, oy, game_t, alarm):
    _wall_panels(surf, ox, oy)
    _ceiling_pipes(surf, ox, oy)
    _machine_silhouettes(surf, ox, oy)
    _scrap_piles(surf, ox, oy)
    _factory_doors(surf, ox, oy)
    _boiler_pipes(surf, ox, oy, game_t)
    _cargo_crates(surf, ox, oy)
    _crane_rail(surf, ox, oy)
    if alarm and int(game_t*3) % 2 == 0:
        aw = pygame.Surface((SW, SH), pygame.SRCALPHA)
        aw.fill((180, 80, 8, 10)); surf.blit(aw, (0, 0))


def draw_floor_section(surf, ox, oy, x1, x2, stripe=False):
    sx1 = x1-ox; sx2 = x2-ox; fy = FLOOR-oy
    if sx2 < -5 or sx1 > SW+5: return
    pygame.draw.rect(surf, DGRAY, (max(0,sx1), fy, min(SW,sx2)-max(0,sx1), 140))
    pygame.draw.line(surf, LGRAY, (max(0,sx1), fy), (min(SW,sx2), fy), 3)
    if stripe:
        _hazard_stripes(surf, x1, x2, FLOOR, ox, oy)


def draw_npc_booth(surf, ox, oy):
    bx = 186 - ox; by = FLOOR - 98 - oy
    pygame.draw.rect(surf, (50, 30, 12), (bx, by, 132, 98))
    pygame.draw.rect(surf, LRUST,        (bx, by, 132, 98), 2)
    pygame.draw.polygon(surf, (60, 36, 10),
        [(bx-14,by),(bx+146,by),(bx+134,by-22),(bx,by-22)])
    for rib in range(bx, bx+134, 14):
        pygame.draw.line(surf, DRUST, (rib, by-22), (rib, by), 1)
    pygame.draw.rect(surf, LRUST, (bx, by-2, 132, 3))
    pygame.draw.rect(surf, MGRAY, (bx-8, by+60, 148, 16))
    pygame.draw.rect(surf, LGRAY, (bx-8, by+60, 148, 16), 1)
    for ix, iw, ih, ic in [(bx+8,14,20,RUST),(bx+32,8,24,DGRAY),(bx+62,12,18,MGRAY)]:
        pygame.draw.rect(surf, ic,    (ix, by+60-ih, iw, ih))
        pygame.draw.rect(surf, LGRAY, (ix, by+60-ih, iw, ih), 1)
    pygame.draw.rect(surf, AMBER, (bx+10, by+12, 110, 20))
    pygame.draw.rect(surf, DRUST, (bx+10, by+12, 110, 20), 1)
    if _fsml:
        st = _fsml.render("KIOSK 7", True, (22, 12, 2))
        surf.blit(st, (bx+24, by+15))


def draw_zone_sign(surf, ox, oy, world_x, world_y, text):
    sx = world_x - ox; sy = world_y - oy
    if not (-130 < sx < SW+130): return
    bw = len(text)*7 + 24; bh = 22
    pygame.draw.rect(surf, AMBER, (sx, sy, bw, bh))
    pygame.draw.rect(surf, DRUST, (sx, sy, bw, bh), 2)
    pygame.draw.rect(surf, DRUST, (sx, sy, 18, bh))
    pygame.draw.polygon(surf, AMBER, [(sx+3,sy+5),(sx+14,sy+5),(sx+9,sy+17)])
    if _fsml:
        t = _fsml.render(text, True, (18, 12, 4))
        surf.blit(t, (sx+22, sy+3))


def draw_puzzle_hint(surf, ox, oy, world_x, world_y, text, col=None):
    """[YENİ] Bulmaca ipucu tabelası (steampunk amber renk şeması)."""
    c = col or LBLUE
    sx = world_x - ox; sy = world_y - oy
    if not (-160 < sx < SW+160): return
    bw = len(text)*7 + 28; bh = 26
    pygame.draw.rect(surf, (30, 16, 4), (sx, sy, bw, bh))
    pygame.draw.rect(surf, c, (sx, sy, bw, bh), 2)
    pygame.draw.rect(surf, (30, 16, 4), (sx, sy, 20, bh))
    pygame.draw.polygon(surf, c, [(sx+3,sy+6),(sx+16,sy+6),(sx+10,sy+20)])
    if _fsml:
        t = _fsml.render(text, True, c)
        surf.blit(t, (sx+24, sy+5))


def draw_exit_door(surf, ox, oy, game_t, triggered):
    dx = ZONE_EXIT_X - ox; dy = FLOOR - 138 - oy
    col = YELLOW if triggered else (50, 30, 8)
    pygame.draw.rect(surf, GRAY,  (dx-10, dy-10, 80, 12))
    pygame.draw.rect(surf, GRAY,  (dx-10, dy,    14, 135))
    pygame.draw.rect(surf, GRAY,  (dx+56, dy,    14, 135))
    pygame.draw.rect(surf, col,   (dx,    dy,    60, 122))
    pygame.draw.rect(surf, LGRAY, (dx,    dy,    60, 122), 3)
    pygame.draw.circle(surf, AMBER, (dx+46, dy+62), 6)
    pygame.draw.circle(surf, DRUST, (dx+46, dy+62), 3)
    if _fsml:
        et = _fsml.render("EXIT", True, DRUST if not triggered else YELLOW)
        surf.blit(et, (dx+6, dy+52))
    if triggered:
        a = int(min(220, abs(math.sin(game_t*3))*200+58))
        g = pygame.Surface((145, 265), pygame.SRCALPHA)
        pygame.draw.rect(g, (220, 160, 20, a//10), (0, 0, 145, 265))
        surf.blit(g, (dx-43, dy-78))


# ── BİTİŞ SAHNESİ ────────────────────────────────────────────────────────────────
class EndScene:
    def __init__(self, sw, sh):
        self.sw = sw; self.sh = sh; self.t = 0.; self.done = False
        try:
            self.f1 = pygame.font.SysFont("Courier New", 40, bold=True)
            self.f2 = pygame.font.SysFont("Courier New", 15)
        except:
            self.f1 = pygame.font.Font(None, 50)
            self.f2 = pygame.font.Font(None, 20)

    def update(self, dt):
        self.t += dt; self.done = self.t > 6.5; return self.done

    def draw(self, surf):
        a = int(255*min(1., self.t/1.1))
        fo = pygame.Surface((self.sw, self.sh))
        fo.set_alpha(a); fo.fill((14, 7, 2)); surf.blit(fo, (0, 0))
        if self.t > 1.4:
            ta = int(255*min(1., (self.t-1.4)/.8))
            s1 = self.f1.render("ESCAPED", True, YELLOW); s1.set_alpha(ta)
            surf.blit(s1, (self.sw//2 - s1.get_width()//2, self.sh//2 - 36))
        if self.t > 3.0:
            ta2 = int(255*min(1., (self.t-3.)/.7))
            s2 = self.f2.render("Beyond the factory walls — the city breathes.",
                                True, (200, 145, 55))
            s2.set_alpha(ta2)
            surf.blit(s2, (self.sw//2 - s2.get_width()//2, self.sh//2 + 24))
        if self.t > 4.4:
            ta3 = int(255*min(1., (self.t-4.4)/.6))
            s3 = self.f2.render("But they will come looking.", True, (140, 90, 30))
            s3.set_alpha(ta3)
            surf.blit(s3, (self.sw//2 - s3.get_width()//2, self.sh//2 + 50))


# ════════════════════════════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════════════════════════════
def main():
    global _fsml

    pygame.init()
    screen = pygame.display.set_mode((SW, SH), pygame.FULLSCREEN | pygame.HWSURFACE | pygame.DOUBLEBUF)
    pygame.display.set_caption("DEAD FACTORY — LVL 03: ESCAPE SEQUENCE  [v3]")
    clock = pygame.time.Clock()

    try:
        fhud  = pygame.font.SysFont("Courier New", 18)
        fdead = pygame.font.SysFont("Courier New", 52, bold=True)
        fbig  = pygame.font.SysFont("Courier New", 52, bold=True)
        fmed  = pygame.font.SysFont("Courier New", 28, bold=True)
        fsml  = pygame.font.SysFont("Courier New", 18)
    except:
        fhud = fdead = fbig = fmed = fsml = pygame.font.Font(None, 24)
    _fsml = fsml

    # ── DÜNYA ────────────────────────────────────────────────────────────────────
    plats = [
        pygame.Rect(0,    FLOOR, WW, 140),   # ana zemin

        # Bölge 1
        pygame.Rect(120,  FLOOR-80,  160, 18),
        pygame.Rect(420,  FLOOR-65,  140, 18),
        pygame.Rect(680,  FLOOR-90,  130, 18),

        # Bölge 2 — konveyörler (conv_system ile hizali)
        pygame.Rect( 900, FLOOR-46, 380, 18),
        pygame.Rect(1285, FLOOR-46, 325, 18),
        pygame.Rect(1615, FLOOR-46, 305, 18),

        # Bölge 3 — devriye koridoru
        pygame.Rect(2020, FLOOR-85,  210, 18),
        pygame.Rect(2380, FLOOR-85,  210, 18),
        pygame.Rect(2740, FLOOR-85,  210, 18),

        # Bölge 4 — buhar zamanlaması
        pygame.Rect(3070, FLOOR-65,  175, 18),
        pygame.Rect(3330, FLOOR-110, 160, 18),
        pygame.Rect(3590, FLOOR-65,  175, 18),

        # Bölge 5 — makine salonu
        pygame.Rect(3970, FLOOR-105, 200, 18),
        pygame.Rect(4250, FLOOR-170, 190, 18),
        pygame.Rect(4510, FLOOR-105, 200, 18),
        pygame.Rect(4790, FLOOR-65,  200, 18),
        pygame.Rect(5030, FLOOR-85,  210, 18),

        # Geçiş rampası → Bölge 6
        pygame.Rect(5200, FLOOR-60,  240, 18),
        pygame.Rect(5440, FLOOR-30,  300, 18),

        # Bölge 6 — Sunucu Odası
        pygame.Rect(5680, FLOOR-95,  195, 18),
        pygame.Rect(5940, FLOOR-150, 185, 18),
        pygame.Rect(6170, FLOOR-95,  195, 18),
        pygame.Rect(6440, FLOOR-150, 180, 18),
        pygame.Rect(6660, FLOOR-95,  195, 18),

        # Bölge 7 — Bakım Tünelleri
        pygame.Rect(7150, FLOOR-75,  195, 18),
        pygame.Rect(7420, FLOOR-125, 185, 18),
        pygame.Rect(7680, FLOOR-75,  195, 18),
        pygame.Rect(7950, FLOOR-125, 185, 18),
        pygame.Rect(8120, FLOOR-75,  195, 18),

        # Bölge 8 — Yük Deposu (basınç plakası platformları)
        # Fiziksel sıra (sol→sağ): "2" AMBER, "1" CİYAN, "4" YEŞİL, "3" KIRMIZI
        pygame.Rect(8490, FLOOR-108, 90, 18),   # üst "2" AMBER
        pygame.Rect(8635, FLOOR-162, 90, 18),   # üst "1" CİYAN  ← önce bunu bul
        pygame.Rect(8780, FLOOR-108, 90, 18),   # üst "4" YEŞİL
        pygame.Rect(8925, FLOOR-162, 90, 18),   # üst "3" KIRMIZI

        # Çıkış rampası
        pygame.Rect(9240, FLOOR-65,  210, 18),
        pygame.Rect(9460, FLOOR-35,  260, 18),
    ]

    npc = NPC(308, FLOOR-40)

    # Tünel hayatta kalanı NPC
    npc2 = NPC(7300, FLOOR-40)
    npc2.LINES = [
        "You made it past the servers.",
        "The sequence lock — clever, right?",
        "Tunnels next. Arms swing fast.",
        "Steam vents fire in pairs. Watch.",
        "Loading bay: step the plates 1-2-3-4.",
        "Wrong plate... bad news. Trust me.",
    ]

    guards = [
        # Bölge 3
        Guard(2055, FLOOR-44, 1960, 2340),
        Guard(2445, FLOOR-44, 2310, 2690),
        Guard(2730, FLOOR-44, 2610, 2950),
        Guard(2910, FLOOR-44, 2790, 3065),
        # Bölge 6 — daha hızlı, daha geniş görüş
        Guard(5800, FLOOR-44, 5620, 6200, speed_mult=1.25),
        Guard(6250, FLOOR-44, 6050, 6750, speed_mult=1.25),
        # Bölge 8 — agresif bekçiler
        Guard(8620, FLOOR-44, 8420, 9000, speed_mult=1.35),
        Guard(8950, FLOOR-44, 8750, 9300, speed_mult=1.35),
        Guard(9150, FLOOR-44, 9000, 9450, speed_mult=1.40),
    ]

    conv_system = ConveyorSystem()

    # Bölge 4 buhar jetleri
    vents = [
        SteamVent(3132, FLOOR-14, 115),
        SteamVent(3298, FLOOR-14, 132),
        SteamVent(3498, FLOOR-14, 120),
        SteamVent(3692, FLOOR-14, 115),
    ]
    for i, v in enumerate(vents):
        v.cycle_t = i * (v.PAUSE_DUR / len(vents))

    # Bölge 7 buhar jetleri — çift çift ateşlenir
    vents2 = [
        SteamVent(7170, FLOOR-14, 128),
        SteamVent(7350, FLOOR-14, 135),
        SteamVent(7560, FLOOR-14, 125),
        SteamVent(7730, FLOOR-14, 132),
        SteamVent(7930, FLOOR-14, 128),
        SteamVent(8100, FLOOR-14, 122),
    ]
    # Çift indexler duraklama, tek indexler patlama fazında başlar
    for i, v in enumerate(vents2):
        if i % 2 == 1:
            v.bursting = True
            v.cycle_t = v.BURST_DUR * 0.4

    # Bölge 5 mekanik kollar
    mech_arms = [
        MechArm(4095, FLOOR-305, 178, speed=1.15),
        MechArm(4628, FLOOR-285, 158, speed=1.65),
    ]
    # Bölge 7 mekanik kollar — daha hızlı!
    mech_arms2 = [
        MechArm(7380, FLOOR-295, 168, speed=1.85),
        MechArm(7760, FLOOR-285, 155, speed=2.20),
        MechArm(8050, FLOOR-275, 172, speed=1.70),
    ]

    sparks = [
        SparkEmitter(4025, FLOOR-22),
        SparkEmitter(4172, FLOOR-22),
        SparkEmitter(4330, FLOOR-198),
        SparkEmitter(4562, FLOOR-22),
        SparkEmitter(4710, FLOOR-22),
        SparkEmitter(4888, FLOOR-22),
        SparkEmitter(5068, FLOOR-118),
        # Bölge 6
        SparkEmitter(5720, FLOOR-22),
        SparkEmitter(6100, FLOOR-22),
        SparkEmitter(6500, FLOOR-22),
        SparkEmitter(6850, FLOOR-22),
        # Bölge 8
        SparkEmitter(8520, FLOOR-22),
        SparkEmitter(8820, FLOOR-22),
        SparkEmitter(9100, FLOOR-22),
    ]

    mach_debris  = MachineFalling(ZONE_MACH_X1,   ZONE_MACH_X2)
    load_debris  = MachineFalling(ZONE_LOAD_X1,   ZONE_LOAD_X2)   # Bölge 8 yük deposu

    wlights = [
        WarningLight(3068, FLOOR-222, RED),
        WarningLight(3528, FLOOR-222, RED),
        WarningLight(3958, FLOOR-222, AMBER),
        WarningLight(4428, FLOOR-222, RED),
        WarningLight(4928, FLOOR-222, AMBER),
        # Bölge 6
        WarningLight(5650, FLOOR-222, BLUE),
        WarningLight(6200, FLOOR-222, BLUE),
        WarningLight(6700, FLOOR-222, BLUE),
        # Bölge 7
        WarningLight(7200, FLOOR-222, AMBER),
        WarningLight(7800, FLOOR-222, AMBER),
        # Bölge 8
        WarningLight(8500, FLOOR-222, RED),
        WarningLight(9000, FLOOR-222, RED),
        # Çıkış
        WarningLight(9580, FLOOR-222, AMBER),
    ]
    wlights[-1].active = True

    # ── [YENİ] KAZAN VANASI BULMACASI (Bölge 6) ───────────────────────────────
    # Renk sırası: KIRMIZI(I) → SARI(II) → TURUNCU(III) → BEYAZ(IV)
    valves = [
        BoilerValve(5750, FLOOR - 0, 1),   # kırmızı
        BoilerValve(6100, FLOOR - 0, 3),   # turuncu  ← sıra dışı yerleşim (zorluk)
        BoilerValve(6450, FLOOR - 0, 2),   # sarı     ← sıra dışı
        BoilerValve(6790, FLOOR - 0, 4),   # beyaz
    ]
    valve_next  = 1     # sıradaki beklenen seq_num
    server_gate = Gate(6920, h=215)

    # ── [YENİ] HAREKETLİ PLATFORMLAR ──────────────────────────────────────────
    # Bölge 7: yatay salınan platformlar (geçiş boşlukları)
    mov_plats = [
        MovingPlatform(7240, FLOOR-108, 130, 18, 'x', 160, 0.85, phase=0.),
        MovingPlatform(7530, FLOOR-108, 130, 18, 'x', 145, 1.05, phase=math.pi/2),
        MovingPlatform(7830, FLOOR-108, 130, 18, 'x', 155, 0.92, phase=math.pi),
    ]
    # Bölge 8: vinç platformu (yatay, geniş)
    crane_plat = MovingPlatform(8350, FLOOR-130, 150, 22, 'x', 280, 0.60, phase=0.)

    # ── [YENİ] BASINÇ PLAKALARI (Bölge 8) ─────────────────────────────────────
    # Fiziksel sıra (sol→sağ): 2(AMBER), 1(CYAN), 4(GREEN), 3(RED)
    # Doğru sıra: 1 → 2 → 3 → 4
    plates = [
        PressurePlate(8505, FLOOR-108-12, AMBER,  2),   # platf. 8490'da
        PressurePlate(8650, FLOOR-162-12, CYAN,   1),   # platf. 8635'de ← önce bu
        PressurePlate(8795, FLOOR-108-12, AMBER, 4),   # platf. 8780'de
        PressurePlate(8940, FLOOR-162-12, RED,    3),   # platf. 8925'de
    ]
    plate_next = 1          # sıradaki beklenen basınç numarası
    load_gate  = Gate(9130, h=215)

    # ── OYUNCU & KAMERA ────────────────────────────────────────────────────────
    player = Player(62, FLOOR-44)
    cam = Cam()

    state = "play"
    eq = []; alarm_active = False; exit_triggered = False; end_done = False
    endscene = EndScene(SW, SH)
    game_t = 0.; hint_t = 0.; HINT_DUR = 5.5
    dead_t = 0.

    # Bulmaca geri bildirim mesajları
    puzzle_msg     = ""
    puzzle_msg_t   = 0.
    PUZZLE_MSG_DUR = 2.2

    # ── ANA DÖNGÜ ──────────────────────────────────────────────────────────────
    while True:
        dt = min(clock.tick(FPS)/1000., .05)
        game_t += dt

        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                pygame.quit(); sys.exit()
            if ev.type == pygame.KEYDOWN:
                if ev.key == pygame.K_ESCAPE:
                    pygame.quit(); sys.exit()
                if ev.key == pygame.K_r:
                    main(); return
                if state == "play":
                    if ev.key in (pygame.K_k, pygame.K_x, pygame.K_LSHIFT,
                                  pygame.K_f, pygame.K_RSHIFT):
                        player.dash()

                    # [YENİ] E tuşu: vana etkileşimi
                    if ev.key == pygame.K_e:
                        for valve in valves:
                            if valve.nearby(player.rect) and not valve.turned:
                                if valve.seq_num == valve_next:
                                    valve.turn()
                                    valve_next += 1
                                    if valve_next > len(valves):
                                        server_gate.unlock()
                                        puzzle_msg = "BASINÇ TAMAM — KAPI AÇIK"
                                        puzzle_msg_t = PUZZLE_MSG_DUR
                                    else:
                                        puzzle_msg = f"VANA {valve.seq_num} — AÇILDI"
                                        puzzle_msg_t = PUZZLE_MSG_DUR
                                else:
                                    # Yanlış sıra — buhar patlaması!
                                    for v2 in valves: v2.trigger_error()
                                    valve_next = 1
                                    player.take_hit(cam)
                                    cam.shake(9, .32)
                                    puzzle_msg = "YANLIŞ VANA — BUHAR BASINCI SIFIR"
                                    puzzle_msg_t = PUZZLE_MSG_DUR
                                break

        # Hasar uygula
        for e2 in eq:
            if e2["t"] == "HIT" and state == "play":
                player.take_hit(cam)
        eq.clear()

        # ── OYNA ───────────────────────────────────────────────────────────────
        if state == "play":
            hint_t += dt
            if puzzle_msg_t > 0: puzzle_msg_t = max(0., puzzle_msg_t - dt)

            # Alarm yayılımı
            any_alert = any(g.state in ("alert", "chasing") for g in guards)
            if any_alert and not alarm_active:
                alarm_active = True
                for g in guards:
                    if g.state == "idle": g.go_suspicious()
            elif not any_alert:
                alarm_active = False

            # Hareketli platform çarpışma listesi (dinamik)
            dyn_plats = plats + conv_system.plat_rects + [mp.as_plat_rect() for mp in mov_plats] + [crane_plat.as_plat_rect()]

            # Kapı çarpışması: kilitliyse oyuncuyu geri iter
            for gate in (server_gate, load_gate):
                gate.update(dt)
                gr = gate.as_rect()
                if gr and player.rect.colliderect(gr):
                    if player.rect.centerx < gr.centerx:
                        player.rect.right = gr.left
                    else:
                        player.rect.left = gr.right
                    player.vx = 0

            player.update(dt, dyn_plats)
            npc.update(dt, player.rect.centerx, player.rect.centery)
            npc2.update(dt, player.rect.centerx, player.rect.centery)

            conv_system.update(dt, player)

            for v in vents:
                v.update(dt)
                hr = v.hazard_rect()
                if hr and hr.colliderect(player.rect): player.take_hit(cam)

            for v in vents2:
                v.update(dt)
                hr = v.hazard_rect()
                if hr and hr.colliderect(player.rect): player.take_hit(cam)

            for arm in mech_arms:
                arm.update(dt)
                if arm.check_hit(player.rect): player.take_hit(cam)

            for arm in mech_arms2:
                arm.update(dt)
                if arm.check_hit(player.rect): player.take_hit(cam)

            for sp in sparks: sp.update(dt)

            mach_debris.try_activate(player.rect.centerx)
            mach_debris.update(dt)
            if mach_debris.check_hit(player.rect):
                player.take_hit(cam); cam.shake(4, .14)

            load_debris.try_activate(player.rect.centerx)
            load_debris.update(dt)
            if load_debris.check_hit(player.rect):
                player.take_hit(cam); cam.shake(4, .14)

            for g in guards: g.update(dt, player, dyn_plats, eq)

            # Hareketli platformlar
            for mp in mov_plats: mp.update(dt, player)
            crane_plat.update(dt, player)

            # Vana güncelle
            for valve in valves: valve.update(dt)

            # [YENİ] Basınç plakası kontrolü
            for plate in plates:
                plate.update(dt)
                if not plate.pressed and plate.check_press(player.rect, player.on):
                    if plate.order_num == plate_next:
                        plate.pressed = True
                        plate_next += 1
                        if plate_next > len(plates):
                            load_gate.unlock()
                            puzzle_msg = "PRESSURE GRID — GATE UNLOCKED"
                            puzzle_msg_t = PUZZLE_MSG_DUR
                        else:
                            puzzle_msg = f"PLATE {plate.order_num} — LOCKED"
                            puzzle_msg_t = PUZZLE_MSG_DUR
                    else:
                        # Yanlış sıra — elektrik şoku!
                        for p2 in plates:
                            p2.reset()
                            if p2.order_num == plate.order_num:
                                p2.trigger_error()
                        plate_next = 1
                        player.take_hit(cam)
                        cam.shake(6, .22)
                        puzzle_msg = "WRONG PLATE — GRID RESET"
                        puzzle_msg_t = PUZZLE_MSG_DUR

            for wl in wlights[:-1]:
                wl.active = alarm_active or player.rect.x > ZONE_MACH_X1

            # Ölüm kontrolü
            if not player.alive:
                if player.death_landed or player.rect.top > WH+80:
                    state = "dead"; dead_t = 0.
            elif player.rect.top > WH + 80:
                player.hp = 0; player.alive = False
                player.death_landed = True; state = "dead"; dead_t = 0.

            # Çıkış tetikleyici
            if player.alive and player.rect.x > ZONE_EXIT_X-60 and not end_done:
                end_done = True; exit_triggered = True; state = "endseq"

            cam.update(dt, player.rect.centerx, player.rect.centery, player.f)

        elif state == "endseq":
            if endscene.update(dt): state = "done"

        elif state == "dead":
            dead_t += dt
            if dead_t > 3.2: main(); return

        # ── RENDER ─────────────────────────────────────────────────────────────
        ox = cam.ox; oy = cam.oy
        screen.fill(BG)

        for iy2 in range(0, SH, 80):
            pygame.draw.line(screen, (18, 10, 4), (0, iy2), (SW, iy2), 1)

        draw_industrial_bg(screen, ox, oy, game_t, alarm_active)

        # Zemin + tehlike şeritleri
        draw_floor_section(screen, ox, oy, 0, WW)
        draw_floor_section(screen, ox, oy, ZONE_STEAM_X1,  ZONE_STEAM_X2,  stripe=True)
        draw_floor_section(screen, ox, oy, ZONE_MACH_X1,   ZONE_MACH_X2,   stripe=True)
        draw_floor_section(screen, ox, oy, ZONE_MAINT_X1,  ZONE_MAINT_X2,  stripe=True)
        draw_floor_section(screen, ox, oy, ZONE_LOAD_X1,   ZONE_LOAD_X2,   stripe=True)

        draw_npc_booth(screen, ox, oy)

        # Bölge işaretleri
        draw_zone_sign(screen, ox, oy, ZONE_CONV_X1   + 22, FLOOR-152, "CONVEYOR — ACTIVE")
        draw_zone_sign(screen, ox, oy, ZONE_PATROL_X1 + 22, FLOOR-152, "RESTRICTED — GUARDS PRESENT")
        draw_zone_sign(screen, ox, oy, ZONE_STEAM_X1  + 22, FLOOR-152, "STEAM HAZARD — TIMED PASSAGE")
        draw_zone_sign(screen, ox, oy, ZONE_MACH_X1   + 22, FLOOR-152, "MACHINERY HALL — DANGER")
        draw_zone_sign(screen, ox, oy, ZONE_SERVER_X1 + 22, FLOOR-152, "KAZAN DAİRESİ — BUHAR KONTROL")
        draw_zone_sign(screen, ox, oy, ZONE_MAINT_X1  + 22, FLOOR-152, "MAINTENANCE TUNNELS — EXTREME CAUTION")
        draw_zone_sign(screen, ox, oy, ZONE_LOAD_X1   + 22, FLOOR-152, "LOADING BAY — FINAL CHECKPOINT")

        # Bulmaca ipuçları
        draw_puzzle_hint(screen, ox, oy, 5560, FLOOR-200, "VANA SIRASI: KIRMIZI → SARI → TURUNCU → BEYAZ  [E]")
        draw_puzzle_hint(screen, ox, oy, 8390, FLOOR-200, "PRESSURE GRID: STEP PLATES 1 -> 2 -> 3 -> 4")

        # Platformlar
        for r in plats: draw_plat(screen, r, ox, oy)

        # Hareketli platformlar
        for mp in mov_plats: mp.draw(screen, ox, oy)
        crane_plat.draw(screen, ox, oy)

        # Konveyörler
        conv_system.draw(screen, ox, oy, game_t)

        # Buhar jetleri
        for v in vents:  v.draw(screen, ox, oy)
        for v in vents2: v.draw(screen, ox, oy)

        # Uyarı ışıkları
        for wl in wlights: wl.draw(screen, ox, oy, game_t)

        # Mekanik kollar
        for arm in mech_arms:  arm.draw(screen, ox, oy, game_t)
        for arm in mech_arms2: arm.draw(screen, ox, oy, game_t)

        # Kıvılcımlar
        for sp in sparks: sp.draw(screen, ox, oy)

        # Düşen hurda
        mach_debris.draw(screen, ox, oy)
        load_debris.draw(screen, ox, oy)

        # Kapılar
        server_gate.draw(screen, ox, oy, game_t)
        load_gate.draw(screen, ox, oy, game_t)

        # Vana şeması ve vanalar
        _draw_valve_schema(screen, ox, oy, valve_next, len(valves), game_t)
        for valve in valves:
            near_hint = valve.nearby(player.rect) and not valve.turned
            valve.draw(screen, ox, oy, fsml, game_t, near_hint)

        # Basınç plakaları
        for plate in plates: plate.draw(screen, ox, oy, fsml)

        # Çıkış kapısı
        draw_exit_door(screen, ox, oy, game_t, exit_triggered)

        # Bekçiler
        for g in guards: g.draw(screen, ox, oy, game_t)

        # NPC'ler + Oyuncu
        npc.draw(screen, ox, oy, fsml)
        npc2.draw(screen, ox, oy, fsml)
        player.draw(screen, ox, oy)

        if state in ("endseq", "done"): endscene.draw(screen)

        # ── HUD ────────────────────────────────────────────────────────────────
        if state == "play":
            player.draw_hud(screen, game_t)

            if alarm_active and int(game_t*4) % 2 == 0:
                ab = fdead.render("!! ALARM — GUARDS ALERTED !!", True, RED)
                screen.blit(ab, (SW//2 - ab.get_width()//2, 14))

            # Bölgeye özel ipuçları
            px_w = player.rect.x
            if ZONE_PATROL_X1 < px_w < ZONE_PATROL_X2:
                tip = fhud.render("Guards face away — DASH past now!  [ K / F ]", True, CYAN)
                screen.blit(tip, (SW//2 - tip.get_width()//2, SH-40))
            elif ZONE_STEAM_X1 < px_w < ZONE_STEAM_X2:
                tip = fhud.render("Watch the steam gap — sprint through!", True, CYAN)
                screen.blit(tip, (SW//2 - tip.get_width()//2, SH-40))
            elif ZONE_MACH_X1 < px_w < ZONE_MACH_X2:
                tip = fhud.render("Mechanical arms — time your dash through the gap!", True, AMBER)
                screen.blit(tip, (SW//2 - tip.get_width()//2, SH-40))
            elif ZONE_SERVER_X1 < px_w < ZONE_SERVER_X2:
                    tip = fhud.render(f"RENK SIRASINI TAKİP ET — VANA {valve_next} ÇEVİR  [ E ]", True, AMBER) if valve_next <= len(valves) else fhud.render("Tüm vanalar açıldı — kapı geçilebilir!", True, LGREEN)
                    screen.blit(tip, (SW//2 - tip.get_width()//2, SH-40))
            elif ZONE_MAINT_X1 < px_w < ZONE_MAINT_X2:
                tip = fhud.render("Alternating steam + fast arms — time every move!", True, AMBER)
                screen.blit(tip, (SW//2 - tip.get_width()//2, SH-40))
            elif ZONE_LOAD_X1 < px_w < ZONE_LOAD_X2:
                if plate_next <= len(plates):
                    tip = fhud.render(f"Step on Plate {plate_next} next — numbered platforms!", True, LGREEN)
                else:
                    tip = fhud.render("All plates stepped — gate open! Nearly there!", True, LGREEN)
                screen.blit(tip, (SW//2 - tip.get_width()//2, SH-40))

            # Kontrol yardımı — ilk HINT_DUR saniye
            if hint_t < HINT_DUR:
                alpha = 255
                if hint_t > HINT_DUR-1.3:
                    alpha = int(255*(HINT_DUR - hint_t)/1.3)
                bw3 = 900; bh3 = 240; bx4 = SW//2-bw3//2; by4 = SH//2-bh3//2
                hs = pygame.Surface((bw3, bh3), pygame.SRCALPHA)
                hs.fill((0, 0, 0, int(205*(alpha/255)))); screen.blit(hs, (bx4, by4))
                pygame.draw.rect(screen, (*AMBER, alpha), (bx4, by4, bw3, bh3), 2)
                for i, (txt, fn) in enumerate([
                    ("A / D   MOVE",                        fbig),
                    ("W / SPACE   JUMP",                    fmed),
                    ("K / F / SHIFT   DASH",                fmed),
                    ("E   INTERACT  (vanalar)",              fmed),
                ]):
                    s = fn.render(txt, True, AMBER if i == 0 else CYAN)
                    s.set_alpha(alpha)
                    screen.blit(s, (SW//2 - s.get_width()//2, by4+20+i*52))

            # [YENİ] Bulmaca geri bildirim mesajı
            if puzzle_msg_t > 0 and puzzle_msg:
                pa = min(255, int(puzzle_msg_t / PUZZLE_MSG_DUR * 255 * 2))
                ok = "GRANTED" in puzzle_msg or "LOCKED" in puzzle_msg or "UNLOCKED" in puzzle_msg
                mc = YELLOW if ok else RED
                pm = fmed.render(puzzle_msg, True, mc)
                pm.set_alpha(pa)
                screen.blit(pm, (SW//2 - pm.get_width()//2, SH//2 - 60))

        # Ölüm ekranı
        if state == "dead":
            fo = pygame.Surface((SW, SH))
            fo.set_alpha(min(220, int(dead_t*82)))
            fo.fill((18, 8, 2)); screen.blit(fo, (0, 0))
            if dead_t > 0.45:
                dm = fdead.render("// TERMINATED //", True, RED)
                screen.blit(dm, (SW//2 - dm.get_width()//2, SH//2 - 22))
                dm2 = fhud.render("Restarting...", True, (140, 60, 15))
                screen.blit(dm2, (SW//2 - dm2.get_width()//2, SH//2 + 18))

        pygame.display.flip()


if __name__ == "__main__":
    main()