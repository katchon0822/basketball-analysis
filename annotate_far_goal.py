#!/usr/bin/env python3
"""
annotate_far_goal.py  —  Far goal (far_ring) pixel annotator

Left click  : mark far goal center
A / <-      : prev 30 frames
D / ->      : next 30 frames
Scroll      : zoom in / out
T           : toggle court overlay
Backspace   : undo / clear mark
S / Enter   : save & quit
Q / Esc     : cancel
"""

import cv2, json, numpy as np, argparse

DISPLAY_W = 1280
PANEL_W   = 220

# FIBA court constants (cm)
SIDELINE = 750; HALF_Y = 1432; FULL_Y = HALF_Y*2; BASKET_Y = 160
FT_Y = 580; LANE_X = 245; PT3_CX = 665; PT3_CY = 420; PT3_R = 705


def make_proj(H):
    def proj(cx, cy):
        pt  = np.array([[[float(cx), float(cy)]]], dtype=np.float64)
        out = cv2.perspectiveTransform(pt, H)
        return (int(out[0,0,0]), int(out[0,0,1]))
    return proj


def draw_court_overlay(frame, proj, W, H_px):
    def seg(x1,y1,x2,y2,col,t=1):
        p1,p2 = proj(x1,y1), proj(x2,y2)
        if all(0<=p[0]<W and 0<=p[1]<H_px for p in (p1,p2)):
            cv2.line(frame,p1,p2,col,t,cv2.LINE_AA)
    WH=(170,170,170); BL=(100,190,255); OR=(40,210,255)
    seg(-SIDELINE,0,SIDELINE,0,WH,2)
    seg(-SIDELINE,0,-SIDELINE,HALF_Y,WH,2)
    seg(SIDELINE,0,SIDELINE,HALF_Y,WH,2)
    seg(-SIDELINE,HALF_Y,SIDELINE,HALF_Y,WH,1)
    seg(-LANE_X,0,-LANE_X,FT_Y,BL); seg(LANE_X,0,LANE_X,FT_Y,BL)
    seg(-LANE_X,FT_Y,LANE_X,FT_Y,BL)
    seg(-PT3_CX,0,-PT3_CX,PT3_CY,OR); seg(PT3_CX,0,PT3_CX,PT3_CY,OR)
    arc=[]
    for d in range(-115,116,3):
        r=np.radians(d); cx_=PT3_R*np.sin(r); cy_=BASKET_Y+PT3_R*np.cos(r)
        if abs(cx_)<=PT3_CX:
            p=proj(cx_,cy_)
            if 0<=p[0]<W and 0<=p[1]<H_px: arc.append(p)
    for i in range(len(arc)-1): cv2.line(frame,arc[i],arc[i+1],OR,1,cv2.LINE_AA)


# ── minimap (full court, landscape) ─────────────────────────────────────────
# Horizontal: court y (0=near baseline left, FULL_Y=far baseline right)
# Vertical:   court x (SIDELINE=top, -SIDELINE=bottom)
MAP_W, MAP_H, MAP_PAD = 200, 96, 6
CENTER_R = 180

