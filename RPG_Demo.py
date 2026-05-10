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
    FLOOR: (( 80,  58,  38), ( 96,  72,  50), ( 58,  42,  26)),  # 暗い茶色の石畳
    WALL:  (( 28,  22,  20), ( 48,  40,  36), ( 14,  10,   8)),  # 黒に近い石壁
    TREE:  (( 28,  22,  20), ( 48,  40,  36), ( 14,  10,   8)),  # TREE→壁扱い
    WATER: (( 28,  22,  20), ( 48,  40,  36), ( 14,  10,   8)),  # WATER→壁扱い
    PATH:  (( 68,  50,  34), ( 84,  64,  46), ( 52,  38,  24)),  # 少し明るい石畳
    DOOR:  (( 80,  58,  38), ( 96,  72,  50), ( 58,  42,  26)),  # 床と同色
}

# 衝突するタイル
SOLID_TILES = {WALL, TREE, WATER}
ACTIVE_CHESTS: list = []  # 現在の部屋の宝箱リスト（Player._solid_at から参照）

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
        grid[r][c] = random.choice([_W, _W, _W, _W])
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

# ワープポイント (build_dungeon() で設定)
WARP_ROOM: int = 0
WARP_TILE: tuple = (7, 5)  # (col, row)


def build_dungeon() -> None:
    """ゲーム開始/リスタートごとに 5×5 ダンジョングリッドを再構築する"""
    global ROOM_MAPS, ROOM_EXITS, ROOM_TYPES, WARP_ROOM, WARP_TILE
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
    n_treasure  = random.randint(1, 2)
    type_list   = ['treasure'] * n_treasure + ['monster'] * (n_others - n_treasure)
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

    # START_ROOM のスポーン周辺（col 6-9, row 4-6）を強制クリア
    for _r in range(4, 7):
        for _c in range(6, 10):
            if ROOM_MAPS[START_ROOM][_r][_c] in SOLID_TILES:
                ROOM_MAPS[START_ROOM][_r][_c] = _F

    # 全部屋のドア遷移着地点も強制クリア
    # 上から入る → row=1, col 7-8
    # 下から入る → row=9, col 7-8
    # 左から入る → col=13, row 4-5
    # 右から入る → col=2,  row 4-5
    _spawn_areas = [
        [(1, 7), (1, 8), (2, 7), (2, 8)],        # 上から着地
        [(9, 7), (9, 8), (8, 7), (8, 8)],         # 下から着地
        [(4, 13), (5, 13), (4, 12), (5, 12)],     # 左から着地
        [(4, 2),  (5, 2),  (4, 3),  (5, 3)],      # 右から着地
    ]
    for rid in range(N_ROOMS):
        gr, gc = divmod(rid, GRID_COLS)
        areas_to_clear = []
        if gr > 0:             areas_to_clear.append(_spawn_areas[0])
        if gr < GRID_ROWS - 1: areas_to_clear.append(_spawn_areas[1])
        if gc > 0:             areas_to_clear.append(_spawn_areas[2])
        if gc < GRID_COLS - 1: areas_to_clear.append(_spawn_areas[3])
        for area in areas_to_clear:
            for (_r, _c) in area:
                if ROOM_MAPS[rid][_r][_c] in SOLID_TILES:
                    ROOM_MAPS[rid][_r][_c] = _F

    # ワープポイント: START_ROOM 以外の部屋からランダムに1つ選ぶ
    WARP_ROOM = random.choice([i for i in range(N_ROOMS) if i != START_ROOM])
    floor_tiles = [
        (c, r)
        for r in range(3, ROWS - 3)
        for c in range(3, COLS - 3)
        if ROOM_MAPS[WARP_ROOM][r][c] == _F
    ]
    WARP_TILE = random.choice(floor_tiles) if floor_tiles else (7, 5)
    # ワープタイルも確実に床にする
    ROOM_MAPS[WARP_ROOM][WARP_TILE[1]][WARP_TILE[0]] = _F


def _make_narrow_room() -> list:
    """ボス前の入口部屋: 上方向のみ出口の狭い通路"""
    grid = [[_W] * COLS for _ in range(ROWS)]
    for r in range(1, ROWS - 1):
        for c in range(5, 11):
            grid[r][c] = _F
    grid[0][7] = _D
    grid[0][8] = _D
    return grid


def _make_boss_room() -> list:
    """ボス部屋: 下方向のみ出口の広い空間"""
    grid = [[_W] * COLS for _ in range(ROWS)]
    for r in range(1, ROWS - 1):
        for c in range(1, COLS - 1):
            grid[r][c] = _F
    grid[10][7] = _D
    grid[10][8] = _D
    return grid


