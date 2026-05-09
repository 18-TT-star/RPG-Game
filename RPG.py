"""
初代ゼルダ風ゲーム ─ 一画面プロトタイプ
操作: 矢印キーで移動/スペースキーで攻撃
"""

import sys
import random
import pygame

# ─── 定数 ────────────────────────────────────────────────
TILE      = 48          # 1タイルのピクセルサイズ
COLS      = 16          # 横タイル数
ROWS      = 11          # 縦タイル数
HUD_H     = 64          # HUDエリアの高さ
WIN_W     = TILE * COLS # 768
WIN_H     = TILE * ROWS + HUD_H  # 592
FPS       = 60

# タイル種別
FLOOR = 0
WALL  = 1
TREE  = 2
WATER = 3
PATH  = 4
DOOR  = 5  # 扉（通行可能）

# タイルカラー (メイン色, ハイライト色, シャドウ色)
TILE_COLORS = {
    FLOOR: ((104, 160,  80), (134, 190, 110), ( 74, 130,  50)),
    WALL:  ((128, 128, 128), (160, 160, 160), ( 88,  88,  88)),
    TREE:  (( 40, 100,  40), ( 60, 140,  60), ( 20,  70,  20)),
    WATER: (( 64, 128, 200), ( 96, 160, 230), ( 40,  96, 160)),
    PATH:  ((192, 168, 120), (210, 190, 150), (160, 136,  96)),
    DOOR:  ((160, 100,  40), (200, 140,  80), (100,  60,  20)),
}

# 衝突するタイル
SOLID_TILES = {WALL, TREE, WATER}

# ─── タイル記号 & ダンジョングリッド定数 ───────────────────────────
# W=壁, F=床, T=木, A=水, P=砂道, D=扉
_W, _F, _T, _A, _P, _D = WALL, FLOOR, TREE, WATER, PATH, DOOR

# ダンジョン: 5×5 グリッド配置
GRID_ROWS  = 5
GRID_COLS  = 5
N_ROOMS    = GRID_ROWS * GRID_COLS           # 25
START_ROOM = (GRID_ROWS - 1) * GRID_COLS + GRID_COLS // 2  # 22 (下段中央)


# ─── ランダム部屋生成 ────────────────────────────────────────────────

def _near_passage(r: int, c: int,
                  top: bool, bottom: bool,
                  left: bool, right: bool) -> bool:
    """通路入口付近（障害物配置禁止ゾーン）かどうか"""
    if top    and r <= 2 and 6 <= c <= 9:  return True
    if bottom and r >= 8 and 6 <= c <= 9:  return True
    if left   and 3 <= r <= 6 and c <= 2:  return True
    if right  and 3 <= r <= 6 and c >= 13: return True
    return False


def generate_room(top: bool = True, bottom: bool = True,
                  left: bool = True, right: bool = True) -> list:
    """指定4方向に通路を持つランダム部屋マップを生成する"""
    grid = [[_W] * COLS for _ in range(ROWS)]
    for r in range(1, ROWS - 1):
        for c in range(1, COLS - 1):
            grid[r][c] = _F
    if top:    grid[0][7]  = _D; grid[0][8]  = _D
    if bottom: grid[10][7] = _D; grid[10][8] = _D
    if left:   grid[4][0]  = _D; grid[5][0]  = _D
    if right:  grid[4][15] = _D; grid[5][15] = _D
    # ランダム障害物
    for _ in range(random.randint(4, 10)):
        r = random.randint(1, ROWS - 2)
        c = random.randint(1, COLS - 2)
        if _near_passage(r, c, top, bottom, left, right):
            continue
        grid[r][c] = random.choice([_W, _W, _T, _A])
    # ランダム砂道
    for _ in range(random.randint(0, 3)):
        r = random.randint(2, ROWS - 3)
        c = random.randint(2, COLS - 3)
        dr, dc = random.choice([(0, 1), (1, 0)])
        for i in range(random.randint(3, 7)):
            nr, nc = r + dr * i, c + dc * i
            if 1 <= nr <= ROWS - 2 and 1 <= nc <= COLS - 2:
                if grid[nr][nc] == _F:
                    grid[nr][nc] = _P
    return grid