def build_minimap_base():
    img    = np.zeros((MAP_H, MAP_W, 3), dtype=np.uint8)
    scl_x  = (MAP_W - MAP_PAD*2) / FULL_Y          # court y → pixel x
    scl_y  = (MAP_H - MAP_PAD*2) / (SIDELINE*2)    # court x → pixel y

    def c2p(cx, cy):
        """court (cx, cy) → minimap pixel  (cy=0 left, cx=SIDELINE top)"""
        return (MAP_PAD + int(cy * scl_x),
                MAP_PAD + int((SIDELINE - cx) * scl_y))

    G=(60,60,60); WL=(100,100,100)
    def ml(x1,y1,x2,y2,col=G,t=1):
        cv2.line(img,c2p(x1,y1),c2p(x2,y2),col,t,cv2.LINE_AA)

    # outer boundary
    ml(-SIDELINE,0,     SIDELINE,0,     WL,2)   # near baseline (left edge)
    ml(-SIDELINE,FULL_Y,SIDELINE,FULL_Y,WL,2)   # far baseline (right edge)
    ml(-SIDELINE,0,-SIDELINE,FULL_Y,    WL,2)   # bottom sideline
    ml( SIDELINE,0, SIDELINE,FULL_Y,    WL,2)   # top sideline
    ml(-SIDELINE,HALF_Y,SIDELINE,HALF_Y,WL,1)   # center line
    cv2.circle(img,c2p(0,HALF_Y),max(1,int(CENTER_R*scl_x)),G,1)
    rim_r = max(1,int(23.75*scl_x))

    # near half (left side)
    ml(-LANE_X,0,-LANE_X,FT_Y); ml(LANE_X,0,LANE_X,FT_Y); ml(-LANE_X,FT_Y,LANE_X,FT_Y)
    ml(-PT3_CX,0,-PT3_CX,PT3_CY); ml(PT3_CX,0,PT3_CX,PT3_CY)
    arc=[]
    for d in range(-115,116,5):
        r=np.radians(d); cx_=PT3_R*np.sin(r); cy_=BASKET_Y+PT3_R*np.cos(r)
        if abs(cx_)<=PT3_CX: arc.append(c2p(cx_,cy_))
    for i in range(len(arc)-1): cv2.line(img,arc[i],arc[i+1],G,1,cv2.LINE_AA)
    cv2.circle(img,c2p(0,BASKET_Y),rim_r,(60,80,200),1)

    # far half (right side, mirror)
    FAR_B=FULL_Y-BASKET_Y; FAR_F=FULL_Y-FT_Y; FAR_P=FULL_Y-PT3_CY
    ml(-LANE_X,FULL_Y,-LANE_X,FAR_F); ml(LANE_X,FULL_Y,LANE_X,FAR_F); ml(-LANE_X,FAR_F,LANE_X,FAR_F)
    ml(-PT3_CX,FULL_Y,-PT3_CX,FAR_P); ml(PT3_CX,FULL_Y,PT3_CX,FAR_P)
    arc2=[]
    for d in range(-115,116,5):
        r=np.radians(d); cx_=PT3_R*np.sin(r); cy_=FAR_B-PT3_R*np.cos(r)
        if abs(cx_)<=PT3_CX: arc2.append(c2p(cx_,cy_))
    for i in range(len(arc2)-1): cv2.line(img,arc2[i],arc2[i+1],G,1,cv2.LINE_AA)
    cv2.circle(img,c2p(0,FAR_B),rim_r,(60,80,200),1)

    # labels
    cv2.putText(img,"NEAR",(MAP_PAD,   MAP_H-3),cv2.FONT_HERSHEY_SIMPLEX,0.22,(80,80,80),1)
    cv2.putText(img,"FAR", (MAP_W-28,  MAP_H-3),cv2.FONT_HERSHEY_SIMPLEX,0.22,(80,80,80),1)
    return img, c2p

_MAP_BASE, _C2P = build_minimap_base()


def draw_minimap(disp, _near, _far):
    """Draw horizontal full-court minimap in bottom-left corner."""
    H_d = disp.shape[0]
    mx = 10;  my = H_d - MAP_H - 26   # above status bar

    mm = _MAP_BASE.copy()
    scl_x = (MAP_W - MAP_PAD*2) / FULL_Y
    rim_r = max(1, int(23.75*scl_x))
    cv2.circle(mm, _C2P(0, BASKET_Y),       rim_r+2, (60,  60, 255), 2)   # near
    cv2.circle(mm, _C2P(0, FULL_Y-BASKET_Y),rim_r+2, (255,130,   0), 2)   # far

    overlay = disp.copy()
    cv2.rectangle(overlay,(mx-2,my-16),(mx+MAP_W+2,my+MAP_H+2),(22,22,22),-1)
    cv2.addWeighted(overlay,0.72,disp,0.28,0,disp)
    disp[my:my+MAP_H, mx:mx+MAP_W] = mm
    cv2.rectangle(disp,(mx-1,my-1),(mx+MAP_W+1,my+MAP_H+1),(80,80,80),1)
    cv2.putText(disp,"Court map",(mx,my-4),cv2.FONT_HERSHEY_SIMPLEX,0.30,(120,120,120),1)


