"""
generate_swords.py  ─  一度だけ実行して sword_lv1-4.png を生成するスクリプト

  python generate_swords.py

New Piskel.png をベースに 4 レベル分の剣スプライトを生成します。
  sword_lv1.png … 木の短剣（原画そのまま）
  sword_lv2.png … 鉄の短剣（スチール青灰）
  sword_lv3.png … 炎の短剣（炎オレンジ）
  sword_lv4.png … 伝説の短剣（黄金）
"""

import os
import shutil
import colorsys
from PIL import Image

BASE = os.path.dirname(os.path.abspath(__file__))
SRC  = os.path.join(BASE, "New Piskel.png")


def recolor(src_path: str, dst_path: str,
            target_h: float, sat_mult: float, val_mult: float) -> None:
    """
    HSV 色相を target_h に変えてコピーを保存する。
    輪郭（V < 0.18）はそのまま維持。
    """
    img = Image.open(src_path).convert("RGBA")
    out = img.copy()
    pw  = img.load()
    po  = out.load()
    w, h = img.size

    for y in range(h):
        for x in range(w):
            r, g, b, a = pw[x, y]
            if a < 10:
                continue  # 透明はスキップ

            hf, sf, vf = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)

            if vf < 0.18:
                continue  # 輪郭（ほぼ黒）はそのまま

            if sf > 0.12:
                # 色がある部分（刃・鍔・柄）→ 色相を変える
                new_h = target_h
                new_s = min(1.0, sf * sat_mult)
                new_v = min(1.0, vf * val_mult)
            else:
                # 無彩色（ハイライト系）→ 色相をやや加味して明度調整
                new_h = target_h
                new_s = 0.15 * sat_mult
                new_v = min(1.0, vf * val_mult)

            nr, ng, nb = colorsys.hsv_to_rgb(new_h, new_s, new_v)
            po[x, y] = (int(nr * 255), int(ng * 255), int(nb * 255), a)

    out.save(dst_path)
    print(f"  保存: {os.path.basename(dst_path)}")


if not os.path.exists(SRC):
    print(f"エラー: {SRC} が見つかりません")
    raise SystemExit(1)

# Lv1: 原画をそのままコピー
shutil.copy(SRC, os.path.join(BASE, "sword_lv1.png"))
print("  保存: sword_lv1.png（原画コピー）")

# Lv2: 鉄の短剣 ── スチール青灰（H=0.60, 低彩度）
recolor(SRC, os.path.join(BASE, "sword_lv2.png"),
        target_h=0.60, sat_mult=0.35, val_mult=1.15)

# Lv3: 炎の短剣 ── 炎オレンジ（H=0.07）
recolor(SRC, os.path.join(BASE, "sword_lv3.png"),
        target_h=0.07, sat_mult=1.15, val_mult=1.10)

# Lv4: 伝説の短剣 ── ゴールド（H=0.13）
recolor(SRC, os.path.join(BASE, "sword_lv4.png"),
        target_h=0.13, sat_mult=1.20, val_mult=1.30)

print("\n完了！sword_lv1.png〜sword_lv4.png を生成しました。")
