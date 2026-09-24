"""
コートキーポイント Web アノテーター

起動:
    venv/bin/python3 annotator_web.py

機能:
  - フルコート表示（撮影位置・近/遠サイドライン表示）
  - 左/右バスケット選択
  - F キー: near/far X 反転
  - 既存ドットをクリックで直接位置修正
  - Backspace でフレームスキップ取り消し
  - コート線を画像上に描画
"""

import json
import os
import webbrowser
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

FRAME_DIR   = "outputs/annotation_frames"
ANNOTATIONS = "outputs/annotations.json"
PORT        = 8765


HTML = r"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<title>Court Annotator</title>
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  display: flex; height: 100vh;
  background: #1a1a1a; color: #eee;
  font-family: system-ui, -apple-system, sans-serif;
  font-size: 13px; overflow: hidden; user-select: none;
}
#sidebar {
  width: 160px; background: #1e1e1e;
  border-right: 1px solid #2e2e2e;
  display: flex; flex-direction: column; flex-shrink: 0;
}
#sidebar h3, #panel h3 {
  padding: 6px 10px; font-size: 10px; color: #555;
  text-transform: uppercase; letter-spacing: 1px;
  border-bottom: 1px solid #2e2e2e; flex-shrink: 0;
}
#frame-list { flex: 1; overflow-y: auto; padding: 3px; }
.fi {
  padding: 4px 7px; cursor: pointer; border-radius: 3px;
  margin-bottom: 1px; font-size: 11px; border-left: 3px solid #333;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.fi:hover { background: #2a2a2a; }
.fi.sel   { background: #303030; }
.fi.done  { border-color: #4caf50; color: #7ec87e; }
.fi.skip  { border-color: #1976d2; color: #7aadec; }
.fi.todo  { border-color: #333; color: #777; }
/* Center */
#center { flex: 1; display: flex; flex-direction: column; min-width: 0; }
#toolbar {
  background: #1e1e1e; padding: 6px 12px;
  display: flex; align-items: center; gap: 10px;
  border-bottom: 1px solid #2e2e2e; flex-shrink: 0; min-height: 42px;
}
.kp-name  { color: #ff9800; font-weight: 600; }
.kp-coord { font-size: 11px; color: #777; margin-top: 1px; }
.spacer { flex: 1; }
#flip-btn {
  padding: 4px 10px; background: #2a2a2a;
  border: 1px solid #444; border-radius: 4px;
  color: #bbb; cursor: pointer; font-size: 12px; transition: all .15s;
}
#flip-btn.on { background: #7f1010; border-color: #e53935; color: #fff; }
#wrap { flex: 1; position: relative; background: #0f0f0f; overflow: hidden; }
#cv   { position: absolute; top: 0; left: 0; }
#stbar {
  background: #1e1e1e; padding: 3px 10px;
  font-size: 10px; color: #555; border-top: 1px solid #2e2e2e;
  display: flex; gap: 12px; flex-shrink: 0;
}
#stbar .hint { margin-left: auto; }
/* Panel */
#panel {
  width: 222px; background: #1e1e1e;
  border-left: 1px solid #2e2e2e;
  display: flex; flex-direction: column; flex-shrink: 0;
}
/* Camera setup */
#cam-setup {
  padding: 5px 8px; border-bottom: 1px solid #2e2e2e; flex-shrink: 0;
}
#cam-setup .cam-label {
  font-size: 9px; color: #555; text-transform: uppercase; letter-spacing: .8px;
  margin-bottom: 4px;
}
#cam-setup .cam-btns { display: flex; gap: 4px; }
#cam-setup button {
  flex: 1; padding: 4px 3px; background: #252525;
  border: 1px solid #3a3a3a; border-radius: 3px;
  color: #666; cursor: pointer; font-size: 11px; transition: all .15s;
}
#cam-setup button.active {
  background: #0d2a3a; border-color: #29b6f6; color: #7dd4f8; font-weight: 600;
}
#cam-open-btn {
  width: 100%; margin-top: 4px; padding: 3px;
  background: none; border: 1px solid #2a2a2a; border-radius: 3px;
  color: #555; cursor: pointer; font-size: 10px; transition: all .15s;
}
#cam-open-btn:hover { border-color: #29b6f6; color: #7dd4f8; }
/* Basket selector */
#basket-sel {
  display: flex; gap: 4px; padding: 5px 8px;
  border-bottom: 1px solid #2e2e2e; flex-shrink: 0;
}
#basket-sel button {
  flex: 1; padding: 4px; background: #252525;
  border: 1px solid #3a3a3a; border-radius: 3px;
  color: #666; cursor: pointer; font-size: 11px; transition: all .15s;
}
#basket-sel button.active {
  background: #1a3a1a; border-color: #4caf50; color: #80d080; font-weight: 600;
}
#ref-wrap { padding: 6px 8px 4px; border-bottom: 1px solid #2e2e2e; flex-shrink: 0; }
#rcv { width: 100%; display: block; border-radius: 3px; }
#orient-btn {
  padding: 2px 7px; background: #1e2a1e; border: 1px solid #2a4a2a;
  border-radius: 3px; color: #6a9a6a; cursor: pointer; font-size: 9px;
  float: right; margin-bottom: 3px;
}
#orient-btn:hover { border-color: #4caf50; color: #90d090; }
#kp-list { flex: 1; overflow-y: auto; padding: 3px 4px; }
.line-hdr {
  font-size: 9px; color: #555; padding: 4px 6px 2px;
  text-transform: uppercase; letter-spacing: .8px;
  border-top: 1px solid #262626; margin-top: 2px;
  display: flex; align-items: center; gap: 5px;
}
.line-hdr:first-child { border-top: none; margin-top: 0; }
.ldots { display: flex; gap: 2px; margin-left: auto; }
.ldot  { width: 5px; height: 5px; border-radius: 50%; background: #2e2e2e; }
.ldot.done { background: currentColor; }
.ki {
  padding: 2px 6px; margin-bottom: 1px; border-radius: 3px;
  font-size: 11px; display: flex; align-items: center; gap: 5px;
  cursor: pointer;
}
.ki:hover { background: rgba(255,255,255,.06); }
.ki .dot { width: 7px; height: 7px; border-radius: 50%; flex-shrink: 0; }
.ki.cur    { background: rgba(255,152,0,.18); }
.ki.done   { opacity: .6; }
.ki.skip   { opacity: .3; font-style: italic; }
.ki.todo   { opacity: .2; }
.ki.active { background: rgba(100,200,255,.18) !important; border-left: 2px solid #29b6f6; padding-left: 4px; color: #7dd4f8; opacity: 1 !important; }
.ki-del {
  margin-left: auto; opacity: 0; flex-shrink: 0;
  border: none; background: none; color: #ff5555; cursor: pointer;
  font-size: 13px; line-height: 1; padding: 0 2px; border-radius: 2px;
}
.ki:hover .ki-del { opacity: .7; }
.ki-del:hover { opacity: 1 !important; background: rgba(255,50,50,.2); }
#hints {
  padding: 7px 10px 9px; border-top: 1px solid #2e2e2e; flex-shrink: 0;
  font-size: 10px; color: #4a4a4a; line-height: 1.9;
}
kbd {
  background: #2a2a2a; border: 1px solid #444;
  padding: 0 4px; border-radius: 3px; font-size: 10px; color: #999;
}
/* Line selection */
.line-hdr { cursor: pointer; }
.line-hdr:hover { background: #1f1f2f; }
.line-hdr.sel { background: #1a1a35; border-left: 3px solid #7070ff; padding-left: 3px; }
.line-hdr .line-key { font-size: 9px; color: #3a3a5a; margin-left: 4px; }
.line-hdr.sel .line-key { color: #7070ff; }
/* Camera setup modal */
#setup-modal {
  position: fixed; inset: 0; background: rgba(0,0,0,.88);
  display: flex; align-items: center; justify-content: center;
  z-index: 999;
}
#setup-modal.hidden { display: none; }
#setup-box {
  background: #1e1e1e; border: 1px solid #333; border-radius: 10px;
  padding: 22px 28px; max-width: 480px; width: 95%;
  color: #ddd; text-align: center;
}
#setup-box h2 { font-size: 16px; margin-bottom: 5px; color: #fff; }
#setup-box .setup-hint { font-size: 11px; color: #666; margin-bottom: 10px; }
#setup-cv-main { display: block; margin: 0 auto 8px; border-radius: 6px; cursor: crosshair; }
#setup-info { font-size: 12px; color: #888; margin-bottom: 12px; }
#setup-near-pos { font-weight: 600; }
#setup-confirm {
  padding: 7px 22px; background: #1a3a1a;
  border: 1px solid #4caf50; border-radius: 5px;
  color: #80d080; cursor: pointer; font-size: 12px; margin-right: 10px;
}
#setup-confirm:hover { background: #234a23; }
#setup-skip {
  background: none; border: none; color: #444; cursor: pointer;
  font-size: 11px; text-decoration: underline;
}
#setup-skip:hover { color: #777; }
#setup-reset {
  padding: 7px 14px; background: #2a1a0a;
  border: 1px solid #7a4a1a; border-radius: 5px;
  color: #c08040; cursor: pointer; font-size: 12px;
}
#setup-reset:hover { background: #3a2a0a; }
#setup-presets {
  display: flex; flex-wrap: wrap; gap: 4px;
  justify-content: center; margin: 6px 0 2px;
}
#setup-presets button {
  padding: 3px 7px; background: #1e2a1e;
  border: 1px solid #2a4a2a; border-radius: 3px;
  color: #6a9a6a; cursor: pointer; font-size: 10px;
}
#setup-presets button:hover { background: #243024; border-color: #4caf50; color: #90d090; }
</style>
</head>
<body>