def draw_panel(disp, lines, x, y0, row_h=20):
    ph = row_h * len(lines) + 16
    overlay = disp.copy()
    cv2.rectangle(overlay, (x-8, y0-14), (x+PANEL_W, y0+ph), (18,18,18), -1)
    cv2.addWeighted(overlay, 0.75, disp, 0.25, 0, disp)
    cv2.rectangle(disp, (x-8, y0-14), (x+PANEL_W, y0+ph), (70,70,70), 1)
    for i, (txt, col) in enumerate(lines):
        cv2.putText(disp, txt, (x, y0+i*row_h), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (0,0,0), 2)
        cv2.putText(disp, txt, (x, y0+i*row_h), cv2.FONT_HERSHEY_SIMPLEX, 0.38, col, 1)


def draw_crosshair(disp, dx, dy):
    h, w = disp.shape[:2]
    cv2.line(disp,(0,dy),(w,dy),(0,180,180),1,cv2.LINE_AA)
    cv2.line(disp,(dx,0),(dx,h),(0,180,180),1,cv2.LINE_AA)
    cv2.circle(disp,(dx,dy),6,(0,220,220),1,cv2.LINE_AA)


def draw_marker(disp, p, label, col):
    cv2.circle(disp,p,24,(0,0,0),4)
    cv2.circle(disp,p,24,col,2)
    cv2.circle(disp,p,4,col,-1)
    cv2.line(disp,(p[0]-18,p[1]),(p[0]+18,p[1]),col,1,cv2.LINE_AA)
    cv2.line(disp,(p[0],p[1]-18),(p[0],p[1]+18),col,1,cv2.LINE_AA)
    cv2.putText(disp,label,(p[0]+8,p[1]-10),cv2.FONT_HERSHEY_SIMPLEX,0.42,(0,0,0),3)
    cv2.putText(disp,label,(p[0]+8,p[1]-10),cv2.FONT_HERSHEY_SIMPLEX,0.42,col,1)


