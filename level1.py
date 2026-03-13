import pygame, sys, math, random

# ── SABITLER ──────────────────────────────────────────────────────────────────
SW, SH   = 1280, 720
FPS      = 60
WW       = 4200
WH       = 1500
GRAVITY  = 980.0

BG       = (4, 6, 10)
BG_DEEP  = (2, 3, 6)
WHITE    = (255, 255, 255)
CYAN     = (0, 220, 200)
AMBER    = (255, 160, 0)
RED      = (200, 35, 35)
GRAY     = (90, 105, 115)
DGRAY    = (45, 58, 68)
LGRAY    = (130, 150, 165)
BROWN    = (90, 72, 52)
DBROWN   = (52, 40, 26)
LBROWN   = (130, 108, 80)
RUST     = (110, 55, 30)

# Zemin seviyeleri
FLOOR1   = 1200   # Cop Dagi + Derin Bolum
FLOOR2   = 820    # Tunel + Dovus zemini

# Bolge sinirlar
ZONE_TUNNEL_X1 = 1500
ZONE_TUNNEL_X2 = 2200
ZONE_AVALAN_X1 = 2200
ZONE_AVALAN_X2 = 2700
ZONE_FIGHT_X   = 2700
ZONE_DEEP_X    = 3300
ZONE_END_X     = 3950