<!-- Camera Setup Modal -->
<div id="setup-modal">
  <div id="setup-box">
    <h2 id="setup-title">📷 Step 1: カメラ位置の設定</h2>
    <div class="setup-hint">
      📷 アイコンをドラッグしてコート上の撮影位置を設定してください<br>
      <span style="color:#555">後から変更するには右パネルの「📷 位置を変更…」ボタンを使います</span>
    </div>
    <canvas id="setup-cv-main" width="420" height="270"></canvas>
    <div id="setup-presets"></div>
    <div id="setup-info">
      映像の中で NEAR サイドラインは <span id="setup-near-pos">RIGHT ▶</span> に表示されます
    </div>
    <div style="display:flex;gap:8px;justify-content:center;align-items:center;flex-wrap:wrap;">
      <button id="setup-confirm" onclick="confirmCamPos()">確認して開始 →</button>
      <button id="setup-reset"   onclick="resetCamPos()">↺ Reset</button>
      <button id="setup-skip"    onclick="closeModal()">スキップ</button>
    </div>
    <div style="margin-top:10px;font-size:10px;color:#444;line-height:1.7;text-align:left">
      <b style="color:#666">操作方法：</b><br>
      · 📷 をドラッグ → コート内外どこにでも置けます<br>
      · 視野コーン（水色）がカメラから見える範囲を示します<br>
      · センターラインをまたいだ位置でも設定可能です<br>
      · ↺ Reset でデフォルト位置（エンドライン中央下）に戻ります
    </div>
  </div>
</div>

<div id="sidebar">
  <h3>Frames</h3>
  <div id="frame-list"></div>
</div>

<div id="center">
  <div id="toolbar">
    <div>
      <div class="kp-name" id="kp-name">Loading…</div>
      <div class="kp-coord" id="kp-coord"></div>
    </div>
    <div class="spacer"></div>
    <button id="flip-btn" onclick="toggleFlip()">⇄ Flip X &nbsp;<kbd>F</kbd></button>
  </div>
  <div id="wrap"><canvas id="cv"></canvas></div>
  <div id="stbar">
    <span id="st-f">-</span><span id="st-k">-</span><span id="st-z">100%</span>
    <span class="hint"><kbd>Click dot</kbd>=edit · <kbd>Click empty</kbd>=add · <kbd>N</kbd>=skip · <kbd>BS</kbd>=undo/unskip · <kbd>←→</kbd>=nav · <kbd>F</kbd>=flip · <kbd>X</kbd>=skip frame · Scroll=zoom · Alt+drag=pan</span>
  </div>
</div>

<div id="panel">
  <h3>Court Overview</h3>
  <div id="cam-setup">
    <div class="cam-label">Near sideline in video</div>
    <div class="cam-btns">
      <button id="cam-right" onclick="setCamSide('right')">NEAR ▶ Right</button>
      <button id="cam-left"  onclick="setCamSide('left')">Left ◀ NEAR</button>
    </div>
    <button id="cam-open-btn" onclick="showModal()">📷 位置を変更…</button>
  </div>
  <div id="basket-sel">
    <button id="btn-left"   onclick="setBasket('left')">◄ L</button>
    <button id="btn-center" onclick="setBasket('center')">─ C ─</button>
    <button id="btn-right"  onclick="setBasket('right')">R ►</button>
  </div>
  <div id="ref-wrap">
    <div style="display:flex;gap:4px;margin-bottom:3px">
      <button id="orient-btn"  onclick="toggleCourtOrient()" style="flex:1;padding:2px 4px;background:#1e2a1e;border:1px solid #2a4a2a;border-radius:3px;color:#6a9a6a;cursor:pointer;font-size:9px">↔ 横</button>
      <button id="rotate-btn"  onclick="toggleCourtFlipH()"  style="flex:1;padding:2px 4px;background:#1e2a1e;border:1px solid #2a4a2a;border-radius:3px;color:#6a9a6a;cursor:pointer;font-size:9px">⟳ 90°</button>
    </div>
    <canvas id="rcv" width="206" height="282"></canvas>
  </div>
  <div id="kp-list"></div>
  <div id="hints">
    <kbd>1</kbd>–<kbd>7</kbd> Select line · <kbd>0</kbd> All lines<br>
    <kbd>Click dot</kbd> Move KP · <kbd>Click empty</kbd> Add KP<br>
    <kbd>N</kbd>/<kbd>Space</kbd> Skip KP · <kbd>BS</kbd> Undo<br>
    <kbd>F</kbd> Flip · <kbd>X</kbd> Skip frame · <kbd>←→</kbd> Nav
  </div>
</div>

<script>
const KPS = [
  {id:"end_near_side",  d:"Near sideline",   cx:+750, cy:0},
  {id:"end_far_side",   d:"Far sideline",    cx:-750, cy:0},
  {id:"end_near_lane",  d:"Near lane",       cx:+245, cy:0},
  {id:"end_far_lane",   d:"Far lane",        cx:-245, cy:0},
  {id:"ft_near_lane",   d:"Near lane",       cx:+245, cy:580},
  {id:"ft_far_lane",    d:"Far lane",        cx:-245, cy:580},
  {id:"ft_near_side",   d:"Near sideline",   cx:+750, cy:580},
  {id:"ft_far_side",    d:"Far sideline",    cx:-750, cy:580},
  {id:"center_near",    d:"Near sideline",   cx:+750, cy:1400},
  {id:"center_far",     d:"Far sideline",    cx:-750, cy:1400},
  {id:"ring",           d:"Basket ring",     cx:0,    cy:160},
];
const COLORS = [
  "#00e060","#00aaff","#ffa000","#cc00ff",
  "#00e0e0","#ff6600","#66ff00","#ff0066",
  "#6666ff","#ffee00"
];

// Court lines — ordered KP IDs + display color
const COURT_LINES = [
  {name:"Endline",        color:"#ffcc44", kps:["end_far_side","end_far_lane","end_near_lane","end_near_side"]},
  {name:"Freethrow Line", color:"#44ccff", kps:["ft_far_side","ft_far_lane","ft_near_lane","ft_near_side"]},
  {name:"Centerline",     color:"#ff88cc", kps:["center_far","center_near"]},
  {name:"Near Sideline",  color:"#88ff88", kps:["end_near_side","ft_near_side","center_near"]},
  {name:"Far Sideline",   color:"#ff8888", kps:["end_far_side","ft_far_side","center_far"]},
  {name:"Near Lane",      color:"#88ffee", kps:["end_near_lane","ft_near_lane"]},
  {name:"Far Lane",       color:"#ee88ff", kps:["end_far_lane","ft_far_lane"]},
  {name:"Basket",         color:"#ff8000", kps:["ring"]},
];

// Primary line for each KP (first occurrence in COURT_LINES)
const KP_LINE = {};
for (const l of COURT_LINES) for (const id of l.kps) if (!KP_LINE[id]) KP_LINE[id] = l;

let frames=[], anns={};
let fi=0, flipped=false;
let globalFlip = localStorage.getItem('globalFlip')==='true';
let selectedLine = null;
let activatedKP  = null;   // KP id explicitly selected from list (null = follow order)
let kpDragging   = null;   // annotation object being dragged
let courtHoriz   = localStorage.getItem('courtHoriz')==='true';
let courtFlipH   = localStorage.getItem('courtFlipH')==='true'; // flip near/far in horiz mode

// Camera position in FIBA court coords (persisted)
const CAM_DEFAULT = {x: 0, y: -600};  // below bottom endline center
let camPos = JSON.parse(localStorage.getItem('camPos') || 'null') || {...CAM_DEFAULT};
let setupDragging = false;

let zoom=1, panX=0, panY=0;
let img=null, imgW=1, imgH=1;
let dragging=false, dragBase={};
let mouse={x:-1,y:-1}, hoveredKP=null;

// Setup canvas — wide view to allow camera anywhere around court
// FIBA unit ≈ 1 cm; full court 2800×1500. View margin ±2400/−1800〜5600
const S_W=420, S_H=270;
const S_VX0=-2400, S_VX1=2400, S_VY0=-1800, S_VY1=5600;
const S_VW=S_VX1-S_VX0, S_VH=S_VY1-S_VY0;
function f2s(cx,cy){return[(cx-S_VX0)/S_VW*S_W, (1-(cy-S_VY0)/S_VH)*S_H];}
function s2f(sx,sy){return[S_VX0+(sx/S_W)*S_VW, S_VY0+(1-sy/S_H)*S_VH];}

