#!/usr/bin/env python3
"""
game_setup_wizard.py — ゲームセットアップウィザード

Flow:
  1. YouTube URL を入力 → yt-dlp でダウンロード
  2. サンプルフレームを表示 (12枚)
  3. 既存プロファイルと自動比較 (ORB + 床色ヒストグラム)
  4. 同じコート → プロファイルを再利用  /  新コート → ランドマーク10点アノテーション
  5. フルコートH行列を計算 → プロファイル保存
  6. render_full_detection.py で選手位置プロット可能に

Usage:
  python game_setup_wizard.py
  python game_setup_wizard.py --url "https://www.youtube.com/watch?v=XXXXX"
"""

import cv2, json, numpy as np, argparse, webbrowser, threading, subprocess, os, re, time
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from pathlib import Path
import base64

PORT        = 8771
PROFILE_DIR = Path("outputs/venue_profiles")
VIDEO_DIR   = Path("data/videos")
PROFILE_DIR.mkdir(parents=True, exist_ok=True)
VIDEO_DIR.mkdir(parents=True, exist_ok=True)

# FIBA constants (cm)
SIDELINE = 750; HALF_Y = 1432; FULL_Y = 2864; BASKET_Y = 160
FT_Y = 580; LANE_X = 245; PT3_CX = 665; PT3_CY = 420; PT3_R = 705; CENTER_R = 180

# Landmarks for full-court H matrix calibration (both halves)
# Required 10 for H, optional 3 for visual overlays
CALIB_LM = [
    {"id":"nc_l",  "label":"Near endline × Left sideline",  "court":[-750,    0], "req":True,  "group":"near"},
    {"id":"nc_r",  "label":"Near endline × Right sideline", "court":[ 750,    0], "req":True,  "group":"near"},
    {"id":"ft_nl", "label":"Near FT line × Left lane",      "court":[-LANE_X, FT_Y], "req":True,  "group":"near"},
    {"id":"ft_nr", "label":"Near FT line × Right lane",     "court":[ LANE_X, FT_Y], "req":True,  "group":"near"},
    {"id":"ctr_l", "label":"Center line × Left sideline",   "court":[-750,    HALF_Y], "req":True,  "group":"mid"},
    {"id":"ctr_r", "label":"Center line × Right sideline",  "court":[ 750,    HALF_Y], "req":True,  "group":"mid"},
    {"id":"ft_fl", "label":"Far FT line × Left lane",       "court":[-LANE_X, FULL_Y-FT_Y], "req":True,  "group":"far"},
    {"id":"ft_fr", "label":"Far FT line × Right lane",      "court":[ LANE_X, FULL_Y-FT_Y], "req":True,  "group":"far"},
    {"id":"fc_l",  "label":"Far endline × Left sideline",   "court":[-750,    FULL_Y], "req":True,  "group":"far"},
    {"id":"fc_r",  "label":"Far endline × Right sideline",  "court":[ 750,    FULL_Y], "req":True,  "group":"far"},
    {"id":"near_ring",     "label":"Near basket (ring center)", "court":[0, BASKET_Y],         "req":False, "group":"opt"},
    {"id":"far_ring",      "label":"Far basket (ring center)",  "court":[0, FULL_Y-BASKET_Y],  "req":False, "group":"opt"},
    {"id":"center_circle", "label":"Center circle center",      "court":[0, HALF_Y],           "req":False, "group":"opt"},
]
REQ_IDS  = [lm["id"] for lm in CALIB_LM if lm["req"]]
OPT_IDS  = [lm["id"] for lm in CALIB_LM if not lm["req"]]

# ── Global state ─────────────────────────────────────────────────────────────
srv = {
    "phase":    "idle",   # idle|downloading|previewing|auto_calibrating|confirming|annotating|done|error
    "url":      "",
    "video_path": None,
    "video_name": "",
    "fps":      30.0,
    "total":    0,
    "samples":  [],          # list of frame indices
    "dl_log":   [],
    "profiles": [],
    "scores":   {},          # {profile_name: float}
    "best":     None,        # best matching profile name
    "action":   None,        # "reuse" | "new"
    "reuse_name": None,
    "ann":      {},          # {lm_id: [ix, iy]}
    "ann_frame": 0,
    "H":        None,
    "inliers":  0,
    "new_name": "",
    "error":    "",
    # KaliCalib auto-calibration
    "kali_log":    [],       # progress messages
    "kali_H":      None,     # estimated H (list) or None
    "kali_inliers": 0,
    "kali_frame":  0,
    "kali_debug":  None,     # JPEG bytes of debug image
}
cap_main = None   # VideoCapture for the new video
cap_prof  = {}    # {profile_name: VideoCapture}
_kali_model = None   # lazy-loaded KaliCalib model


# ── Utilities ─────────────────────────────────────────────────────────────────

def open_cap(path):
    c = cv2.VideoCapture(str(path))
    if not c.isOpened():
        return None
    return c


def get_jpg(cap, fi, w=None):
    cap.set(cv2.CAP_PROP_POS_FRAMES, max(0, fi))
    ret, fr = cap.read()
    if not ret:
        return None
    if w:
        h = int(fr.shape[0] * w / fr.shape[1])
        fr = cv2.resize(fr, (w, h))
    _, buf = cv2.imencode(".jpg", fr, [cv2.IMWRITE_JPEG_QUALITY, 82])
    return bytes(buf)


def frame_to_b64(cap, fi, w=None):
    data = get_jpg(cap, fi, w)
    if data is None:
        return ""
    return base64.b64encode(data).decode()


def get_sample_indices(total, n=12):
    start = max(0, int(total * 0.08))
    end   = min(total - 1, int(total * 0.92))
    if n >= end - start:
        return list(range(start, end + 1))
    step = (end - start) // (n - 1)
    return [start + i * step for i in range(n)]


def compute_similarity(f1_bgr, f2_bgr):
    """ORB feature matching + HSV histogram on floor region → 0..1 score"""
    def resize(f): return cv2.resize(f, (640, 360))
    def floor_mask(f):
        hsv = cv2.cvtColor(f, cv2.COLOR_BGR2HSV)
        m1 = cv2.inRange(hsv, (8,35,80), (50,210,245))
        m2 = cv2.inRange(hsv, (0,20,90), (15,190,255))
        return cv2.bitwise_or(m1, m2)

    a, b = resize(f1_bgr), resize(f2_bgr)
    ma, mb = floor_mask(a), floor_mask(b)

    # Histogram score
    def hist(f, m):
        h = cv2.calcHist([f],[0,1,2],m,[8,8,8],[0,256]*3)
        cv2.normalize(h,h); return h
    hscore = max(0.0, float(cv2.compareHist(hist(a,ma), hist(b,mb), cv2.HISTCMP_CORREL)))

    # ORB score
    orb = cv2.ORB_create(nfeatures=400)
    g1 = cv2.cvtColor(a, cv2.COLOR_BGR2GRAY)
    g2 = cv2.cvtColor(b, cv2.COLOR_BGR2GRAY)
    kp1, d1 = orb.detectAndCompute(g1, ma)
    kp2, d2 = orb.detectAndCompute(g2, mb)
    oscore = 0.0
    if d1 is not None and d2 is not None and len(d1)>10 and len(d2)>10:
        bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
        good = [m for m in bf.match(d1,d2) if m.distance < 55]
        oscore = min(1.0, len(good) / max(len(kp1), len(kp2), 1) * 8)

    return round(0.55 * hscore + 0.45 * oscore, 3)