def build_boss_floor() -> None:
    """3階: ボスフロア（入口部屋 + ボス部屋の2室構成）を構築する"""
    global ROOM_MAPS, ROOM_EXITS, ROOM_TYPES, WARP_ROOM, WARP_TILE
    ROOM_MAPS  = {}
    ROOM_EXITS = {}
    ROOM_TYPES = {}

    boss_room_id = START_ROOM - GRID_COLS  # STARTの1つ上 (= 17)

    ROOM_MAPS[START_ROOM]    = _make_narrow_room()
    ROOM_TYPES[START_ROOM]   = 'main'
    ROOM_MAPS[boss_room_id]  = _make_boss_room()
    ROOM_TYPES[boss_room_id] = 'boss'

    # 扉の繋がり
    ROOM_EXITS[(START_ROOM,   7,  0)] = (boss_room_id, 7, 9)
    ROOM_EXITS[(START_ROOM,   8,  0)] = (boss_room_id, 7, 9)
    ROOM_EXITS[(boss_room_id, 7, 10)] = (START_ROOM,   7, 1)
    ROOM_EXITS[(boss_room_id, 8, 10)] = (START_ROOM,   7, 1)

    # ワープポイント（ボス部屋中央: ボス討伐後の出口プレースホルダー）
    WARP_ROOM = boss_room_id
    WARP_TILE = (8, 5)


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
        pass  # 装飾なし（無地の石畳）

    elif render in (WALL, TREE, WATER):
        # 黒めの石壁（レンガ風ブロック）
        half = TILE // 2
        pygame.draw.rect(surf, sh,  (x,          y,          TILE,  2))
        pygame.draw.rect(surf, hi,  (x,          y + 2,      TILE,  3))
        pygame.draw.rect(surf, sh,  (x,          y + half,   TILE,  2))
        pygame.draw.rect(surf, hi,  (x,          y + half+2, TILE,  3))
        # 縦目山
        pygame.draw.line(surf, sh, (x + TILE // 3,     y),      (x + TILE // 3,     y + half), 1)
        pygame.draw.line(surf, sh, (x + TILE * 2 // 3, y + half),(x + TILE * 2 // 3, y + TILE), 1)

    elif render == PATH:
        # 明るめの石畚（少し卐り検の出た範囲）
        for i in range(0, TILE, 16):
            pygame.draw.line(surf, sh, (x + i, y), (x + i, y + TILE), 1)
            pygame.draw.line(surf, sh, (x, y + i), (x + TILE, y + i), 1)

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
from artifacts import ARTIFACT_DEFS


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
        self.xp          = 0  # 累積経験値
        self.sword_level = 1  # 剣レベル (1〜4)
        # ── インベントリ（アイテム種別 -> 所持数）──
        self.inventory: dict[str, int] = {}
        # アイテムスロット（Qキーで選択中アイテム使用）
        self._item_slots: list[str] = list(ITEM_DEFS.keys())  # ['potion', 'para_drug']
        self.selected_slot: int = 0  # 現在選択中スロットindex
        # ── 状態異常 ──
        self.status_effect: "StatusEffect | None" = None  # 自分への状態異常（将来拡張用）
        # ── アーティファクト ──
        self.artifacts: list[str] = []  # 所持アーティファクトのidリスト
        self.atk_bonus      = 0  # sharp_eyeなどによる攻撃力ボーナス
        self.inv_multiplier = 1  # mana_shieldによる無敵時間倍率

    # 剣レベル定数
    _XP_THRESHOLDS = [60, 150, 300]  # Lv1→2, Lv2→3, Lv3→4
    _SWORD_NAMES   = {1: '木の剣', 2: '鉄の剣', 3: '炎の剣', 4: '伝説の剣'}
    _SWORD_COLORS  = {1: (180, 120, 60), 2: (190, 190, 210), 3: (255, 130, 30), 4: (255, 230, 60)}

    def attack_damage(self) -> int:
        return self.sword_level + self.atk_bonus

    def gain_xp(self, amount: int) -> bool:
        """経験値加算。レベルアップしたら True を返す"""
        self.xp += amount
        if self.sword_level < 4 and self.xp >= self._XP_THRESHOLDS[self.sword_level - 1]:
            self.sword_level += 1
            return True
        return False

    # 移動とタイル衝突
    def update(self, keys) -> None:
        # 攻撃中は移動入力を無視（硬直）
        if self.attack_timer <= 0:
            dx = dy = 0
            if keys[pygame.K_a]:      dx = -self.SPEED
            if keys[pygame.K_d]:      dx =  self.SPEED
            if keys[pygame.K_w]:      dy = -self.SPEED
            if keys[pygame.K_s]:      dy =  self.SPEED

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

            # 宝箱との衝突（押し戻し）
            pr = pygame.Rect(int(self.x) + 2, int(self.y) + 2,
                             self.SIZE - 4, self.SIZE - 4)
            for ch in ACTIVE_CHESTS:
                if ch.opened:
                    continue
                cr = pygame.Rect(int(ch.x) + 2, int(ch.y) + 2,
                                 ch.SIZE - 4, ch.SIZE - 4)
                if pr.colliderect(cr):
                    # 重なり量の小さい軸で押し戻す
                    ol = pr.right  - cr.left
                    or_ = cr.right - pr.left
                    ot = pr.bottom - cr.top
                    ob = cr.bottom - pr.top
                    m = min(ol, or_, ot, ob)
                    if m == ol:
                        self.x -= ol
                    elif m == or_:
                        self.x += or_
                    elif m == ot:
                        self.y -= ot
                    else:
                        self.y += ob
                    pr = pygame.Rect(int(self.x) + 2, int(self.y) + 2,
                                     self.SIZE - 4, self.SIZE - 4)

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
            self.attack_timer    = 8
            self.attack_cooldown = 16
            self._attacked_set.clear()
            return True
        return False

    def take_damage(self, amount: int = 1, kbx: float = 0.0, kby: float = 0.0) -> None:
        """ダメージを受ける。無敵時間中は無効。"""
        if self.inv_timer > 0:
            return
        self.hp = max(0, self.hp - amount)
        self.inv_timer = 60 * self.inv_multiplier   # mana_shieldで増幅
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
        # 攻撃中は剣を描画（レベルに応じた色）
        sr = self.sword_rect()
        if sr:
            sc    = self._SWORD_COLORS[self.sword_level]
            sc_hi = tuple(min(255, c + 50) for c in sc)
            pygame.draw.rect(surf, sc, sr)
            hi = sr.inflate(-4, -4)
            if hi.width > 0 and hi.height > 0:
                pygame.draw.rect(surf, sc_hi, hi)


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
        self.xp_value  = 5
        self.hit_timer = 0   # >0 の間ヒットフラッシュ
        self.alive     = True
        self.kbx       = 0.0  # ヒットバック速度X
        self.kby       = 0.0  # ヒットバック速度Y
        self.status: "StatusEffect | None" = None  # 毒・麻痺
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

    def update(self, px: float = -1, py: float = -1) -> int:
        """更新。毒ダメージが発生した場合そのダメージ量を返す（通常は0）"""
        if self.hit_timer > 0:
            self.hit_timer -= 1
        # 状態異常更新
        poison_dmg = 0
        if self.status and self.status.active:
            poison_dmg = self.status.update()
            if poison_dmg:
                self.hp -= poison_dmg
                if self.hp <= 0:
                    self.alive = False
            if not self.status.active:
                self.status = None
        else:
            self.status = None
        # 麻痺中は移動しない
        if self.status and self.status.kind == 'para':
            return poison_dmg
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

        # プレイヤーへの追跡
        CHASE_RANGE = TILE * 8  # 追跡開始距離（8タイル以内）
        chasing = False
        if px >= 0 and py >= 0:
            edx = (px + self.SIZE / 2) - (self.x + self.SIZE / 2)
            edy = (py + self.SIZE / 2) - (self.y + self.SIZE / 2)
            dist = math.hypot(edx, edy)
            if dist < CHASE_RANGE and dist > 1:
                chasing = True
                # X/Y のどちらか距離が大きい方向へ1ステップ進む
                if abs(edx) >= abs(edy):
                    self.dx = 1 if edx > 0 else -1
                    self.dy = 0
                else:
                    self.dx = 0
                    self.dy = 1 if edy > 0 else -1

        if not chasing:
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
        return poison_dmg

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
        # 状態異常エフェクト
        if self.status and self.status.active:
            self.status.draw(surf, self.x, self.y, s)


class BlueEnemy(Enemy):
    """青いスライム。基本の敵より体力が高い。"""

    def __init__(self, x: float, y: float) -> None:
        super().__init__(x, y)
        self.hp = 6
        self.xp_value = 15

    def draw(self, surf: pygame.Surface) -> None:
        x, y = int(self.x), int(self.y)
        s = self.SIZE
        body_color = (255, 255, 255) if self.hit_timer > 0 else (40, 80, 200)
        hi_color   = (255, 255, 255) if self.hit_timer > 0 else (80, 130, 230)
        body_rect = pygame.Rect(x + 2, y + 8, s - 4, s - 8)
        pygame.draw.ellipse(surf, body_color, body_rect)
        pygame.draw.ellipse(surf, hi_color,
                            pygame.Rect(x + 6, y + 10, (s - 4) // 2, (s - 8) // 3))
        pygame.draw.circle(surf, (255, 255, 255), (x + 9,  y + 14), 4)
        pygame.draw.circle(surf, (255, 255, 255), (x + 19, y + 14), 4)
        pygame.draw.circle(surf, (20, 20, 20),    (x + 10, y + 15), 2)
        pygame.draw.circle(surf, (20, 20, 20),    (x + 20, y + 15), 2)
        if self.status and self.status.active:
            self.status.draw(surf, self.x, self.y, s)


class ArrowEnemy(Enemy):
    """弓使いの敵（2階以降）。プレイヤーから一定距離を保ちつつ矢を射る。"""
    SPEED      = 1
    SIZE       = 28
    KEEP_DIST  = TILE * 4   # 保ちたい距離（4タイル）
    SHOOT_CD   = 120        # 矢の発射間隔(フレーム)

    def __init__(self, x: float, y: float) -> None:
        super().__init__(x, y)
        self.hp        = 3
        self.xp_value  = 12
        self._shoot_timer = random.randint(60, self.SHOOT_CD)

    def update(self, px: float = -1, py: float = -1) -> int:
        """更新。戻り値は毒ダメージ（通常0）。矢発射タイミングは shoot() で別管理。"""
        if self.hit_timer > 0:
            self.hit_timer -= 1
        poison_dmg = 0
        if self.status and self.status.active:
            poison_dmg = self.status.update()
            if poison_dmg:
                self.hp -= poison_dmg
                if self.hp <= 0:
                    self.alive = False
            if not self.status.active:
                self.status = None
        else:
            self.status = None
        if self.status and self.status.kind == 'para':
            return poison_dmg
        if self.kbx or self.kby:
            if not self._solid_at(self.x + self.kbx, self.y):
                self.x += self.kbx
            if not self._solid_at(self.x, self.y + self.kby):
                self.y += self.kby
            self.kbx *= 0.70
            self.kby *= 0.70
            if abs(self.kbx) < 0.3: self.kbx = 0.0
            if abs(self.kby) < 0.3: self.kby = 0.0

        # プレイヤーとの距離に応じて逃げるか近づく
        if px >= 0 and py >= 0:
            edx = (px + self.SIZE / 2) - (self.x + self.SIZE / 2)
            edy = (py + self.SIZE / 2) - (self.y + self.SIZE / 2)
            dist = math.hypot(edx, edy)
            if dist > 1:
                if dist < self.KEEP_DIST:
                    # 近すぎる → 逃げる
                    mx = -edx / dist
                    my = -edy / dist
                else:
                    # 遠すぎる → 近づく（8タイル超のみ）
                    if dist > TILE * 8:
                        mx = edx / dist
                        my = edy / dist
                    else:
                        mx, my = 0, 0
                if abs(mx) >= abs(my):
                    self.dx = 1 if mx > 0 else (-1 if mx < 0 else 0)
                    self.dy = 0
                else:
                    self.dx = 0
                    self.dy = 1 if my > 0 else (-1 if my < 0 else 0)
        else:
            self.move_timer -= 1
            if self.move_timer <= 0:
                self._pick_direction()

        nx = self.x + self.dx * self.SPEED
        ny = self.y + self.dy * self.SPEED
        if self.dx:
            if not self._solid_at(nx, self.y):
                self.x = nx
            else:
                self._pick_direction()
        if self.dy:
            if not self._solid_at(self.x, ny):
                self.y = ny
            else:
                self._pick_direction()
        self.x = max(0, min(self.x, WIN_W - self.SIZE))
        self.y = max(0, min(self.y, TILE * ROWS - self.SIZE))
        return poison_dmg

    def try_shoot(self, px: float, py: float) -> "EnemyArrow | None":
        """発射クールダウンが切れたらEnemyArrowを返す。まだなら None。"""
        self._shoot_timer -= 1
        if self._shoot_timer <= 0:
            self._shoot_timer = self.SHOOT_CD
            edx = (px + self.SIZE / 2) - (self.x + self.SIZE / 2)
            edy = (py + self.SIZE / 2) - (self.y + self.SIZE / 2)
            dist = math.hypot(edx, edy)
            if dist > 1:
                vx = edx / dist * EnemyArrow.SPEED
                vy = edy / dist * EnemyArrow.SPEED
                return EnemyArrow(self.x + self.SIZE / 2, self.y + self.SIZE / 2, vx, vy)
        return None

    def draw(self, surf: pygame.Surface) -> None:
        x, y = int(self.x), int(self.y)
        s = self.SIZE
        body_color = (255, 255, 255) if self.hit_timer > 0 else (160, 100, 40)
        hi_color   = (255, 255, 255) if self.hit_timer > 0 else (210, 150, 80)
        # 体（茶色の楕円）
        pygame.draw.ellipse(surf, body_color, pygame.Rect(x + 2, y + 8, s - 4, s - 8))
        pygame.draw.ellipse(surf, hi_color,   pygame.Rect(x + 6, y + 10, (s - 4) // 2, (s - 8) // 3))
        # 目
        pygame.draw.circle(surf, (255, 255, 255), (x + 9,  y + 14), 4)
        pygame.draw.circle(surf, (255, 255, 255), (x + 19, y + 14), 4)
        pygame.draw.circle(surf, (20, 20, 20),    (x + 10, y + 15), 2)
        pygame.draw.circle(surf, (20, 20, 20),    (x + 20, y + 15), 2)
        # 弓（右側に小さな弧）
        bow_x, bow_y = x + s - 4, y + s // 2
        pygame.draw.arc(surf, (180, 120, 40),
                        pygame.Rect(bow_x - 6, bow_y - 8, 8, 16), -1.2, 1.2, 2)
        pygame.draw.line(surf, (180, 120, 40), (bow_x - 2, bow_y - 8), (bow_x - 2, bow_y + 8), 1)
        if self.status and self.status.active:
            self.status.draw(surf, self.x, self.y, s)


class EnemyArrow:
    """弓使い敵が放つ矢。プレイヤーに当たると1ダメージ。"""
    SIZE  = 8
    SPEED = 5.0
    RANGE = TILE * 12

    def __init__(self, x: float, y: float, vx: float, vy: float) -> None:
        self.x    = float(x)
        self.y    = float(y)
        self.vx   = vx
        self.vy   = vy
        self._dist = 0.0
        self.alive = True

    def update(self) -> None:
        if not self.alive:
            return
        self.x += self.vx
        self.y += self.vy
        self._dist += math.hypot(self.vx, self.vy)
        if (self._dist > self.RANGE or
                self.x < 0 or self.x > WIN_W or
                self.y < 0 or self.y > TILE * ROWS):
            self.alive = False
            return
        col = int(self.x // TILE)
        row = int(self.y // TILE)
        if 0 <= row < ROWS and 0 <= col < COLS:
            if CURRENT_MAP[row][col] in SOLID_TILES:
                self.alive = False

    def draw(self, surf: pygame.Surface) -> None:
        if not self.alive:
            return
        cx, cy = int(self.x), int(self.y)
        # 矢の向きに合わせた線
        length = 10
        spd = math.hypot(self.vx, self.vy)
        if spd > 0:
            nx, ny = self.vx / spd * length, self.vy / spd * length
        else:
            nx, ny = length, 0
        # 矢本体（白〜薄黄）
        pygame.draw.line(surf, (220, 200, 140), (cx, cy), (int(cx - nx), int(cy - ny)), 2)
        # 矢じり（先端の三角）
        tip_x, tip_y = cx + int(nx * 0.4), cy + int(ny * 0.4)
        perp_x, perp_y = -ny * 0.25, nx * 0.25
        pts = [
            (tip_x, tip_y),
            (int(cx - int(nx * 0.1) + perp_x), int(cy - int(ny * 0.1) + perp_y)),
            (int(cx - int(nx * 0.1) - perp_x), int(cy - int(ny * 0.1) - perp_y)),
        ]
        pygame.draw.polygon(surf, (255, 220, 100), pts)


class Boss:
    """3階ボス: 巨大な四角い一つ目モンスター。突撃攻撃と画面揺れ。"""
    SIZE     = 80
    MAX_HP   = 40

    # フェーズ1
    _WINDUP_P1  = 90   # 予備動作フレーム
    _CHARGE_SPD_P1 = 7.0
    _CD_P1      = 180  # 突撃後クールダウン

    # フェーズ2 (HP半分以下)
    _WINDUP_P2  = 50
    _CHARGE_SPD_P2 = 11.0
    _CD_P2      = 100

    _STATE_IDLE   = 0
    _STATE_WINDUP = 1
    _STATE_CHARGE = 2
    _STATE_COOL   = 3
    _STATE_JUMP   = 4   # ジャンプ中（点滅→再出現）

    _JUMP_CD      = 240  # ジャンプ発動下限クールタイム
    _JUMP_CHANCE  = 0.35 # クールダウン終了時のジャンプ確率

    def __init__(self, x: float, y: float) -> None:
        self.x   = float(x)
        self.y   = float(y)
        self.hp  = self.MAX_HP
        self.alive = True
        self.hit_timer = 0
        self._state   = self._STATE_COOL
        self._timer   = 60  # 最初だけ少し待つ
        self._vx      = 0.0
        self._vy      = 0.0
        self._anim    = 0
        self.shake    = 0   # 画面揺れの強さ（呼び出し元が読む）
        self._jump_cd    = 0   # ジャンプクールダウン
        self._jump_flash = 0   # 着地フラッシュタイマ
        self._jump_sx    = 0.0 # ジャンプ開始X
        self._jump_sy    = 0.0 # ジャンプ開始Y
        self._jump_tx    = 0.0 # ジャンプ目標X
        self._jump_ty    = 0.0 # ジャンプ目標Y
        self._jump_total = 50  # ジャンプアニメーション総フレーム数

    @property
    def _phase2(self) -> bool:
        return self.hp <= self.MAX_HP // 2

    def take_damage(self, amount: int = 1, kbx: float = 0.0, kby: float = 0.0) -> None:
        self.hp -= amount
        self.hit_timer = 10
        if self.hp <= 0:
            self.alive = False

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

    def update(self, px: float, py: float) -> None:
        """状態機械で突撃パターンを制御。"""
        self._anim += 1
        self.shake = 0
        if self.hit_timer > 0:
            self.hit_timer -= 1
        if self._jump_cd > 0:
            self._jump_cd -= 1
        if self._jump_flash > 0:
            self._jump_flash -= 1

        windup = self._WINDUP_P2 if self._phase2 else self._WINDUP_P1
        charge_spd = self._CHARGE_SPD_P2 if self._phase2 else self._CHARGE_SPD_P1
        cool = self._CD_P2 if self._phase2 else self._CD_P1

        if self._state == self._STATE_COOL:
            self._timer -= 1
            if self._timer <= 0:
                # クールダウン終了→ジャンプか突撃か判定
                if self._jump_cd == 0 and random.random() < self._JUMP_CHANCE:
                    # 着地目標を事前に決定
                    best_x, best_y = self.x, self.y
                    best_dist = 0.0
                    for _ in range(30):
                        tc = random.randint(2, COLS - 3)
                        tr = random.randint(2, ROWS - 3)
                        tx_ = float(tc * TILE)
                        ty_ = float(tr * TILE)
                        if self._solid_at(tx_, ty_):
                            continue
                        d_ = math.hypot(tx_ - px, ty_ - py)
                        if d_ > best_dist:
                            best_dist = d_
                            best_x, best_y = tx_, ty_
                    self._jump_sx = self.x
                    self._jump_sy = self.y
                    self._jump_tx = best_x
                    self._jump_ty = best_y
                    self._jump_total = 45 if not self._phase2 else 30
                    self._state = self._STATE_JUMP
                    self._timer = self._jump_total
                    self._jump_cd = self._JUMP_CD
                else:
                    self._state = self._STATE_WINDUP
                    self._timer = windup
                    # 突撃方向を決定（4方向からランダム）
                    dirs = [(1,0),(-1,0),(0,1),(0,-1)]
                    # プレイヤー方向に少しバイアス
                    dx = px - (self.x + self.SIZE/2)
                    dy = py - (self.y + self.SIZE/2)
                    if abs(dx) >= abs(dy):
                        preferred = (1,0) if dx > 0 else (-1,0)
                    else:
                        preferred = (0,1) if dy > 0 else (0,-1)
                    d = preferred if random.random() < 0.6 else random.choice(dirs)
                    self._vx = d[0] * charge_spd
                    self._vy = d[1] * charge_spd

        elif self._state == self._STATE_JUMP:
            self._timer -= 1
            # smoothstepで位置を補間（最初と最後はゆっくり、中間は速い）
            t = 1.0 - self._timer / max(1, self._jump_total)
            ease_t = t * t * (3.0 - 2.0 * t)
            self.x = self._jump_sx + (self._jump_tx - self._jump_sx) * ease_t
            self.y = self._jump_sy + (self._jump_ty - self._jump_sy) * ease_t
            if self._timer <= 0:
                self.x = self._jump_tx
                self.y = self._jump_ty
                self.shake = 15 if self._phase2 else 10
                self._jump_flash = 15
                self._state = self._STATE_COOL
                cool_now = self._CD_P2 if self._phase2 else self._CD_P1
                self._timer = cool_now // 2

        elif self._state == self._STATE_WINDUP:
            self._timer -= 1
            if self._timer <= 0:
                self._state = self._STATE_CHARGE

        elif self._state == self._STATE_CHARGE:
            # 壁に当たるまで突進
            hit_wall = False
            nx = self.x + self._vx
            ny = self.y + self._vy
            if self._solid_at(nx, self.y):
                self._vx = 0.0
                hit_wall = True
            else:
                self.x = nx
            if self._solid_at(self.x, ny):
                self._vy = 0.0
                hit_wall = True
            else:
                self.y = ny

            if hit_wall or (self._vx == 0.0 and self._vy == 0.0):
                self.shake = 18 if self._phase2 else 12
                self._state = self._STATE_COOL
                self._timer = cool

        # 画面端クランプ
        self.x = max(0, min(self.x, WIN_W - self.SIZE))
        self.y = max(0, min(self.y, TILE * ROWS - self.SIZE))

    def draw(self, surf: pygame.Surface) -> None:
        s_base = self.SIZE

        # ジャンプ中はスケールアップ（弧の頂点で最大）・着地影を描画
        if self._state == self._STATE_JUMP:
            t = 1.0 - self._timer / max(1, self._jump_total)
            jump_scale = 1.0 + math.sin(t * math.pi) * 0.6
            s = int(s_base * jump_scale)
            x = int(self.x) - (s - s_base) // 2
            y = int(self.y) - (s - s_base) // 2
            # 着地地点に影（近づくほど大きく）
            sx_ = int(self._jump_tx) + s_base // 2
            sy_ = int(self._jump_ty) + s_base // 2
            sr = max(0, int(s_base // 2 * min(1.0, t * 2.5)))
            if sr > 2:
                pygame.draw.ellipse(surf, (15, 10, 10),
                    (sx_ - sr, sy_ - sr // 3, sr * 2, sr * 2 // 3))
        elif self._jump_flash > 0:
            s = s_base
            x = int(self.x)
            y = int(self.y)
        else:
            s = s_base
            x = int(self.x)
            y = int(self.y)

        # 予備動作中は赤く点滅
        if self._state == self._STATE_WINDUP:
            flash = (self._anim // 5) % 2 == 0
            body_col = (255, 80, 80) if flash else (160, 30, 30)
        elif self._state == self._STATE_JUMP:
            # 頂点付近でオレンジ→白に輝く
            t = 1.0 - self._timer / max(1, self._jump_total)
            glow = int(math.sin(t * math.pi) * 255)
            body_col = (min(255, 80 + glow), min(255, 20 + glow // 2), min(255, 80 + glow))
        elif self._jump_flash > 0:
            body_col = (255, 255, 255)
        elif self.hit_timer > 0:
            body_col = (255, 255, 255)
        elif self._phase2:
            body_col = (180, 20, 20)
        else:
            body_col = (80, 20, 80)

        # ボディ（大きな四角）
        pygame.draw.rect(surf, body_col, pygame.Rect(x, y, s, s))
        # 縁取り
        edge_col = (255, 100, 255) if self._phase2 else (140, 60, 180)
        pygame.draw.rect(surf, edge_col, pygame.Rect(x, y, s, s), 4)

        # 中央の目玉
        cx, cy = x + s // 2, y + s // 2
        # 白目
        pygame.draw.circle(surf, (240, 240, 240), (cx, cy), s // 4)
        # 瞳（プレイヤー方向を向く）
        pupil_r = s // 8
        if self._state == self._STATE_CHARGE:
            # 突撃中は目が大きく
            pupil_r = s // 6
            iris_col = (220, 40, 40)
        elif self._state == self._STATE_WINDUP:
            iris_col = (255, 100, 0)
        else:
            iris_col = (20, 20, 120) if not self._phase2 else (180, 0, 0)
        pygame.draw.circle(surf, iris_col, (cx, cy), pupil_r)
        # ハイライト
        pygame.draw.circle(surf, (255, 255, 255), (cx - pupil_r//3, cy - pupil_r//3), max(2, pupil_r//3))

        # フェーズ2: 目の周りに稲妻エフェクト
        if self._phase2:
            for i in range(6):
                ang = self._anim * 0.12 + i * math.pi / 3
                ex = cx + int(math.cos(ang) * (s // 4 + 6))
                ey = cy + int(math.sin(ang) * (s // 4 + 6))
                pygame.draw.circle(surf, (255, 60, 60), (ex, ey), 3)

        # HP バー
        bar_w = s
        bar_h = 8
        hp_ratio = max(0, self.hp / self.MAX_HP)
        pygame.draw.rect(surf, (60, 0, 0),   pygame.Rect(x, y - 12, bar_w, bar_h))
        pygame.draw.rect(surf, (220, 40, 40), pygame.Rect(x, y - 12, int(bar_w * hp_ratio), bar_h))
        pygame.draw.rect(surf, (255, 255, 255), pygame.Rect(x, y - 12, bar_w, bar_h), 1)


# ─── HUD 描画 ─────────────────────────────────────────────
def draw_hud(surf: pygame.Surface, player: Player, font: pygame.font.Font) -> None:
    hud_y = TILE * ROWS
    pygame.draw.rect(surf, (20, 20, 20), pygame.Rect(0, hud_y, WIN_W, HUD_H))
    pygame.draw.line(surf, (80, 80, 80), (0, hud_y), (WIN_W, hud_y), 2)

    # ハート（上段）
    heart_size = 18
    gap        = 4
    start_x    = 12
    start_y    = hud_y + 6
    for i in range(player.max_hp):
        color = (220, 40, 40) if i < player.hp else (70, 70, 70)
        _draw_heart(surf, start_x + i * (heart_size + gap), start_y, heart_size, color)

    # 剣レベル名（ハートの右）
    sc = Player._SWORD_COLORS[player.sword_level]
    stxt = font.render(f"剣: {Player._SWORD_NAMES[player.sword_level]}", True, sc)
    heart_end_x = start_x + player.max_hp * (heart_size + gap) + 8
    surf.blit(stxt, (heart_end_x, start_y + 1))

    # XPバー（下段）
    bar_x, bar_y, bar_w, bar_h = 12, hud_y + 36, WIN_W // 2 - 20, 10
    pygame.draw.rect(surf, (50, 50, 50), pygame.Rect(bar_x, bar_y, bar_w, bar_h))
    if player.sword_level < 4:
        prev  = Player._XP_THRESHOLDS[player.sword_level - 2] if player.sword_level > 1 else 0
        nxt   = Player._XP_THRESHOLDS[player.sword_level - 1]
        ratio = max(0.0, min(1.0, (player.xp - prev) / (nxt - prev)))
    else:
        ratio = 1.0
    fill_w = int(bar_w * ratio)
    if fill_w > 0:
        pygame.draw.rect(surf, sc, pygame.Rect(bar_x, bar_y, fill_w, bar_h))
    pygame.draw.rect(surf, (100, 100, 100), pygame.Rect(bar_x, bar_y, bar_w, bar_h), 1)
    if player.sword_level == 4:
        lbl = font.render("LEVEL MAX", True, (255, 230, 60))
    else:
        lbl = font.render("EXP", True, (160, 160, 160))
    surf.blit(lbl, (bar_x + bar_w + 4, bar_y - 1))

    # アイテムスロット（HUD右寄り上段）
    # Q:使用  ←→:スロット切替
    slot_size = 24
    slot_gap  = 4
    n_slots   = len(player._item_slots)
    slot_total_w = n_slots * (slot_size + slot_gap)
    slot_start_x = WIN_W - slot_total_w - 140  # 右端から少し左
    for i, kind in enumerate(player._item_slots):
        sx = slot_start_x + i * (slot_size + slot_gap)
        sy = hud_y + 4
        selected = (i == player.selected_slot)
        border_col = (220, 200, 60) if selected else (80, 80, 80)
        pygame.draw.rect(surf, (40, 40, 40), pygame.Rect(sx, sy, slot_size, slot_size))
        pygame.draw.rect(surf, border_col,   pygame.Rect(sx, sy, slot_size, slot_size), 2)
        count = player.inventory.get(kind, 0)
        if count > 0:
            if kind == 'potion':
                # 緑の入った瓶アイコン
                bx, by = sx + slot_size // 2, sy + slot_size // 2
                # 瓶ボディ
                pygame.draw.rect(surf, (60, 160, 60),
                                 pygame.Rect(bx - 5, by - 3, 10, 9))
                # 瓶の中の液体（明るい緑）
                pygame.draw.rect(surf, (100, 230, 100),
                                 pygame.Rect(bx - 4, by, 8, 5))
                # 瓶の口
                pygame.draw.rect(surf, (180, 180, 180),
                                 pygame.Rect(bx - 2, by - 6, 4, 4))
            elif kind == 'para_drug':
                # 雷マーク（稲妻）
                bx, by = sx + slot_size // 2, sy + 4
                bolt = [
                    (bx + 3, by),
                    (bx - 1, by + 8),
                    (bx + 2, by + 8),
                    (bx - 3, by + 18),
                    (bx + 1, by + 10),
                    (bx - 2, by + 10),
                ]
                pygame.draw.polygon(surf, (255, 230, 40), bolt)
                pygame.draw.polygon(surf, (255, 255, 160), bolt, 1)
            cnt_txt = font.render(str(count), True, (220, 220, 220))
            surf.blit(cnt_txt, (sx + slot_size - cnt_txt.get_width() - 1,
                                sy + slot_size - cnt_txt.get_height()))
    # スロットラベル
    q_hint = font.render("Q:使用  ←→:切替", True, (100, 100, 130))
    surf.blit(q_hint, (slot_start_x, hud_y + slot_size + 8))


# ─── メニュー画面描画 ────────────────────────────────────────────
_MENU_TABS = ['セーブ', 'ロード', 'アイテム', '装備', 'ステータス', 'アーティファクト', 'オプション']
_DEMO_LOCKED = {0, 1}  # セーブ・ロードは体験版では不可

def draw_menu(surf: pygame.Surface, player: "Player",
              tab: int, font_title: pygame.font.Font,
              font_item: pygame.font.Font, floor_level: int) -> None:
    """Mキーで開くメニューオーバーレイを描画する"""
    # ── 半透明暗転 ──
    overlay = pygame.Surface((WIN_W, WIN_H), pygame.SRCALPHA)
    overlay.fill((0, 0, 20, 200))
    surf.blit(overlay, (0, 0))

    SIDEBAR_W = 160
    MENU_H    = WIN_H - 40
    MENU_Y    = 20
    CONTENT_X = 20 + SIDEBAR_W + 16
    CONTENT_W = WIN_W - CONTENT_X - 20

    # ── サイドバー背景 ──
    pygame.draw.rect(surf, (25, 25, 50),
                     pygame.Rect(20, MENU_Y, SIDEBAR_W, MENU_H))
    pygame.draw.rect(surf, (80, 80, 140),
                     pygame.Rect(20, MENU_Y, SIDEBAR_W, MENU_H), 2)

    # ── タブ一覧 ──
    TAB_H = 44
    for i, name in enumerate(_MENU_TABS):
        ty = MENU_Y + 10 + i * TAB_H
        if i == tab:
            pygame.draw.rect(surf, (70, 70, 160),
                             pygame.Rect(22, ty, SIDEBAR_W - 4, TAB_H - 2))
        color = (240, 240, 255) if i == tab else (140, 140, 170)
        t = font_title.render(name, True, color)
        surf.blit(t, (20 + SIDEBAR_W // 2 - t.get_width() // 2, ty + TAB_H // 2 - t.get_height() // 2))

    # ── コンテンツエリア背景 ──
    pygame.draw.rect(surf, (20, 20, 40),
                     pygame.Rect(CONTENT_X - 8, MENU_Y, CONTENT_W + 8, MENU_H))
    pygame.draw.rect(surf, (80, 80, 140),
                     pygame.Rect(CONTENT_X - 8, MENU_Y, CONTENT_W + 8, MENU_H), 2)

    # ── タブタイトル ──
    title = font_title.render(_MENU_TABS[tab], True, (200, 200, 255))
    surf.blit(title, (CONTENT_X, MENU_Y + 14))
    pygame.draw.line(surf, (80, 80, 140),
                     (CONTENT_X, MENU_Y + 14 + title.get_height() + 4),
                     (WIN_W - 28, MENU_Y + 14 + title.get_height() + 4), 1)

    CY = MENU_Y + 14 + title.get_height() + 16  # コンテンツ開始Y

    if tab in _DEMO_LOCKED:
        # ── セーブ / ロード: 体験版制限 ──
        msg1 = font_title.render('体験版では利用できません', True, (220, 60, 60))
        msg2 = font_item.render('製品版でご利用いただけます。', True, (160, 160, 160))
        cx   = CONTENT_X + CONTENT_W // 2
        cy   = MENU_Y + MENU_H // 2
        surf.blit(msg1, (cx - msg1.get_width() // 2, cy - 20))
        surf.blit(msg2, (cx - msg2.get_width() // 2, cy + 10))

    elif tab == 2:  # アイテム
        _ITEM_DESC = {
            'potion':   ('ポーション', 'HPを 3 回復する。冒険者御用達の一品'),
            'para_drug': ('麻痺薬', '前方に投げて敵を 2 秒間麻痺させる。距離は結構長いぞ'),
        }
        has_any = any(player.inventory.get(k, 0) > 0 for k in ITEM_DEFS)
        if not has_any:
            msg = font_item.render('アイテムはない', True, (160, 160, 160))
            surf.blit(msg, (CONTENT_X, CY))
        else:
            iy = CY
            for kind, defs in ITEM_DEFS.items():
                count = player.inventory.get(kind, 0)
                if count <= 0:
                    continue
                name, desc = _ITEM_DESC.get(kind, (defs['name'], ''))
                name_txt = font_item.render(f'{name}  x{count}', True, (220, 220, 220))
                surf.blit(name_txt, (CONTENT_X, iy))
                desc_txt = font_item.render(f'  {desc}', True, (140, 160, 140))
                surf.blit(desc_txt, (CONTENT_X, iy + 22))
                iy += 50

    elif tab == 3:  # 装備
        sword_name  = Player._SWORD_NAMES[player.sword_level]
        sword_color = Player._SWORD_COLORS[player.sword_level]
        lbl  = font_item.render('装備中の剣:', True, (180, 180, 200))
        swd  = font_title.render(sword_name, True, sword_color)
        lvl  = font_item.render(f'剣レベル  Lv.{player.sword_level}', True, (160, 160, 160))
        atk  = font_item.render(f'攻撃力   +{player.sword_level}', True, (160, 160, 160))
        surf.blit(lbl, (CONTENT_X, CY))
        surf.blit(swd, (CONTENT_X, CY + 28))
        surf.blit(lvl, (CONTENT_X, CY + 60))
        surf.blit(atk, (CONTENT_X, CY + 82))

    elif tab == 4:  # ステータス
        rows = [
            ('HP',      f'{player.hp}  /  {player.max_hp}'),
            ('経験値',   str(player.xp)),
            ('剣レベル', f'Lv.{player.sword_level}  {Player._SWORD_NAMES[player.sword_level]}'),
            ('現在階層', f'地下 {floor_level} 階' if floor_level > 1 else '地上'),
        ]
        for i, (label, val) in enumerate(rows):
            lbl_s = font_item.render(label, True, (160, 160, 200))
            val_s = font_item.render(val,   True, (230, 230, 230))
            y = CY + i * 30
            surf.blit(lbl_s, (CONTENT_X, y))
            surf.blit(val_s, (CONTENT_X + 120, y))

    elif tab == 5:  # アーティファクト
        if not player.artifacts:
            msg = font_item.render('アーティファクトはまだ持っていない', True, (160, 160, 160))
            surf.blit(msg, (CONTENT_X, CY))
            hint2 = font_item.render('ボス撃破・階層移動で入手できる', True, (120, 120, 120))
            surf.blit(hint2, (CONTENT_X, CY + 26))
        else:
            iy = CY
            for art_id in player.artifacts:
                adef = ARTIFACT_DEFS.get(art_id, {})
                icon_col = adef.get('icon_color', (180, 180, 180))
                name_str = adef.get('name', art_id)
                desc_str = adef.get('desc', '')
                # アイコン（小さい四角）
                pygame.draw.rect(surf, icon_col, pygame.Rect(CONTENT_X, iy + 2, 20, 20))
                pygame.draw.rect(surf, (255, 255, 255), pygame.Rect(CONTENT_X, iy + 2, 20, 20), 1)
                name_txt = font_item.render(name_str, True, icon_col)
                surf.blit(name_txt, (CONTENT_X + 28, iy))
                desc_txt = font_item.render(desc_str, True, (150, 160, 150))
                surf.blit(desc_txt, (CONTENT_X + 28, iy + 22))
                iy += 52
                if iy > MENU_Y + MENU_H - 40:
                    break

    elif tab == 6:  # オプション
        opts = [
            ('BGM音量',  '▐▐▐▐▐░░░░░  50%'),
            ('SE音量',   '▐▐▐▐▐▐▐░░░  70%'),
            ('難易度',   'ノーマル'),
            ('表示FPS', '60'),
        ]
        note = font_item.render('※ 体験版ではオプション変更はできません', True, (120, 120, 120))
        surf.blit(note, (CONTENT_X, CY))
        for i, (k, v) in enumerate(opts):
            ks = font_item.render(k, True, (140, 140, 160))
            vs = font_item.render(v, True, (180, 180, 180))
            y  = CY + 28 + i * 28
            surf.blit(ks, (CONTENT_X, y))
            surf.blit(vs, (CONTENT_X + 130, y))

    # ── 操作説明 (下部) ──
    hint = font_item.render('↑↓ : タブ切替     M / ESC : 閉じる', True, (100, 100, 130))
    surf.blit(hint, (WIN_W // 2 - hint.get_width() // 2, MENU_Y + MENU_H - hint.get_height() - 8))


def draw_artifact_select(surf: pygame.Surface, choices: list[str],
                         cursor: int,
                         font_title: pygame.font.Font,
                         font_item: pygame.font.Font) -> None:
    """アーティファクト選択オーバーレイ（3択）を描画する。"""
    overlay = pygame.Surface((WIN_W, WIN_H), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 210))
    surf.blit(overlay, (0, 0))

    # タイトル
    title = font_title.render('── アーティファクトを1つ選べ ──', True, (255, 220, 80))
    surf.blit(title, (WIN_W // 2 - title.get_width() // 2, 30))

    CARD_W  = 200
    CARD_H  = 160
    GAP     = 24
    total_w = CARD_W * len(choices) + GAP * (len(choices) - 1)
    start_x = WIN_W // 2 - total_w // 2
    card_y  = WIN_H // 2 - CARD_H // 2

    for i, art_id in enumerate(choices):
        adef      = ARTIFACT_DEFS.get(art_id, {})
        icon_col  = adef.get('icon_color', (180, 180, 180))
        name_str  = adef.get('name', art_id)
        desc_str  = adef.get('desc', '')
        cx        = start_x + i * (CARD_W + GAP)
        selected  = (i == cursor)

        # カード背景
        bg_col  = (50, 50, 90) if not selected else (80, 80, 160)
        bd_col  = (255, 220, 80) if selected else (100, 100, 160)
        pygame.draw.rect(surf, bg_col,  pygame.Rect(cx, card_y, CARD_W, CARD_H), border_radius=10)
        pygame.draw.rect(surf, bd_col,  pygame.Rect(cx, card_y, CARD_W, CARD_H), 3, border_radius=10)

        # アイコン（大きめ四角）
        icon_size = 44
        icon_x    = cx + CARD_W // 2 - icon_size // 2
        icon_y    = card_y + 14
        pygame.draw.rect(surf, icon_col, pygame.Rect(icon_x, icon_y, icon_size, icon_size), border_radius=6)
        pygame.draw.rect(surf, (255, 255, 255), pygame.Rect(icon_x, icon_y, icon_size, icon_size), 2, border_radius=6)

        # 名前
        name_surf = font_title.render(name_str, True, icon_col if not selected else (255, 240, 120))
        surf.blit(name_surf, (cx + CARD_W // 2 - name_surf.get_width() // 2, icon_y + icon_size + 10))

        # 説明（折り返し）
        words    = desc_str
        max_w    = CARD_W - 12
        desc_y   = icon_y + icon_size + 10 + name_surf.get_height() + 6
        line_buf = ''
        for ch in words:
            test = line_buf + ch
            if font_item.size(test)[0] > max_w:
                ls = font_item.render(line_buf, True, (190, 190, 190))
                surf.blit(ls, (cx + 6, desc_y))
                desc_y += ls.get_height() + 2
                line_buf = ch
            else:
                line_buf = test
        if line_buf:
            ls = font_item.render(line_buf, True, (190, 190, 190))
            surf.blit(ls, (cx + 6, desc_y))

        # 選択中マーカー
        if selected:
            mark = font_title.render('▼ 決定: SPACEキー ▼', True, (255, 220, 80))
            surf.blit(mark, (WIN_W // 2 - mark.get_width() // 2, card_y + CARD_H + 18))

    # 操作説明
    hint = font_item.render('← → : カード切替', True, (140, 140, 160))
    surf.blit(hint, (WIN_W // 2 - hint.get_width() // 2, card_y + CARD_H + 50))


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


# ─── XPオーブエフェクト ─────────────────────────────────────────────
class XPOrb:
    """敵死亡時に飛び散り、プレイヤーへ吸い込まれる四角い経験値オーブ"""
    SIZE = 6

    def __init__(self, cx: float, cy: float, xp_value: int) -> None:
        angle = random.uniform(0, 2 * math.pi)
        speed = random.uniform(2.0, 5.0)
        self.x   = cx
        self.y   = cy
        self.vx  = math.cos(angle) * speed
        self.vy  = math.sin(angle) * speed
        self.xp_value = xp_value
        self._scatter = random.randint(20, 40)  # 飛び散りフェーズのフレーム数
        self._timer   = 0
        self.collected = False

    @property
    def alive(self) -> bool:
        return not self.collected

    def update(self, player: "Player") -> None:
        self._timer += 1
        if self._timer < self._scatter:
            # 飛び散りフェーズ: 減速しながら広がる
            self.vx *= 0.88
            self.vy *= 0.88
        else:
            # 吸い込みフェーズ: プレイヤー中心へ向かう
            pcx = player.x + player.SIZE / 2
            pcy = player.y + player.SIZE / 2
            dx  = pcx - (self.x + self.SIZE / 2)
            dy  = pcy - (self.y + self.SIZE / 2)
            dist = math.hypot(dx, dy)
            if dist < 8:
                self.collected = True
                return
            spd = min(10.0, 2.0 + (self._timer - self._scatter) * 0.15)
            self.vx = dx / dist * spd
            self.vy = dy / dist * spd
        self.x += self.vx
        self.y += self.vy

    def draw(self, surf: pygame.Surface) -> None:
        t = min(1.0, self._timer / max(1, self._scatter))
        # 吸い込み中は明るく光る
        if self._timer >= self._scatter:
            col = (120, 255, 180)
        else:
            col = (80, 220, 120)
        pygame.draw.rect(surf, col,
                         pygame.Rect(int(self.x), int(self.y), self.SIZE, self.SIZE))
        # ハイライト
        pygame.draw.rect(surf, (200, 255, 220),
                         pygame.Rect(int(self.x) + 1, int(self.y) + 1, 2, 2))


# ─── ダメージ数字エフェクト ────────────────────────────────────────
class DamageNumber:
    DURATION = 50

    def __init__(self, x: float, y: float, amount: int) -> None:
        self.x = float(x)
        self.y = float(y)
        self.amount = amount
        self.timer  = self.DURATION

    @property
    def alive(self) -> bool:
        return self.timer > 0

    def update(self) -> None:
        self.timer -= 1
        self.y -= 0.8

    def draw(self, surf: pygame.Surface, font: pygame.font.Font) -> None:
        t   = self.timer / self.DURATION
        if self.amount < 0:  # 回復表示（負値で渡す）
            col = (int(80 + 120 * t), 255, int(80 + 60 * t))
            txt = font.render(f'+{-self.amount}', True, col)
        else:
            col = (255, int(200 * t), 50)
            txt = font.render(str(self.amount), True, col)
        surf.blit(txt, (int(self.x) - txt.get_width() // 2, int(self.y)))


class ItemPopup:
    """アイテム入手時に画面中央付近に浮かぶ通知"""
    DURATION = 120

    def __init__(self, item_kind: str) -> None:
        self.item_kind = item_kind
        self.timer = self.DURATION

    @property
    def alive(self) -> bool:
        return self.timer > 0

    def update(self) -> None:
        self.timer -= 1

    def draw(self, surf: pygame.Surface, font: pygame.font.Font) -> None:
        t = self.timer / self.DURATION
        name = ITEM_DEFS[self.item_kind]['name']
        color = ITEM_DEFS[self.item_kind]['color']
        # フェードイン/アウト（最初と最後の20フレーム）
        if t > 0.85:
            alpha = int(255 * (1.0 - t) / 0.15)
        elif t < 0.15:
            alpha = int(255 * t / 0.15)
        else:
            alpha = 255
        label = font.render(f'入手: {name}', True, color)
        w, h = label.get_width() + 24, label.get_height() + 12
        x = (WIN_W - w) // 2
        y = WIN_H // 3
        bg = pygame.Surface((w, h), pygame.SRCALPHA)
        bg.fill((0, 0, 0, min(alpha, 180)))
        surf.blit(bg, (x, y))
        label.set_alpha(alpha)
        surf.blit(label, (x + 12, y + 6))


# ─── アイテム定義 ────────────────────────────────────────────────
# kind: 'potion' | 'para_drug'
# 'potion'    : 使用で HP+3
# 'para_drug' : 使用で前方に麻痺薬を投擲。命中した敵に麻痺状態付与
ITEM_DEFS = {
    'potion':   {'name': 'ポーション', 'color': (60, 200, 80),  'max_stack': 9},
    'para_drug':{'name': '麻痺薬',     'color': (220, 200, 50), 'max_stack': 9},
}
_CHEST_ITEMS = ['potion', 'para_drug']


# ─── 飛翔体（毒矢・痺薬）エフェクト ─────────────────────────────────
class Projectile:
    """プレイヤーが使うアイテム飛翔体"""
    SIZE   = 10
    SPEED  = 7.0
    RANGE  = TILE * 8  # 最大射程

    def __init__(self, x: float, y: float, vx: float, vy: float, kind: str) -> None:
        self.x    = float(x)
        self.y    = float(y)
        self.vx   = vx
        self.vy   = vy
        self.kind = kind   # 'para_drug'
        self._dist = 0.0
        self.alive = True
        self._anim = 0

    def update(self) -> None:
        if not self.alive:
            return
        self._anim += 1
        self.x += self.vx
        self.y += self.vy
        self._dist += math.hypot(self.vx, self.vy)
        # 画面外 or 射程オーバー or 壁
        if (self._dist > self.RANGE or
                self.x < 0 or self.x > WIN_W or
                self.y < 0 or self.y > TILE * ROWS or
                self._solid_at(self.x, self.y)):
            self.alive = False

    def _solid_at(self, px: float, py: float) -> bool:
        s = self.SIZE
        for cx, cy in [(px, py), (px+s, py), (px, py+s), (px+s, py+s)]:
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
        # para_drug: 黄色い瓶投擲
        pygame.draw.circle(surf, (220, 200, 40), (x, y), 6)
        pygame.draw.circle(surf, (255, 240, 100), (x - 2, y - 2), 3)
        # スパーク（雷のような放射）
        a = self._anim * 0.4
        for i in range(4):
            ang = a + i * math.pi / 2
            ex = x + int(math.cos(ang) * 7)
            ey = y + int(math.sin(ang) * 7)
            pygame.draw.circle(surf, (255, 220, 60), (ex, ey), 2)


# ─── 状態異常エフェクト（毒・麻痺） ─────────────────────────────────
class StatusEffect:
    """敵に付く状態異常の視覚エフェクト"""
    def __init__(self, kind: str) -> None:
        self.kind  = kind   # 'poison' or 'para'
        if kind == 'poison':
            self.duration = 180  # 3秒
            self.tick     = 30   # 30fごとにダメージ
        else:  # para
            self.duration = 120  # 2秒
            self.tick     = 999  # ダメージなし（移動停止のみ）
        self._tick_count = 0
        self._anim       = 0

    @property
    def active(self) -> bool:
        return self.duration > 0

    def update(self) -> int:
        """毎フレーム呼ぶ。毒ダメージが発生したら1を返す、それ以外は0"""
        self.duration    -= 1
        self._anim       += 1
        self._tick_count += 1
        if self.kind == 'poison' and self._tick_count >= self.tick:
            self._tick_count = 0
            return 1
        return 0

    def draw(self, surf: pygame.Surface, ex: float, ey: float, size: int) -> None:
        cx = int(ex + size / 2)
        cy = int(ey)
        if self.kind == 'poison':
            # 緑の泡が上へ浮かぶ
            for i in range(3):
                off = (self._anim * 2 + i * 20) % 30
                bx = cx + (i - 1) * 6
                by = cy - off - 4
                alpha = max(0, 255 - off * 8)
                r = max(2, 4 - off // 10)
                if 0 <= bx < WIN_W and 0 <= by < TILE * ROWS:
                    pygame.draw.circle(surf, (60, 200, 60), (bx, by), r)
        else:  # para
            # 黄色い星マーク点滅
            if (self._anim // 6) % 2 == 0:
                for i in range(4):
                    ang = self._anim * 0.15 + i * math.pi / 2
                    sx = cx + int(math.cos(ang) * 10)
                    sy = cy - 8 + int(math.sin(ang) * 4)
                    if 0 <= sx < WIN_W and 0 <= sy < TILE * ROWS:
                        pygame.draw.circle(surf, (255, 240, 50), (sx, sy), 3)


# ─── 宝箱クラス ──────────────────────────────────────────────────
class Chest:
    SIZE = 32

    def __init__(self, x: float, y: float, item_kind: str) -> None:
        self.x         = float(x)
        self.y         = float(y)
        self.item_kind = item_kind
        self.opened    = False

    def try_open(self, player: "Player") -> str | None:
        """プレイヤーが1タイル以内なら開封し、アイテム種別を返す"""
        if self.opened:
            return None
        dx = abs((self.x + self.SIZE / 2) - (player.x + player.SIZE / 2))
        dy = abs((self.y + self.SIZE / 2) - (player.y + player.SIZE / 2))
        if dx < TILE and dy < TILE:
            self.opened = True
            return self.item_kind
        return None

    def draw(self, surf: pygame.Surface) -> None:
        x, y = int(self.x), int(self.y)
        s = self.SIZE
        if not self.opened:
            # 蓋付き宝箱（茶色ボックス＋金の帯）
            pygame.draw.rect(surf, (120, 70, 20), pygame.Rect(x, y + 10, s, s - 10))
            pygame.draw.rect(surf, (160, 100, 30), pygame.Rect(x, y + 4, s, 10))
            pygame.draw.rect(surf, (200, 170, 50), pygame.Rect(x + s // 2 - 5, y + 8, 10, 10))
            pygame.draw.rect(surf, (80, 50, 10),  pygame.Rect(x, y + 10, s, s - 10), 2)
        else:
            # 開いた宝箱（蓋が開いた状態）
            pygame.draw.rect(surf, (100, 60, 15), pygame.Rect(x, y + 10, s, s - 10))
            pygame.draw.rect(surf, (160, 100, 30), pygame.Rect(x - 2, y - 2, s + 4, 10))
            pygame.draw.rect(surf, (80, 50, 10),  pygame.Rect(x, y + 10, s, s - 10), 2)


# ─── 敵スポーン位置をランダムに決定 ──────────────────────────────────
def spawn_enemy_pos(player_x: float, player_y: float,
                    min_dist: int = 5) -> tuple[float, float]:
    """ソリッドでなく、プレイヤーからmin_distタイル以上離れたタイルをランダム選択"""
    px_tile = int(player_x // TILE)
    py_tile = int(player_y // TILE)
    # min_dist を徐々に縮小してフォールバック
    for dist in range(min_dist, -1, -1):
        candidates = []
        for row in range(1, ROWS - 1):
            for col in range(1, COLS - 1):
                if CURRENT_MAP[row][col] in SOLID_TILES:
                    continue
                if CURRENT_MAP[row][col] == DOOR:
                    continue
                if abs(col - px_tile) < dist and abs(row - py_tile) < dist:
                    continue
                candidates.append((col, row))
        if candidates:
            break
    col, row = random.choice(candidates)
    x = col * TILE + (TILE - Enemy.SIZE) // 2
    y = row * TILE + (TILE - Enemy.SIZE) // 2
    return float(x), float(y)


# ─── ワープポイント描画 ──────────────────────────────────────────
def draw_warp_point(surf: pygame.Surface, col: int, row: int, anim: int,
                    color: tuple = (0, 200, 255)) -> None:
    """光輪ワープポイントを描画する。colorで色を変更可能"""
    cx = col * TILE + TILE // 2
    cy = row * TILE + TILE // 2
    pulse = math.sin(anim * 0.08) * 4
    r1 = int(19 + pulse)
    r2 = int(12 + pulse * 0.6)
    r3 = int(6  + abs(pulse) * 0.3)
    c1 = color
    c2 = tuple(min(255, v + 80) for v in color)
    c3 = tuple(min(255, v + 150) for v in color)
    pygame.draw.circle(surf, c1, (cx, cy), r1, 3)
    pygame.draw.circle(surf, c2, (cx, cy), r2, 2)
    pygame.draw.circle(surf, c3, (cx, cy), r3)


# ─── 部屋遷移ヘルパー ─────────────────────────────────────────
def _make_enemy(px: float, py: float, floor_level: int) -> "Enemy":
    """floor_level に応じた確率で各種敵を生成する。"""
    r = random.random()
    if floor_level >= 2:
        # 2階以降: ArrowEnemy 20%, BlueEnemy 30%, Enemy 50%
        arrow_chance = min(0.40, 0.20 + (floor_level - 2) * 0.05)
        blue_chance  = min(0.80, 0.10 + (floor_level - 1) * 0.20)
        if r < arrow_chance:
            cls = ArrowEnemy
        elif r < blue_chance:
            cls = BlueEnemy
        else:
            cls = Enemy
    else:
        # 1階: 10% BlueEnemy, 残りEnemy
        blue_chance = 0.10
        cls = BlueEnemy if r < blue_chance else Enemy
    return cls(*spawn_enemy_pos(px, py))


def enter_room(room_id: int, spawn_col: int, spawn_row: int,
               player: "Player", floor_level: int = 1,
               room_enemies: dict = None,
               room_chests: dict = None) -> tuple:
    """部屋遷移処理。CURRENT_MAP更新・tile_surf再ビルド・enemies/chests生成を返す"""
    global CURRENT_MAP
    CURRENT_MAP = ROOM_MAPS[room_id]
    tile_surf = build_tile_surface(CURRENT_MAP)
    player.x = float(spawn_col * TILE + (TILE - player.SIZE) // 2)
    player.y = float(spawn_row * TILE + (TILE - player.SIZE) // 2)
    player.attack_timer = 0
    player.attack_cooldown = 0
    # キャッシュ済みならそれを使う（敵をリセットしない）
    if room_enemies is not None and room_id in room_enemies:
        enemies = room_enemies[room_id]
    else:
        rtype = ROOM_TYPES.get(room_id, 'main')
        # ボスフロア（'boss'/'main'のみの2室構成）では通常モブを出さない
        is_boss_floor = not any(t == 'monster' for t in ROOM_TYPES.values())
        if is_boss_floor:
            enemies = []
        elif rtype == 'monster':
            enemies = [_make_enemy(player.x, player.y, floor_level) for _ in range(5)]
        elif rtype == 'main':
            enemies = [_make_enemy(player.x, player.y, floor_level) for _ in range(2)]
        else:
            enemies = []
        if room_enemies is not None:
            room_enemies[room_id] = enemies
    # 宝箱キャッシュ
    if room_chests is not None and room_id in room_chests:
        chests = room_chests[room_id]
    else:
        chests = _make_chests(room_id)
        if room_chests is not None:
            room_chests[room_id] = chests
    return tile_surf, enemies, chests


def _make_chests(room_id: int, player: "Player | None" = None) -> list:
    """宝部屋に宝箱1〜2個、mainに稀に1個、それ以外は0個。lucky_chest所持時は+1個"""
    rtype = ROOM_TYPES.get(room_id, 'main')
    if rtype == 'treasure':
        n = random.randint(1, 2)
    elif rtype == 'boss':
        return []  # 宝箱はボス撃破後にゲームループで生成
    elif rtype == 'main' and random.random() < 0.15:
        n = 1
    else:
        return []
    # lucky_chest アーティファクトで +1
    if player and 'lucky_chest' in player.artifacts:
        n += 1
    chests = []
    used = set()
    for _ in range(n):
        for _attempt in range(50):
            col = random.randint(2, COLS - 3)
            row = random.randint(2, ROWS - 3)
            if CURRENT_MAP[row][col] in SOLID_TILES:
                continue
            if (col, row) in used:
                continue
            used.add((col, row))
            kind = random.choice(_CHEST_ITEMS)
            cx = col * TILE + (TILE - Chest.SIZE) // 2
            cy = row * TILE + (TILE - Chest.SIZE) // 2
            chests.append(Chest(float(cx), float(cy), kind))
            break
    return chests


def _pick_artifact_choices(player: "Player", n: int = 3) -> list[str]:
    """プレイヤーが未所持のアーティファクトからランダムにn種を選んで返す。"""
    pool = [k for k in ARTIFACT_DEFS if k not in player.artifacts]
    if not pool:
        pool = list(ARTIFACT_DEFS.keys())  # 全取得済みなら全候補から
    return random.sample(pool, min(n, len(pool)))


def _apply_artifact(player: "Player", art_id: str) -> None:
    """アーティファクトの即時効果をプレイヤーに適用する。"""
    if art_id == 'iron_heart':
        player.max_hp += 2
        player.hp = min(player.hp + 2, player.max_hp)
    elif art_id == 'swift_boots':
        # SPEEDはクラス変数なのでインスタンス変数で上書き
        player.SPEED = getattr(player, 'SPEED', 3) + 1
    elif art_id == 'sharp_eye':
        # 攻撃力はattack_damage()で参照するボーナスをインスタンスに持たせる
        player.atk_bonus = getattr(player, 'atk_bonus', 0) + 1
    elif art_id == 'mana_shield':
        player.inv_multiplier = getattr(player, 'inv_multiplier', 1) * 2
    # fire_ring / cold_aura / lucky_chest は
    # ゲームループ側で player.artifacts を参照して効果を発動する（passive）


# ─── メイン ───────────────────────────────────────────────
def main() -> None:
    global CURRENT_MAP, WARP_ROOM, WARP_TILE
    pygame.init()
    screen = pygame.display.set_mode((WIN_W, WIN_H))
    pygame.display.set_caption("Zelda-like  ─  One Screen Prototype")
    clock = pygame.time.Clock()
    font_room       = pygame.font.SysFont("msgothic", 18)
    font_hud        = pygame.font.SysFont("msgothic", 14)
    font_dmg        = pygame.font.SysFont("msgothic", 16, bold=True)
    font_menu_title = pygame.font.SysFont("msgothic", 20, bold=True)
    font_menu_item  = pygame.font.SysFont("msgothic", 16)

    build_dungeon()
    current_room = START_ROOM
    CURRENT_MAP = ROOM_MAPS[current_room]
    tile_surf = build_tile_surface(CURRENT_MAP)

    # プレイヤーをスタート部屋中央に配置
    player = Player(
        x=TILE * 7 + (TILE - Player.SIZE) // 2,
        y=TILE * 5 + (TILE - Player.SIZE) // 2,
    )

    floor_level = 1   # 現在の階層（1が地上、潜るごとに増加）
    room_enemies: dict = {}  # room_id -> enemies キャッシュ
    room_chests:  dict = {}  # room_id -> chests キャッシュ

    # スタート部屋 (main): 敵2体
    enemies = [_make_enemy(player.x, player.y, floor_level) for _ in range(2)]
    room_enemies[START_ROOM] = enemies
    chests = _make_chests(START_ROOM, player)
    room_chests[START_ROOM] = chests
    ACTIVE_CHESTS[:] = chests
    projectiles: list = []  # 飛翔体リスト（プレイヤー発射）
    enemy_arrows: list = []  # 敵の矢リスト
    explosions:  list = []
    damage_nums:  list = []
    item_popups:  list = []
    xp_orbs:     list = []
    boss: "Boss | None" = None   # ボスインスタンス
    shake_timer  = 0             # 画面揺れ残りフレーム
    shake_mag    = 0             # 揺れ強度
    boss_death_seq   = 0   # ボス撃破エフェクトカウンター（0で非アクティブ）
    boss_death_cx    = 0.0 # ボス死亡座標X
    boss_death_cy    = 0.0 # ボス死亡座標Y
    _BOSS_DEATH_DUR  = 120 # 爆発エフェクト總フレーム数
    door_cooldown = 0  # 連続遷移防止
    warp_anim   = 0   # ワープ光輪アニメーションカウンタ
    debug_warp  = False  # Pキーで生成したデバッグワープかどうか
    menu_open   = False
    menu_tab    = 0   # 0=セーブ 1=ロード 2=アイテム 3=装備 4=ステータス 5=アーティファクト 6=オプション
    game_over = False
    # ── アーティファクト選択 ──
    artifact_choices: list = []   # 提示中の3候補ID
    artifact_cursor  = 0          # 選択カーソル位置

    # 部屋タイプ名
    _TYPE_NAMES = {
        'main':     'フィールド',
        'monster':  'モンスターハウス',
        'treasure': '宝部屋',
        'boss':     'ボス部屋',
    }

    running = True
    while running:
        # ── イベント ──
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    if menu_open:
                        menu_open = False
                    elif artifact_choices:
                        pass  # 選択中はESCで閉じない
                    else:
                        running = False
                # アーティファクト選択中の操作
                elif artifact_choices:
                    if event.key == pygame.K_LEFT:
                        artifact_cursor = (artifact_cursor - 1) % len(artifact_choices)
                    elif event.key == pygame.K_RIGHT:
                        artifact_cursor = (artifact_cursor + 1) % len(artifact_choices)
                    elif event.key == pygame.K_SPACE:
                        chosen = artifact_choices[artifact_cursor]
                        player.artifacts.append(chosen)
                        _apply_artifact(player, chosen)
                        artifact_choices = []
                        artifact_cursor  = 0
                elif event.key == pygame.K_m:
                    if not game_over:
                        menu_open = not menu_open
                elif menu_open:
                    if event.key == pygame.K_UP:
                        menu_tab = (menu_tab - 1) % len(_MENU_TABS)
                    elif event.key == pygame.K_DOWN:
                        menu_tab = (menu_tab + 1) % len(_MENU_TABS)
                elif event.key == pygame.K_SPACE:
                    if not game_over:
                        player.try_attack()
                elif event.key == pygame.K_q and not game_over:
                    # 選択中アイテムを使用
                    kind = player._item_slots[player.selected_slot]
                    if player.inventory.get(kind, 0) > 0:
                        player.inventory[kind] -= 1
                        if kind == 'potion':
                            heal = min(3, player.max_hp - player.hp)
                            player.hp = min(player.max_hp, player.hp + 3)
                            if heal > 0:
                                # 回復エフェクト（負値で渡すと緑表示）
                                damage_nums.append(DamageNumber(
                                    player.x + player.SIZE / 2,
                                    player.y - 4, -heal))
                        elif kind in ('para_drug',):
                            fdx, fdy = player.facing
                            spd = Projectile.SPEED
                            px = player.x + player.SIZE / 2
                            py = player.y + player.SIZE / 2
                            projectiles.append(Projectile(px, py, fdx * spd, fdy * spd, kind))
                elif event.key == pygame.K_LEFT and not game_over:
                    n = len(player._item_slots)
                    player.selected_slot = (player.selected_slot - 1) % n
                elif event.key == pygame.K_RIGHT and not game_over:
                    n = len(player._item_slots)
                    player.selected_slot = (player.selected_slot + 1) % n
                elif event.key == pygame.K_p and not game_over:
                    # デバッグ: プレイヤーの目の前にボス階層ワープゲートを生成（黄色）
                    fdx, fdy = player.facing
                    wt_col = int((player.x + player.SIZE / 2) // TILE) + fdx
                    wt_row = int((player.y + player.SIZE / 2) // TILE) + fdy
                    wt_col = max(1, min(COLS - 2, wt_col))
                    wt_row = max(1, min(ROWS - 2, wt_row))
                    WARP_ROOM = current_room
                    WARP_TILE = (wt_col, wt_row)
                    debug_warp = True
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
                    room_enemies = {}
                    room_chests  = {}
                    enemies = [_make_enemy(player.x, player.y, 1) for _ in range(2)]
                    room_enemies[START_ROOM] = enemies
                    chests = _make_chests(START_ROOM, player)
                    room_chests[START_ROOM] = chests
                    ACTIVE_CHESTS[:] = chests
                    projectiles.clear()
                    enemy_arrows.clear()
                    explosions.clear()
                    damage_nums.clear()
                    xp_orbs.clear()
                    door_cooldown = 0
                    floor_level = 1
                    boss = None
                    warp_anim   = 0
                    menu_open   = False
                    menu_tab    = 0
                    game_over = False

        # ── 更新 ──
        if not game_over and not menu_open and not artifact_choices:
            keys = pygame.key.get_pressed()
            player.update(keys)
            for e in enemies:
                pdmg = e.update(player.x, player.y)
                if pdmg:
                    damage_nums.append(DamageNumber(e.x + e.SIZE / 2, e.y - 6, pdmg))
                # ArrowEnemy の矢発射
                if isinstance(e, ArrowEnemy) and e.alive:
                    arrow = e.try_shoot(player.x, player.y)
                    if arrow:
                        enemy_arrows.append(arrow)

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
                    tile_surf, enemies, chests = enter_room(dest_room, dest_col, dest_row, player, floor_level, room_enemies, room_chests)
                    ACTIVE_CHESTS[:] = chests
                    explosions.clear()
                    xp_orbs.clear()
                    door_cooldown = 60
                    # ボス部屋に入ったときボスをスポーン（まだ倒していない場合）
                    if ROOM_TYPES.get(current_room) == 'boss' and (boss is None or not boss.alive):
                        bx = WIN_W / 2 - Boss.SIZE / 2
                        by = TILE * ROWS / 2 - Boss.SIZE / 2
                        boss = Boss(bx, by)

            # ── ワープ判定 ──
            _boss_alive = boss is not None and boss.alive
            if door_cooldown == 0 and current_room == WARP_ROOM and not _boss_alive:
                wcx = WARP_TILE[0] * TILE + TILE // 2
                wcy = WARP_TILE[1] * TILE + TILE // 2
                pcx = player.x + player.SIZE / 2
                pcy = player.y + player.SIZE / 2
                if abs(pcx - wcx) < TILE // 2 and abs(pcy - wcy) < TILE // 2:
                    if debug_warp:
                        # デバッグワープ: 強制的にボス階層（3F）へ
                        floor_level = 3
                        build_boss_floor()
                        debug_warp = False
                    else:
                        floor_level += 1
                        if floor_level == 3:
                            build_boss_floor()
                        else:
                            build_dungeon()
                    room_enemies.clear()  # 新フロアなので全部屋リセット
                    room_chests.clear()
                    current_room = START_ROOM
                    tile_surf, enemies, chests = enter_room(START_ROOM, 7, 5, player, floor_level, room_enemies, room_chests)
                    ACTIVE_CHESTS[:] = chests
                    explosions.clear()
                    damage_nums.clear()
                    xp_orbs.clear()
                    projectiles.clear()
                    enemy_arrows.clear()
                    boss = None
                    door_cooldown = 90
                    # 階層移動時にアーティファクト選択画面を開く
                    artifact_choices = _pick_artifact_choices(player)
                    artifact_cursor  = 0

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
                            dmg = player.attack_damage()
                            e.take_damage(dmg, _dx / _d * 9.0, _dy / _d * 9.0)
                            player._attacked_set.add(id(e))
                            damage_nums.append(DamageNumber(
                                e.x + e.SIZE / 2, e.y, dmg))
                            # fire_ring: ヒット時に小爆発
                            if 'fire_ring' in player.artifacts:
                                explosions.append(Explosion(e.x + e.SIZE/2, e.y + e.SIZE/2))
                # ボスへの剣当たり判定（ボス部屋のみ）
                if boss and boss.alive and ROOM_TYPES.get(current_room) == 'boss':
                    b_rect = pygame.Rect(int(boss.x), int(boss.y), Boss.SIZE, Boss.SIZE)
                    if sword_r.colliderect(b_rect) and id(boss) not in player._attacked_set:
                        _dx = (boss.x + Boss.SIZE/2) - (player.x + player.SIZE/2)
                        _dy = (boss.y + Boss.SIZE/2) - (player.y + player.SIZE/2)
                        _d  = max(1.0, math.hypot(_dx, _dy))
                        dmg = player.attack_damage()
                        boss.take_damage(dmg)
                        player._attacked_set.add(id(boss))
                        damage_nums.append(DamageNumber(boss.x + Boss.SIZE/2, boss.y, dmg))
                        # 剣攻撃でボスが死亡した場合も演出シーケンスを開始
                        if not boss.alive and boss_death_seq == 0:
                            boss_death_cx = boss.x + Boss.SIZE / 2
                            boss_death_cy = boss.y + Boss.SIZE / 2
                            boss_death_seq = _BOSS_DEATH_DUR
                            shake_timer = 30
                            shake_mag   = 30
            for e in enemies:
                if not e.alive:
                    cx = e.x + e.SIZE / 2
                    cy = e.y + e.SIZE / 2
                    explosions.append(Explosion(cx, cy))
                    xp_amt = e.xp_value
                    n_orbs = max(1, xp_amt // 3)
                    for _ in range(n_orbs):
                        xp_orbs.append(XPOrb(cx, cy, xp_amt // n_orbs))
                else:
                    # cold_aura: 近くの敵の速度を-20%
                    if 'cold_aura' in player.artifacts:
                        dist = math.hypot((e.x + e.SIZE/2) - (player.x + player.SIZE/2),
                                         (e.y + e.SIZE/2) - (player.y + player.SIZE/2))
                        if dist < TILE * 5:
                            e.SPEED = max(0.2, e.__class__.SPEED * 0.8)
                        else:
                            e.SPEED = e.__class__.SPEED
            enemies = [e for e in enemies if e.alive]
            room_enemies[current_room] = enemies  # 倒された敵を反映

            # 宝箱の自動開封（開いたら消去）
            opened_any = False
            for ch in chests:
                got = ch.try_open(player)
                if got:
                    cur = player.inventory.get(got, 0)
                    max_s = ITEM_DEFS[got]['max_stack']
                    player.inventory[got] = min(max_s, cur + 1)
                    item_popups.append(ItemPopup(got))
                    opened_any = True
            if opened_any:
                chests = [ch for ch in chests if not ch.opened]
                room_chests[current_room] = chests
                ACTIVE_CHESTS[:] = chests

            # 飛翔体の更新と敵への当たり判定
            for proj in projectiles:
                proj.update()
                if proj.alive:
                    pr = pygame.Rect(int(proj.x), int(proj.y), proj.SIZE, proj.SIZE)
                    for e in enemies:
                        e_rect = pygame.Rect(int(e.x), int(e.y), e.SIZE, e.SIZE)
                        if pr.colliderect(e_rect):
                            proj.alive = False
                            if proj.kind == 'para_drug':
                                if not (e.status and e.status.kind == 'para'):
                                    e.status = StatusEffect('para')
                            break
            projectiles = [p for p in projectiles if p.alive]
            # 敵の矢更新・プレイヤー当たり判定
            p_rect = pygame.Rect(int(player.x) + 4, int(player.y) + 4,
                                 player.SIZE - 8, player.SIZE - 8)
            for arr in enemy_arrows:
                arr.update()
                if arr.alive:
                    a_rect = pygame.Rect(int(arr.x) - arr.SIZE // 2,
                                         int(arr.y) - arr.SIZE // 2,
                                         arr.SIZE, arr.SIZE)
                    if a_rect.colliderect(p_rect):
                        arr.alive = False
                        _adx = arr.vx / max(1, math.hypot(arr.vx, arr.vy)) * 4
                        _ady = arr.vy / max(1, math.hypot(arr.vx, arr.vy)) * 4
                        player.take_damage(1, _adx, _ady)
            enemy_arrows[:] = [arr for arr in enemy_arrows if arr.alive]
            for ex in explosions:
                ex.update()
            explosions = [ex for ex in explosions if ex.alive]
            for dn in damage_nums:
                dn.update()
            damage_nums = [dn for dn in damage_nums if dn.alive]
            for ip in item_popups:
                ip.update()
            item_popups[:] = [ip for ip in item_popups if ip.alive]
            for orb in xp_orbs:
                orb.update(player)
                if orb.collected:
                    player.gain_xp(orb.xp_value)
            xp_orbs = [orb for orb in xp_orbs if orb.alive]

            # ボス更新・接触ダメージ（ボス部屋にいる間のみ）
            in_boss_room = ROOM_TYPES.get(current_room) == 'boss'
            if boss and boss.alive and in_boss_room:
                boss.update(player.x, player.y)
                if boss.shake > 0:
                    shake_timer = boss.shake
                    shake_mag   = boss.shake
                b_rect = pygame.Rect(int(boss.x), int(boss.y), Boss.SIZE, Boss.SIZE)
                p_rect_b = pygame.Rect(int(player.x) + 4, int(player.y) + 4,
                                       player.SIZE - 8, player.SIZE - 8)
                # ジャンプ中は接触ダメージなし
                if b_rect.colliderect(p_rect_b) and boss._state != Boss._STATE_JUMP:
                    _dx = (player.x + player.SIZE/2) - (boss.x + Boss.SIZE/2)
                    _dy = (player.y + player.SIZE/2) - (boss.y + Boss.SIZE/2)
                    _d  = max(1.0, math.hypot(_dx, _dy))
                    player.take_damage(1, _dx / _d * 8.0, _dy / _d * 8.0)
                if not boss.alive:
                    # ボス討伐: 巨大爆発シーケンス開始（宝箱・ワープはシーケンス終了後に生成）
                    boss_death_cx = boss.x + Boss.SIZE / 2
                    boss_death_cy = boss.y + Boss.SIZE / 2
                    boss_death_seq = _BOSS_DEATH_DUR
                    shake_timer = 30
                    shake_mag   = 30

            # ボス撃破爆発シーケンス
            if boss_death_seq > 0:
                boss_death_seq -= 1
                # 毎フレームごとにランダム位置に爆発を追加
                if boss_death_seq % 6 == 0:
                    _spread = TILE * 2
                    ex = boss_death_cx + random.uniform(-_spread, _spread)
                    ey = boss_death_cy + random.uniform(-_spread, _spread)
                    explosions.append(Explosion(ex, ey))
                    shake_timer = max(shake_timer, 8)
                    shake_mag   = max(shake_mag,   8)
                # 中間点で中央大爆発
                if boss_death_seq == _BOSS_DEATH_DUR // 2:
                    for _ in range(6):
                        ex = boss_death_cx + random.uniform(-TILE, TILE)
                        ey = boss_death_cy + random.uniform(-TILE, TILE)
                        explosions.append(Explosion(ex, ey))
                    shake_timer = 25
                    shake_mag   = 25
                # シーケンス終了→宝箱・ワープ生成
                if boss_death_seq == 0:
                    room_cx = WIN_W / 2
                    room_cy = TILE * (ROWS // 2 + 2)
                    for off_x in [-TILE, 0, TILE]:
                        cx_ = room_cx + off_x - Chest.SIZE / 2
                        cy_ = room_cy - Chest.SIZE / 2
                        kind_ = random.choice(_CHEST_ITEMS)
                        chests.append(Chest(float(cx_), float(cy_), kind_))
                    ACTIVE_CHESTS[:] = chests
                    WARP_ROOM = current_room
                    WARP_TILE = (int(room_cx // TILE), int((room_cy + Chest.SIZE) // TILE) + 1)
                    # アーティファクト選択画面を開く
                    artifact_choices = _pick_artifact_choices(player)
                    artifact_cursor  = 0

            # 画面揺れ更新
            if shake_timer > 0:
                shake_timer -= 1

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
        warp_anim += 1
        # 画面揺れオフセット
        sx = random.randint(-shake_timer, shake_timer) if shake_timer > 0 else 0
        sy = random.randint(-shake_timer, shake_timer) if shake_timer > 0 else 0
        screen.blit(tile_surf, (sx, sy))
        # ボスが生存中・爆発演出中はワープゲートを非表示
        boss_alive = boss is not None and boss.alive
        if current_room == WARP_ROOM and not boss_alive and boss_death_seq == 0:
            warp_col = (255, 220, 0) if debug_warp else (0, 200, 255)
            draw_warp_point(screen, WARP_TILE[0], WARP_TILE[1], warp_anim, color=warp_col)
        for ch in chests:
            ch.draw(screen)
        for e in enemies:
            e.draw(screen)
        if boss and boss.alive and ROOM_TYPES.get(current_room) == 'boss':
            boss.draw(screen)
        for proj in projectiles:
            proj.draw(screen)
        for arr in enemy_arrows:
            arr.draw(screen)
        for ex in explosions:
            ex.draw(screen)
        for orb in xp_orbs:
            orb.draw(screen)
        for dn in damage_nums:
            dn.draw(screen, font_dmg)
        for ip in item_popups:
            ip.draw(screen, font_hud)
        player.draw(screen)
        draw_hud(screen, player, font_hud)

        # 部屋名をHUD右端に表示
        name_txt = font_room.render(
            _TYPE_NAMES.get(ROOM_TYPES.get(current_room, 'main'), ''), True, (200, 200, 200))
        screen.blit(name_txt, (WIN_W - name_txt.get_width() - 12,
                               TILE * ROWS + 6))
        # M キーヒントをHUD右端下段に表示
        menu_hint = font_hud.render("M : メニュー", True, (100, 100, 140))
        screen.blit(menu_hint, (WIN_W - menu_hint.get_width() - 12,
                                TILE * ROWS + HUD_H - menu_hint.get_height() - 6))
        # 階層表示をHUD中央に表示
        floor_label = f"地下 {floor_level} 階" if floor_level > 1 else "地上"
        floor_txt = font_room.render(floor_label, True, (180, 220, 255))
        screen.blit(floor_txt, (WIN_W // 2 - floor_txt.get_width() // 2,
                                TILE * ROWS + (HUD_H - floor_txt.get_height()) // 2))

        # ── アーティファクト選択画面 ──
        if artifact_choices:
            draw_artifact_select(screen, artifact_choices, artifact_cursor,
                                 font_menu_title, font_menu_item)

        # ── メニュー画面 ──
        if menu_open:
            draw_menu(screen, player, menu_tab, font_menu_title, font_menu_item, floor_level)

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