// Preset camera positions {label, x, y}
const CAM_PRESETS = [
  {label:'エンドライン中央', x:0,    y:-600},
  {label:'右サイドライン',   x:1600, y:1400},
  {label:'左サイドライン',   x:-1600,y:1400},
  {label:'右下コーナー',     x:1200, y:-500},
  {label:'左下コーナー',     x:-1200,y:-500},
  {label:'反対エンドライン', x:0,    y:3400},
];

// Reference canvas transform (module-level so rcv click handler can use it)
function getRefTr() {
  const rw=rcv.width, rh=rcv.height;
  const mx=13, topM=7, camZone=36;
  const cw=rw-mx*2, totH=rh-topM-camZone, halfH=totH/2;
  const midY=topM+halfH, endY=topM+halfH*2;
  function trA(cx,cy){return[mx+(cx+750)/1500*cw, topM+halfH+(1-cy/1400)*halfH];}
  function trO(cx,cy){return[mx+(cx+750)/1500*cw, topM+(1-cy/1400)*halfH];}
  return {trA, trO, mx, topM, cw, halfH, midY, endY};
}

const cv   = document.getElementById('cv');
const ctx  = cv.getContext('2d');
const rcv  = document.getElementById('rcv');
const rctx = rcv.getContext('2d');
const wrap = document.getElementById('wrap');

// ── Init ──────────────────────────────────────────────────────
async function init() {
  [frames, anns] = await Promise.all([
    fetch('/api/frames').then(r=>r.json()),
    fetch('/api/annotations').then(r=>r.json()),
  ]);
  document.addEventListener('keydown', onKey);
  wrap.addEventListener('wheel', onWheel, {passive:false});
  cv.addEventListener('mousedown', onMouseDown);
  wrap.addEventListener('mousemove', onMouseMove);
  wrap.addEventListener('mouseup', onMouseUp);
  new ResizeObserver(()=>{ fitCv(); render(); }).observe(wrap);
  rcv.addEventListener('click', onRcvClick);
  updateCamSetup();
  const ob=document.getElementById('orient-btn');
  if(ob) ob.textContent=courtHoriz?'↕ 縦':'↔ 横';
  const rb=document.getElementById('rotate-btn');
  if(rb) rb.style.opacity=courtHoriz?'1':'0.4';
  loadFrame(0);
  // Setup canvas mouse events
  const sc = document.getElementById('setup-cv-main');
  if (sc) {
    sc.addEventListener('mousedown', onSetupMouseDown);
    sc.addEventListener('mousemove', onSetupMouseHover);
  }
  // Always show camera setup on load; pre-fill with saved position
  showModal();
}

// ── Frame ──────────────────────────────────────────────────────
function loadFrame(i) {
  fi = Math.max(0, Math.min(frames.length-1, i));
  flipped = globalFlip;
  document.getElementById('flip-btn').classList.toggle('on', flipped);
  zoom=1; panX=0; panY=0;
  img=new Image();
  img.onload=()=>{ imgW=img.naturalWidth; imgH=img.naturalHeight; fitCv(); render(); };
  img.src='/frame/'+frames[fi];
  updateSidebar(); updateKPList(); updateToolbar(); updateBasketBtns(); updateStatus();
}

function fitCv() { cv.width=wrap.clientWidth||800; cv.height=wrap.clientHeight||600; }

// ── Transforms ────────────────────────────────────────────────
function bs()  { return Math.min(cv.width/imgW, cv.height/imgH); }
function i2d(ix,iy) {
  const s=bs()*zoom;
  return [ix*s+(cv.width-imgW*s)/2+panX, iy*s+(cv.height-imgH*s)/2+panY];
}
function d2i(dx,dy) {
  const s=bs()*zoom;
  return [(dx-(cv.width-imgW*s)/2-panX)/s, (dy-(cv.height-imgH*s)/2-panY)/s];
}

// ── Main canvas render ────────────────────────────────────────
function render() {
  ctx.clearRect(0,0,cv.width,cv.height);
  ctx.fillStyle='#0f0f0f'; ctx.fillRect(0,0,cv.width,cv.height);
  if (!img) return;
  const s=bs()*zoom, ox=(cv.width-imgW*s)/2+panX, oy=(cv.height-imgH*s)/2+panY;
  ctx.drawImage(img,ox,oy,imgW*s,imgH*s);

  const fname=frames[fi];

  // Skipped overlay
  if (anns[fname]==='__skipped__') {
    ctx.fillStyle='rgba(0,0,0,.55)'; ctx.fillRect(0,0,cv.width,cv.height);
    ctx.textAlign='center';
    ctx.fillStyle='#2196f3'; ctx.font='bold 36px system-ui';
    ctx.fillText('SKIPPED', cv.width/2, cv.height/2-16);
    ctx.fillStyle='#666'; ctx.font='15px system-ui';
    ctx.fillText('Backspace to unskip', cv.width/2, cv.height/2+18);
    ctx.textAlign='left'; updateStatus(); return;
  }

  drawCourtLines(fname);

  // KP dots
  for (const ann of getAnns(fname)) {
    if (!ann.img) continue;
    const [dx,dy] = i2d(ann.img[0],ann.img[1]);
    const ci = KPS.findIndex(k=>k.id===ann.id);
    const col = COLORS[ci>=0?ci:0];
    const hov = (ann===hoveredKP);
    const isAct = (ann.id===activatedKP);
    const isDrg = (ann===kpDragging);
    const rad = (isDrg||hov)?11:isAct?9:7;
    ctx.beginPath(); ctx.arc(dx,dy,rad,0,Math.PI*2);
    ctx.fillStyle=col; ctx.fill();
    ctx.strokeStyle=isDrg?'#fff':isAct?'#29b6f6':hov?'#fff':'rgba(255,255,255,.7)';
    ctx.lineWidth=(isDrg||isAct)?2.5:hov?2:1.5; ctx.stroke();
    if (isDrg) {
      ctx.fillStyle='rgba(0,0,0,.8)';
      ctx.fillRect(dx+13,dy-19,110,20);
      ctx.fillStyle='#7dd4f8'; ctx.font='11px system-ui';
      ctx.fillText('Dragging…', dx+17,dy-4);
    } else if (hov) {
      ctx.fillStyle='rgba(0,0,0,.75)';
      ctx.fillRect(dx+13,dy-19,120,20);
      ctx.fillStyle='#fff'; ctx.font='11px system-ui';
      ctx.fillText('Drag to move', dx+17,dy-4);
    } else {
      ctx.fillStyle=isAct?'#29b6f6':col; ctx.font='10px system-ui';
      ctx.fillText(ann.id.replace('_',' ').split(' ').slice(0,2).join('_'), dx+9,dy-3);
    }
  }

  // Crosshair
  if (mouse.x>=0 && !hoveredKP) {
    ctx.strokeStyle='rgba(255,255,255,.18)'; ctx.lineWidth=1;
    ctx.beginPath();
    ctx.moveTo(mouse.x,0); ctx.lineTo(mouse.x,cv.height);
    ctx.moveTo(0,mouse.y); ctx.lineTo(cv.width,mouse.y);
    ctx.stroke();
  }
  drawRef(); updateStatus();
}

function drawCourtLines(fname) {
  const m = buildAnnMap(fname);
  for (const l of COURT_LINES) {
    const pts = l.kps.filter(id=>m[id]?.img).map(id=>i2d(m[id].img[0],m[id].img[1]));
    if (pts.length<2) continue;
    ctx.beginPath(); ctx.moveTo(...pts[0]);
    for (let i=1;i<pts.length;i++) ctx.lineTo(...pts[i]);
    ctx.strokeStyle=hexA(l.color,.5); ctx.lineWidth=1.5;
    ctx.setLineDash([5,4]); ctx.stroke(); ctx.setLineDash([]);
  }
}
function hexA(h,a) {
  const r=parseInt(h.slice(1,3),16),g=parseInt(h.slice(3,5),16),b=parseInt(h.slice(5,7),16);
  return `rgba(${r},${g},${b},${a})`;
}