# ─── 部屋グラフ（ゲーム開始時に build_dungeon() で構築） ───────────
ROOM_MAPS:  dict = {}
ROOM_EXITS: dict = {}
ROOM_TYPES: dict = {}

# 現在の部屋マップ（_solid_at系が参照するグローバル）
CURRENT_MAP: list = []


def build_dungeon() -> None:
    """ゲーム開始/リスタートごとに 5×5 ダンジョングリッドを再構築する"""
    global ROOM_MAPS, ROOM_EXITS, ROOM_TYPES
    ROOM_MAPS  = {}
    ROOM_EXITS = {}
    ROOM_TYPES = {}

    # 各部屋をグリッド位置に応じた通路で生成（境界壁には扉なし）
    for gr in range(GRID_ROWS):
        for gc in range(GRID_COLS):
            room_id    = gr * GRID_COLS + gc
            has_top    = gr > 0
            has_bottom = gr < GRID_ROWS - 1
            has_left   = gc > 0
            has_right  = gc < GRID_COLS - 1
            ROOM_MAPS[room_id] = generate_room(has_top, has_bottom, has_left, has_right)

    # 部屋タイプ割り当て（スタート部屋は 'main'、残りはランダム）
    other_rooms = [i for i in range(N_ROOMS) if i != START_ROOM]
    n_others    = len(other_rooms)   # 24
    n_monster   = n_others // 2     # 12
    type_list   = ['monster'] * n_monster + ['treasure'] * (n_others - n_monster)
    random.shuffle(type_list)
    ROOM_TYPES[START_ROOM] = 'main'
    for room_id, rtype in zip(other_rooms, type_list):
        ROOM_TYPES[room_id] = rtype

    # 隣接部屋への出口マッピング（グリッド端は出口なし）
    for gr in range(GRID_ROWS):
        for gc in range(GRID_COLS):
            room_id = gr * GRID_COLS + gc
            # 上壁 (tile row=0) → 上の部屋の下側内側 (row=9)
            if gr > 0:
                above = (gr - 1) * GRID_COLS + gc
                ROOM_EXITS[(room_id,  7,  0)] = (above, 7, 9)
                ROOM_EXITS[(room_id,  8,  0)] = (above, 7, 9)
            # 下壁 (tile row=10) → 下の部屋の上側内側 (row=1)
            if gr < GRID_ROWS - 1:
                below = (gr + 1) * GRID_COLS + gc
                ROOM_EXITS[(room_id,  7, 10)] = (below, 7, 1)
                ROOM_EXITS[(room_id,  8, 10)] = (below, 7, 1)
            # 左壁 (tile col=0) → 左の部屋の右側内側 (col=13)
            if gc > 0:
                left_r = gr * GRID_COLS + (gc - 1)
                ROOM_EXITS[(room_id,  0,  4)] = (left_r, 13, 5)
                ROOM_EXITS[(room_id,  0,  5)] = (left_r, 13, 5)
            # 右壁 (tile col=15) → 右の部屋の左側内側 (col=2)
            if gc < GRID_COLS - 1:
                right_r = gr * GRID_COLS + (gc + 1)
                ROOM_EXITS[(room_id, 15,  4)] = (right_r, 2, 5)
                ROOM_EXITS[(room_id, 15,  5)] = (right_r, 2, 5)


