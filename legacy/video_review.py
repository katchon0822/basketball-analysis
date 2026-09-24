"""
動画レビューツール - 生成動画の問題点を具体的に記録するシステム

起動:
    python video_review.py

ブラウザで http://localhost:8766

機能:
  - outputs/ 以下の .mp4 を自動リスト
  - 動画再生中に問題をマーク（タイムスタンプ自動記録）
  - 問題種別 / 説明テキスト / 画面クリック位置を保存
  - マーク済み一覧をクリックで該当時刻へジャンプ
  - outputs/video_issues.json に保存（再起動しても残る）
  - キーボード: M=マーク, Space=再生停止, ←→=±1秒
"""

import json
import os
import threading
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, unquote
from pathlib import Path

ISSUES_FILE = "outputs/video_issues.json"
VIDEO_ROOT  = Path("outputs")
PORT        = 8766

# ── HTML ──────────────────────────────────────────────────────
HTML = r"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<title>Basketball AI - 動画レビュー</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:system-ui,sans-serif;background:#111827;color:#e5e7eb;height:100vh;display:flex;flex-direction:column}
header{background:#1f2937;padding:10px 16px;display:flex;align-items:center;gap:12px;border-bottom:1px solid #374151;flex-shrink:0}
header h1{font-size:16px;color:#60a5fa;white-space:nowrap}
#videoSel{background:#111827;color:#e5e7eb;border:1px solid #374151;border-radius:6px;padding:5px 8px;font-size:13px;flex:1;max-width:400px}
.main{display:flex;flex:1;overflow:hidden}

/* 左: 動画 */
.left{flex:1;display:flex;flex-direction:column;padding:12px;gap:8px;min-width:0}
.video-wrap{position:relative;background:#000;border-radius:8px;overflow:hidden;flex:1}
video{width:100%;height:100%;object-fit:contain;display:block}
.click-layer{position:absolute;inset:0;cursor:crosshair}
.pin{position:absolute;width:22px;height:22px;border-radius:50%;border:3px solid #ef4444;transform:translate(-50%,-50%);pointer-events:none;box-shadow:0 0 6px #ef4444}
.controls{display:flex;align-items:center;gap:10px;flex-shrink:0;flex-wrap:wrap}
.time-badge{font-size:24px;font-weight:700;color:#60a5fa;min-width:90px;font-variant-numeric:tabular-nums}
button{padding:7px 14px;border:none;border-radius:6px;cursor:pointer;font-size:13px;font-weight:500}
.btn-mark{background:#ef4444;color:#fff;font-size:15px}
.btn-mark:hover{background:#dc2626}
.btn-play{background:#2563eb;color:#fff}
.btn-play:hover{background:#1d4ed8}
.hint{font-size:11px;color:#6b7280}
.pin-info{font-size:11px;color:#9ca3af}

/* 右: パネル */
.right{width:360px;display:flex;flex-direction:column;border-left:1px solid #374151;overflow:hidden}
.panel{padding:12px;border-bottom:1px solid #374151;flex-shrink:0}
.panel h3{font-size:11px;color:#9ca3af;text-transform:uppercase;letter-spacing:.8px;margin-bottom:8px}
select,textarea{width:100%;background:#1f2937;color:#e5e7eb;border:1px solid #374151;border-radius:6px;padding:6px 8px;font-size:13px;font-family:inherit}
textarea{height:72px;resize:vertical;margin-top:6px}
select:focus,textarea:focus{outline:none;border-color:#60a5fa}

.issue-list{flex:1;overflow-y:auto;padding:8px}
.empty{color:#6b7280;text-align:center;padding:24px;font-size:13px}
.issue{background:#1f2937;border-radius:8px;padding:10px;margin-bottom:8px;border-left:4px solid #ef4444;cursor:pointer;position:relative}
.issue:hover{background:#263045}
.issue .row1{display:flex;align-items:center;gap:6px}
.issue .ts{color:#60a5fa;font-weight:700;font-size:14px;font-variant-numeric:tabular-nums}
.badge{background:#374151;border-radius:10px;padding:2px 7px;font-size:11px;color:#d1d5db}
.issue .desc{font-size:12px;color:#9ca3af;margin-top:4px;line-height:1.4}
.issue .pos{font-size:11px;color:#6b7280;margin-top:3px}
.del-btn{position:absolute;top:8px;right:8px;background:none;border:none;color:#6b7280;cursor:pointer;font-size:16px;padding:0;line-height:1}
.del-btn:hover{color:#ef4444}
</style>
</head>
<body>
<header>
  <h1>🏀 動画レビュー</h1>
  <select id="videoSel" onchange="changeVideo()">
    <option value="">── 動画を選択 ──</option>
  </select>
  <span class="hint">M = マーク &nbsp;|&nbsp; Space = 再生 &nbsp;|&nbsp; ← → = ±1秒</span>
</header>

<div class="main">
  <!-- 左: 動画プレイヤー -->
  <div class="left">
    <div class="video-wrap">
      <video id="vid" controls preload="metadata"></video>
      <div class="click-layer" id="clickLayer" onclick="handleClick(event)"></div>
      <div class="pin" id="pin" style="display:none"></div>
    </div>
    <div class="controls">
      <span class="time-badge" id="timeBadge">0.00 s</span>
      <button class="btn-mark" onclick="markIssue()">⚑ 問題をマーク (M)</button>
      <button class="btn-play" onclick="togglePlay()">▶ / ⏸</button>
      <span class="pin-info" id="pinInfo"></span>
    </div>
  </div>

  <!-- 右: 問題パネル -->
  <div class="right">
    <div class="panel">
      <h3>問題の種別</h3>
      <select id="issueType">
        <option value="hoop_detection">フープ検出ミス</option>
        <option value="court_overlay">コートオーバーレイのずれ</option>
        <option value="player_position">選手位置ミス (RADAR)</option>
        <option value="team_classification">チーム分類ミス</option>
        <option value="ball_detection">ボール検出ミス</option>
        <option value="player_id">選手ID断絶・スワップ</option>
        <option value="left_ring">左リング未表示</option>
        <option value="center_line">センターライン未表示</option>
        <option value="other">その他</option>
      </select>
      <textarea id="issueDesc" placeholder="何がおかしいか具体的に&#10;例: 左バスケットのリング円が画面外に飛んでいる"></textarea>
    </div>

    <div class="panel" style="padding-bottom:8px">
      <h3>マーク済み問題 &nbsp;<span id="cnt" style="color:#60a5fa">0</span> 件</h3>
    </div>
    <div class="issue-list" id="issueList">
      <div class="empty">まだ問題はマークされていません</div>
    </div>
  </div>
</div>

<script>
let issues = [];
let pin = null;  // {x, y, rx, ry} in video pixels / render pixels
let currentVid = '';

const TYPE_JP = {
  hoop_detection:'フープ検出', court_overlay:'オーバーレイ',
  player_position:'選手位置', team_classification:'チーム分類',
  ball_detection:'ボール検出', player_id:'ID断絶',
  left_ring:'左リング', center_line:'センターライン', other:'その他'
};

// ── 動画リスト読み込み ────────────────────────────────────
async function init() {
  const r = await fetch('/api/videos');
  const list = await r.json();
  const sel = document.getElementById('videoSel');
  list.forEach(v => {
    const o = document.createElement('option');
    o.value = v; o.textContent = v; sel.appendChild(o);
  });

  const saved = await fetch('/api/issues');
  issues = await saved.json();
  render();
}

function changeVideo() {
  currentVid = document.getElementById('videoSel').value;
  if (!currentVid) return;
  const vid = document.getElementById('vid');
  vid.src = '/video/' + encodeURIComponent(currentVid);
  vid.load();
  pin = null;
  document.getElementById('pin').style.display = 'none';
  document.getElementById('pinInfo').textContent = '';
}

// ── 動画クリックでピン ────────────────────────────────────
function handleClick(e) {
  const layer = document.getElementById('clickLayer');
  const vid   = document.getElementById('vid');
  const rect  = layer.getBoundingClientRect();
  // 動画の実際の描画領域を計算 (object-fit:contain)
  const vAspect = vid.videoWidth / vid.videoHeight;
  const bAspect = rect.width / rect.height;
  let drawW, drawH, offX = 0, offY = 0;
  if (vAspect > bAspect) {
    drawW = rect.width; drawH = drawW / vAspect;
    offY = (rect.height - drawH) / 2;
  } else {
    drawH = rect.height; drawW = drawH * vAspect;
    offX = (rect.width - drawW) / 2;
  }
  const rx = e.clientX - rect.left;
  const ry = e.clientY - rect.top;
  const px = Math.round((rx - offX) / drawW * vid.videoWidth);
  const py = Math.round((ry - offY) / drawH * vid.videoHeight);
  if (px < 0 || py < 0 || px > vid.videoWidth || py > vid.videoHeight) return;
  pin = {x: px, y: py, rx, ry};

  const pinEl = document.getElementById('pin');
  pinEl.style.left = rx + 'px'; pinEl.style.top = ry + 'px';
  pinEl.style.display = 'block';
  document.getElementById('pinInfo').textContent = `📍 (${px}, ${py}) px`;
}

// ── マーク ────────────────────────────────────────────────
async function markIssue() {
  const vid = document.getElementById('vid');
  vid.pause();
  if (!currentVid) { alert('動画を選択してください'); return; }

  const issue = {
    id: Date.now(),
    video: currentVid,
    timestamp: parseFloat(vid.currentTime.toFixed(3)),
    type: document.getElementById('issueType').value,
    description: document.getElementById('issueDesc').value.trim() || '(説明なし)',
    click_pos: pin ? {x: pin.x, y: pin.y} : null
  };

  issues.push(issue);
  issues.sort((a,b) => a.timestamp - b.timestamp);
  render();
  await save();

  document.getElementById('issueDesc').value = '';
  pin = null;
  document.getElementById('pin').style.display = 'none';
  document.getElementById('pinInfo').textContent = '';
}

async function deleteIssue(id, e) {
  e.stopPropagation();
  issues = issues.filter(i => i.id !== id);
  render();
  await save();
}

function jumpTo(t) {
  document.getElementById('vid').currentTime = t;
}

function render() {
  document.getElementById('cnt').textContent = issues.length;
  const list = document.getElementById('issueList');
  if (!issues.length) {
    list.innerHTML = '<div class="empty">まだ問題はマークされていません</div>';
    return;
  }
  list.innerHTML = issues.map(iss => `
    <div class="issue" onclick="jumpTo(${iss.timestamp})">
      <button class="del-btn" onclick="deleteIssue(${iss.id}, event)">✕</button>
      <div class="row1">
        <span class="ts">${iss.timestamp.toFixed(2)}s</span>
        <span class="badge">${TYPE_JP[iss.type] || iss.type}</span>
      </div>
      <div class="desc">${iss.description}</div>
      ${iss.click_pos ? `<div class="pos">📍 (${iss.click_pos.x}, ${iss.click_pos.y}) px</div>` : ''}
      <div class="pos" style="color:#374151;font-size:10px">${iss.video}</div>
    </div>
  `).join('');
}

async function save() {
  await fetch('/api/save', {
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify(issues)
  });
}

// ── 時刻表示 ──────────────────────────────────────────────
document.getElementById('vid').addEventListener('timeupdate', () => {
  document.getElementById('timeBadge').textContent =
    document.getElementById('vid').currentTime.toFixed(2) + ' s';
});

// ── キーボード ────────────────────────────────────────────
document.addEventListener('keydown', e => {
  if (['TEXTAREA','INPUT','SELECT'].includes(e.target.tagName)) return;
  const vid = document.getElementById('vid');
  if (e.key === 'm' || e.key === 'M') { e.preventDefault(); markIssue(); }
  if (e.key === ' ')          { e.preventDefault(); togglePlay(); }
  if (e.key === 'ArrowLeft')  { e.preventDefault(); vid.currentTime = Math.max(0, vid.currentTime - 1); }
  if (e.key === 'ArrowRight') { e.preventDefault(); vid.currentTime = vid.currentTime + 1; }
});

function togglePlay() {
  const vid = document.getElementById('vid');
  vid.paused ? vid.play() : vid.pause();
}

init();
</script>
</body>
</html>
"""


# ── HTTP サーバー ──────────────────────────────────────────────
class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass  # ログ抑制

    def send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', len(body))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(body)

    def do_HEAD(self):
        """HEAD リクエスト対応（ブラウザが動画再生前に必ず送る）"""
        parsed = urlparse(self.path)
        if parsed.path.startswith('/video/'):
            rel   = unquote(parsed.path[len('/video/'):])
            fpath = VIDEO_ROOT / rel
            if not fpath.exists():
                self.send_response(404); self.end_headers(); return
            size = fpath.stat().st_size
            self.send_response(200)
            self.send_header('Content-Type', 'video/mp4')
            self.send_header('Content-Length', size)
            self.send_header('Accept-Ranges', 'bytes')
            self.end_headers()
        else:
            self.send_response(200); self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path   = parsed.path

        if path == '/':
            body = HTML.encode()
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', len(body))
            self.end_headers()
            self.wfile.write(body)

        elif path == '/api/videos':
            mp4s = sorted(
                str(p.relative_to(VIDEO_ROOT))
                for p in VIDEO_ROOT.rglob('*.mp4')
            )
            self.send_json(mp4s)

        elif path == '/api/issues':
            try:
                data = json.loads(Path(ISSUES_FILE).read_text())
            except Exception:
                data = []
            self.send_json(data)

        elif path.startswith('/video/'):
            rel  = unquote(path[len('/video/'):])
            fpath = VIDEO_ROOT / rel
            if not fpath.exists():
                self.send_response(404); self.end_headers(); return
            self._serve_file_range(fpath)

        else:
            self.send_response(404); self.end_headers()

    def do_POST(self):
        if self.path == '/api/save':
            length = int(self.headers.get('Content-Length', 0))
            body   = self.rfile.read(length)
            data   = json.loads(body)
            Path(ISSUES_FILE).parent.mkdir(parents=True, exist_ok=True)
            Path(ISSUES_FILE).write_text(
                json.dumps(data, ensure_ascii=False, indent=2))
            self.send_json({'ok': True})
        else:
            self.send_response(404); self.end_headers()

    def _serve_file_range(self, fpath: Path):
        """Range リクエスト対応（HTML5 動画シークに必須）"""
        size = fpath.stat().st_size
        rng  = self.headers.get('Range')

        if rng and rng.startswith('bytes='):
            parts = rng[6:].split('-')
            start = int(parts[0]) if parts[0] else 0
            end   = int(parts[1]) if parts[1] else size - 1
            end   = min(end, size - 1)
            length = end - start + 1
            self.send_response(206)
            self.send_header('Content-Range', f'bytes {start}-{end}/{size}')
        else:
            start = 0; length = size
            self.send_response(200)

        self.send_header('Content-Type', 'video/mp4')
        self.send_header('Content-Length', length)
        self.send_header('Accept-Ranges', 'bytes')
        self.end_headers()

        with open(fpath, 'rb') as f:
            f.seek(start)
            remaining = length
            while remaining:
                chunk = f.read(min(65536, remaining))
                if not chunk: break
                self.wfile.write(chunk)
                remaining -= len(chunk)


def main():
    Path("outputs").mkdir(exist_ok=True)
    server = HTTPServer(('', PORT), Handler)
    url = f'http://localhost:{PORT}'
    print(f"起動中: {url}")
    threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n終了")


if __name__ == '__main__':
    main()