// ── Full court reference diagram ───────────────────────────────
function drawRef() {
  const rw = rcv.width;
  const fname = frames[fi];
  const basket = getBasket(fname);
  const nearCx = flipped?-750:+750, farCx = flipped?+750:-750;
  const annBg = basket==='left'?'rgba(255,140,0,.18)':basket==='right'?'rgba(30,144,255,.18)':'rgba(0,60,0,.45)';

  let trAnn, trOth, f2r, rh, mx, topM;

  if (courtHoriz) {
    // ── Horizontal mode: two halves side-by-side ──────────────
    rcv.height = 116;
    rh = 116; mx = 8; topM = 5;
    const totW = rw-mx*2, halfW = totW/2, cH = rh-topM-6, midX = mx+halfW;
    const annOnLeft = basket !== 'right';
    function normN(cx){
      const base = flipped?(cx+750)/1500:(750-cx)/1500;
      return courtFlipH ? 1-base : base;
    }
    trAnn = annOnLeft
      ? (cx,cy) => [mx+(cy/1400)*halfW,     topM+normN(cx)*cH]
      : (cx,cy) => [midX+(1-cy/1400)*halfW, topM+normN(cx)*cH];
    trOth = annOnLeft
      ? (cx,cy) => [midX+(1-cy/1400)*halfW, topM+normN(cx)*cH]
      : (cx,cy) => [mx+(cy/1400)*halfW,     topM+normN(cx)*cH];
    f2r = function(cx, cy) {
      const canY = topM+normN(cx)*cH;
      let canX;
      if (annOnLeft) canX=cy<=1400?mx+(cy/1400)*halfW:midX+((cy-1400)/1400)*halfW;
      else           canX=cy<=1400?midX+(1-cy/1400)*halfW:midX-((cy-1400)/1400)*halfW;
      return [canX, canY];
    };
    rctx.clearRect(0,0,rw,rh);
    rctx.fillStyle='#0b180b'; rctx.fillRect(0,0,rw,rh);
    const annX=annOnLeft?mx:midX, othX=annOnLeft?midX:mx;
    rctx.fillStyle=annBg;              rctx.fillRect(annX,topM,halfW,cH);
    rctx.fillStyle='rgba(0,30,0,.35)'; rctx.fillRect(othX,topM,halfW,cH);
    rctx.strokeStyle='#3a5a3a'; rctx.lineWidth=1; rctx.strokeRect(mx,topM,totW,cH);
    rctx.beginPath(); rctx.moveTo(midX,topM); rctx.lineTo(midX,topM+cH);
    rctx.strokeStyle='#5a8a5a'; rctx.lineWidth=1.5; rctx.stroke(); rctx.lineWidth=1;
    function drawLaneH(trFn, dimmed) {
      rctx.strokeStyle=dimmed?'#1a3a1a':'#3a6a3a';
      const n1=trFn(-245,0),n2=trFn(245,0),f1=trFn(-245,580),f2_=trFn(245,580);
      rctx.beginPath();
      rctx.moveTo(n1[0],n1[1]); rctx.lineTo(f1[0],f1[1]);
      rctx.moveTo(n2[0],n2[1]); rctx.lineTo(f2_[0],f2_[1]);
      rctx.moveTo(f1[0],f1[1]); rctx.lineTo(f2_[0],f2_[1]);
      rctx.stroke();
      const c=trFn(0,160);
      rctx.beginPath(); rctx.arc(c[0],c[1],3,0,Math.PI*2);
      rctx.fillStyle=dimmed?'#664422':'#ff8000'; rctx.fill();
    }
    drawLaneH(trAnn,false); drawLaneH(trOth,true);
    // NEAR/FAR labels (top/bottom edges in horiz mode)
    rctx.font='bold 7px system-ui'; rctx.textAlign='center';
    const[npx,npy]=trAnn(nearCx,700),[fpx,fpy]=trAnn(farCx,700);
    rctx.fillStyle='rgba(80,255,80,.95)'; rctx.fillText('N',npx,npy+(npy<rh/2?9:-2));
    rctx.fillStyle='rgba(255,80,80,.95)'; rctx.fillText('F',fpx,fpy+(fpy<rh/2?9:-2));

  } else {
    // ── Vertical mode ────────────────────────────────────────
    rcv.height = 200;
    rh = 200; mx = 13; topM = 5;
    const camZone=28, cw=rw-mx*2, totH=rh-topM-camZone, halfH=totH/2, midY=topM+halfH;
    const trA_   =(cx,cy)=>[mx+(cx+750)/1500*cw, topM+halfH+(1-cy/1400)*halfH];
    // trTop_: cy=0 (endline) at TOP edge, cy=1400 (center) at DIVIDER
    const trTop_ =(cx,cy)=>[mx+(cx+750)/1500*cw, topM+(cy/1400)*halfH];
    // LEFT basket → annotated half at TOP (endline at top), RIGHT/default → bottom (endline at bottom)
    trAnn = basket==='left' ? trTop_ : trA_;
    trOth = basket==='left' ? trA_   : trTop_;
    f2r = function(cx, cy) {
      const sx=mx+(cx+750)/1500*cw;
      let sy;
      if (basket==='left') sy=cy<=1400?topM+(cy/1400)*halfH:topM+halfH+((cy-1400)/1400)*halfH;
      else                 sy=cy<=1400?topM+halfH+(1-cy/1400)*halfH:topM+(1-(cy-1400)/1400)*halfH;
      return [sx, sy];
    };
    rctx.clearRect(0,0,rw,rh);
    rctx.fillStyle='#0b180b'; rctx.fillRect(0,0,rw,rh);
    const annTopY=basket==='left'?topM:midY, othTopY=basket==='left'?midY:topM;
    rctx.fillStyle=annBg;              rctx.fillRect(mx,annTopY,cw,halfH);
    rctx.fillStyle='rgba(0,30,0,.35)'; rctx.fillRect(mx,othTopY,cw,halfH);
    rctx.strokeStyle='#3a5a3a'; rctx.lineWidth=1; rctx.strokeRect(mx,topM,cw,halfH*2);
    rctx.beginPath(); rctx.moveTo(mx,midY); rctx.lineTo(mx+cw,midY);
    rctx.strokeStyle='#5a8a5a'; rctx.lineWidth=1.5; rctx.stroke(); rctx.lineWidth=1;
    function drawHalfLane(trFn, dimmed) {
      rctx.strokeStyle=dimmed?'#1a3a1a':'#3a6a3a';
      const n1=trFn(-245,0),n2=trFn(245,0),f1=trFn(-245,580),f2_=trFn(245,580);
      rctx.beginPath();
      rctx.moveTo(n1[0],n1[1]); rctx.lineTo(f1[0],f1[1]);
      rctx.moveTo(n2[0],n2[1]); rctx.lineTo(f2_[0],f2_[1]);
      rctx.moveTo(f1[0],f1[1]); rctx.lineTo(f2_[0],f2_[1]);
      rctx.stroke();
      const c=trFn(0,160);
      rctx.beginPath(); rctx.arc(c[0],c[1],3,0,Math.PI*2);
      rctx.fillStyle=dimmed?'#664422':'#ff8000'; rctx.fill();
    }
    drawHalfLane(trAnn,false); drawHalfLane(trOth,true);
    // NEAR/FAR labels (left/right edges)
    rctx.font='bold 7.5px system-ui';
    const np=trAnn(nearCx,280), fp=trAnn(farCx,280);
    rctx.fillStyle='rgba(80,255,80,.95)';
    rctx.textAlign=nearCx>0?'right':'left';
    rctx.fillText('NEAR',np[0]+(nearCx>0?-2:2),np[1]);
    rctx.fillStyle='rgba(255,80,80,.95)';
    rctx.textAlign=farCx>0?'right':'left';
    rctx.fillText('FAR',fp[0]+(farCx>0?-2:2),fp[1]);
  }

  // ── FOV cone + camera icon (shared) ──────────────────────────
  {
    const[camRx,camRy]=f2r(camPos.x,camPos.y);
    const[tx,ty]=f2r(0,1400);
    const ddx=tx-camRx, ddy=ty-camRy, dlen=Math.hypot(ddx,ddy);
    if(dlen>1){
      const ndx=ddx/dlen, ndy=ddy/dlen;
      const fovR=30*Math.PI/180;
      function rot2(vx,vy,a){const c2=Math.cos(a),s2=Math.sin(a);return[vx*c2-vy*s2,vx*s2+vy*c2];}
      const[lx,ly]=rot2(ndx,ndy,fovR),[rx2,ry2]=rot2(ndx,ndy,-fovR);
      const L=Math.max(rh*2,dlen*2);
      rctx.beginPath(); rctx.moveTo(camRx,camRy);
      rctx.lineTo(camRx+lx*L,camRy+ly*L); rctx.lineTo(camRx+rx2*L,camRy+ry2*L);
      rctx.closePath();
      rctx.fillStyle='rgba(100,200,255,.09)'; rctx.fill();
      rctx.strokeStyle='rgba(100,200,255,.32)'; rctx.lineWidth=1; rctx.stroke();
    }
    const iconX=Math.max(8,Math.min(rw-8,camRx));
    const iconY=Math.max(8,Math.min(rh-8,camRy));
    const offCanvas=(camRx<0||camRx>rw||camRy<0||camRy>rh);
    if(offCanvas){
      const adx=camRx-iconX,ady=camRy-iconY,al=Math.hypot(adx,ady)||1;
      rctx.strokeStyle='rgba(100,200,255,.5)'; rctx.lineWidth=1; rctx.setLineDash([2,3]);
      rctx.beginPath(); rctx.moveTo(iconX,iconY);
      rctx.lineTo(iconX+adx/al*10,iconY+ady/al*10); rctx.stroke(); rctx.setLineDash([]);
    }
    rctx.beginPath(); rctx.arc(iconX,iconY,8,0,Math.PI*2);
    rctx.fillStyle='rgba(20,60,100,.85)'; rctx.fill();
    rctx.strokeStyle='rgba(100,200,255,.9)'; rctx.lineWidth=1.5; rctx.stroke();
    rctx.font='10px system-ui'; rctx.textAlign='center'; rctx.textBaseline='middle';
    rctx.fillText('📷',iconX,iconY); rctx.textBaseline='alphabetic';
  }

  // ── Basket labels ─────────────────────────────────────────────
  rctx.textAlign='center';
  if (basket==='center') {
    rctx.fillStyle='rgba(100,200,255,.6)'; rctx.font='bold 7px system-ui';
    const[clx,cly]=trAnn(0,1400);
    rctx.fillText('CENTER LINE ONLY',clx,cly+(courtHoriz?-3:-4));
    rctx.fillStyle='rgba(100,100,100,.35)'; rctx.font='7px system-ui';
    if(!courtHoriz) rctx.fillText('(basket not visible)',clx,cly+7);
  } else {
    const bColor=basket==='left'?'#ff9500':'#29b6f6';
    const bArrow=basket==='left'?'◄ ':'► ';
    const[bdx,bdy]=trAnn(0,160);
    rctx.beginPath(); rctx.arc(bdx,bdy,8,0,Math.PI*2);
    rctx.fillStyle=basket==='left'?'rgba(255,149,0,.3)':'rgba(41,182,246,.3)'; rctx.fill();
    rctx.beginPath(); rctx.arc(bdx,bdy,4,0,Math.PI*2);
    rctx.fillStyle=bColor; rctx.fill();
    rctx.strokeStyle='rgba(255,255,255,.6)'; rctx.lineWidth=1; rctx.stroke();
    rctx.fillStyle=bColor; rctx.font='bold 7px system-ui'; rctx.textAlign='center';
    const lbl_=trAnn(0,350);
    rctx.fillText(bArrow+(basket==='left'?'LEFT':'RIGHT'),lbl_[0],lbl_[1]);
    rctx.fillStyle='rgba(120,120,120,.4)'; rctx.font='7px system-ui';
    const oLbl_=trOth(0,350);
    rctx.fillText(basket==='left'?'RIGHT':'LEFT',oLbl_[0],oLbl_[1]);
  }

  // ── Line shortcut numbers ─────────────────────────────────────
  if (!courtHoriz) {
    const lineNumPos=[
      trAnn(0,30), trAnn(0,550), trAnn(0,1370),
      trAnn(nearCx+(nearCx>0?-30:30),700),
      trAnn(farCx+(farCx>0?-30:30),700),
      trAnn(flipped?-245:245,280),
      trAnn(flipped?245:-245,280),
    ];
    rctx.font='bold 7.5px system-ui'; rctx.textAlign='center';
    COURT_LINES.forEach((l,i)=>{
      const isSel=(selectedLine===i);
      const[nx2,ny2]=lineNumPos[i]||[0,0];
      rctx.globalAlpha=isSel?1:0.45;
      rctx.fillStyle=isSel?hexA(l.color,.25):'transparent';
      if(isSel){rctx.fillRect(nx2-9,ny2-9,18,12);}
      rctx.fillStyle=isSel?l.color:'rgba(220,220,220,.7)';
      rctx.fillText('['+(i+1)+']',nx2,ny2);
    });
    rctx.globalAlpha=1;
  }

  // ── KP dots + annotated line segments ─────────────────────────
  const annMap=buildAnnMap(fname);
  const ni=nextKpIdx(fname);
  rctx.setLineDash([]);
  for (const l of COURT_LINES) {
    const pts=l.kps.filter(id=>annMap[id]?.img).map(id=>{
      const kp=KPS.find(k=>k.id===id); if(!kp) return null;
      const cx2=flipped?-kp.cx:kp.cx; return trAnn(cx2,kp.cy);
    }).filter(Boolean);
    if(pts.length<2) continue;
    rctx.beginPath(); rctx.moveTo(...pts[0]);
    for(let i=1;i<pts.length;i++) rctx.lineTo(...pts[i]);
    rctx.strokeStyle=hexA(l.color,.75); rctx.lineWidth=2; rctx.stroke();
  }
  KPS.forEach((kp,i)=>{
    const cx2=flipped?-kp.cx:kp.cx;
    const[rx3,ry3]=trAnn(cx2,kp.cy);
    const col=COLORS[i];
    const ann=annMap[kp.id];
    const isCur=(i===ni),isAct=(kp.id===activatedKP);
    if(ann?.img){
      rctx.globalAlpha=.3; rctx.beginPath(); rctx.arc(rx3,ry3,9,0,Math.PI*2);
      rctx.fillStyle=col; rctx.fill();
      rctx.globalAlpha=1; rctx.beginPath(); rctx.arc(rx3,ry3,5,0,Math.PI*2);
      rctx.fillStyle=col; rctx.fill();
      rctx.strokeStyle='rgba(255,255,255,.9)'; rctx.lineWidth=1.5; rctx.stroke();
    } else if(isCur||isAct){
      rctx.globalAlpha=1; rctx.beginPath(); rctx.arc(rx3,ry3,7,0,Math.PI*2);
      rctx.fillStyle=col; rctx.fill();
      rctx.strokeStyle='rgba(255,255,255,.8)'; rctx.lineWidth=1; rctx.stroke();
      if(!courtHoriz){rctx.fillStyle='#fff';rctx.font='bold 7px system-ui';rctx.textAlign='left';rctx.fillText(kp.id,rx3+6,ry3+3);}
    } else {
      rctx.globalAlpha=ann&&ann.img===null?0.1:0.2;
      rctx.beginPath(); rctx.arc(rx3,ry3,3,0,Math.PI*2);
      rctx.fillStyle=col; rctx.fill();
    }
  });
  rctx.globalAlpha=1;

  // Annotated count badge (top strip)
  const doneN=KPS.filter(k=>annMap[k.id]?.img).length;
  if(doneN>0){
    rctx.fillStyle='rgba(0,0,0,.6)'; rctx.fillRect(mx,topM,rw-mx*2,12);
    rctx.fillStyle=doneN===KPS.length?'#80d080':'#ffcc44';
    rctx.font='bold 8px system-ui'; rctx.textAlign='center';
    rctx.fillText(`${doneN} / ${KPS.length} KPs`,(rw)/2,topM+9);
  }
  rctx.textAlign='left';
}