def load_profiles():
    profs = []
    for p in sorted(PROFILE_DIR.glob("*.json")):
        try:
            with open(p) as f: data = json.load(f)
            profs.append({
                "name":      p.stem,
                "path":      str(p),
                "video":     data.get("video",""),
                "frame_idx": data.get("frame_idx", 0),
                "fullcourt": data.get("fullcourt", False),
                "has_H":     "H_court_to_image" in data,
                "data":      data,
            })
        except Exception:
            pass
    return profs


def compute_H(ann):
    """Compute H_court_to_image from annotation dict"""
    img_pts, court_pts = [], []
    for lm in CALIB_LM:
        xy = ann.get(lm["id"])
        if xy:
            img_pts.append(xy)
            court_pts.append(lm["court"])
    if len(img_pts) < 4:
        return None, 0
    img_arr   = np.float32(img_pts)
    court_arr = np.float32(court_pts)
    H_i2c, mask = cv2.findHomography(img_arr, court_arr, cv2.RANSAC, 25.0)
    if H_i2c is None:
        return None, 0
    H_c2i = np.linalg.inv(H_i2c)
    inliers = int(mask.sum()) if mask is not None else len(img_pts)
    return H_c2i.tolist(), inliers


def do_auto_calibrate():
    """
    KaliCalib で自動コートキャリブレーションを実行。
    結果を srv["kali_*"] に格納し、phase を "confirming" に遷移。
    """
    global _kali_model
    srv["phase"]    = "auto_calibrating"
    srv["kali_log"] = ["Loading KaliCalib model (ResNet18, ~14M params)…"]

    try:
        import sys
        _root = Path(__file__).resolve().parent.parent
        sys.path.insert(0, str(_root / "kalicalib"))
        sys.path.insert(0, str(_root / "calibration"))
        from auto_calibrate import load_kali_model, calibrate_frame, _draw_projected_court
    except Exception as e:
        srv["kali_log"].append(f"Import error: {e}")
        srv["phase"] = "annotating"   # fallback to manual
        return

    try:
        if _kali_model is None:
            _kali_model = load_kali_model()
        srv["kali_log"].append("Model loaded. Running inference on sample frames…")
    except Exception as e:
        srv["kali_log"].append(f"Model load error: {e}")
        srv["phase"] = "annotating"
        return

    # サンプルフレームのうち n=5 で推定 → inliers 最大を採用
    n_try = min(5, len(srv["samples"]))
    idxs  = [srv["samples"][int(i * (len(srv["samples"]) - 1) / max(n_try - 1, 1))]
             for i in range(n_try)]
    best_H, best_inliers, best_fi, best_debug = None, -1, 0, None

    for fi in idxs:
        srv["kali_log"].append(f"Frame {fi} …")
        data = get_jpg(cap_main, fi)
        if data is None:
            continue
        frame_bgr = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
        try:
            H, inliers, debug = calibrate_frame(frame_bgr, _kali_model)
        except Exception as e:
            srv["kali_log"].append(f"  → error: {e}")
            continue
        srv["kali_log"].append(f"  → inliers={inliers}")
        if inliers > best_inliers:
            best_H, best_inliers, best_fi, best_debug = H, inliers, fi, debug

    srv["kali_inliers"] = best_inliers
    srv["kali_frame"]   = best_fi
    srv["kali_H"]       = best_H.tolist() if best_H is not None else None

    # デバッグ画像 (RGB→BGR→JPEG)
    if best_debug is not None:
        dbg_bgr = cv2.cvtColor(best_debug, cv2.COLOR_RGB2BGR)
        _, buf   = cv2.imencode(".jpg", dbg_bgr, [cv2.IMWRITE_JPEG_QUALITY, 88])
        srv["kali_debug"] = bytes(buf)
        srv["kali_log"].append(f"Done. Best frame={best_fi}, inliers={best_inliers}")
    else:
        srv["kali_log"].append("No valid calibration found → switching to manual annotation")

    srv["phase"] = "confirming"