# ── KAMERA ────────────────────────────────────────────────────────────────────
class Cam:
    def __init__(self): self.x=0.;self.y=0.;self.st=0.;self.si=0.;self.sx=0;self.sy=0;self.sf=1.
    def update(self,dt,px,py,f):
        self.sf+=(f-self.sf)*min(1.,4.*dt)
        tx=max(0.,min(float(WW-SW),px-SW//2+self.sf*140.))
        ty=max(0.,min(float(WH-SH),py-SH//2-60))
        self.x+=(tx-self.x)*min(1.,6.*dt);self.y+=(ty-self.y)*min(1.,6.*dt)
        if self.st>0:
            self.st-=dt;i=int(self.si);self.sx=random.randint(-i,i);self.sy=random.randint(-i,i)
        else: self.sx=self.sy=0
        self.x=max(0.,min(float(WW-SW),self.x))
        self.y=max(0.,min(float(WH-SH),self.y))
    def shake(self,i,d=.3): self.si=i;self.st=d
    @property
    def ox(self): return int(self.x)+self.sx
    @property
    def oy(self): return int(self.y)+self.sy

def resolve(rect,vy,plats):
    on=False
    for p in plats:
        if vy>=0 and rect.colliderect(p): rect.bottom=p.top;vy=0.;on=True
    return vy,on

# ── OYUNCU ────────────────────────────────────────────────────────────────────
class Player:
    W=22;H=40;HP=6
    def __init__(self,x,y):
        self.rect=pygame.Rect(x,y,self.W,self.H)
        self.vx=0.;self.vy=0.;self.on=False;self.f=1
        self.hp=self.HP;self.hc=0.;self.dc=0.;self.dt=0.;self.ac=0.
        self.alive=True
    def take_hit(self,cam):
        if self.hc>0: return
        self.hp=max(0,self.hp-1);self.hc=.6;cam.shake(5,.2)
        self.vx=-self.f*160.;self.vy=-100.
        if self.hp<=0: self.alive=False
    def update(self,dt,plats):
        for a in("hc","dc","dt","ac"):
            v=getattr(self,a)
            if v>0: setattr(self,a,max(0.,v-dt))
        if self.dt>0: self.vx=self.f*460.
        else:
            mv=(pygame.key.get_pressed()[pygame.K_d] or pygame.key.get_pressed()[pygame.K_RIGHT])\
              -(pygame.key.get_pressed()[pygame.K_a] or pygame.key.get_pressed()[pygame.K_LEFT])
            if mv: self.f=mv
            self.vx=mv*200.
        keys=pygame.key.get_pressed()
        if (keys[pygame.K_w] or keys[pygame.K_UP] or keys[pygame.K_SPACE]) and self.on:
            self.vy=-470.;self.on=False
        self.vy=min(self.vy+GRAVITY*dt,1400)
        self.rect.x+=int(self.vx*dt);self.rect.x=max(0,self.rect.x)
        self.rect.y+=int(self.vy*dt)
        self.vy,self.on=resolve(self.rect,self.vy,plats)
    def dash(self):
        if self.dc<=0: self.dt=.13;self.dc=.65;self.vy=min(self.vy,0)
    def draw(self,surf,ox,oy):
        if self.hc>0 and int(self.hc*12)%2==0: return
        bx=self.rect.x-ox;by=self.rect.y-oy
        if self.dt>0:
            for i in range(1,4):
                s=pygame.Surface((self.W,self.H),pygame.SRCALPHA)
                s.fill((*CYAN,max(0,70-i*24)));surf.blit(s,(bx-self.f*i*12,by))
        pygame.draw.rect(surf,RED if self.hc>0 else WHITE,(bx,by,self.W,self.H))
        pygame.draw.rect(surf,CYAN,(bx+3,by-14,16,14))
        bw=38;pygame.draw.rect(surf,(40,10,10),(bx-8,by-24,bw,5))
        pygame.draw.rect(surf,RED,(bx-8,by-24,int(bw*self.hp/self.HP),5))

# ── DUSMAN (COP SAKINI) ───────────────────────────────────────────────────────
class Grunt:
    W=26;H=42;HP=3
    def __init__(self,x,y):
        self.rect=pygame.Rect(x,y,self.W,self.H)
        self.vy=0.;self.hp=self.HP;self.f=-1
        self.state="patrol";self.st=0.;self.at=0.
        self.pd=random.choice([-1,1]);self.pt=random.uniform(1.,2.5);self.ptimer=0.
    def hit(self,cam):
        if self.state=="dead": return
        self.hp-=1;cam.shake(5,.18)
        if self.hp<=0: self.state="dead"
        else: self.state="stun";self.st=.35;self.vy=-130.
    def update(self,dt,player,plats,eq):
        if self.state=="dead": return
        self.vy+=GRAVITY*dt;self.rect.y+=int(self.vy*dt)
        self.vy,_=resolve(self.rect,self.vy,plats)
        dx=player.rect.centerx-self.rect.centerx;dist=abs(dx)
        if self.state=="stun":
            self.st-=dt
            if self.st<=0: self.state="patrol"
            return
        if self.state=="patrol":
            self.ptimer+=dt;self.rect.x+=int(self.pd*85.*dt);self.f=self.pd
            if self.ptimer>self.pt: self.pd*=-1;self.ptimer=0;self.pt=random.uniform(1.,2.5)
            if dist<300: self.state="chase"
        elif self.state=="chase":
            self.f=1 if dx>0 else -1;self.rect.x+=int(self.f*140.*dt)
            if dist<50: self.state="attack"
            if dist>450: self.state="patrol"
        elif self.state=="attack":
            self.f=1 if dx>0 else -1;self.at+=dt
            if self.at>=.55:
                self.at=0.
                dy=abs(player.rect.centery-self.rect.centery)
                if abs(dx)<55 and dy<self.H+10: eq.append({"t":"HIT"})
            if dist>70: self.state="chase";self.at=0.
    def draw(self,surf,ox,oy):
        if self.state=="dead": return
        bx=self.rect.x-ox;by=self.rect.y-oy
        col=(80,40,25) if self.state=="stun" else BROWN
        pygame.draw.rect(surf,col,(bx,by,self.W,self.H))
        # Hurda zirh
        pygame.draw.rect(surf,DGRAY,(bx+2,by+4,10,14))
        pygame.draw.rect(surf,DGRAY,(bx+14,by+4,10,14))
        pygame.draw.line(surf,LGRAY,(bx+2,by+4),(bx+12,by+4),1)
        pygame.draw.line(surf,LGRAY,(bx+14,by+4),(bx+24,by+4),1)
        pygame.draw.rect(surf,BROWN,(bx+3,by-12,20,12))
        ex=bx+15 if self.f>0 else bx+5
        pygame.draw.rect(surf,RED,(ex,by-8,5,4))
        bw=34;pygame.draw.rect(surf,(40,10,10),(bx-3,by-19,bw,4))
        pygame.draw.rect(surf,(200,35,35),(bx-3,by-19,int(bw*self.hp/self.HP),4))

# ── COP AKINTISI ──────────────────────────────────────────────────────────────
class FallingScrap:
    BURST=2.2   # saniye yagar
    PAUSE=1.6   # saniye durur
    def __init__(self,x1,x2):
        self.x1=x1;self.x2=x2
        self.pieces=[];self.spawn_t=0.;self.active=False
        self.cycle_t=0.;self.raining=True
    def try_activate(self,px):
        if not self.active and px>self.x1-350: self.active=True
    def update(self,dt):
        if not self.active: return
        self.cycle_t+=dt
        limit=self.BURST if self.raining else self.PAUSE
        if self.cycle_t>=limit:
            self.cycle_t=0.;self.raining=not self.raining
        if self.raining:
            self.spawn_t+=dt
            if self.spawn_t>0.06:
                self.spawn_t=0.
                sx=random.uniform(self.x1,self.x2)
                self.pieces.append({
                    "x":float(sx),"y":-30.,
                    "w":random.randint(10,46),"h":random.randint(6,20),
                    "vy":random.uniform(260,580),
                    "rot":random.uniform(0,360),"rs":random.uniform(-240,240),
                    "col":random.choice([BROWN,DBROWN,GRAY,DGRAY,RUST,LGRAY]),
                    "alive":True
                })
        for p in self.pieces:
            p["y"]+=p["vy"]*dt;p["rot"]+=p["rs"]*dt
            if p["y"]>WH+100: p["alive"]=False
        self.pieces=[p for p in self.pieces if p["alive"]]
    def check_hit(self,prect):
        for p in self.pieces:
            pr=pygame.Rect(int(p["x"]-p["w"]//2),int(p["y"]-p["h"]//2),p["w"],p["h"])
            if pr.colliderect(prect): return True
        return False
    def draw(self,surf,ox,oy):
        for p in self.pieces:
            sx=int(p["x"]-ox);sy=int(p["y"]-oy)
            if not(-80<sx<SW+80 and -80<sy<SH+80): continue
            s=pygame.Surface((p["w"],p["h"]),pygame.SRCALPHA)
            pygame.draw.rect(s,p["col"],(0,0,p["w"],p["h"]))
            pygame.draw.rect(s,LGRAY,(0,0,p["w"],p["h"]),1)
            rs=pygame.transform.rotate(s,p["rot"]%360)
            surf.blit(rs,(sx-rs.get_width()//2,sy-rs.get_height()//2))

# ── COKEN PLATFORM ────────────────────────────────────────────────────────────
class Debris:
    def __init__(self,x,y,w,h):
        self.x=float(x);self.y=float(y);self.w=w;self.h=h
        self.vx=random.uniform(-180,180);self.vy=random.uniform(-320,-80)
        self.rot=0.;self.rot_spd=random.uniform(-240,240)
        self.bounce=0;self.floor_y=None;self.alive=True
        self.col=random.choice([BROWN,DBROWN,GRAY,DGRAY])
    def update(self,dt):
        self.vy+=GRAVITY*dt;self.x+=self.vx*dt;self.y+=self.vy*dt
        self.rot+=self.rot_spd*dt
        if self.floor_y and self.y+self.h>self.floor_y:
            self.y=self.floor_y-self.h;self.vy*=-0.38;self.vx*=0.72
            self.rot_spd*=0.6;self.bounce+=1
            if self.bounce>3 or abs(self.vy)<20: self.vy=0;self.vx*=0.85
        if abs(self.x)>WW+400: self.alive=False
    def draw(self,surf,ox,oy):
        sx=int(self.x-ox);sy=int(self.y-oy)
        if not(-60<sx<SW+60 and -60<sy<SH+60): return
        s=pygame.Surface((self.w,self.h),pygame.SRCALPHA)
        pygame.draw.rect(s,self.col,(0,0,self.w,self.h))
        pygame.draw.rect(s,LGRAY,(0,0,self.w,self.h),1)
        rot_s=pygame.transform.rotate(s,self.rot%360)
        surf.blit(rot_s,(sx-rot_s.get_width()//2,sy-rot_s.get_height()//2))

class ColPlat:
    def __init__(self,x,y,w,cam):
        self.rect=pygame.Rect(x,y,w,18);self.t=-1.;self.fallen=False
        self.cam=cam;self.sd=False;self.debris=[];self._floor_y=y+18;self._fade=1.0
    def set_floor(self,fy): self._floor_y=fy
    def trigger(self):
        if self.t<0: self.t=0.
    def update(self,dt,eq):
        for d in self.debris: d.update(dt)
        self.debris=[d for d in self.debris if d.alive]
        if self.t<0: return
        self.t+=dt
        if self.t>=.55 and not self.sd: self.sd=True;self.cam.shake(8,.55)
        if self.t>=.55: self._fade=max(0.,1.0-(self.t-.55)/.55)
        if self.t>=1.1 and not self.fallen:
            self.fallen=True;eq.append({"t":"COL"})
            x_cur=self.rect.x
            while x_cur<self.rect.right:
                pw=random.randint(18,44);pw=min(pw,self.rect.right-x_cur)
                ph=random.randint(10,22)
                d=Debris(x_cur+pw//2,self.rect.y,pw,ph)
                d.floor_y=self._floor_y;self.debris.append(d)
                x_cur+=pw
    def draw(self,surf,ox,oy):
        for d in self.debris: d.draw(surf,ox,oy)
        if self._fade<=0: return
        dr=self.rect.move(-ox,-oy)
        if self.t>.55: dr=dr.move(random.randint(-2,2),0)
        alpha=int(255*self._fade)
        s=pygame.Surface((dr.w,dr.h),pygame.SRCALPHA)
        if self.t>.55:
            r2=min(1.,(self.t-.55)/.55)
            c=(int(60+140*r2),int(45*(1-r2)),int(30*(1-r2)),alpha)
        else: c=(*BROWN,alpha)
        pygame.draw.rect(s,c,(0,0,dr.w,dr.h))
        pygame.draw.rect(s,(*LBROWN,alpha),(0,0,dr.w,dr.h),2)
        surf.blit(s,(dr.x,dr.y))

# ── PLATFORM CIZIMI ───────────────────────────────────────────────────────────
def draw_plat(surf,r,ox,oy,scrap=False):
    dr=r.move(-ox,-oy)
    if dr.x+dr.w<-80 or dr.x>SW+80: return
    if dr.y+dr.h<-80 or dr.y>SH+80: return
    base=DBROWN if scrap else DGRAY
    edge=LBROWN if scrap else LGRAY
    pygame.draw.rect(surf,base,dr)
    pygame.draw.line(surf,edge,(dr.x,dr.y),(dr.x+dr.w,dr.y),3)
    pygame.draw.line(surf,GRAY,(dr.x,dr.y),(dr.x,dr.y+dr.h),1)
    pygame.draw.line(surf,(20,28,34),(dr.x,dr.y+dr.h),(dr.x+dr.w,dr.y+dr.h),2)
    pygame.draw.line(surf,(20,28,34),(dr.x+dr.w,dr.y),(dr.x+dr.w,dr.y+dr.h),2)
    if dr.h>12:
        lc=(55,38,22) if scrap else (35,46,55)
        for iy in range(6,dr.h,10):
            pygame.draw.line(surf,lc,(dr.x+2,dr.y+iy),(dr.x+dr.w-2,dr.y+iy),1)

# ── ATMOSFER YARDIMCILARI ─────────────────────────────────────────────────────



def draw_tunnel(surf,ox,oy):
    """Dar Hurda Tuneli — iki cop duvari arasinda dar gecit.
    Tunel: ZONE_TUNNEL_X1..ZONE_TUNNEL_X2, tavan y=560"""
    x1=ZONE_TUNNEL_X1-ox
    x2=ZONE_TUNNEL_X2-ox
    tw=ZONE_TUNNEL_X2-ZONE_TUNNEL_X1
    ceil_y=560-oy
    floor_y=FLOOR2-oy

    if x2<-120 or x1>SW+120: return

    # Tavan blogu (cop yigini)
    pygame.draw.rect(surf,DGRAY,(x1,0,tw,ceil_y))
    pygame.draw.line(surf,LGRAY,(x1,ceil_y),(x2,ceil_y),3)
    # Ic desen
    for iy in range(8,max(8,ceil_y),12):
        pygame.draw.line(surf,(28,38,46),(x1+2,iy),(x2-2,iy),1)
    # Alt dis coplar
    for i in range(0,tw,22):
        h=6+((i*7)%14)
        pygame.draw.line(surf,GRAY,(x1+i,ceil_y),(x1+i+9,ceil_y+h),2)
    # Sol duvar (giris kuyrusu)
    pygame.draw.rect(surf,DBROWN,(x1-70,ceil_y,70,floor_y-ceil_y))
    pygame.draw.line(surf,LBROWN,(x1,ceil_y),(x1,floor_y),3)
    pygame.draw.line(surf,(20,28,34),(x1-70,ceil_y),(x1-70,floor_y),1)
    # Sag duvar (cikis)
    pygame.draw.rect(surf,DBROWN,(x2,ceil_y,70,floor_y-ceil_y))
    pygame.draw.line(surf,LBROWN,(x2,ceil_y),(x2,floor_y),3)



# ── ACILIS SİNEMASI ───────────────────────────────────────────────────────────
class Opening:
    """Karakter cop yiginine cakiliyor — toz + hurda parcalari saciliyor."""
    IY=400
    def __init__(self,sw,sh):
        self.sw=sw;self.sh=sh;self.t=0.;self.done=False;self.imp=False
        self.debris=[];self.dust=[]
        try:
            self.f1=pygame.font.SysFont("Courier New",26,bold=True)
            self.f2=pygame.font.SysFont("Courier New",15)
        except:
            self.f1=pygame.font.Font(None,32)
            self.f2=pygame.font.Font(None,20)

    def update(self,dt):
        self.t+=dt
        if self.t>=1.5 and not self.imp:
            self.imp=True;cx=self.sw//2
            for _ in range(42):
                a=random.uniform(0,math.pi);s=random.uniform(80,460)
                self.debris.append([cx,self.IY,
                    math.cos(a)*s*random.choice([-1,1]),-math.sin(a)*s,
                    random.uniform(.5,2.2),0.,
                    random.choice([BROWN,DBROWN,GRAY,DGRAY,RUST]),
                    random.randint(3,14)])
            for _ in range(14):
                a=random.uniform(-math.pi,0);s=random.uniform(60,300)
                self.debris.append([cx,self.IY,math.cos(a)*s,math.sin(a)*s,
                    random.uniform(.3,.9),0.,(255,210,50),2])
            for _ in range(24):
                angle=random.uniform(0,math.tau);speed=random.uniform(40,200)
                self.dust.append({
                    "x":float(cx),"y":float(self.IY),
                    "vx":math.cos(angle)*speed,"vy":math.sin(angle)*speed-30,
                    "life":random.uniform(.9,2.4),"t":0.,
                    "r":random.randint(4,18)
                })
        for d in self.debris:
            d[5]+=dt;d[3]+=700*dt;d[0]+=d[2]*dt;d[1]+=d[3]*dt
        for du in self.dust:
            du["t"]+=dt;du["x"]+=du["vx"]*dt;du["y"]+=du["vy"]*dt
            du["vy"]+=140*dt
        self.dust=[du for du in self.dust if du["t"]<du["life"]]
        if self.t>=6.5: self.done=True
        return self.done

    def draw(self,surf):
        t=self.t;surf.fill(BG)
        for i in range(0,self.sw,110):
            pygame.draw.rect(surf,DGRAY,(i,self.sh//2,12,self.sh//2))
        pygame.draw.rect(surf,DBROWN,(0,self.IY+38,self.sw,self.sh))
        pygame.draw.line(surf,BROWN,(0,self.IY+38),(self.sw,self.IY+38),2)
        # Hurda parcalari
        for d in self.debris:
            if d[5]<d[4]:
                a=max(0,1-d[5]/d[4]);s=max(1,int(d[7]*a))
                pygame.draw.rect(surf,d[6],(int(d[0])-s//2,int(d[1])-s//2,s,s))
        # Toz bulutlari
        for du in self.dust:
            prog=du["t"]/du["life"]
            a=int(110*(1-prog));r=max(1,int(du["r"]*(1-prog*0.5)))
            s=pygame.Surface((r*2,r*2),pygame.SRCALPHA)
            pygame.draw.circle(s,(130,110,85,a),(r,r),r)
            surf.blit(s,(int(du["x"])-r,int(du["y"])-r))
        # Karakter animasyonu
        px=self.sw//2
        if t<1.5:
            e=min(t/1.5,1.)**3;py=int(-120+(self.IY+120)*e)
            st=int(10+(t/1.5)*28);pygame.draw.rect(surf,WHITE,(px-10,py,20,st))
        elif t<2.1:
            p=(t-1.5)/.6;pygame.draw.rect(surf,WHITE,(px-10,self.IY-16+int(p*20),20,36))
        elif t<3.0:
            p=(t-2.1)/.9;h=int(12+p*30);pygame.draw.rect(surf,WHITE,(px-10,self.IY+38-h,20,h))
        else:
            pygame.draw.rect(surf,WHITE,(px-10,self.IY,20,40))
        # Carpma flasi
        if 1.5<=t<=1.63:
            a=int(255*(1-(t-1.5)/.13));s=pygame.Surface((self.sw,self.sh),pygame.SRCALPHA)
            s.fill((255,255,255,a));surf.blit(s,(0,0))
        # Baslik: THE GUTTER / ABANDONED SCRAP ZONE
        if t>3.2:
            fa=int(255*min(1.,(t-3.2)/.5))
            bw=500;bh=80;bx=self.sw//2-bw//2;by=80
            bs=pygame.Surface((bw,bh),pygame.SRCALPHA)
            bs.fill((0,0,0,int(195*(fa/255))));surf.blit(bs,(bx,by))
            pygame.draw.rect(surf,(*CYAN,fa),(bx,by,bw,bh),1)
            pygame.draw.rect(surf,(160,18,18),(bx,by,3,bh))
            s1=self.f1.render("THE GUTTER",True,CYAN)
            s1.set_alpha(fa);surf.blit(s1,(bx+14,by+8))
            s2=self.f2.render("ABANDONED SCRAP ZONE",True,(155,195,175))
            s2.set_alpha(fa);surf.blit(s2,(bx+14,by+46))
        # Kararma
        if t>5.8:
            a=int(255*min(1.,(t-5.8)/.7));fo=pygame.Surface((self.sw,self.sh))
            fo.set_alpha(a);fo.fill(BG);surf.blit(fo,(0,0))

# ── BITIS SAHNESI ─────────────────────────────────────────────────────────────
class EndScene:
    """Karakter derin bolume duser — sessizlik, uzakta isiklar, ekran kararir."""
    def __init__(self,sw,sh):
        self.sw=sw;self.sh=sh;self.t=0.;self.done=False
        try:
            self.f1=pygame.font.SysFont("Courier New",28,bold=True)
            self.f2=pygame.font.SysFont("Courier New",14)
        except:
            self.f1=pygame.font.Font(None,34)
            self.f2=pygame.font.Font(None,18)
    def update(self,dt): self.t+=dt;self.done=self.t>5.2;return self.done
    def draw(self,surf):
        a=int(255*min(1.,self.t/.75))
        fo=pygame.Surface((self.sw,self.sh))
        fo.set_alpha(a);fo.fill(BG_DEEP);surf.blit(fo,(0,0))
        if self.t>1.3:
            ta=int(255*min(1.,(self.t-1.3)/.6))
            s=self.f1.render("DEEPER LEVEL",True,CYAN)
            s.set_alpha(ta);surf.blit(s,(self.sw//2-s.get_width()//2,self.sh//2-28))
        if self.t>2.3:
            ta2=int(255*min(1.,(self.t-2.3)/.5))
            s2=self.f2.render("SETTLEMENT DETECTED  —  HUMAN TERRITORY",True,(95,150,128))
            s2.set_alpha(ta2);surf.blit(s2,(self.sw//2-s2.get_width()//2,self.sh//2+16))

# ── ANA DONGU ─────────────────────────────────────────────────────────────────
def main():
    pygame.init()
    screen=pygame.display.set_mode((SW,SH))
    pygame.display.set_caption("THE GUTTER — BOLUM 01")
    clock=pygame.time.Clock()

    try:
        fhud=pygame.font.SysFont("Courier New",13)
        fdead=pygame.font.SysFont("Courier New",34,bold=True)
        fbig=pygame.font.SysFont("Courier New",38,bold=True)
        fmed=pygame.font.SysFont("Courier New",22,bold=True)
    except:
        fhud=pygame.font.Font(None,16);fdead=pygame.font.Font(None,40)
        fbig=pygame.font.Font(None,48);fmed=pygame.font.Font(None,28)

    cam=Cam();eq=[]
    state="cutscene"
    opening=Opening(SW,SH);endscene=EndScene(SW,SH)
    dead_t=0.;end_done=False;col_rm=False;game_t=0.

    # ====================================================================
    # SEVIYE DUZENI  (soldan saga anlatiya gore)
    #
    #  BOLGE 1  x=0–1500      COP DAGI         FLOOR1=1200
    #  BOLGE 2  x=1300–1500   INIS / GECIS
    #  BOLGE 3  x=1500–2200   DAR HURDA TUNELI  FLOOR2=820  (gorsel tavan)
    #  BOLGE 4  x=2200–2700   COP AKINTISI      FLOOR2      FallingScrap
    #  BOLGE 5  x=2700–3050   KUCUK DOVAS ALANI FLOOR2      2 Grunt
    #  BOLGE 6  x=3060        COKEN PLATFORM    ColPlat
    #  BOLGE 7  x=3300–4100   DERIN BOLUM       FLOOR1      atmosfer
    # ====================================================================

    plats=[
        # Ana zemin bloklar
        pygame.Rect(0,    FLOOR1,1500,160),   # Cop Dagi
        pygame.Rect(1300, FLOOR2,1800, 20),   # Tunel + Dovus zemini
        pygame.Rect(3300, FLOOR1, 900,160),   # Derin Bolum

        # -- COP DAGI tirmanma platformlari (zigzag) --
        pygame.Rect(  40,1120,200,22), pygame.Rect(160,1050,170,22),
        pygame.Rect(  90, 970,160,22), pygame.Rect(270, 908,195,22),
        pygame.Rect( 200, 838,145,22), pygame.Rect(390, 768,185,22),
        pygame.Rect( 310, 692,140,22), pygame.Rect(490, 618,195,22),
        pygame.Rect( 410, 538,165,22), pygame.Rect(590, 458,215,22),
        pygame.Rect( 510, 378,160,22),
        pygame.Rect( 690, 308,240,22),   # TEPE — ilk dövüş

        # -- Tepeden inis --
        pygame.Rect( 970, 400,175,22),
        pygame.Rect(1100, 530,175,22),
        pygame.Rect(1210, 670,160,22),

        # -- Tunel ici atlama platformlari --
        pygame.Rect(1660, 750,120,18),
        pygame.Rect(1840, 700,110,18),
        pygame.Rect(2010, 750,120,18),
        pygame.Rect(2110, 700,110,18),

        # -- Cop Akintisi gecis platformlari --
        pygame.Rect(2250, 760,120,18),
        pygame.Rect(2430, 720,120,18),
        pygame.Rect(2580, 760,120,18),
    ]

    # Coken platform — dar kopru, BOLGE 5 sonu
    colp=ColPlat(3060,FLOOR2-20,240,cam)
    colp.set_floor(FLOOR1)
    plats.append(colp.rect)

    # Dusmanlar:
    #   enemies[0] = BOLGE 1 tepe — ilk tehlike (tek, kisa savas)
    #   enemies[1] = BOLGE 5 — kucuk dovas alani, birinci
    #   enemies[2] = BOLGE 5 — kucuk dovas alani, ikinci
    enemies=[
        Grunt(960,  290),   # ilk tehlike
        Grunt(2760, 800),   # kucuk dovas - 1
        Grunt(2900, 800),   # kucuk dovas - 2
    ]

    falling_scrap=FallingScrap(ZONE_AVALAN_X1,ZONE_AVALAN_X2)

    player=Player(55,FLOOR1-44)
    hint_t=0.;HINT_DUR=5.0

    while True:
        dt=min(clock.tick(FPS)/1000.,.05)

        for ev in pygame.event.get():
            if ev.type==pygame.QUIT: pygame.quit();sys.exit()
            if ev.type==pygame.KEYDOWN:
                if ev.key==pygame.K_ESCAPE: pygame.quit();sys.exit()
                if ev.key==pygame.K_r: main();return
                if state=="play":
                    if ev.key in(pygame.K_j,pygame.K_z,pygame.K_LCTRL):
                        if player.ac<=0:
                            player.ac=.32
                            hx=player.rect.centerx+player.f*52
                            hr=pygame.Rect(hx-18,player.rect.y,36,player.H)
                            for e in enemies:
                                if e.state!="dead" and hr.colliderect(e.rect): e.hit(cam)
                    if ev.key in(pygame.K_k,pygame.K_x,pygame.K_LSHIFT): player.dash()

        for e2 in eq:
            if e2["t"]=="HIT" and state=="play":
                player.take_hit(cam)
                if not player.alive: state="dead";dead_t=0.
            elif e2["t"]=="COL" and not col_rm:
                col_rm=True
                if colp.rect in plats: plats.remove(colp.rect)
        eq.clear()

        if state=="cutscene":
            if opening.update(dt):
                state="play";player.rect.topleft=(55,FLOOR1-44);hint_t=0.
        elif state=="play":
            hint_t+=dt;game_t+=dt
            player.update(dt,plats)
            colp.update(dt,eq)
            falling_scrap.try_activate(player.rect.centerx)
            falling_scrap.update(dt)
            if falling_scrap.check_hit(player.rect): player.take_hit(cam)
            for e in enemies: e.update(dt,player,plats,eq)
            if player.rect.top>WH+80:
                player.hp=0;player.alive=False;state="dead";dead_t=0.
            if not colp.fallen and player.rect.colliderect(colp.rect) and player.vy>=0:
                colp.trigger()
            cam.update(dt,player.rect.centerx,player.rect.centery,player.f)
            cam.y=max(0.,min(cam.y,float(WH-SH)))
            if pygame.Rect(ZONE_END_X,FLOOR1-200,80,400).colliderect(player.rect) and not end_done:
                end_done=True;state="endseq"
        elif state=="endseq":
            game_t+=dt
            if endscene.update(dt): state="done"
        elif state=="dead":
            dead_t+=dt
            if dead_t>3.: main();return

        ox=cam.ox;oy=cam.oy

        if state=="cutscene":
            opening.draw(screen)
        else:
            screen.fill(BG)

            # Platformlar
            for r in plats:
                if col_rm and r is colp.rect: continue
                scrap_look=(r.x<1500 and r.h<50)
                draw_plat(screen,r,ox,oy,scrap=scrap_look)

            colp.draw(screen,ox,oy)

            # Dar Hurda Tuneli gorsel (coken duvarlar + tavan)
            draw_tunnel(screen,ox,oy)

            # Ikaz levhasi (Cop Akintisi oncesi)
            # Cop Akintisi parcalari
            falling_scrap.draw(screen,ox,oy)

            # Dusmanlar + oyuncu
            for e in enemies: e.draw(screen,ox,oy)
            if player.alive: player.draw(screen,ox,oy)

            # Bitis cizgisi
            ex=ZONE_END_X-ox
            pygame.draw.line(screen,CYAN,(ex,0),(ex,SH),1)

            if state in("endseq","done"): endscene.draw(screen)

            # Kontrol ipucu
            if state=="play" and hint_t<HINT_DUR:
                alpha=255
                if hint_t>HINT_DUR-1.2: alpha=int(255*(HINT_DUR-hint_t)/1.2)
                bw=680;bh=160;bx2=SW//2-bw//2;by2=SH//2-bh//2
                hs=pygame.Surface((bw,bh),pygame.SRCALPHA)
                hs.fill((0,0,0,int(210*(alpha/255))))
                screen.blit(hs,(bx2,by2))
                pygame.draw.rect(screen,(*CYAN,alpha),(bx2,by2,bw,bh),2)
                lines=[("← A   D →   HAREKET",fbig),("W   ZIPLAMA",fmed),("J   SALDIRI  /  K   DASH",fmed)]
                for i,(txt,fnt) in enumerate(lines):
                    s=fnt.render(txt,True,CYAN if i==0 else AMBER)
                    s.set_alpha(alpha)
                    screen.blit(s,(SW//2-s.get_width()//2,by2+14+i*46))

            # HUD — can
            if state=="play":
                for i in range(player.HP):
                    c=RED if i<player.hp else (30,16,16)
                    pygame.draw.rect(screen,c,(14+i*22,14,16,8))
                    pygame.draw.rect(screen,(75,18,18),(14+i*22,14,16,8),1)

            # Olum ekrani
            if state=="dead":
                fo=pygame.Surface((SW,SH));fo.set_alpha(min(210,int(dead_t*105)));fo.fill(BG);screen.blit(fo,(0,0))
                dm=fdead.render("// TERMINATED //",True,RED)
                screen.blit(dm,(SW//2-dm.get_width()//2,SH//2-20))
                dm2=fhud.render("R  yeniden",True,(115,28,28))
                screen.blit(dm2,(SW//2-dm2.get_width()//2,SH//2+18))

        pygame.display.flip()

if __name__=="__main__":
    main()