// ── Camera setup ─────────────────────────────────────────────
function calcFlipFromCam(cx, cy) {
  // Camera looks toward center of bottom half (cy=700)
  const tx=0, ty=700;
  const dx=tx-cx, dy=ty-cy, len=Math.hypot(dx,dy);
  if (len<10) return false;
  // Right vector (FIBA y-up, CW 90°): (dy/len, -dx/len) → x-component = dy/len
  // NEAR direction = +x; dot = dy/len; flip if negative (camera above center → looking down)
  return (dy/len) < 0;
}

function drawSetupMain() {
  const c = document.getElementById('setup-cv-main'); if (!c) return;
  const ctx = c.getContext('2d');
  ctx.clearRect(0, 0, S_W, S_H);
  ctx.fillStyle='#0a120a'; ctx.fillRect(0,0,S_W,S_H);

  // Distance grid: concentric circles from court center (0, 1400) at 1000cm (≈10m) intervals
  {
    const [gcx, gcy] = f2s(0, 1400);  // court center screen coords
    // 1000 FIBA units in screen pixels (x-axis)
    const r1000 = (1000 / S_VW) * S_W;
    ctx.setLineDash([2, 4]);
    for (let i = 1; i <= 4; i++) {
      const r = r1000 * i;
      ctx.beginPath(); ctx.arc(gcx, gcy, r, 0, Math.PI * 2);
      ctx.strokeStyle = `rgba(60,100,60,${0.4 - i*0.07})`; ctx.lineWidth = 0.8; ctx.stroke();
      // Distance label
      ctx.fillStyle = `rgba(60,100,60,${0.6 - i*0.1})`;
      ctx.font = '8px system-ui'; ctx.textAlign = 'left';
      ctx.fillText(`${i*10}m`, gcx + r + 2, gcy - 2);
    }
    ctx.setLineDash([]);
  }

  // Court fill (full court)
  const [lx,ty2] = f2s(-750,2800), [rx,by2] = f2s(750,0);
  ctx.fillStyle='#0d1f0d';
  ctx.fillRect(lx,ty2,rx-lx,by2-ty2);
  ctx.strokeStyle='#4a7a4a'; ctx.lineWidth=1.5;
  ctx.strokeRect(lx,ty2,rx-lx,by2-ty2);

  // Court lines helper
  function fline(x0,y0,x1,y1,col,w=1){
    const[ax,ay]=f2s(x0,y0),[bx,bby]=f2s(x1,y1);
    ctx.beginPath(); ctx.moveTo(ax,ay); ctx.lineTo(bx,bby);
    ctx.strokeStyle=col; ctx.lineWidth=w; ctx.stroke();
  }
  // Center line
  fline(-750,1400,750,1400,'#5a9a5a',1.5);
  // FT lines & lanes (both halves)
  fline(-245,0,-245,580,'#2a5a2a'); fline(245,0,245,580,'#2a5a2a');
  fline(-245,580,245,580,'#2a5a2a');
  fline(-245,2800,-245,2220,'#2a5a2a'); fline(245,2800,245,2220,'#2a5a2a');
  fline(-245,2220,245,2220,'#2a5a2a');
  // Baskets
  [[0,160],[0,2640]].forEach(([bx,by])=>{
    const[sx,sy]=f2s(bx,by);
    ctx.beginPath(); ctx.arc(sx,sy,4,0,Math.PI*2);
    ctx.fillStyle='#ff8000'; ctx.fill();
  });

  // FOV cone
  drawSetupFOV(ctx);

  // Draggable camera icon
  const[camSx,camSy]=f2s(camPos.x,camPos.y);
  ctx.beginPath(); ctx.arc(camSx,camSy,11,0,Math.PI*2);
  ctx.fillStyle='rgba(30,80,120,.8)'; ctx.fill();
  ctx.strokeStyle='rgba(100,200,255,.9)'; ctx.lineWidth=2; ctx.stroke();
  ctx.font='13px system-ui'; ctx.textAlign='center'; ctx.textBaseline='middle';
  ctx.fillText('📷',camSx,camSy);
  ctx.textBaseline='alphabetic'; ctx.textAlign='left';

  // NEAR/FAR labels (update based on camPos)
  const flip = calcFlipFromCam(camPos.x, camPos.y);
  const nearCx2 = flip ? -750 : 750;
  const farCx2  = flip ?  750 : -750;
  const[nx,ny]=f2s(nearCx2, 700),[fx,fy]=f2s(farCx2, 700);
  ctx.font='bold 9px system-ui';
  ctx.textAlign= nearCx2>0?'right':'left'; ctx.fillStyle='rgba(80,255,80,.95)';
  ctx.fillText('NEAR', nx+(nearCx2>0?-3:3), ny);
  ctx.textAlign= farCx2>0?'right':'left'; ctx.fillStyle='rgba(255,80,80,.95)';
  ctx.fillText('FAR',  fx+(farCx2>0?-3:3), fy);
  ctx.textAlign='left';

  // Update info label
  const nearPos = flip ? '◀ LEFT' : 'RIGHT ▶';
  const el = document.getElementById('setup-near-pos');
  if (el) { el.textContent=nearPos; el.style.color=flip?'#ff8080':'#29b6f6'; }
}