# ─── タイル描画 ───────────────────────────────────────────
def draw_tile(surf: pygame.Surface, col: int, row: int, kind: int) -> None:
    # DOORは通路なので床と全く同じ視覚に描画（壁が凹んだ地続きの通路）
    render = FLOOR if kind == DOOR else kind
    x = col * TILE
    y = row * TILE
    mc, hi, sh = TILE_COLORS[render]
    rect = pygame.Rect(x, y, TILE, TILE)
    pygame.draw.rect(surf, mc, rect)

    if render == FLOOR:
        # 格子状のグラスライン
        for i in range(1, 4):
            pygame.draw.line(surf, sh, (x + i * 12, y), (x + i * 12, y + TILE), 1)
            pygame.draw.line(surf, sh, (x, y + i * 12), (x + TILE, y + i * 12), 1)

    elif render == WALL:
        # レンガ風
        half = TILE // 2
        pygame.draw.rect(surf, sh, (x, y, TILE, 2))
        pygame.draw.rect(surf, hi, (x, y + 2, TILE, 4))
        pygame.draw.rect(surf, sh, (x, y + half, TILE, 2))
        pygame.draw.rect(surf, hi, (x, y + half + 2, TILE, 4))
        pygame.draw.line(surf, sh, (x + TILE // 4, y),      (x + TILE // 4, y + half), 2)
        pygame.draw.line(surf, sh, (x + 3 * TILE // 4, y + half), (x + 3 * TILE // 4, y + TILE), 2)

    elif render == TREE:
        # 幹 + 丸い葉
        trunk_rect = pygame.Rect(x + TILE // 2 - 5, y + TILE // 2, 10, TILE // 2)
        pygame.draw.rect(surf, (100, 60, 20), trunk_rect)
        pygame.draw.circle(surf, hi, (x + TILE // 2, y + TILE // 2 - 2), TILE // 3)
        pygame.draw.circle(surf, sh, (x + TILE // 2 - 6, y + TILE // 2), TILE // 5)
        pygame.draw.circle(surf, sh, (x + TILE // 2 + 6, y + TILE // 2), TILE // 5)

    elif render == WATER:
        # 波紋ライン
        for i in range(3):
            wy = y + 10 + i * 14
            pygame.draw.arc(surf, hi,
                            pygame.Rect(x + 4, wy, 18, 8), 0, 3.14, 2)
            pygame.draw.arc(surf, hi,
                            pygame.Rect(x + 24, wy, 18, 8), 0, 3.14, 2)

    elif render == PATH:
        # 砂利ドット
        dots = [(x + 8, y + 8), (x + 28, y + 16), (x + 14, y + 30),
                (x + 36, y + 36), (x + 22, y + 42)]
        for dx, dy in dots:
            pygame.draw.circle(surf, sh, (dx, dy), 3)

    elif render == DOOR:
        pass  # render=FLOOR にリダイレクト済みのためここには到達しない


def build_tile_surface(room_map: list) -> pygame.Surface:
    """指定マップ1枚のサーフェイスに描画してキャッシュする"""
    surf = pygame.Surface((WIN_W, WIN_H - HUD_H))
    for row in range(ROWS):
        for col in range(COLS):
            draw_tile(surf, col, row, room_map[row][col])
    return surf


# ─── Player クラス ────────────────────────────────────────
class Player:
    SPEED = 3
    SIZE  = 28  # 当たり判定の正方形サイズ

    def __init__(self, x: float, y: float) -> None:
        self.x   = float(x)
        self.y   = float(y)
        self.dir    = (0, 1)   # 向き (dx, dy)
        self.facing = (0, 1)   # 4方向の向き（剣判定用）
        self.max_hp = 8
        self.hp     = 6
        self.attack_timer    = 0   # >0 の間攻撃モーション中
        self.attack_cooldown = 0   # >0 の間攻撃不可
        self._attacked_set: set = set()  # 今の振りでダメージ済みの敵id
        self.inv_timer = 0   # ダメージ後の無敵フレーム数
        self.kbx = 0.0       # ヒットバック速度X
        self.kby = 0.0       # ヒットバック速度Y

    # 移動とタイル衝突
    def update(self, keys) -> None:
        # 攻撃中は移動入力を無視（硬直）
        if self.attack_timer <= 0:
            dx = dy = 0
            if keys[pygame.K_LEFT]:   dx = -self.SPEED
            if keys[pygame.K_RIGHT]:  dx =  self.SPEED
            if keys[pygame.K_UP]:     dy = -self.SPEED
            if keys[pygame.K_DOWN]:   dy =  self.SPEED

            # 斜め移動時は速度を正規化
            if dx and dy:
                dx = int(dx * 0.707)
                dy = int(dy * 0.707)

            if dx or dy:
                self.dir = (dx, dy)
                # facing は常に4方向（水平優先）
                if dx != 0:
                    self.facing = (1 if dx > 0 else -1, 0)
                else:
                    self.facing = (0, 1 if dy > 0 else -1)

            if dx:
                nx = self.x + dx
                if not self._solid_at(nx, self.y):
                    self.x = nx
            if dy:
                ny = self.y + dy
                if not self._solid_at(self.x, ny):
                    self.y = ny

        # ヒットバック処理
        if self.kbx or self.kby:
            if not self._solid_at(self.x + self.kbx, self.y):
                self.x += self.kbx
            if not self._solid_at(self.x, self.y + self.kby):
                self.y += self.kby
            self.kbx *= 0.70
            self.kby *= 0.70
            if abs(self.kbx) < 0.3: self.kbx = 0.0
            if abs(self.kby) < 0.3: self.kby = 0.0

        # 攻撃タイマー更新
        if self.attack_timer > 0:
            self.attack_timer -= 1
            if self.attack_timer == 0:
                self._attacked_set.clear()
        if self.attack_cooldown > 0:
            self.attack_cooldown -= 1
        if self.inv_timer > 0:
            self.inv_timer -= 1

        # 画面端クランプ
        margin = (TILE - self.SIZE) / 2
        self.x = max(0, min(self.x, WIN_W - self.SIZE))
        self.y = max(0, min(self.y, TILE * ROWS - self.SIZE))

    def _solid_at(self, px: float, py: float) -> bool:
        """プレイヤー矩形の4頂点がどれかソリッドタイルに入ったら True"""
        s = self.SIZE
        corners = [
            (px + 2,         py + 2),
            (px + s - 3,     py + 2),
            (px + 2,         py + s - 3),
            (px + s - 3,     py + s - 3),
        ]
        for cx, cy in corners:
            col = int(cx // TILE)
            row = int(cy // TILE)
            if 0 <= row < ROWS and 0 <= col < COLS:
                if CURRENT_MAP[row][col] in SOLID_TILES:
                    return True
            else:
                return True  # 画面外もソリッド
        return False

    def try_attack(self) -> bool:
        """攻撃を発動。クールダウン中は無効。"""
        if self.attack_cooldown == 0:
            self.attack_timer    = 14
            self.attack_cooldown = 28
            self._attacked_set.clear()
            return True
        return False

    def take_damage(self, amount: int = 1, kbx: float = 0.0, kby: float = 0.0) -> None:
        """ダメージを受ける。無敵時間中は無効。"""
        if self.inv_timer > 0:
            return
        self.hp = max(0, self.hp - amount)
        self.inv_timer = 60   # 1秒間無敵
        self.kbx = kbx
        self.kby = kby

    def sword_rect(self):
        """攻撃中なら剣の当たり判定Rectを返す。していなければNone。"""
        if self.attack_timer <= 0:
            return None
        x, y = int(self.x), int(self.y)
        s = self.SIZE
        fdx, fdy = self.facing
        if fdx == 1:    # 右
            return pygame.Rect(x + s,          y + s // 2 - 6, 26, 12)
        elif fdx == -1: # 左
            return pygame.Rect(x - 26,         y + s // 2 - 6, 26, 12)
        elif fdy == 1:  # 下
            return pygame.Rect(x + s // 2 - 6, y + s,          12, 26)
        else:           # 上
            return pygame.Rect(x + s // 2 - 6, y - 26,         12, 26)

    def draw(self, surf: pygame.Surface) -> None:
        # 無敵中は点滅（一定間隔で描画スキップ）
        if self.inv_timer > 0 and self.inv_timer % 6 < 3:
            return
        x, y = int(self.x), int(self.y)
        s = self.SIZE
        # 体 (緑チュニック)
        body_rect = pygame.Rect(x + 6, y + 12, s - 12, s - 12)
        pygame.draw.rect(surf, (60, 160, 60), body_rect)
        # 頭
        pygame.draw.circle(surf, (220, 180, 130), (x + s // 2, y + 8), 8)
        # 帽子
        hat_points = [
            (x + s // 2 - 8, y + 8),
            (x + s // 2,     y - 4),
            (x + s // 2 + 8, y + 8),
        ]
        pygame.draw.polygon(surf, (60, 160, 60), hat_points)
        # 盾 (向き左右で位置変更)
        shield_x = x + 2 if self.dir[0] <= 0 else x + s - 8
        pygame.draw.rect(surf, (80, 80, 200),
                         pygame.Rect(shield_x, y + 14, 6, 12))
        # 攻撃中は剣を描画
        sr = self.sword_rect()
        if sr:
            pygame.draw.rect(surf, (200, 200, 80), sr)
            hi = sr.inflate(-4, -4)
            if hi.width > 0 and hi.height > 0:
                pygame.draw.rect(surf, (240, 240, 200), hi)


# ─── Enemy クラス ───────────────────────────────────────────
class Enemy:
    SPEED = 1
    SIZE  = 28

    DIRS = [(1, 0), (-1, 0), (0, 1), (0, -1), (0, 0)]

    def __init__(self, x: float, y: float) -> None:
        self.x = float(x)
        self.y = float(y)
        self.dx = 0
        self.dy = 0
        self.move_timer = 0
        self.hp        = 2
        self.hit_timer = 0   # >0 の間ヒットフラッシュ
        self.alive     = True
        self.kbx       = 0.0  # ヒットバック速度X
        self.kby       = 0.0  # ヒットバック速度Y
        self._pick_direction()

    def _pick_direction(self) -> None:
        d = random.choice(self.DIRS)
        self.dx, self.dy = d
        self.move_timer = random.randint(60, 180)

    def take_damage(self, amount: int = 1, kbx: float = 0.0, kby: float = 0.0) -> None:
        self.hp -= amount
        self.hit_timer = 10
        self.kbx = kbx
        self.kby = kby
        if self.hp <= 0:
            self.alive = False

    def update(self) -> None:
        if self.hit_timer > 0:
            self.hit_timer -= 1
        # ヒットバック処理
        if self.kbx or self.kby:
            if not self._solid_at(self.x + self.kbx, self.y):
                self.x += self.kbx
            if not self._solid_at(self.x, self.y + self.kby):
                self.y += self.kby
            self.kbx *= 0.70
            self.kby *= 0.70
            if abs(self.kbx) < 0.3: self.kbx = 0.0
            if abs(self.kby) < 0.3: self.kby = 0.0
        self.move_timer -= 1
        if self.move_timer <= 0:
            self._pick_direction()

        nx = self.x + self.dx * self.SPEED
        ny = self.y + self.dy * self.SPEED

        moved = False
        if self.dx:
            if not self._solid_at(nx, self.y):
                self.x = nx
                moved = True
            else:
                self._pick_direction()
        if self.dy:
            if not self._solid_at(self.x, ny):
                self.y = ny
                moved = True
            else:
                self._pick_direction()

        # 画面端クランプ
        self.x = max(0, min(self.x, WIN_W - self.SIZE))
        self.y = max(0, min(self.y, TILE * ROWS - self.SIZE))

    def _solid_at(self, px: float, py: float) -> bool:
        s = self.SIZE
        corners = [
            (px + 2,     py + 2),
            (px + s - 3, py + 2),
            (px + 2,     py + s - 3),
            (px + s - 3, py + s - 3),
        ]
        for cx, cy in corners:
            col = int(cx // TILE)
            row = int(cy // TILE)
            if 0 <= row < ROWS and 0 <= col < COLS:
                if CURRENT_MAP[row][col] in SOLID_TILES:
                    return True
            else:
                return True
        return False

    def draw(self, surf: pygame.Surface) -> None:
        x, y = int(self.x), int(self.y)
        s = self.SIZE
        # ヒット中は白くフラッシュ
        body_color = (255, 255, 255) if self.hit_timer > 0 else (200, 40, 40)
        hi_color   = (255, 255, 255) if self.hit_timer > 0 else (230, 80, 80)
        # ボディ (赤いスライム楕円)
        body_rect = pygame.Rect(x + 2, y + 8, s - 4, s - 8)
        pygame.draw.ellipse(surf, body_color, body_rect)
        # ハイライト
        pygame.draw.ellipse(surf, hi_color,
                            pygame.Rect(x + 6, y + 10, (s - 4) // 2, (s - 8) // 3))
        # 目 (白目)
        pygame.draw.circle(surf, (255, 255, 255), (x + 9,  y + 14), 4)
        pygame.draw.circle(surf, (255, 255, 255), (x + 19, y + 14), 4)
        # 瞳
        pygame.draw.circle(surf, (20, 20, 20),   (x + 10, y + 15), 2)
        pygame.draw.circle(surf, (20, 20, 20),   (x + 20, y + 15), 2)


# ─── HUD 描画 ─────────────────────────────────────────────
def draw_hud(surf: pygame.Surface, player: Player) -> None:
    hud_y = TILE * ROWS
    hud_rect = pygame.Rect(0, hud_y, WIN_W, HUD_H)
    pygame.draw.rect(surf, (20, 20, 20), hud_rect)
    pygame.draw.line(surf, (80, 80, 80), (0, hud_y), (WIN_W, hud_y), 2)

    # ハート
    heart_size = 20
    gap        = 6
    start_x    = 20
    start_y    = hud_y + (HUD_H - heart_size) // 2

    for i in range(player.max_hp):
        hx = start_x + i * (heart_size + gap)
        hy = start_y
        color = (220, 40, 40) if i < player.hp else (70, 70, 70)
        _draw_heart(surf, hx, hy, heart_size, color)


def _draw_heart(surf: pygame.Surface, x: int, y: int, size: int,
                color: tuple) -> None:
    """ハートを2つの円+三角形で描く"""
    half = size // 2
    r    = half // 2
    pygame.draw.circle(surf, color, (x + r,        y + r), r)
    pygame.draw.circle(surf, color, (x + half + r, y + r), r)
    points = [
        (x,               y + r),
        (x + half * 2,    y + r),
        (x + half,        y + size - 2),
    ]
    pygame.draw.polygon(surf, color, points)


import math


# ─── 爆発エフェクトクラス ─────────────────────────────────────
class Explosion:
    """パーティクルベースの爆発アニメーション。
    火花パーティクルが外側に削れてフェードアウトする。"""
    DURATION = 28    # 総フレーム数
    N_PARTICLES = 14  # パーティクル数

    def __init__(self, cx: float, cy: float) -> None:
        self.cx    = cx
        self.cy    = cy
        self.timer = self.DURATION
        # 各パーティクル: [起点x, 起点y, vx, vy, 色, 半径]
        self._particles = []
        for i in range(self.N_PARTICLES):
            angle = (2 * math.pi / self.N_PARTICLES) * i + random.uniform(-0.3, 0.3)
            speed = random.uniform(1.5, 4.0)
            vx    = math.cos(angle) * speed
            vy    = math.sin(angle) * speed
            # 点火色: 白→黄→オレンジ→赤→灰
            color = random.choice([
                (255, 255, 200),
                (255, 220,  60),
                (255, 140,  20),
                (220,  60,  20),
                (160,  80,  80),
            ])
            r = random.randint(3, 6)
            self._particles.append([cx, cy, vx, vy, color, r])
        # 中心自体の円（リング爆発）用
        self._ring_r = 0.0

    @property
    def alive(self) -> bool:
        return self.timer > 0

    def update(self) -> None:
        self.timer -= 1
        t = self.timer / self.DURATION      # 1.0 → 0.0
        self._ring_r = (1.0 - t) * 28
        for p in self._particles:
            p[0] += p[2]   # x += vx
            p[1] += p[3]   # y += vy
            p[2] *= 0.90   # 気流摂動
            p[3] *= 0.90

    def draw(self, surf: pygame.Surface) -> None:
        t    = self.timer / self.DURATION    # 1.0 → 0.0
        alpha = int(255 * t)
        for p in self._particles:
            px, py, _, _, color, r = p
            # 残時間に応じて小さくなる
            cur_r = max(1, int(r * t))
            # 色をフェード
            fc = tuple(max(0, min(255, int(c * t))) for c in color)
            pygame.draw.circle(surf, fc, (int(px), int(py)), cur_r)
        # リング
        ring_alpha = int(255 * t)
        ring_r = int(self._ring_r)
        if ring_r > 1:
            ring_color = (255, max(0, int(180 * t)), 0)
            pygame.draw.circle(surf, ring_color,
                               (int(self.cx), int(self.cy)), ring_r, 2)


# ─── 敵スポーン位置をランダムに決定 ──────────────────────────────────
def spawn_enemy_pos(player_x: float, player_y: float,
                    min_dist: int = 5) -> tuple[float, float]:
    """ソリッドでなく、プレイヤーからmin_distタイル以上離れたタイルをランダム選択"""
    candidates = []
    for row in range(1, ROWS - 1):
        for col in range(1, COLS - 1):
            if CURRENT_MAP[row][col] in SOLID_TILES:
                continue
            if CURRENT_MAP[row][col] == DOOR:
                continue
            px_tile = int(player_x // TILE)
            py_tile = int(player_y // TILE)
            if abs(col - px_tile) < min_dist and abs(row - py_tile) < min_dist:
                continue
            candidates.append((col, row))
    col, row = random.choice(candidates)
    # タイル内の左上ピクセル＋少し余白
    x = col * TILE + (TILE - Enemy.SIZE) // 2
    y = row * TILE + (TILE - Enemy.SIZE) // 2
    return float(x), float(y)


# ─── 部屋遷移ヘルパー ─────────────────────────────────────────
def enter_room(room_id: int, spawn_col: int, spawn_row: int,
               player: "Player") -> tuple:
    """部屋遷移処理。CURRENT_MAP更新・tile_surf再ビルド・enemies生成を返す"""
    global CURRENT_MAP
    CURRENT_MAP = ROOM_MAPS[room_id]
    tile_surf = build_tile_surface(CURRENT_MAP)
    player.x = float(spawn_col * TILE + (TILE - player.SIZE) // 2)
    player.y = float(spawn_row * TILE + (TILE - player.SIZE) // 2)
    player.attack_timer = 0
    player.attack_cooldown = 0
    # 部屋タイプで敵数を決定
    rtype = ROOM_TYPES.get(room_id, 'main')
    n_enemies = 5 if rtype == 'monster' else (2 if rtype == 'main' else 0)
    enemies = [Enemy(*spawn_enemy_pos(player.x, player.y)) for _ in range(n_enemies)]
    return tile_surf, enemies


# ─── メイン ───────────────────────────────────────────────
def main() -> None:
    global CURRENT_MAP
    pygame.init()
    screen = pygame.display.set_mode((WIN_W, WIN_H))
    pygame.display.set_caption("Zelda-like  ─  One Screen Prototype")
    clock = pygame.time.Clock()
    font_room = pygame.font.SysFont("msgothic", 18)

    build_dungeon()
    current_room = START_ROOM
    CURRENT_MAP = ROOM_MAPS[current_room]
    tile_surf = build_tile_surface(CURRENT_MAP)

    # プレイヤーをスタート部屋中央に配置
    player = Player(
        x=TILE * 7 + (TILE - Player.SIZE) // 2,
        y=TILE * 5 + (TILE - Player.SIZE) // 2,
    )

    # スタート部屋 (main): 敵2体
    enemies = [
        Enemy(*spawn_enemy_pos(player.x, player.y)),
        Enemy(*spawn_enemy_pos(player.x, player.y)),
    ]
    explosions: list = []
    door_cooldown = 0  # 連続遷移防止
    game_over = False

    # 部屋タイプ名
    _TYPE_NAMES = {
        'main':     'フィールド',
        'monster':  'モンスターハウス',
        'treasure': '宝部屋',
    }

    running = True
    while running:
        # ── イベント ──
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_SPACE:
                    if not game_over:
                        player.try_attack()
                elif event.key == pygame.K_r and game_over:
                    # リスタート
                    build_dungeon()
                    current_room = START_ROOM
                    CURRENT_MAP = ROOM_MAPS[current_room]
                    tile_surf = build_tile_surface(CURRENT_MAP)
                    player = Player(
                        x=TILE * 7 + (TILE - Player.SIZE) // 2,
                        y=TILE * 5 + (TILE - Player.SIZE) // 2,
                    )
                    enemies = [
                        Enemy(*spawn_enemy_pos(player.x, player.y)),
                        Enemy(*spawn_enemy_pos(player.x, player.y)),
                    ]
                    explosions.clear()
                    door_cooldown = 0
                    game_over = False

        # ── 更新 ──
        if not game_over:
            keys = pygame.key.get_pressed()
            player.update(keys)
            for e in enemies:
                e.update()

            if door_cooldown > 0:
                door_cooldown -= 1

            # ── ドア判定 ──
            if door_cooldown == 0:
                pc = int((player.x + player.SIZE / 2) // TILE)
                pr = int((player.y + player.SIZE / 2) // TILE)
                key = (current_room, pc, pr)
                if key in ROOM_EXITS:
                    dest_room, dest_col, dest_row = ROOM_EXITS[key]
                    current_room = dest_room
                    tile_surf, enemies = enter_room(dest_room, dest_col, dest_row, player)
                    explosions.clear()
                    door_cooldown = 60

            # 剣の当たり判定
            sword_r = player.sword_rect()
            if sword_r:
                for e in enemies:
                    if id(e) not in player._attacked_set:
                        e_rect = pygame.Rect(int(e.x), int(e.y), e.SIZE, e.SIZE)
                        if sword_r.colliderect(e_rect):
                            _dx = (e.x + e.SIZE / 2) - (player.x + player.SIZE / 2)
                            _dy = (e.y + e.SIZE / 2) - (player.y + player.SIZE / 2)
                            _d  = max(1.0, math.hypot(_dx, _dy))
                            e.take_damage(1, _dx / _d * 9.0, _dy / _d * 9.0)
                            player._attacked_set.add(id(e))
            for e in enemies:
                if not e.alive:
                    explosions.append(Explosion(e.x + e.SIZE / 2, e.y + e.SIZE / 2))
            enemies = [e for e in enemies if e.alive]
            for ex in explosions:
                ex.update()
            explosions = [ex for ex in explosions if ex.alive]

            # 敵との接触ダメージ
            p_rect = pygame.Rect(int(player.x) + 4, int(player.y) + 4,
                                 player.SIZE - 8, player.SIZE - 8)
            for e in enemies:
                e_rect = pygame.Rect(int(e.x) + 2, int(e.y) + 2,
                                     e.SIZE - 4, e.SIZE - 4)
                if p_rect.colliderect(e_rect):
                    _dx = (player.x + player.SIZE / 2) - (e.x + e.SIZE / 2)
                    _dy = (player.y + player.SIZE / 2) - (e.y + e.SIZE / 2)
                    _d  = max(1.0, math.hypot(_dx, _dy))
                    player.take_damage(1, _dx / _d * 7.0, _dy / _d * 7.0)
                    break
            if player.hp <= 0:
                game_over = True

        # ── 描画 ──
        screen.blit(tile_surf, (0, 0))
        for e in enemies:
            e.draw(screen)
        for ex in explosions:
            ex.draw(screen)
        player.draw(screen)
        draw_hud(screen, player)

        # 部屋名をHUD右端に表示
        name_txt = font_room.render(
            _TYPE_NAMES.get(ROOM_TYPES.get(current_room, 'main'), ''), True, (200, 200, 200))
        screen.blit(name_txt, (WIN_W - name_txt.get_width() - 12,
                               TILE * ROWS + (HUD_H - name_txt.get_height()) // 2))

        # ── ゲームオーバー画面 ──
        if game_over:
            overlay = pygame.Surface((WIN_W, WIN_H), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 160))
            screen.blit(overlay, (0, 0))
            font_go  = pygame.font.SysFont("msgothic", 56)
            font_sub = pygame.font.SysFont("msgothic", 22)
            txt_go      = font_go.render("GAME OVER", True, (220, 40, 40))
            txt_restart = font_sub.render("R キーで再スタート  /  ESC で終了", True, (200, 200, 200))
            screen.blit(txt_go,      (WIN_W // 2 - txt_go.get_width() // 2,
                                      WIN_H // 2 - 60))
            screen.blit(txt_restart, (WIN_W // 2 - txt_restart.get_width() // 2,
                                      WIN_H // 2 + 20))

        pygame.display.flip()
        clock.tick(FPS)

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