def do_download(url):
    srv["phase"] = "downloading"
    srv["dl_log"] = [f"Downloading: {url}"]
    VIDEO_DIR.mkdir(parents=True, exist_ok=True)

    tmpl = str(VIDEO_DIR / "%(id)s_%(height)sp.%(ext)s")
    cmd  = [
        "yt-dlp", "-f",
        "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720][ext=mp4]/best[height<=720]",
        "--merge-output-format", "mp4",
        "-o", tmpl, url
    ]
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        path_found = None
        for line in proc.stdout:
            line = line.rstrip()
            srv["dl_log"].append(line)
            m = re.search(r'\[download\] Destination: (.+\.mp4)', line)
            if m: path_found = m.group(1)
            m2 = re.search(r'Merging formats into "(.+\.mp4)"', line)
            if m2: path_found = m2.group(1)
        proc.wait()
        if proc.returncode != 0 or not path_found:
            # fallback: find newest mp4 in VIDEO_DIR
            mp4s = sorted(VIDEO_DIR.glob("*.mp4"), key=lambda x: x.stat().st_mtime)
            if mp4s: path_found = str(mp4s[-1])
        if not path_found or not Path(path_found).exists():
            srv["phase"] = "error"; srv["error"] = "Download failed or file not found"
            return
        srv["video_path"] = path_found
        srv["video_name"] = Path(path_found).name
        srv["dl_log"].append(f"✓ Saved: {path_found}")
    except FileNotFoundError:
        srv["phase"] = "error"; srv["error"] = "yt-dlp not found. Install: pip install yt-dlp"
        return

    # Open video
    global cap_main
    cap_main = open_cap(srv["video_path"])
    if cap_main is None:
        srv["phase"] = "error"; srv["error"] = "Cannot open video"
        return
    srv["fps"]   = cap_main.get(cv2.CAP_PROP_FPS) or 30.0
    srv["total"] = int(cap_main.get(cv2.CAP_PROP_FRAME_COUNT))
    srv["samples"] = get_sample_indices(srv["total"])
    srv["ann_frame"] = srv["samples"][len(srv["samples"])//2]

    # Load existing profiles + compute similarity
    srv["profiles"] = load_profiles()
    if srv["profiles"]:
        # Use middle sample frame for comparison
        mid_fi = srv["samples"][len(srv["samples"])//2]
        cap_main.set(cv2.CAP_PROP_POS_FRAMES, mid_fi)
        ret, ref_frame = cap_main.read()
        if ret:
            for prof in srv["profiles"]:
                vid_path = VIDEO_DIR / prof["video"]
                if vid_path.exists():
                    pc = open_cap(vid_path)
                    if pc:
                        pc.set(cv2.CAP_PROP_POS_FRAMES, prof["frame_idx"])
                        r2, pf = pc.read()
                        pc.release()
                        if r2:
                            score = compute_similarity(ref_frame, pf)
                            srv["scores"][prof["name"]] = score
                            continue
                srv["scores"][prof["name"]] = 0.0
            best = max(srv["scores"], key=srv["scores"].get) if srv["scores"] else None
            srv["best"] = best if best and srv["scores"].get(best,0) > 0.55 else None

    # Open profile caps for serving frames
    for prof in srv["profiles"]:
        vid_path = VIDEO_DIR / prof["video"]
        if vid_path.exists():
            cap_prof[prof["name"]] = open_cap(vid_path)

    srv["phase"] = "previewing"


# ── HTML ──────────────────────────────────────────────────────────────────────
HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Game Setup Wizard</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{background:#111;color:#ddd;font-family:system-ui,sans-serif;font-size:13px;min-height:100vh}
h1{font-size:18px;font-weight:700;color:#fff}
h2{font-size:13px;font-weight:600;color:#aaa;text-transform:uppercase;letter-spacing:.8px;margin-bottom:10px}
.page{max-width:1100px;margin:0 auto;padding:20px}
.card{background:#1a1a1a;border:1px solid #252525;border-radius:8px;padding:16px;margin-bottom:14px}
.row{display:flex;gap:12px;align-items:center;margin-bottom:10px}
input[type=text]{flex:1;background:#0e0e0e;border:1px solid #333;border-radius:5px;
  padding:8px 12px;color:#ddd;font-size:13px;outline:none}
input[type=text]:focus{border-color:#29b6f6}
.btn{padding:8px 18px;border-radius:5px;cursor:pointer;font-size:13px;border:1px solid #333;
  background:#1e1e1e;color:#aaa;transition:all .15s}
.btn:hover{background:#262626;color:#ddd}
.btn.primary{background:#0d2a3a;border-color:#29b6f6;color:#7dd4f8}
.btn.primary:hover{background:#1a3f55}
.btn.success{background:#0f3a0f;border-color:#4a9;color:#7d9}
.btn.success:hover{background:#1a5020}
.btn.danger{background:#3a1010;border-color:#944;color:#e88}
.log{background:#0a0a0a;border:1px solid #1a1a1a;border-radius:4px;padding:8px 10px;
  font-family:monospace;font-size:11px;max-height:160px;overflow-y:auto;color:#777}
.log p{line-height:1.6}
.log p.ok{color:#4d9}
.log p.err{color:#e55}

/* Sample frames grid */
.frames-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:6px}
.frame-thumb{position:relative;cursor:pointer;border-radius:4px;overflow:hidden;
  border:2px solid #1e1e1e;transition:border-color .15s}
.frame-thumb:hover{border-color:#444}
.frame-thumb.active{border-color:#29b6f6}
.frame-thumb img{width:100%;display:block}
.frame-thumb .fi{position:absolute;bottom:2px;left:4px;font-size:9px;
  background:rgba(0,0,0,.7);padding:1px 4px;border-radius:2px;color:#aaa}

/* Profile cards */
.prof-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:10px}
.prof-card{background:#151515;border:2px solid #222;border-radius:6px;padding:10px;cursor:pointer;
  transition:all .2s;position:relative}
.prof-card:hover{border-color:#444}
.prof-card.selected{border-color:#29b6f6;background:#0d1e28}
.prof-card.best{border-color:#4a9}
.prof-card img{width:100%;border-radius:3px;display:block;margin-bottom:7px}
.prof-card .name{font-weight:600;color:#ccc;margin-bottom:3px}
.prof-card .score{font-size:11px;margin-bottom:6px}
.score-bar{height:4px;border-radius:2px;background:#1e1e1e;margin-bottom:6px}
.score-fill{height:100%;border-radius:2px;background:#4a9;transition:width .4s}
.badge{display:inline-block;padding:2px 7px;border-radius:10px;font-size:10px;
  background:#0f3a0f;color:#4a9;border:1px solid #2a6a2a}
.badge.best{background:#0a2a1a;color:#5be;border-color:#2a6a5a}

/* Annotation UI */
#ann-wrap{display:flex;gap:12px;min-height:0}
#ann-canvas-wrap{flex:1;position:relative;background:#0a0a0a;border-radius:6px;
  overflow:hidden;cursor:crosshair;min-height:360px}
#ann-cv{position:absolute;top:0;left:0}
#ann-sidebar{width:260px;flex-shrink:0;display:flex;flex-direction:column;gap:8px}

.lm-item{display:flex;align-items:center;gap:8px;padding:5px 8px;border-radius:4px;
  cursor:pointer;transition:background .15s;border:1px solid transparent}
.lm-item:hover{background:#1e1e1e}
.lm-item.active{background:#0d1e28;border-color:#29b6f6}
.lm-item.set{background:#0a1a0a}
.lm-dot{width:9px;height:9px;border-radius:50%;border:1px solid #444;flex-shrink:0}
.lm-dot.set{border:none}
.lm-label{flex:1;font-size:11px;color:#888;line-height:1.3}
.lm-item.active .lm-label{color:#7dd4f8}
.lm-item.set .lm-label{color:#9dc}
.lm-check{font-size:11px;color:#4a9}
.req-badge{font-size:9px;color:#666;background:#1a1a1a;padding:1px 4px;border-radius:2px}

/* Court minimap */
#court-cv{display:block;width:100%;border-radius:3px;background:#0a0a0a}

.progress{font-size:12px;color:#666;text-align:center;padding:8px}
.spin{display:inline-block;animation:spin 1s linear infinite}
@keyframes spin{to{transform:rotate(360deg)}}

.stat-row{display:flex;justify-content:space-between;font-size:11px;margin-bottom:4px}
.stat-row .k{color:#555}.stat-row .v{font-family:monospace;color:#9dc}

#phase-done .big{font-size:20px;color:#4a9;margin-bottom:10px}
#phase-done code{background:#0a0a0a;padding:2px 8px;border-radius:3px;
  font-family:monospace;font-size:13px;color:#7dd4f8;display:block;margin-top:6px}
</style>
</head>
<body>
<div class="page">
  <div class="card" style="margin-bottom:20px">
    <div class="row" style="margin-bottom:0">
      <h1>&#127936; Game Setup Wizard</h1>
      <span id="phase-badge" style="font-size:11px;color:#555;margin-left:auto"></span>
    </div>
  </div>

  <!-- Phase: idle -->
  <div id="phase-idle" class="card">
    <h2>YouTube URL</h2>
    <div class="row">
      <input type="text" id="url-input" placeholder="https://www.youtube.com/watch?v=..." />
      <button class="btn primary" onclick="startDownload()">&#11015; Download</button>
    </div>
    <p style="font-size:11px;color:#444">Supported: YouTube, any yt-dlp-compatible URL. Downloads to data/videos/ at ≤720p.</p>
  </div>

  <!-- Phase: downloading -->
  <div id="phase-downloading" class="card" style="display:none">
    <h2><span class="spin">&#9696;</span> Downloading…</h2>
    <div id="dl-log" class="log"></div>
  </div>

  <!-- Phase: previewing -->
  <div id="phase-previewing" style="display:none">
    <div class="card">
      <div class="row" style="margin-bottom:12px">
        <h2 style="margin:0">Sample Frames — <span id="vid-name" style="color:#555;font-weight:400"></span></h2>
        <span id="vid-info" style="margin-left:auto;font-size:11px;color:#555"></span>
      </div>
      <div id="frames-grid" class="frames-grid"></div>
    </div>

    <div class="card">
      <h2>Existing Profiles — Auto-Detection</h2>
      <div id="prof-grid" class="prof-grid">
        <div class="progress">Loading profiles…</div>
      </div>
      <div class="row" style="margin-top:14px">
        <button class="btn success" id="btn-reuse" onclick="confirmReuse()" disabled>&#10003; Reuse Selected Profile</button>
        <button class="btn danger"  onclick="tryAutoCalib()">&#9881; Auto-Calibrate (KaliCalib)</button>
        <button class="btn"         onclick="startAnnotation()" style="color:#aaa">&#9998; Annotate Manually</button>
      </div>
    </div>
  </div>

  <!-- Phase: auto_calibrating -->
  <div id="phase-auto_calibrating" class="card" style="display:none">
    <h2><span class="spin">&#9881;</span> Running KaliCalib…</h2>
    <p style="font-size:11px;color:#555;margin-bottom:10px">
      AI がコートキーポイントを自動検出しています。15〜30秒かかります。
    </p>
    <div id="kali-log" class="log"></div>
  </div>

  <!-- Phase: confirming -->
  <div id="phase-confirming" style="display:none">
    <div class="card">
      <div class="row" style="margin-bottom:12px">
        <h2 style="margin:0">Auto-Calibration Result</h2>
        <span id="kali-score" style="margin-left:auto;font-size:12px"></span>
      </div>
      <p style="font-size:11px;color:#666;margin-bottom:12px">
        緑のラインがコート境界に合っているか確認してください。
        ズレがある場合は「手動アノテーション」を選んでください。
      </p>
      <div style="position:relative;background:#0a0a0a;border-radius:6px;overflow:hidden;margin-bottom:14px">
        <img id="kali-debug-img" src="" style="width:100%;display:block">
        <div id="kali-overlay-hint" style="position:absolute;bottom:8px;left:8px;
          font-size:11px;background:rgba(0,0,0,.7);padding:3px 8px;border-radius:3px;color:#aaa">
          緑 = KaliCalib 推定コート境界
        </div>
      </div>
      <div class="row">
        <button class="btn success" onclick="acceptKali()">&#10003; 精度OK — このキャリブレーションを使用</button>
        <button class="btn danger"  onclick="startAnnotation()">&#9998; ズレあり — 手動アノテーションへ</button>
      </div>
    </div>
  </div>

  <!-- Phase: annotating -->
  <div id="phase-annotating" style="display:none">
    <div class="card">
      <div class="row" style="margin-bottom:10px">
        <h2 style="margin:0">Court Landmark Annotation</h2>
        <span id="ann-progress" style="margin-left:auto;font-size:12px;color:#666">0 / 10 required</span>
      </div>
      <div id="ann-wrap">
        <div id="ann-canvas-wrap">
          <canvas id="ann-cv"></canvas>
        </div>
        <div id="ann-sidebar">
          <div class="card" style="padding:8px">
            <div style="display:flex;align-items:center;gap:8px;margin-bottom:8px">
              <span style="font-size:11px;color:#555">Frame</span>
              <button class="btn" style="padding:2px 8px;font-size:11px" onclick="annNav(-150)">&#9664;5s</button>
              <button class="btn" style="padding:2px 8px;font-size:11px" onclick="annNav(-1)">&#9664;1</button>
              <button class="btn" style="padding:2px 8px;font-size:11px" onclick="annNav(+1)">1&#9654;</button>
              <button class="btn" style="padding:2px 8px;font-size:11px" onclick="annNav(+150)">5s&#9654;</button>
            </div>
            <canvas id="court-cv" height="160"></canvas>
          </div>
          <div class="card" style="padding:8px;flex:1;overflow-y:auto">
            <div id="lm-list"></div>
          </div>
          <button class="btn success" id="btn-compute-H" onclick="computeH()" disabled style="width:100%">
            &#9654; Compute H Matrix
          </button>
        </div>
      </div>
    </div>
  </div>

  <!-- Phase: done -->
  <div id="phase-done" style="display:none">
    <div class="card" style="text-align:center;padding:30px">
      <div class="big">&#10003; Setup Complete</div>
      <div id="done-info" style="color:#aaa;margin-bottom:16px"></div>
      <div style="text-align:left;max-width:500px;margin:0 auto">
        <div class="stat-row"><span class="k">Profile</span><span id="done-profile" class="v"></span></div>
        <div class="stat-row"><span class="k">Video</span><span id="done-video" class="v"></span></div>
        <div class="stat-row"><span class="k">H inliers</span><span id="done-inliers" class="v"></span></div>
        <div style="margin-top:14px;color:#666;font-size:12px">Run analysis:</div>
        <code id="done-cmd"></code>
      </div>
    </div>
  </div>

  <!-- Phase: error -->
  <div id="phase-error" style="display:none">
    <div class="card" style="border-color:#622">
      <h2 style="color:#e55">Error</h2>
      <div id="error-msg" style="color:#e88;font-family:monospace;font-size:12px"></div>
    </div>
  </div>
</div>

<script>
const CALIB_LM = __CALIB_LM__;
const REQ_IDS  = __REQ_IDS__;

let state       = {phase:'idle', samples:[], profiles:[], scores:{}, best:null,
                   fps:30, total:0, vidName:'', ann:{}, annFrame:0, newName:''};
let selectedProf= null;
let annImg      = null;
let annZoom=1, annPanX=0, annPanY=0, annImgW=0, annImgH=0;
let activeLm    = CALIB_LM[0].id;
let dragging=false,dragSX=0,dragSY=0,dragPX=0,dragPY=0;

const LM_COLORS = {
  near:'#4d9fff', mid:'#ffcc44', far:'#ff6644', opt:'#44ddaa'
};

// ── Phase display ─────────────────────────────────────────────────────────
const ALL_PHASES=['idle','downloading','previewing','auto_calibrating','confirming','annotating','done','error'];
function showPhase(ph){
  ALL_PHASES.forEach(p=>{
    const el=document.getElementById('phase-'+p);
    if(el) el.style.display = p===ph?'':'none';
  });
  document.getElementById('phase-badge').textContent=ph.toUpperCase().replace('_',' ');
}

// ── Polling ───────────────────────────────────────────────────────────────
async function poll(){
  const s = await fetch('/api/state').then(r=>r.json());
  const prevPhase = state.phase;
  Object.assign(state, s);

  if(s.phase==='downloading'){
    showPhase('downloading');
    const log=document.getElementById('dl-log');
    log.innerHTML=(s.dl_log||[]).map(l=>`<p class="${l.startsWith('✓')?'ok':l.startsWith('Error')?'err':''}">${esc(l)}</p>`).join('');
    log.scrollTop=log.scrollHeight;
  } else if(s.phase==='previewing' && prevPhase!=='previewing'){
    showPhase('previewing');
    renderPreview();
  } else if(s.phase==='auto_calibrating'){
    showPhase('auto_calibrating');
    const klog=document.getElementById('kali-log');
    klog.innerHTML=(s.kali_log||[]).map(l=>`<p>${esc(l)}</p>`).join('');
    klog.scrollTop=klog.scrollHeight;
  } else if(s.phase==='confirming' && prevPhase!=='confirming'){
    showPhase('confirming');
    renderConfirming(s);
  } else if(s.phase==='annotating'){
    showPhase('annotating');
    if(prevPhase!=='annotating') initAnnotation();
  } else if(s.phase==='done'){
    showPhase('done');
    renderDone();
    return;
  } else if(s.phase==='error'){
    showPhase('error');
    document.getElementById('error-msg').textContent=s.error||'Unknown error';
    return;
  }
  setTimeout(poll, 800);
}

// ── Download ──────────────────────────────────────────────────────────────
async function startDownload(){
  const url=document.getElementById('url-input').value.trim();
  if(!url){ alert('Enter a URL'); return; }
  showPhase('downloading');
  document.getElementById('dl-log').innerHTML='';
  await fetch('/api/download',{method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({url})});
  poll();
}

// ── Preview ───────────────────────────────────────────────────────────────
function renderPreview(){
  document.getElementById('vid-name').textContent = state.vidName;
  const fps=state.fps||30;
  const dur=((state.total||0)/fps).toFixed(0);
  document.getElementById('vid-info').textContent=`${state.total} frames · ${fps.toFixed(1)}fps · ~${dur}s`;

  // Sample frames
  const grid=document.getElementById('frames-grid'); grid.innerHTML='';
  (state.samples||[]).forEach(fi=>{
    const div=document.createElement('div');
    div.className='frame-thumb';
    div.dataset.fi=fi;
    div.innerHTML=`<img src="/frame/new/${fi}?w=240" loading="lazy"><span class="fi">${fi}</span>`;
    div.onclick=()=>{
      document.querySelectorAll('.frame-thumb').forEach(d=>d.classList.remove('active'));
      div.classList.add('active');
      state.annFrame=fi;
    };
    grid.appendChild(div);
  });
  if(grid.firstChild) grid.firstChild.classList.add('active');

  // Profile cards
  const pg=document.getElementById('prof-grid'); pg.innerHTML='';
  if(!state.profiles||state.profiles.length===0){
    pg.innerHTML='<p style="color:#555;font-size:12px">No existing profiles found.</p>';
    return;
  }
  state.profiles.forEach(prof=>{
    const score=state.scores[prof.name]||0;
    const pct=Math.round(score*100);
    const isBest=prof.name===state.best;
    const card=document.createElement('div');
    card.className='prof-card'+(isBest?' best':'');
    card.dataset.name=prof.name;
    card.innerHTML=`
      <img src="/frame/prof/${prof.name}" loading="lazy">
      <div class="name">${prof.name}</div>
      <div class="score-bar"><div class="score-fill" style="width:${pct}%;background:${score>0.7?'#4a9':score>0.4?'#fa4':'#e44'}"></div></div>
      <div class="score">Match: <b style="color:${score>0.7?'#4d9':score>0.4?'#fa4':'#e55'}">${pct}%</b>
        ${isBest?'<span class="badge best">Best Match</span>':''}
      </div>
      <div style="font-size:10px;color:#444">${prof.video}</div>`;
    card.onclick=()=>selectProfile(prof.name);
    pg.appendChild(card);
  });
  if(state.best) selectProfile(state.best);
}

function selectProfile(name){
  document.querySelectorAll('.prof-card').forEach(c=>c.classList.remove('selected'));
  const c=document.querySelector(`.prof-card[data-name="${name}"]`);
  if(c) c.classList.add('selected');
  selectedProf=name;
  document.getElementById('btn-reuse').disabled=false;
  document.getElementById('btn-reuse').textContent=`✓ Reuse "${name}"`;
}

async function confirmReuse(){
  if(!selectedProf) return;
  await fetch('/api/decide',{method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({action:'reuse',profile:selectedProf})});
}

async function tryAutoCalib(){
  showPhase('auto_calibrating');
  document.getElementById('kali-log').innerHTML='<p>Starting KaliCalib…</p>';
  await fetch('/api/auto_calibrate',{method:'POST',
    headers:{'Content-Type':'application/json'},body:'{}'});
  // poll() will detect phase transition to 'confirming'
}

function renderConfirming(s){
  const inliers = s.kali_inliers||0;
  const quality = inliers>=8?'✅ Good':'inliers>=4?⚠️ Fair':'❌ Poor';
  const col     = inliers>=8?'#4a9':inliers>=4?'#fa0':'#e44';
  document.getElementById('kali-score').innerHTML=
    `Inliers: <b style="color:${col}">${inliers}/10</b> &nbsp;|&nbsp; Frame: ${s.kali_frame||0}`;
  document.getElementById('kali-debug-img').src=`/kali_debug?t=${Date.now()}`;
}

async function acceptKali(){
  await fetch('/api/confirm_kali',{method:'POST',
    headers:{'Content-Type':'application/json'},body:'{}'});
}

async function startAnnotation(){
  await fetch('/api/decide',{method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({action:'new'})});
  showPhase('annotating');
}

// ── Annotation ────────────────────────────────────────────────────────────
let annCv, annCtx, courtCv, courtCtx;

function initAnnotation(){
  annCv   = document.getElementById('ann-cv');
  annCtx  = annCv.getContext('2d');
  courtCv = document.getElementById('court-cv');
  courtCtx= courtCv.getContext('2d');
  buildLmList();
  resizeAnn();
  loadAnnFrame(state.annFrame||0);
  drawCourtMap();
  setupAnnEvents();
}

function resizeAnn(){
  const wrap=document.getElementById('ann-canvas-wrap');
  annCv.width=wrap.clientWidth; annCv.height=wrap.clientHeight;
  const cw=document.getElementById('ann-sidebar').clientWidth-16;
  courtCv.width=cw; courtCv.style.height=Math.round(cw*3/8)+'px';
  courtCv.height=Math.round(cw*3/8);
}

async function loadAnnFrame(fi){
  state.annFrame=fi;
  const img=new Image();
  img.onload=()=>{
    annImg=img; annImgW=img.naturalWidth; annImgH=img.naturalHeight;
    annRender();
  };
  img.src=`/frame/new/${fi}?t=${Date.now()}`;
}

function annNav(d){ loadAnnFrame(Math.max(0,Math.min(state.annFrame+d,state.total-1))); }

function buildLmList(){
  const el=document.getElementById('lm-list'); el.innerHTML='';
  CALIB_LM.forEach(lm=>{
    const div=document.createElement('div');
    const grp=lm.group||'opt';
    const col=LM_COLORS[grp]||'#999';
    div.className='lm-item'+(lm.id===activeLm?' active':'')+(state.ann[lm.id]?' set':'');
    div.id='lmi-'+lm.id;
    div.innerHTML=`
      <div class="lm-dot${state.ann[lm.id]?' set':''}" style="background:${state.ann[lm.id]?col:'#333'};border-color:${col}55"></div>
      <div class="lm-label">${lm.label}</div>
      ${lm.req?'<span class="req-badge">REQ</span>':'<span class="req-badge" style="color:#4d9;background:#0a1a0a">opt</span>'}
      ${state.ann[lm.id]?'<span class="lm-check">✓</span>':''}`;
    div.onclick=()=>selectLm(lm.id);
    el.appendChild(div);
  });
  updateAnnProgress();
}

function selectLm(id){ activeLm=id; buildLmList(); }

function updateAnnProgress(){
  const done=REQ_IDS.filter(id=>state.ann[id]).length;
  document.getElementById('ann-progress').textContent=`${done} / ${REQ_IDS.length} required`;
  document.getElementById('btn-compute-H').disabled = done < 4;
}

// Canvas helpers
function annBS(){ return annImg?Math.min(annCv.width/annImgW,annCv.height/annImgH):1; }
function annI2C(ix,iy){
  const s=annBS()*annZoom;
  const ox=(annCv.width-annImgW*annBS())/2+annPanX, oy=(annCv.height-annImgH*annBS())/2+annPanY;
  const dx=(annBS()-s)/annBS()*annImgW/2, dy=(annBS()-s)/annBS()*annImgH/2;
  return[ox+(ix-dx)*s, oy+(iy-dy)*s];
}
function annC2I(cx,cy){
  const s=annBS()*annZoom;
  const ox=(annCv.width-annImgW*annBS())/2+annPanX, oy=(annCv.height-annImgH*annBS())/2+annPanY;
  const dx=(annBS()-s)/annBS()*annImgW/2, dy=(annBS()-s)/annBS()*annImgH/2;
  return[(cx-ox)/s+dx, (cy-oy)/s+dy];
}

function annRender(){
  if(!annImg) return;
  annCtx.clearRect(0,0,annCv.width,annCv.height);
  const s=annBS()*annZoom;
  const ox=(annCv.width-annImgW*annBS())/2+annPanX, oy=(annCv.height-annImgH*annBS())/2+annPanY;
  const dx=(annBS()-s)/annBS()*annImgW/2, dy=(annBS()-s)/annBS()*annImgH/2;
  annCtx.drawImage(annImg,ox+dx*s,oy+dy*s,annImgW*s,annImgH*s);

  // Draw marks
  CALIB_LM.forEach(lm=>{
    const xy=state.ann[lm.id]; if(!xy) return;
    const[cx,cy]=annI2C(xy[0],xy[1]); // img→canvas
    // actually we need I2C to go from img pixel to canvas
    const[pcx,pcy]=annI2C(xy[0],xy[1]);
    const col=LM_COLORS[lm.group||'opt'];
    const active=lm.id===activeLm, r=active?20:14;
    annCtx.save();
    annCtx.strokeStyle='#000'; annCtx.lineWidth=3;
    annCtx.beginPath(); annCtx.arc(pcx,pcy,r,0,Math.PI*2); annCtx.stroke();
    annCtx.strokeStyle=col; annCtx.lineWidth=active?2:1.5;
    annCtx.beginPath(); annCtx.arc(pcx,pcy,r,0,Math.PI*2); annCtx.stroke();
    annCtx.beginPath();
    annCtx.moveTo(pcx-r+4,pcy); annCtx.lineTo(pcx+r-4,pcy);
    annCtx.moveTo(pcx,pcy-r+4); annCtx.lineTo(pcx,pcy+r-4);
    annCtx.stroke();
    annCtx.fillStyle=col; annCtx.beginPath(); annCtx.arc(pcx,pcy,3,0,Math.PI*2); annCtx.fill();
    if(active){
      annCtx.fillStyle=col; annCtx.font='bold 11px system-ui';
      annCtx.shadowColor='#000'; annCtx.shadowBlur=4;
      annCtx.fillText(lm.label,pcx+r+5,pcy+4);
    }
    annCtx.restore();
  });

  // Highlight active landmark
  const actLm=CALIB_LM.find(l=>l.id===activeLm);
  if(actLm&&!state.ann[actLm.id]){
    annCtx.save();
    annCtx.fillStyle='rgba(41,182,246,.18)';
    annCtx.fillRect(0,annCv.height-26,annCv.width,26);
    annCtx.fillStyle='#7dd4f8'; annCtx.font='11px system-ui';
    annCtx.fillText(`Click to place: ${actLm.label}`,8,annCv.height-9);
    annCtx.restore();
  }
}

function drawCourtMap(){
  const W=courtCv.width, H=courtCv.height, pad=5;
  const SL=750, FY=2864;
  const sx=(W-pad*2)/(SL*2), sy=(H-pad*2)/FY;
  function c2p(cx,cy){ return[pad+(cx+SL)*sx, H-pad-cy*sy]; }

  courtCtx.fillStyle='#0a0a0a'; courtCtx.fillRect(0,0,W,H);
  function ml(x1,y1,x2,y2,col='#2a2a2a',lw=1){
    const[ax,ay]=c2p(x1,y1),[bx,by]=c2p(x2,y2);
    courtCtx.beginPath(); courtCtx.moveTo(ax,ay); courtCtx.lineTo(bx,by);
    courtCtx.strokeStyle=col; courtCtx.lineWidth=lw; courtCtx.stroke();
  }
  ml(-750,0,750,0,'#444',1.5); ml(-750,FY,750,FY,'#444',1.5);
  ml(-750,0,-750,FY,'#444',1.5); ml(750,0,750,FY,'#444',1.5);
  ml(-750,1432,750,1432,'#333',1);

  // Highlight each landmark on court map
  CALIB_LM.forEach(lm=>{
    const[cx,cy]=lm.court;
    const[px,py]=c2p(cx,cy);
    const grp=lm.group||'opt';
    const col=LM_COLORS[grp];
    const isSet=!!state.ann[lm.id];
    const isActive=lm.id===activeLm;
    courtCtx.beginPath(); courtCtx.arc(px,py,isActive?5:3,0,Math.PI*2);
    courtCtx.fillStyle=isSet?col:(isActive?col+'88':'#2a2a2a');
    courtCtx.fill();
    if(isActive){
      courtCtx.beginPath(); courtCtx.arc(px,py,8,0,Math.PI*2);
      courtCtx.strokeStyle=col; courtCtx.lineWidth=1.5; courtCtx.stroke();
    }
  });
}

function setupAnnEvents(){
  annCv.addEventListener('mousedown',e=>{
    if(e.altKey){
      dragging=true;dragSX=e.clientX;dragSY=e.clientY;
      dragPX=annPanX;dragPY=annPanY;annCv.style.cursor='grabbing';
    }
  });
  window.addEventListener('mousemove',e=>{
    if(dragging){annPanX=dragPX+(e.clientX-dragSX);annPanY=dragPY+(e.clientY-dragSY);annRender();}
  });
  window.addEventListener('mouseup',()=>{dragging=false;annCv.style.cursor='crosshair';});

  annCv.addEventListener('click',e=>{
    if(e.altKey) return;
    const rect=annCv.getBoundingClientRect();
    const cx=e.clientX-rect.left, cy=e.clientY-rect.top;
    const[ix,iy]=annC2I(cx,cy);
    if(ix<0||iy<0||ix>=annImgW||iy>=annImgH) return;
    const HIT=22;
    // click existing mark → delete
    for(const lm of CALIB_LM){
      if(state.ann[lm.id]){
        const[mx,my]=annI2C(state.ann[lm.id][0],state.ann[lm.id][1]);
        if(Math.hypot(cx-mx,cy-my)<HIT){
          delete state.ann[lm.id];
          buildLmList(); annRender(); drawCourtMap();
          return;
        }
      }
    }
    // place new
    state.ann[activeLm]=[Math.round(ix),Math.round(iy)];
    // auto-advance to next unset required
    const next=CALIB_LM.find(lm=>lm.req&&!state.ann[lm.id]);
    if(next) activeLm=next.id;
    buildLmList(); annRender(); drawCourtMap();
  });

  annCv.addEventListener('wheel',e=>{
    e.preventDefault();
    const rect=annCv.getBoundingClientRect();
    const mx=e.clientX-rect.left,my=e.clientY-rect.top;
    const[ix,iy]=annC2I(mx,my);
    const f=e.deltaY<0?1.15:1/1.15;
    annZoom=Math.max(1,Math.min(10,annZoom*f));
    const s=annBS()*annZoom,ox=(annCv.width-annImgW*annBS())/2,oy=(annCv.height-annImgH*annBS())/2;
    const dx=(annBS()-s)/annBS()*annImgW/2,dy=(annBS()-s)/annBS()*annImgH/2;
    annPanX=mx-ox-(ix-dx)*s; annPanY=my-oy-(iy-dy)*s;
    annRender();
  },{passive:false});

  document.addEventListener('keydown',e=>{
    if(document.getElementById('phase-annotating').style.display==='none') return;
    if(e.key==='ArrowLeft'||e.key==='a') annNav(e.shiftKey?-450:e.ctrlKey?-150:-1);
    if(e.key==='ArrowRight'||e.key==='d') annNav(e.shiftKey?+450:e.ctrlKey?+150:+1);
    if(e.key==='Backspace'){
      delete state.ann[activeLm]; buildLmList(); annRender(); drawCourtMap();
    }
  });
  window.addEventListener('resize',()=>{resizeAnn();annRender();drawCourtMap();});
}

async function computeH(){
  const r=await fetch('/api/compute_H',{method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({ann:state.ann, frame:state.annFrame})});
  const data=await r.json();
  if(data.error){ alert('H computation failed: '+data.error); return; }
  state.inliers=data.inliers;
  // Phase will become 'done' on next poll
}

// ── Done ──────────────────────────────────────────────────────────────────
function renderDone(){
  document.getElementById('done-info').textContent=
    `Profile "${state.newName||state.reuseProfile}" ready for analysis`;
  document.getElementById('done-profile').textContent=state.newName||state.reuseProfile||'—';
  document.getElementById('done-video').textContent=state.vidName||'—';
  document.getElementById('done-inliers').textContent=
    state.inliers?`${state.inliers} / ${Object.keys(state.ann||{}).length} landmarks`:'(reused)';
  document.getElementById('done-cmd').textContent=
    `python render_full_detection.py --profile outputs/venue_profiles/${state.newName||state.reuseProfile}.json`;
}

// ── Utils ─────────────────────────────────────────────────────────────────
function esc(s){ const d=document.createElement('div'); d.textContent=s; return d.innerHTML; }

// Start
poll();
</script>
</body>
</html>
"""


# ── HTTP handler ──────────────────────────────────────────────────────────────

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_): pass

    def send_json(self, obj, code=200):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", len(body))
        self.end_headers(); self.wfile.write(body)

    def do_GET(self):
        p = urlparse(self.path); qs = parse_qs(p.query)

        if p.path == "/":
            lm_json    = json.dumps([{"id":lm["id"],"label":lm["label"],"group":lm["group"],"req":lm["req"],"court":lm["court"]}
                                      for lm in CALIB_LM])
            req_json   = json.dumps(REQ_IDS)
            body = (HTML.replace("__CALIB_LM__", lm_json)
                        .replace("__REQ_IDS__",  req_json)).encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html;charset=utf-8")
            self.send_header("Content-Length", len(body))
            self.end_headers(); self.wfile.write(body)
            return

        if p.path == "/api/state":
            out = {
                "phase":       srv["phase"],
                "dl_log":      srv["dl_log"][-60:],
                "vidName":     srv["video_name"],
                "fps":         srv["fps"],
                "total":       srv["total"],
                "samples":     srv["samples"],
                "profiles":    [{"name":pf["name"],"video":pf["video"]} for pf in srv["profiles"]],
                "scores":      srv["scores"],
                "best":        srv["best"],
                "ann":         srv["ann"],
                "annFrame":    srv["ann_frame"],
                "inliers":     srv.get("inliers", 0),
                "newName":     srv["new_name"],
                "reuseProfile":srv["reuse_name"],
                "error":       srv["error"],
                "kali_log":    srv["kali_log"][-30:],
                "kali_inliers":srv["kali_inliers"],
                "kali_frame":  srv["kali_frame"],
                "kali_ok":     srv["kali_H"] is not None,
            }
            self.send_json(out); return

        if p.path == "/kali_debug":
            data = srv.get("kali_debug")
            if not data:
                self.send_response(404); self.end_headers(); return
            self.send_response(200)
            self.send_header("Content-Type", "image/jpeg")
            self.send_header("Content-Length", len(data))
            self.send_header("Cache-Control", "no-cache")
            self.end_headers(); self.wfile.write(data); return

        if p.path.startswith("/frame/new/"):
            fi = int(p.path.split("/")[-1])
            w  = int(qs.get("w", ["0"])[0]) or None
            if cap_main is None:
                self.send_response(404); self.end_headers(); return
            data = get_jpg(cap_main, fi, w)
            if data is None:
                self.send_response(404); self.end_headers(); return
            self.send_response(200)
            self.send_header("Content-Type", "image/jpeg")
            self.send_header("Content-Length", len(data))
            self.end_headers(); self.wfile.write(data); return

        if p.path.startswith("/frame/prof/"):
            name = p.path.split("/")[-1]
            prof = next((pf for pf in srv["profiles"] if pf["name"] == name), None)
            if prof is None or name not in cap_prof:
                self.send_response(404); self.end_headers(); return
            data = get_jpg(cap_prof[name], prof["frame_idx"], 320)
            if data is None:
                self.send_response(404); self.end_headers(); return
            self.send_response(200)
            self.send_header("Content-Type", "image/jpeg")
            self.send_header("Content-Length", len(data))
            self.end_headers(); self.wfile.write(data); return

        self.send_response(404); self.end_headers()

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
        p = urlparse(self.path).path

        if p == "/api/download":
            url = body.get("url", "").strip()
            if not url:
                self.send_json({"error": "No URL"}); return
            srv["url"] = url
            threading.Thread(target=do_download, args=(url,), daemon=True).start()
            self.send_json({"ok": True}); return

        if p == "/api/auto_calibrate":
            # KaliCalib 自動キャリブレーション開始
            threading.Thread(target=do_auto_calibrate, daemon=True).start()
            self.send_json({"ok": True}); return

        if p == "/api/confirm_kali":
            # KaliCalib 結果を受け入れてプロファイル保存
            if srv["kali_H"] is None:
                self.send_json({"error": "No KaliCalib result"}); return
            new_name = _unique_name("game")
            profile  = {
                "venue":            new_name,
                "video":            srv["video_name"],
                "fullcourt":        True,
                "frame_idx":        srv["kali_frame"],
                "H_court_to_image": srv["kali_H"],
                "kali_inliers":     srv["kali_inliers"],
                "calibration":      "auto_kalicalib",
            }
            out_path = PROFILE_DIR / f"{new_name}.json"
            with open(out_path, "w") as f:
                json.dump(profile, f, ensure_ascii=False, indent=2)
            srv["new_name"] = new_name
            srv["inliers"]  = srv["kali_inliers"]
            srv["phase"]    = "done"
            print(f"KaliCalib profile saved: {out_path}")
            self.send_json({"ok": True, "name": new_name}); return

        if p == "/api/decide":
            action = body.get("action")
            srv["action"] = action
            if action == "reuse":
                prof_name = body.get("profile")
                prof = next((pf for pf in srv["profiles"] if pf["name"] == prof_name), None)
                if prof is None:
                    self.send_json({"error": "Profile not found"}); return
                # Create new profile by copying existing, update video
                new_data = dict(prof["data"])
                new_data["video"] = srv["video_name"]
                # Generate new name
                base = prof_name
                new_name = _unique_name(base)
                new_data["venue"] = new_name
                out_path = PROFILE_DIR / f"{new_name}.json"
                with open(out_path, "w") as f:
                    json.dump(new_data, f, ensure_ascii=False, indent=2)
                srv["reuse_name"] = new_name
                srv["new_name"]   = new_name
                srv["phase"]      = "done"
                print(f"Saved: {out_path}")
            elif action == "new":
                srv["phase"] = "annotating"
                srv["ann"]   = {}
                srv["ann_frame"] = srv["samples"][len(srv["samples"])//2] if srv["samples"] else 0
            self.send_json({"ok": True}); return

        if p == "/api/compute_H":
            ann       = body.get("ann", {})
            frame_idx = int(body.get("frame", 0))
            srv["ann"] = ann
            H_c2i, inliers = compute_H(ann)
            if H_c2i is None:
                self.send_json({"error": "Not enough points (need ≥4)"}); return

            # Build full venue profile
            new_name = _unique_name("game")
            profile = {
                "venue":       new_name,
                "video":       srv["video_name"],
                "fullcourt":   True,
                "frame_idx":   frame_idx,
                "H_court_to_image": H_c2i,
            }
            # Add near_ring, far_ring, center_circle if annotated
            for opt_id, field in [("near_ring","near_ring_image_xy"),
                                   ("far_ring","far_ring_image_xy"),
                                   ("center_circle","center_circle_image_xy")]:
                if ann.get(opt_id):
                    profile[field] = ann[opt_id]

            # Build pairs (all annotated landmarks)
            pairs = []
            for lm in CALIB_LM:
                if ann.get(lm["id"]):
                    pairs.append({
                        "landmark_id":   lm["id"],
                        "landmark_desc": lm["label"],
                        "court_xy":      lm["court"],
                        "image_xy":      ann[lm["id"]],
                    })
            profile["n_pairs"] = len(pairs)
            profile["pairs"]   = pairs

            out_path = PROFILE_DIR / f"{new_name}.json"
            with open(out_path, "w") as f:
                json.dump(profile, f, ensure_ascii=False, indent=2)

            srv["new_name"] = new_name
            srv["inliers"]  = inliers
            srv["phase"]    = "done"
            print(f"Profile saved: {out_path}  (inliers={inliers})")
            self.send_json({"ok": True, "inliers": inliers, "name": new_name}); return

        self.send_response(404); self.end_headers()


def _unique_name(base):
    existing = {p.stem for p in PROFILE_DIR.glob("*.json")}
    if base not in existing:
        return base
    i = 2
    while f"{base}-{i}" in existing:
        i += 1
    return f"{base}-{i}"


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="", help="YouTube URL (optional, can enter in browser)")
    args = ap.parse_args()

    if args.url:
        srv["url"] = args.url

    url = f"http://localhost:{PORT}"
    print(f"Game Setup Wizard → {url}")
    threading.Thread(
        target=lambda: (time.sleep(0.7), webbrowser.open(url)),
        daemon=True
    ).start()

    if args.url:
        threading.Thread(target=do_download, args=(args.url,), daemon=True).start()

    httpd = HTTPServer(("", PORT), Handler)
    print("Ctrl-C to stop.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("Stopped.")
    finally:
        if cap_main:
            cap_main.release()
        for c in cap_prof.values():
            c.release()


if __name__ == "__main__":
    main()