function drawSetupFOV(ctx) {
  const[sx,sy]=f2s(camPos.x,camPos.y);
  // Always look toward court center line (y=1400) — center of full court
  const tx=0, ty=1400;
  const dx=tx-camPos.x, dy=ty-camPos.y, len=Math.hypot(dx,dy);
  if(len<10) return;
  const ndx=dx/len, ndy=dy/len;
  // 30° half-angle = 60° total (typical broadcast camera)
  const fov=30*Math.PI/180;
  function rot(vx,vy,a){const c=Math.cos(a),s=Math.sin(a);return[vx*c-vy*s,vx*s+vy*c];}
  const[lx,ly]=rot(ndx,ndy,fov), [rx2,ry2]=rot(ndx,ndy,-fov);
  // Find intersection with court bounds
  function rayRect(px,py,vx,vy){
    // Use full court + margin (x -750..750, y -650..3450) so cone shows beyond court edge
    let tmin=5,tmax=1e9;
    if(Math.abs(vx)>.001){const t1=(-750-px)/vx,t2=(750-px)/vx;tmin=Math.max(tmin,Math.min(t1,t2));tmax=Math.min(tmax,Math.max(t1,t2));}
    else if(px<-750||px>750) return null;
    if(Math.abs(vy)>.001){const t1=(-650-py)/vy,t2=(3450-py)/vy;tmin=Math.max(tmin,Math.min(t1,t2));tmax=Math.min(tmax,Math.max(t1,t2));}
    else if(py<-650||py>3450) return null;
    if(tmax<tmin) return null;
    return[px+vx*tmin,py+vy*tmin];
  }
  const lp=rayRect(camPos.x,camPos.y,lx,ly);
  const rp=rayRect(camPos.x,camPos.y,rx2,ry2);
  if(!lp&&!rp) return;
  const[lsx,lsy]=f2s(lp?lp[0]:camPos.x+lx*3000,lp?lp[1]:camPos.y+ly*3000);
  const[rsx,rsy]=f2s(rp?rp[0]:camPos.x+rx2*3000,rp?rp[1]:camPos.y+ry2*3000);
  ctx.beginPath(); ctx.moveTo(sx,sy); ctx.lineTo(lsx,lsy); ctx.lineTo(rsx,rsy); ctx.closePath();
  ctx.fillStyle='rgba(100,200,255,.1)'; ctx.fill();
  ctx.strokeStyle='rgba(100,200,255,.35)'; ctx.lineWidth=1; ctx.stroke();
}

// Setup canvas mouse events
// Use window-level move/up so drag works even outside canvas bounds
function onSetupMouseDown(e) {
  const r = e.target.getBoundingClientRect();
  const mx = e.clientX-r.left, my = e.clientY-r.top;
  const [csx,csy] = f2s(camPos.x, camPos.y);
  if (Math.hypot(mx-csx, my-csy) < 22) {
    setupDragging = true;
    e.target.style.cursor = 'grabbing';
    e.preventDefault();
    window.addEventListener('mousemove', _setupDragMove);
    window.addEventListener('mouseup',   _setupDragEnd);
  }
}
function _setupDragMove(e) {
  if (!setupDragging) return;
  const c = document.getElementById('setup-cv-main');
  if (!c) return;
  const r = c.getBoundingClientRect();
  const sx = e.clientX-r.left, sy = e.clientY-r.top;
  camPos.x = S_VX0 + (sx/S_W)*S_VW;
  camPos.y = S_VY0 + (1-sy/S_H)*S_VH;
  drawSetupMain();
}
function _setupDragEnd() {
  setupDragging = false;
  const c = document.getElementById('setup-cv-main');
  if (c) c.style.cursor = '';
  window.removeEventListener('mousemove', _setupDragMove);
  window.removeEventListener('mouseup',   _setupDragEnd);
}
// Cursor hint: grab when hovering over camera icon
function onSetupMouseHover(e) {
  if (setupDragging) return;
  const r = e.target.getBoundingClientRect();
  const mx = e.clientX-r.left, my = e.clientY-r.top;
  const [csx,csy] = f2s(camPos.x, camPos.y);
  e.target.style.cursor = Math.hypot(mx-csx,my-csy)<22 ? 'grab' : 'crosshair';
}

function setCamSide(side) {
  globalFlip = (side === 'left');
  localStorage.setItem('globalFlip', globalFlip);
  updateCamSetup();
  flipped = globalFlip;
  document.getElementById('flip-btn').classList.toggle('on', flipped);
  updateKPList(); updateToolbar(); render();
}
function resetCamPos() {
  camPos = {...CAM_DEFAULT};
  drawSetupMain();
}
function setPresetCam(x, y) {
  camPos = {x, y};
  drawSetupMain();
}
function confirmCamPos() {
  globalFlip = calcFlipFromCam(camPos.x, camPos.y);
  localStorage.setItem('globalFlip', globalFlip);
  localStorage.setItem('camPos', JSON.stringify(camPos));
  updateCamSetup();
  flipped = globalFlip;
  document.getElementById('flip-btn').classList.toggle('on', flipped);
  updateKPList(); updateToolbar(); render();
  closeModal();
}
function updateCamSetup() {
  document.getElementById('cam-right').classList.toggle('active', !globalFlip);
  document.getElementById('cam-left').classList.toggle('active',  globalFlip);
}
function showModal() {
  const hasSaved = localStorage.getItem('camPos') !== null;
  const title = document.getElementById('setup-title');
  const btn   = document.getElementById('setup-confirm');
  if (title) title.textContent = hasSaved ? '📷 カメラ位置の確認' : '📷 Step 1: カメラ位置の設定';
  if (btn)   btn.textContent   = hasSaved ? '← この位置で開始'   : '確認して開始 →';
  // Build preset buttons
  const el = document.getElementById('setup-presets');
  if (el) {
    el.innerHTML = '<span style="font-size:10px;color:#555;align-self:center">プリセット:</span>';
    for (const p of CAM_PRESETS) {
      const b = document.createElement('button');
      b.textContent = p.label;
      b.onclick = () => setPresetCam(p.x, p.y);
      el.appendChild(b);
    }
  }
  document.getElementById('setup-modal').classList.remove('hidden');
  drawSetupMain();
}
function closeModal() { document.getElementById('setup-modal').classList.add('hidden'); }

