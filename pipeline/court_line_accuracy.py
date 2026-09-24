"""
コートラインの逆投影精度チェック
ホモグラフィーでNBAコート座標→ピクセルに変換し動画フレームに重ねる
"""
import cv2, json, numpy as np, re
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from pathlib import Path

BASKET      = (0, 160)
SIDELINE    = 750
HALFCOURT_Y = 1432
FT_Y        = 580
LANE_X      = 245
PT3_RADIUS   = 705   # RANSAC auto-fit from this court (NBA=724, FIBA=675)
PT3_CORNER_X = 665   # corner straight endpoint

VIDEO   = "data/videos/game_EE1swQMsXJc_720p.mp4"
ANN_JSON = "outputs/annotations.json"
OUT_DIR  = Path("outputs/sam3_300s")
OUT_DIR.mkdir(parents=True, exist_ok=True)


def court_lines(pt3_radius=None):
    """(color_bgr, [[cx,cy], ...]) のリスト"""
    r3  = pt3_radius if pt3_radius else PT3_RADIUS
    cx3 = PT3_CORNER_X
    lines = []
    CW = (255,255,255)
    CB = (255,180,80)
    CO = (50,180,255)

    lines += [
        (CW, [[-SIDELINE,0],[SIDELINE,0]]),
        (CW, [[-SIDELINE,0],[-SIDELINE,HALFCOURT_Y]]),
        (CW, [[SIDELINE,0],[SIDELINE,HALFCOURT_Y]]),
        (CW, [[-SIDELINE,HALFCOURT_Y],[SIDELINE,HALFCOURT_Y]]),
        (CB, [[-LANE_X,0],[-LANE_X,FT_Y]]),
        (CB, [[LANE_X,0],[LANE_X,FT_Y]]),
        (CB, [[-LANE_X,FT_Y],[LANE_X,FT_Y]]),
        (CO, [[-cx3,0],[-cx3,420]]),
        (CO, [[cx3,0],[cx3,420]]),
    ]
    bx, by = BASKET
    arc = []
    for deg in range(-115, 116, 2):
        rad = np.radians(deg)
        cx = bx + r3 * np.sin(rad)
        cy = by + r3 * np.cos(rad)
        if abs(cx) <= cx3:
            arc.append([cx, cy])
    if arc:
        lines.append((CO, arc))
    return lines


def build_H_inv(pts_list):
    src, dst = [], []
    for p in pts_list:
        if p['img'] is None:
            continue
        src.append(p['img'])
        dst.append(p['court'])
    if len(src) < 4:
        return None
    H, _ = cv2.findHomography(np.array(src, dtype=np.float32),
                               np.array(dst, dtype=np.float32), cv2.RANSAC)
    if H is None:
        return None
    return np.linalg.inv(H)


def project(H_inv, cx, cy):
    pt = np.array([[[float(cx), float(cy)]]], dtype=np.float64)
    out = cv2.perspectiveTransform(pt, H_inv)
    px, py = float(out[0,0,0]), float(out[0,0,1])
    if not (-100 < px < 1400 and -100 < py < 900):
        return None
    return (int(px), int(py))


def draw_overlay(frame, H_inv, pts_list, pt3_radius=None):
    out = frame.copy()
    r3 = pt3_radius if pt3_radius else PT3_RADIUS
    for color, pts in court_lines(pt3_radius=r3):
        pxpts = [project(H_inv, p[0], p[1]) for p in pts]
        pxpts = [p for p in pxpts if p]
        for i in range(len(pxpts)-1):
            cv2.line(out, pxpts[i], pxpts[i+1], color, 2, cv2.LINE_AA)

    KP_COLORS = {
        'ring': (0, 255, 0),
        'ft_near_lane': (80,180,255), 'ft_far_lane': (80,180,255),
        'ft_near_side': (80,180,255), 'ft_far_side': (80,180,255),
    }
    for p in pts_list:
        if p['img'] is None:
            continue
        px, py = int(p['img'][0]), int(p['img'][1])
        c = KP_COLORS.get(p['id'], (0, 255, 255))
        cv2.circle(out, (px, py), 9, (0,0,0), -1)
        cv2.circle(out, (px, py), 7, c, -1)
        cv2.circle(out, (px, py), 7, (255,255,255), 1)
        short = (p['id']
                 .replace('end_near_side','E-NS').replace('end_far_side','E-FS')
                 .replace('end_near_lane','E-NL').replace('end_far_lane','E-FL')
                 .replace('ft_near_side','FT-NS').replace('ft_far_side','FT-FS')
                 .replace('ft_near_lane','FT-NL').replace('ft_far_lane','FT-FL')
                 .replace('center_near','C-N').replace('center_far','C-F')
                 .replace('ring','RING'))
        cv2.putText(out, short, (px+9, py-4), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (0,0,0), 3)
        cv2.putText(out, short, (px+9, py-4), cv2.FONT_HERSHEY_SIMPLEX, 0.38, c, 1)
    return out