def draw_statusbar(disp, txt):
    h, w = disp.shape[:2]
    overlay = disp.copy()
    cv2.rectangle(overlay,(0,h-22),(w,h),(12,12,12),-1)
    cv2.addWeighted(overlay,0.85,disp,0.15,0,disp)
    cv2.putText(disp,txt,(8,h-6),cv2.FONT_HERSHEY_SIMPLEX,0.34,(180,180,180),1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", default="outputs/venue_profiles/game2-1.json")
    args = ap.parse_args()

    with open(args.profile) as f:
        prof = json.load(f)

    video = f"data/videos/{prof['video']}"
    cap   = cv2.VideoCapture(video)
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    H_mat       = np.array(prof["H_court_to_image"])
    proj        = make_proj(H_mat)
    existing    = prof.get("far_ring_image_xy")
    click_pt    = list(existing) if existing else None
    prev_pt     = list(existing) if existing else None  # for undo
    mouse_pos   = [0, 0]
    show_overlay= True

    fi   = prof.get("frame_idx", 0)
    zoom = 1.0
    zoom_center = None

    def load_frame(idx):
        cap.set(cv2.CAP_PROP_POS_FRAMES, max(0, min(idx, total-1)))
        ret, frame = cap.read()
        return frame if ret else None

    frame_orig = load_frame(fi)
    H_px, W    = frame_orig.shape[:2]
    scale      = DISPLAY_W / W
    disp_h     = int(H_px * scale)

    def zc():
        return zoom_center if zoom_center else (W/2, H_px/2)

    def to_disp(ox, oy):
        zx, zy = zc()
        return (int((ox-zx)*zoom*scale + DISPLAY_W/2),
                int((oy-zy)*zoom*scale + disp_h/2))

    def to_orig(dx, dy):
        zx, zy = zc()
        return ((dx-DISPLAY_W/2)/(zoom*scale)+zx,
                (dy-disp_h/2)  /(zoom*scale)+zy)

    def render():
        if frame_orig is None:
            return np.zeros((disp_h, DISPLAY_W, 3), dtype=np.uint8)

        zx, zy = zc()
        nw=int(W/zoom); nh=int(H_px/zoom)
        x1=max(0,int(zx-nw/2)); y1=max(0,int(zy-nh/2))
        x2=min(W,x1+nw);        y2=min(H_px,y1+nh)
        disp = cv2.resize(frame_orig[y1:y2,x1:x2], (DISPLAY_W,disp_h))

        # court overlay
        if show_overlay:
            def scaled_proj(cx, cy):
                p = proj(cx, cy)
                return to_disp(p[0], p[1])
            draw_court_overlay(disp, scaled_proj, DISPLAY_W, disp_h)

        # near goal marker (reference)
        for pair in prof.get("pairs",[]):
            if pair["landmark_id"] == "ring":
                np_ = to_disp(*pair["image_xy"])
                draw_marker(disp, np_, "NEAR GOAL", (60,60,255))
                break

        # far goal marker (annotation target)
        if click_pt:
            draw_marker(disp, to_disp(*click_pt),
                        f"FAR ({click_pt[0]:.0f},{click_pt[1]:.0f})",
                        (255,130,0))

        # crosshair
        dx, dy = mouse_pos
        draw_crosshair(disp, dx, dy)

        # minimap
        draw_minimap(disp, None, None)

        # help panel
        ox, oy = to_orig(dx, dy)
        overlay_lbl = "ON " if show_overlay else "OFF"
        lines = [
            ("--- CONTROLS ---",              (255,220,60)),
            ("Left click : mark FAR GOAL",    (200,200,200)),
            ("A / <- : -30 frames",           (200,200,200)),
            ("D / -> : +30 frames",           (200,200,200)),
            ("Scroll : zoom in/out",          (200,200,200)),
            (f"T : overlay [{overlay_lbl}]",  (100,220,255)),
            ("Backspace : undo",              (200,200,200)),
            ("S / Enter : SAVE",              (100,255,100)),
            ("Q / Esc   : cancel",            (160,160,160)),
            ("",                              (0,0,0)),
            (f"frame {fi}/{total-1}",         (160,200,255)),
            (f"zoom  {zoom:.1f}x",            (160,200,255)),
            (f"({ox:.0f}, {oy:.0f})",         (130,130,130)),
        ]
        draw_panel(disp, lines, DISPLAY_W-PANEL_W-6, 12)

        state = (f"FAR GOAL: ({click_pt[0]:.0f}, {click_pt[1]:.0f})"
                 if click_pt else "FAR GOAL: not set  —  click to mark")
        draw_statusbar(disp, f"  {state}    |  {args.profile}")
        return disp

    WIN = "annotate_far_goal  [S=save  T=overlay  Q=cancel]"
    cv2.namedWindow(WIN, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(WIN, DISPLAY_W, disp_h)

    def on_mouse(event, dx, dy, flags, _):
        nonlocal click_pt, zoom, zoom_center, prev_pt
        mouse_pos[0]=dx; mouse_pos[1]=dy
        ox, oy = to_orig(dx, dy)
        if event == cv2.EVENT_LBUTTONDOWN:
            prev_pt  = list(click_pt) if click_pt else None
            click_pt = [round(ox,1), round(oy,1)]
        elif event == cv2.EVENT_MOUSEWHEEL:
            old=zoom
            zoom=max(1.0,min(8.0,zoom*(1.15 if flags>0 else 1/1.15)))
            if zoom!=old: zoom_center=(ox,oy)

    cv2.setMouseCallback(WIN, on_mouse)

    while True:
        cv2.imshow(WIN, render())
        key = cv2.waitKey(20) & 0xFF

        if key in (ord('q'), 27):
            print("Cancelled.")
            break
        elif key in (ord('s'), 13):
            if click_pt is None:
                print("Nothing marked yet.")
                continue
            prof["far_ring_image_xy"] = [int(round(click_pt[0])), int(round(click_pt[1]))]
            with open(args.profile, "w") as f:
                json.dump(prof, f, ensure_ascii=False, indent=2)
            print(f"Saved: far_ring_image_xy = {prof['far_ring_image_xy']}")
            break
        elif key == ord('t'):
            show_overlay = not show_overlay
        elif key in (8, 127):   # Backspace
            click_pt = list(prev_pt) if prev_pt else None
        elif key in (ord('d'), 83):
            fi = min(fi+30, total-1)
            frame_orig = load_frame(fi)
        elif key in (ord('a'), 81):
            fi = max(fi-30, 0)
            frame_orig = load_frame(fi)

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