function toggleCourtOrient() {
  courtHoriz = !courtHoriz;
  localStorage.setItem('courtHoriz', courtHoriz);
  const btn = document.getElementById('orient-btn');
  if (btn) btn.textContent = courtHoriz ? '↕ 縦' : '↔ 横';
  const rb2 = document.getElementById('rotate-btn');
  if (rb2) rb2.style.opacity = courtHoriz ? '1' : '0.4';
  drawRef();
}
function toggleCourtFlipH() {
  courtFlipH = !courtFlipH;
  localStorage.setItem('courtFlipH', courtFlipH);
  drawRef();
}

// ── Line selection ────────────────────────────────────────────
function selectLine(li) {
  selectedLine = (selectedLine === li) ? null : li;
  updateKPList(); updateToolbar(); render();
}

// Click on reference canvas → select line
function onRcvClick(e) {
  const r = rcv.getBoundingClientRect();
  const px = e.clientX-r.left, py = e.clientY-r.top;
  const {trA} = getRefTr();
  function ptSegDist(qx,qy,ax,ay,bx,by){
    const dx=bx-ax,dy=by-ay,l2=dx*dx+dy*dy;
    if(l2<1)return Math.hypot(qx-ax,qy-ay);
    const t=Math.max(0,Math.min(1,((qx-ax)*dx+(qy-ay)*dy)/l2));
    return Math.hypot(qx-(ax+t*dx),qy-(ay+t*dy));
  }
  let bestLi=-1, bestD=14;
  for(let li=0;li<COURT_LINES.length;li++){
    const ids=COURT_LINES[li].kps;
    for(let k=0;k<ids.length-1;k++){
      const k1=KPS.find(k=>k.id===ids[k]),k2=KPS.find(k=>k.id===ids[k+1]);
      if(!k1||!k2)continue;
      const[ax,ay]=trA(flipped?-k1.cx:k1.cx,k1.cy);
      const[bx,by]=trA(flipped?-k2.cx:k2.cx,k2.cy);
      const d=ptSegDist(px,py,ax,ay,bx,by);
      if(d<bestD){bestD=d;bestLi=li;}
    }
  }
  if(bestLi>=0)selectLine(bestLi);
}

// ── Basket selector ───────────────────────────────────────────
function getBasket(fname) { return anns[fname+':basket'] || 'left'; }
function setBasket(side) {
  const fname = frames[fi];
  anns[fname+':basket'] = side;
  updateBasketBtns(); save(); drawRef();
}
function updateBasketBtns() {
  const b = getBasket(frames[fi]);
  document.getElementById('btn-left').classList.toggle('active',   b==='left');
  document.getElementById('btn-center').classList.toggle('active', b==='center');
  document.getElementById('btn-right').classList.toggle('active',  b==='right');
}

// ── Annotation helpers ────────────────────────────────────────
function buildAnnMap(fname) {
  const m={};
  for (const a of getAnns(fname)) m[a.id]=a;
  return m;
}
function getAnns(fname) { const v=anns[fname]; return Array.isArray(v)?v:[]; }
function frameStatus(fname) {
  if (anns[fname]==='__skipped__') return 'skip';
  if (Array.isArray(anns[fname])&&anns[fname].length) return 'done';
  return 'todo';
}
function nextKpIdx(fname) {
  const done=new Set(getAnns(fname).map(a=>a.id));
  const lineFilter = selectedLine !== null ? new Set(COURT_LINES[selectedLine].kps) : null;
  for (let i=0;i<KPS.length;i++) {
    if (done.has(KPS[i].id)) continue;
    if (lineFilter && !lineFilter.has(KPS[i].id)) continue;
    return i;
  }
  return KPS.length;
}
function findNearKP(fname,dx,dy,thr=14) {
  let best=null, bd=thr;
  for (const ann of getAnns(fname)) {
    if (!ann.img) continue;
    const [ax,ay]=i2d(ann.img[0],ann.img[1]);
    const d=Math.hypot(dx-ax,dy-ay);
    if (d<bd){bd=d;best=ann;}
  }
  return best;
}

async function save() {
  await fetch('/api/annotations',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(anns)});
  updateSidebar();
}
function confirmKP(ix,iy) {
  const fname=frames[fi];
  if (activatedKP!==null) {
    const kp=KPS.find(k=>k.id===activatedKP);
    if (!kp) { activatedKP=null; return; }
    const cx=flipped?-kp.cx:kp.cx;
    if (!Array.isArray(anns[fname])) anns[fname]=[];
    const existing=anns[fname].find(a=>a.id===activatedKP);
    if (existing) {
      existing.img=[Math.round(ix),Math.round(iy)];
      existing.court=[cx,kp.cy];
    } else {
      anns[fname].push({id:kp.id,img:[Math.round(ix),Math.round(iy)],court:[cx,kp.cy]});
    }
    activatedKP=null;
    save(); updateKPList(); updateToolbar(); render();
    return;
  }
  const ni=nextKpIdx(fname);
  if (ni>=KPS.length) return;
  const kp=KPS[ni], cx=flipped?-kp.cx:kp.cx;
  if (!Array.isArray(anns[fname])) anns[fname]=[];
  anns[fname].push({id:kp.id,img:[Math.round(ix),Math.round(iy)],court:[cx,kp.cy]});
  save(); updateKPList(); updateToolbar(); render();
}
function editKP(ann,ix,iy) {
  ann.img=[Math.round(ix),Math.round(iy)]; save(); render();
}
function deleteKP(fname, kpId) {
  if (!Array.isArray(anns[fname])) return;
  anns[fname]=anns[fname].filter(a=>a.id!==kpId);
  if (!anns[fname].length) delete anns[fname];
  if (activatedKP===kpId) activatedKP=null;
  save(); updateKPList(); updateToolbar(); render();
}
function skipKP() {
  const fname=frames[fi], ni=nextKpIdx(fname);
  if (ni>=KPS.length) return;
  const kp=KPS[ni], cx=flipped?-kp.cx:kp.cx;
  if (!Array.isArray(anns[fname])) anns[fname]=[];
  anns[fname].push({id:kp.id,img:null,court:[cx,kp.cy]});
  save(); updateKPList(); updateToolbar(); render();
}
function undoLast() {
  const fname=frames[fi];
  if (anns[fname]==='__skipped__') {
    delete anns[fname];
    save(); updateSidebar(); updateKPList(); updateToolbar(); render(); return;
  }
  if (!Array.isArray(anns[fname])||!anns[fname].length) return;
  anns[fname].pop();
  if (!anns[fname].length) delete anns[fname];
  save(); updateKPList(); updateToolbar(); render();
}
function skipFrame() {
  anns[frames[fi]]='__skipped__'; save(); updateSidebar(); render();
  if (fi<frames.length-1) loadFrame(fi+1);
}

// ── UI ────────────────────────────────────────────────────────
function updateSidebar() {
  const el=document.getElementById('frame-list'); el.innerHTML='';
  frames.forEach((f,i)=>{
    const d=document.createElement('div');
    d.className='fi '+frameStatus(f)+(i===fi?' sel':'');
    d.textContent=f.replace('frame_','').replace('.jpg','');
    d.onclick=()=>loadFrame(i); el.appendChild(d);
  });
  el.querySelector('.sel')?.scrollIntoView({block:'nearest'});
}

function updateKPList() {
  const el=document.getElementById('kp-list'); el.innerHTML='';
  const fname=frames[fi];
  const annMap=buildAnnMap(fname);
  const ni=nextKpIdx(fname);
  const rendered=new Set();

  for (let li=0; li<COURT_LINES.length; li++) {
    const lineGroup=COURT_LINES[li];
    const lineKPs=lineGroup.kps.filter(id=>!rendered.has(id)&&KPS.some(k=>k.id===id));
    if (!lineKPs.length) continue;

    // Line header with completion dots + key shortcut
    const hdr=document.createElement('div');
    const isSel=(selectedLine===li);
    hdr.className='line-hdr'+(isSel?' sel':'');
    hdr.title=`Click or press ${li+1} to focus this line`;
    hdr.innerHTML=`<span>${lineGroup.name}</span><span class="line-key">[${li+1}]</span>`;
    hdr.addEventListener('click', ()=>selectLine(li));
    const dots=document.createElement('div'); dots.className='ldots';
    for (const id of lineKPs) {
      const dot=document.createElement('div');
      const ann=annMap[id];
      const isDone=!!ann?.img;
      dot.className='ldot'+(isDone?' done':'');
      dot.style.color=lineGroup.color;
      dots.appendChild(dot);
    }
    hdr.appendChild(dots); el.appendChild(hdr);

    for (const kpId of lineKPs) {
      rendered.add(kpId);
      const i=KPS.findIndex(k=>k.id===kpId); if (i<0) continue;
      const kp=KPS[i], ann=annMap[kpId];
      const d=document.createElement('div');
      let cls='ki ';
      if      (activatedKP===kpId)    cls+='active';
      else if (ann?.img)              cls+='done';
      else if (ann&&ann.img===null)   cls+='skip';
      else if (i===ni)                cls+='cur';
      else                            cls+='todo';
      d.className=cls;
      const dot=document.createElement('div');
      dot.className='dot'; dot.style.background=COLORS[i];
      const lbl=document.createElement('span');
      const icon=activatedKP===kpId?'◎ ':ann?.img?'✓ ':(ann&&ann.img===null)?'– ':i===ni?'▶ ':'';
      const cx=flipped?-kp.cx:kp.cx;
      lbl.textContent=`${icon}${kp.id}`;
      lbl.title=`クリックして選択 | court (${cx}, ${kp.cy}) cm`;
      d.addEventListener('click', (e)=>{
        e.stopPropagation();
        activatedKP=(activatedKP===kpId)?null:kpId;
        updateKPList(); updateToolbar(); render();
      });
      d.appendChild(dot); d.appendChild(lbl);
      if (ann) {
        const del=document.createElement('button');
        del.className='ki-del'; del.textContent='×'; del.title='このKPを削除';
        del.addEventListener('click',(e)=>{ e.stopPropagation(); deleteKP(frames[fi],kpId); });
        d.appendChild(del);
      }
      el.appendChild(d);
    }
  }
}