def reproj_error(H_inv, pts_list):
    errs = []
    for p in pts_list:
        if p['img'] is None:
            continue
        pp = project(H_inv, p['court'][0], p['court'][1])
        if pp:
            errs.append(np.hypot(pp[0]-p['img'][0], pp[1]-p['img'][1]))
    return errs


def key_to_frame(key, fps):
    m = re.search(r'(\d+)s', key)
    return int(int(m.group(1)) * fps) if m else 0


def main():
    from auto_fit_3pt import collect_arc_points, fit_radius_ransac, white_mask

    with open(ANN_JSON) as f:
        ann_data = json.load(f)

    cap = cv2.VideoCapture(VIDEO)
    fps = cap.get(cv2.CAP_PROP_FPS)

    ann_keys = [k for k in ann_data.keys() if isinstance(ann_data[k], list)]
    # キーポイントが多い順に並べ、最大6フレーム
    ann_keys_sorted = sorted(
        [k for k in ann_keys if sum(1 for p in ann_data[k] if p['img']) >= 6],
        key=lambda k: sum(1 for p in ann_data[k] if p['img']),
        reverse=True
    )
    step = max(1, len(ann_keys_sorted) // 6)
    picks = ann_keys_sorted[::step][:6]

    fig, axes = plt.subplots(2, 3, figsize=(22, 12), facecolor='#0d1117')
    fig.suptitle(
        'Court Line Accuracy — RANSAC Auto-fit 3PT Radius per Frame\n'
        'White=Boundary  Blue=Paint/FT  Orange=3PT(auto-fit)  Dots=Keypoints',
        color='white', fontsize=13)

    fitted_radii = []

    for idx, key in enumerate(picks):
        r, c = divmod(idx, 3)
        ax = axes[r][c]
        fi = key_to_frame(key, fps)
        cap.set(cv2.CAP_PROP_POS_FRAMES, fi)
        ret, frame = cap.read()
        if not ret:
            ax.axis('off'); continue

        pts_list = ann_data[key]
        H_inv = build_H_inv(pts_list)
        if H_inv is None:
            ax.axis('off'); continue

        # RANSAC で3PT半径をフィット
        hits = collect_arc_points(frame, H_inv, init_radius=PT3_RADIUS)
        fitted_r, inliers = fit_radius_ransac(hits, H_inv)
        use_r = fitted_r if fitted_r and len(inliers) >= 8 else PT3_RADIUS
        if fitted_r and len(inliers) >= 8:
            fitted_radii.append(fitted_r)

        vis = draw_overlay(frame, H_inv, pts_list, pt3_radius=use_r)
        # inlier点を描画
        for i in inliers:
            px, py = hits[i][0], hits[i][1]
            cv2.circle(vis, (px, py), 5, (0,255,100), -1)

        errs = reproj_error(H_inv, pts_list)
        mean_e = np.mean(errs) if errs else 0

        ax.imshow(cv2.cvtColor(vis, cv2.COLOR_BGR2RGB))
        ts = fi / fps
        mm, ss = int(ts//60), int(ts%60)
        r_label = f'{use_r:.0f}cm' if use_r != PT3_RADIUS else f'{PT3_RADIUS}cm(default)'
        ax.set_title(
            f't={mm}:{ss:02d}  3PT r={r_label}  hits={len(inliers)}/{len(hits)}\n'
            f'Reproj err={mean_e:.1f}px',
            color='white', fontsize=9, pad=5)
        ax.axis('off')

    cap.release()

    if fitted_radii:
        mean_r = np.mean(fitted_radii)
        print(f'RANSAC fitted radii: {[f"{r:.0f}" for r in fitted_radii]}')
        print(f'Mean fitted radius: {mean_r:.1f}cm')

    legend = [
        Line2D([0],[0], color='white',        lw=2, label='Court boundary / Sideline'),
        Line2D([0],[0], color='#50B4FF',      lw=2, label='Paint / Free-throw line'),
        Line2D([0],[0], color='#32B4FF',      lw=2, label='3-point arc + corner'),
        Line2D([0],[0], marker='o', color='#00FFFF', lw=0, markersize=8, label='Annotation corners'),
        Line2D([0],[0], marker='o', color='#00FF00', lw=0, markersize=8, label='Annotation ring'),
    ]
    fig.legend(handles=legend, loc='lower center', ncol=5,
               facecolor='#1a1a2e', labelcolor='white', fontsize=10,
               bbox_to_anchor=(0.5, 0.01), framealpha=0.9)

    plt.tight_layout(rect=[0, 0.06, 1, 0.95])
    out = OUT_DIR / 'court_line_accuracy.png'
    fig.savefig(out, dpi=120, bbox_inches='tight', facecolor='#0d1117')
    plt.close(fig)
    print(f'Saved: {out}')


if __name__ == '__main__':
    main()
