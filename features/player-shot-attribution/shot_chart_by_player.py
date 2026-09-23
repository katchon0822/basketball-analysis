"""shots_attributed.json から FIBAハーフコートの選手別シュートチャートを生成。"""
import json
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from matplotlib.patches import Arc, Circle, Rectangle

OUT_DIR = Path(__file__).resolve().parent / "outputs"

TEAM_COLOR = {"white": "#E8E4DA", "navy": "#1F3A6E", "?": "#999999"}
TEAM_EDGE = {"white": "#8A8577", "navy": "#12234a", "?": "#666666"}

JP_FONT = None
for f in ["Hiragino Sans", "Hiragino Kaku Gothic ProN", "Noto Sans CJK JP"]:
    if any(f in x.name for x in fm.fontManager.ttflist):
        JP_FONT = f
        break
if JP_FONT:
    plt.rcParams["font.family"] = JP_FONT


def draw_half_court(ax):
    """FIBAハーフコート (cm)。x: -750..750, y: 0(エンドライン)..1400。"""
    line = dict(color="#3d3a35", lw=1.6, fill=False)
    ax.add_patch(Rectangle((-750, 0), 1500, 1400, **line))
    ax.add_patch(Rectangle((-245, 0), 490, 580, **line))          # レーン
    ax.add_patch(Circle((0, 580), 180, **line))                    # FTサークル
    ax.add_patch(Circle((0, 157.5), 22.5, color="#c9542e", fill=False, lw=1.6))  # リング
    ax.plot([-90, 90], [120, 120], color="#3d3a35", lw=1.6)        # ボード
    # 3PT: コーナー直線 x=±660 (y=0..297) + 半径675のアーク
    ax.plot([-660, -660], [0, 297], color="#3d3a35", lw=1.6)
    ax.plot([660, 660], [0, 297], color="#3d3a35", lw=1.6)
    ax.add_patch(Arc((0, 157.5), 1350, 1350, theta1=12, theta2=168, **{
        "color": "#3d3a35", "lw": 1.6}))
    ax.add_patch(Arc((0, 1400), 360, 360, theta1=180, theta2=360, **line.copy()))
    ax.set_xlim(-800, 800)
    ax.set_ylim(-40, 1480)
    ax.set_aspect("equal")
    ax.axis("off")


def main():
    data = json.load(open(OUT_DIR / "shots_attributed.json"))
    shots = [s for s in data["shots"] if s.get("court_cm")]

    fig, ax = plt.subplots(figsize=(7.5, 7.5), dpi=150)
    fig.patch.set_facecolor("#faf8f4")
    ax.set_facecolor("#faf8f4")
    draw_half_court(ax)

    for s in shots:
        cx, cy = s["court_cm"]
        team = s.get("team") or "?"
        ax.scatter(cx, cy, s=420, marker="o",
                   c=TEAM_COLOR[team], edgecolors=TEAM_EDGE[team],
                   linewidths=2, zorder=5)
        ax.annotate(f"ID{s['shooter_id']}", (cx, cy), ha="center", va="center",
                    fontsize=8, fontweight="bold", zorder=6,
                    color="#1c1a17" if team == "white" else "white")
        ax.annotate(f"{s['ts']}s", (cx, cy - 85), ha="center", va="top",
                    fontsize=7.5, color="#6b675f", zorder=6)

    n_w = sum(1 for s in shots if s.get("team") == "white")
    n_n = sum(1 for s in shots if s.get("team") == "navy")
    ax.set_title("選手別シュートチャート — McByte++ ID × 自動チーム判定\n"
                 f"白 {n_w}本 / 紺 {n_n}本 (26–36秒区間)",
                 fontsize=11, color="#1c1a17", pad=12)
    fig.tight_layout()
    out = OUT_DIR / "shot_chart_by_player.png"
    fig.savefig(out, facecolor=fig.get_facecolor())
    print("[OK] ->", out)


if __name__ == "__main__":
    main()