function updateToolbar() {
  const fname=frames[fi];
  if (anns[fname]==='__skipped__') {
    document.getElementById('kp-name').textContent='Frame skipped';
    document.getElementById('kp-coord').textContent='Backspace to unskip';
    return;
  }
  if (activatedKP!==null) {
    const kp=KPS.find(k=>k.id===activatedKP);
    const existing=buildAnnMap(fname)[activatedKP];
    const action=existing?.img?'Move':'Place';
    document.getElementById('kp-name').textContent=`◎ ${action}: ${activatedKP}`;
    document.getElementById('kp-coord').textContent=`Click canvas to ${action==='Move'?'move':'place'} · ESC or click again to cancel`;
    return;
  }
  const ni=nextKpIdx(fname);
  const lineTag = selectedLine!==null ? ` [${COURT_LINES[selectedLine].name}]` : '';
  if (ni<KPS.length) {
    const kp=KPS[ni], cx=flipped?-kp.cx:kp.cx;
    document.getElementById('kp-name').textContent=`KP ${ni+1}/${KPS.length}: ${kp.id}${lineTag}`;
    document.getElementById('kp-coord').textContent=`court (${cx}, ${kp.cy}) cm${flipped?' [FLIPPED]':''}`;
  } else {
    const doneMsg = selectedLine!==null ? `${COURT_LINES[selectedLine].name} done ✓` : 'All KPs done ✓';
    document.getElementById('kp-name').textContent=doneMsg;
    document.getElementById('kp-coord').textContent='→ 0=all lines, next frame';
  }
}
function updateStatus() {
  document.getElementById('st-f').textContent=`${fi+1}/${frames.length}: ${frames[fi]}`;
  const ni=anns[frames[fi]]==='__skipped__'?0:nextKpIdx(frames[fi]);
  document.getElementById('st-k').textContent=`${ni}/${KPS.length} KPs`;
  document.getElementById('st-z').textContent=`${Math.round(zoom*100)}%`;
}

// ── Events ────────────────────────────────────────────────────
function toggleFlip() {
  flipped=!flipped;
  document.getElementById('flip-btn').classList.toggle('on',flipped);
  updateKPList(); updateToolbar(); render();
}
function onKey(e) {
  if (e.target!==document.body&&e.target!==document.documentElement) return;
  if      (e.key==='ArrowRight'||e.key==='d'||e.key==='s') loadFrame(fi+1);
  else if (e.key==='ArrowLeft' ||e.key==='a')               loadFrame(fi-1);
  else if (e.key==='n'||e.key===' ') { e.preventDefault(); skipKP(); }
  else if (e.key==='Backspace')       undoLast();
  else if (e.key==='x'||e.key==='X') skipFrame();
  else if (e.key==='f'||e.key==='F') toggleFlip();
  else if (e.key==='0'||e.key==='Escape') { selectedLine=null; activatedKP=null; updateKPList(); updateToolbar(); render(); }
  else if (e.key>='1'&&e.key<='7') {
    const li=parseInt(e.key)-1;
    if (li<COURT_LINES.length) { selectLine(li); }
  }
}
function onWheel(e) {
  e.preventDefault();
  zoom=Math.max(.3,Math.min(10,zoom+(e.deltaY>0?-.12:.12))); render();
}
function onMouseDown(e) {
  if (e.button===1||(e.button===0&&e.altKey)) {
    dragging=true; dragBase={x:e.clientX,y:e.clientY,px:panX,py:panY};
    return;
  }
  if (e.button===0) {
    const r=wrap.getBoundingClientRect();
    const dx=e.clientX-r.left, dy=e.clientY-r.top;
    const fname=frames[fi];
    if (anns[fname]==='__skipped__') return;
    const nearby=findNearKP(fname,dx,dy);
    if (nearby) {
      kpDragging=nearby;
      cv.style.cursor='grabbing';
      e.preventDefault();
      window.addEventListener('mousemove',_kpDragMove);
      window.addEventListener('mouseup',  _kpDragEnd);
    }
  }
}
function _kpDragMove(e) {
  if (!kpDragging) return;
  const r=wrap.getBoundingClientRect();
  const [ix,iy]=d2i(e.clientX-r.left, e.clientY-r.top);
  kpDragging.img=[Math.round(ix),Math.round(iy)];
  render();
}
function _kpDragEnd(e) {
  if (!kpDragging) return;
  const r=wrap.getBoundingClientRect();
  const [ix,iy]=d2i(e.clientX-r.left, e.clientY-r.top);
  kpDragging.img=[Math.round(ix),Math.round(iy)];
  kpDragging=null;
  cv.style.cursor='';
  window.removeEventListener('mousemove',_kpDragMove);
  window.removeEventListener('mouseup',  _kpDragEnd);
  save(); render();
}
function onMouseMove(e) {
  const r=wrap.getBoundingClientRect();
  mouse={x:e.clientX-r.left,y:e.clientY-r.top};
  if (dragging){ panX=dragBase.px+(e.clientX-dragBase.x); panY=dragBase.py+(e.clientY-dragBase.y); }
  if (kpDragging) return;
  const fname=frames[fi];
  const prev=hoveredKP;
  hoveredKP=(anns[fname]!=='__skipped__')?findNearKP(fname,mouse.x,mouse.y):null;
  cv.style.cursor=hoveredKP?'grab':(activatedKP?'cell':'crosshair');
  if (hoveredKP!==prev||dragging) render();
}
function onMouseUp(e) {
  if (dragging){ dragging=false; return; }
  if (kpDragging) return;  // handled by _kpDragEnd
  if (e.button!==0) return;
  const r=wrap.getBoundingClientRect();
  const dx=e.clientX-r.left, dy=e.clientY-r.top;
  const fname=frames[fi];
  if (anns[fname]==='__skipped__') return;
  if (findNearKP(fname,dx,dy)) return;  // dragging handles repositioning
  const [ix,iy]=d2i(dx,dy);
  if (ix<0||iy<0||ix>imgW||iy>imgH) return;
  confirmKP(ix,iy);
}

init();
</script>
</body>
</html>"""


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args): pass

    def do_GET(self):
        p = urlparse(self.path).path
        if p == '/':
            self._send(200, 'text/html; charset=utf-8', HTML.encode())
        elif p == '/api/frames':
            fs = sorted(f for f in os.listdir(FRAME_DIR) if f.lower().endswith('.jpg'))
            self._json(fs)
        elif p == '/api/annotations':
            data = {}
            if os.path.exists(ANNOTATIONS):
                with open(ANNOTATIONS) as f:
                    data = json.load(f)
            self._json(data)
        elif p.startswith('/frame/'):
            fpath = os.path.join(FRAME_DIR, p[7:])
            if os.path.isfile(fpath):
                with open(fpath, 'rb') as f: body = f.read()
                self._send(200, 'image/jpeg', body)
            else:
                self.send_error(404)
        else:
            self.send_error(404)

    def do_POST(self):
        if urlparse(self.path).path == '/api/annotations':
            n   = int(self.headers.get('Content-Length', 0))
            data = json.loads(self.rfile.read(n))
            with open(ANNOTATIONS, 'w') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            print(f"\r  [saved] {len(data)} entries    ", end='', flush=True)
            self._json({'ok': True})
        else:
            self.send_error(404)

    def _send(self, code, ct, body):
        self.send_response(code)
        self.send_header('Content-Type', ct)
        self.send_header('Content-Length', len(body))
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj):
        body = json.dumps(obj, ensure_ascii=False).encode()
        self._send(200, 'application/json', body)


def _open_browser():
    import time; time.sleep(0.6)
    webbrowser.open(f'http://localhost:{PORT}')


if __name__ == '__main__':
    if not os.path.isdir(FRAME_DIR):
        print(f"[ERROR] {FRAME_DIR} not found"); raise SystemExit(1)
    threading.Thread(target=_open_browser, daemon=True).start()
    server = HTTPServer(('localhost', PORT), Handler)
    print(f"Court Annotator  →  http://localhost:{PORT}")
    print("Ctrl+C to stop.\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
