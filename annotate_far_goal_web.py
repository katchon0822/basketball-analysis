#!/usr/bin/env python3
"""
annotate_far_goal_web.py — Court landmark annotator (browser UI)

Landmarks (all editable):
  near_ring       → near_ring_image_xy   (near basket rim center)
  far_ring        → far_ring_image_xy    (far basket rim center)
  center_circle   → center_circle_image_xy (center circle center)

Click empty space : place selected landmark
Click a mark      : delete it
Alt + drag        : pan   |  Scroll : zoom
T : court overlay |  R : rotate minimap
S : save & quit   |  Esc : cancel
"""

import cv2, json, numpy as np, argparse, webbrowser, threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

SIDELINE=750; HALF_Y=1432; FULL_Y=HALF_Y*2; BASKET_Y=160
FT_Y=580; LANE_X=245; PT3_CX=665; PT3_CY=420; PT3_R=705; CENTER_R=180

PORT=8770
prof=None; cap=None; total=0; H_mat=None; profile_path=""

LANDMARKS = [
    {"key":"near_ring",     "label":"Near Goal",     "field":"near_ring_image_xy",     "color_bgr":(255,100,60),  "color_hex":"#4488ff"},
    {"key":"far_ring",      "label":"Far Goal",      "field":"far_ring_image_xy",      "color_bgr":(60,130,255),  "color_hex":"#ff8822"},
    {"key":"center_circle", "label":"Center Circle", "field":"center_circle_image_xy", "color_bgr":(255,200,0),   "color_hex":"#22bbff"},
]


def get_frame(fi:int, overlay:bool)->bytes:
    cap.set(cv2.CAP_PROP_POS_FRAMES, max(0,min(fi,total-1)))
    ret,frame=cap.read()
    if not ret: frame=np.zeros((360,640,3),dtype=np.uint8)
    if overlay and H_mat is not None: _draw_overlay(frame)
    _,buf=cv2.imencode(".jpg",frame,[cv2.IMWRITE_JPEG_QUALITY,88])
    return bytes(buf)


def _draw_overlay(frame):
    H_px,W=frame.shape[:2]
    def proj(cx,cy):
        pt=np.array([[[float(cx),float(cy)]]],dtype=np.float64)
        out=cv2.perspectiveTransform(pt,H_mat)
        return (int(out[0,0,0]),int(out[0,0,1]))
    def seg(x1,y1,x2,y2,col,t=1):
        p1,p2=proj(x1,y1),proj(x2,y2)
        if all(0<=p[0]<W and 0<=p[1]<H_px for p in (p1,p2)):
            cv2.line(frame,p1,p2,col,t,cv2.LINE_AA)
    WH=(170,170,170); BL=(100,190,255); OR=(40,210,255)
    seg(-SIDELINE,0,SIDELINE,0,WH,2); seg(-SIDELINE,FULL_Y,SIDELINE,FULL_Y,WH,2)
    seg(-SIDELINE,0,-SIDELINE,HALF_Y,WH,2); seg(SIDELINE,0,SIDELINE,HALF_Y,WH,2)
    seg(-SIDELINE,HALF_Y,SIDELINE,HALF_Y,WH,1)
    seg(-LANE_X,0,-LANE_X,FT_Y,BL); seg(LANE_X,0,LANE_X,FT_Y,BL)
    seg(-LANE_X,FT_Y,LANE_X,FT_Y,BL)
    seg(-PT3_CX,0,-PT3_CX,PT3_CY,OR); seg(PT3_CX,0,PT3_CX,PT3_CY,OR)
    arc=[]
    for d in range(-115,116,3):
        r=np.radians(d); x=PT3_R*np.sin(r); y=BASKET_Y+PT3_R*np.cos(r)
        if abs(x)<=PT3_CX:
            p=proj(x,y)
            if 0<=p[0]<W and 0<=p[1]<H_px: arc.append(p)
    for i in range(len(arc)-1): cv2.line(frame,arc[i],arc[i+1],OR,1,cv2.LINE_AA)
    cc=proj(0,HALF_Y)
    if 0<=cc[0]<W and 0<=cc[1]<H_px:
        cv2.circle(frame,cc,max(1,int(CENTER_R*abs(proj(CENTER_R,HALF_Y)[0]-cc[0])/CENTER_R)),WH,1,cv2.LINE_AA)


HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Court Landmark Annotator</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{display:flex;flex-direction:column;height:100vh;background:#141414;color:#ddd;
  font-family:system-ui,sans-serif;font-size:13px;overflow:hidden;user-select:none}
#topbar{display:flex;align-items:center;gap:8px;padding:5px 12px;
  background:#1c1c1c;border-bottom:1px solid #2a2a2a;flex-shrink:0}
#topbar h2{font-size:13px;color:#fff;font-weight:600}
.sep{color:#2e2e2e}
.tbtn{padding:4px 11px;border-radius:4px;cursor:pointer;font-size:12px;
  border:1px solid #333;background:#222;color:#aaa;transition:all .15s}
.tbtn:hover{background:#2a2a2a;color:#ddd}
.tbtn.on{background:#0d2a3a;border-color:#29b6f6;color:#7dd4f8}
#save-btn{background:#1a3a1a;border-color:#4c9;color:#7d9}
#save-btn:hover{background:#245024}
#cancel-btn{color:#e88;border-color:#844}
.spacer{flex:1}
#status-lbl{font-size:11px;color:#666;max-width:380px;white-space:nowrap;overflow:hidden}

#main{display:flex;flex:1;min-height:0}
#canvas-wrap{flex:1;position:relative;background:#0a0a0a;overflow:hidden;cursor:crosshair}
#cv{position:absolute;top:0;left:0}

#sidebar{width:230px;background:#1a1a1a;border-left:1px solid #222;
  display:flex;flex-direction:column;gap:7px;padding:8px;overflow-y:auto;flex-shrink:0}
.card{background:#1e1e1e;border:1px solid #272727;border-radius:6px;padding:8px}
.card-hdr{display:flex;align-items:center;margin-bottom:7px}
.card-hdr h3{font-size:10px;color:#555;text-transform:uppercase;letter-spacing:1px;flex:1}
.card-hdr button{padding:2px 7px;font-size:10px;border-radius:3px;cursor:pointer;
  background:#222;border:1px solid #333;color:#777;transition:all .15s}
.card-hdr button:hover{color:#bbb;border-color:#555}

/* landmark buttons */
.lm-btn{width:100%;text-align:left;padding:7px 9px;margin-bottom:3px;
  border-radius:5px;cursor:pointer;font-size:12px;
  border:1px solid #272727;background:#181818;color:#777;
  display:flex;align-items:center;gap:8px;transition:all .15s}
.lm-btn:hover{background:#212121;color:#bbb}
.lm-btn.active{background:#1e1e28;border-color:var(--lm-col);color:var(--lm-col)}
.lm-dot{width:9px;height:9px;border-radius:50%;flex-shrink:0;background:#333}
.lm-dot.set{background:var(--lm-col)}
.lm-status{margin-left:auto;font-size:10px;opacity:.55}

#minimap-cv{display:block;width:100%;border-radius:3px}

.coord-row{display:flex;justify-content:space-between;font-size:11px;margin-bottom:3px}
.lbl{color:#555}.val{font-family:monospace;color:#999}
.val.set{color:#7d9}.val.ref{color:#68f}

.hint-row{font-size:11px;color:#505050;line-height:2.1}
kbd{background:#252525;border:1px solid #3a3a3a;padding:0 4px;
  border-radius:3px;font-size:10px;color:#888}

#bottombar{display:flex;align-items:center;gap:7px;padding:4px 10px;
  background:#1a1a1a;border-top:1px solid #222;flex-shrink:0}
#frame-slider{flex:1;accent-color:#29b6f6}
#frame-lbl{font-size:11px;color:#555;min-width:90px;text-align:right}
.nav-btn{padding:2px 9px;background:#1e1e1e;border:1px solid #2a2a2a;
  border-radius:3px;color:#666;cursor:pointer;font-size:12px}
.nav-btn:hover{color:#bbb;border-color:#444}
</style>
</head>
<body>

<div id="topbar">
  <h2>Court Landmark Annotator</h2>
  <span class="sep">|</span>
  <button id="overlay-btn" class="tbtn" onclick="toggleOverlay()">Overlay: OFF</button>
  <button id="undo-btn"    class="tbtn" onclick="undoLast()">&#8617; Undo</button>
  <span class="spacer"></span>
  <span id="status-lbl">Select a landmark, then click on the image</span>
  <span class="spacer"></span>
  <button id="save-btn"   class="tbtn" onclick="saveAndQuit()">&#10003; Save</button>
  <button id="cancel-btn" class="tbtn" onclick="cancelQuit()">&#10007; Cancel</button>
</div>

<div id="main">
  <div id="canvas-wrap"><canvas id="cv"></canvas></div>

  <div id="sidebar">

    <div class="card">
      <div class="card-hdr"><h3>Landmarks</h3></div>
      <div id="lm-list"></div>
    </div>

    <div class="card">
      <div class="card-hdr">
        <h3>Court Map</h3>
        <button onclick="toggleMapOrient()">&#8645; Rotate</button>
      </div>
      <canvas id="minimap-cv"></canvas>
    </div>

    <div class="card">
      <div class="card-hdr"><h3>Coordinates</h3></div>
      <div id="coord-rows"></div>
      <div class="coord-row" style="margin-top:4px;border-top:1px solid #252525;padding-top:4px">
        <span class="lbl">Cursor</span>
        <span class="val" id="coord-cursor">—</span>
      </div>
    </div>

    <div class="card">
      <div class="card-hdr"><h3>Controls</h3></div>
      <div class="hint-row">
        <kbd>Click</kbd> Place mark<br>
        <kbd>Click mark</kbd> Delete it<br>
        <kbd>A</kbd><kbd>D</kbd> ±1 frame<br>
        <kbd>Ctrl+A/D</kbd> ±5s &nbsp; <kbd>Shift+A/D</kbd> ±15s<br>
        <kbd>Scroll</kbd> Zoom &nbsp; <kbd>Alt+drag</kbd> Pan<br>
        <kbd>T</kbd> Court overlay<br>
        <kbd>R</kbd> Rotate map<br>
        <kbd>BS</kbd> Undo &nbsp; <kbd>S</kbd> Save
      </div>
    </div>

  </div>
</div>

<div id="bottombar">
  <button class="nav-btn" onclick="navigate(-450)" title="15 sec">&#9664;&#9664;&#9664;15s</button>
  <button class="nav-btn" onclick="navigate(-150)" title="5 sec">&#9664;&#9664;5s</button>
  <button class="nav-btn" onclick="navigate(-1)">&#9664;1</button>
  <input  id="frame-slider" type="range" min="0" value="0" oninput="goFrame(+this.value)">
  <button class="nav-btn" onclick="navigate(+1)">1&#9654;</button>
  <button class="nav-btn" onclick="navigate(+150)" title="5 sec">5s&#9654;&#9654;</button>
  <button class="nav-btn" onclick="navigate(+450)" title="15 sec">15s&#9654;&#9654;&#9654;</button>
  <span   id="frame-lbl">0 / 0</span>
</div>

<script>
const LM_DEFS = __LM_DEFS__;

const SIDELINE=750,HALF_Y=1432,FULL_Y=HALF_Y*2,BASKET_Y=160;
const FT_Y=580,LANE_X=245,PT3_CX=665,PT3_CY=420,PT3_R=705,CENTER_R=180;

const cv=document.getElementById('cv'), ctx=cv.getContext('2d');
const mmcv=document.getElementById('minimap-cv'), mmctx=mmcv.getContext('2d');

let state={}, fi=0, overlay=false, mapVertical=false;
let zoom=1, panX=0, panY=0, imgW=0, imgH=0, curImg=null;
let activeLm=LM_DEFS[0].key;
let marks={}, prevMarks={};
let dragging=false, dragSX=0, dragSY=0, dragPX=0, dragPY=0;

// ── init ─────────────────────────────────────────────────────────────────
async function init(){
  state=await fetch('/api/state').then(r=>r.json());
  fi=state.fi;
  LM_DEFS.forEach(d=>{ marks[d.key]=state.lm_coords[d.key]||null; });
  prevMarks=copy(marks);

  document.getElementById('frame-slider').max=state.total-1;
  document.getElementById('frame-slider').value=fi;

  buildLmButtons(); buildCoordRows();
  resizeCanvas();
  await loadFrame(fi);
  drawMinimap();
}

function copy(o){return JSON.parse(JSON.stringify(o));}

// ── landmark buttons ──────────────────────────────────────────────────────
function buildLmButtons(){
  const el=document.getElementById('lm-list'); el.innerHTML='';
  LM_DEFS.forEach(d=>{
    const isActive=d.key===activeLm;
    const btn=document.createElement('button');
    btn.className='lm-btn'+(isActive?' active':'');
    btn.style.setProperty('--lm-col',d.color);
    btn.id='lmbtn-'+d.key;

    const dot=document.createElement('span');
    dot.className='lm-dot'+(marks[d.key]?' set':'');
    dot.style.setProperty('--lm-col',d.color);

    const name=document.createElement('span');
    name.textContent=d.label;

    const st=document.createElement('span');
    st.className='lm-status';
    st.id='lmst-'+d.key;
    st.textContent=marks[d.key]?'set':'—';

    btn.append(dot,name,st);
    btn.onclick=()=>selectLm(d.key);
    el.appendChild(btn);
  });
}

function refreshLmButton(key){
  const d=LM_DEFS.find(x=>x.key===key); if(!d) return;
  const btn=document.getElementById('lmbtn-'+key);
  if(!btn) return;
  btn.querySelector('.lm-dot').className='lm-dot'+(marks[key]?' set':'');
  document.getElementById('lmst-'+key).textContent=marks[key]?'set':'—';
}

// ── coord rows ────────────────────────────────────────────────────────────
function buildCoordRows(){
  const el=document.getElementById('coord-rows'); el.innerHTML='';
  LM_DEFS.forEach(d=>{
    const row=document.createElement('div');
    row.className='coord-row';
    row.innerHTML=`<span class="lbl" style="color:${d.color}99">${d.label}</span>
      <span class="val" id="cval-${d.key}">—</span>`;
    el.appendChild(row);
  });
  updateCoords();
}

function updateCoords(){
  LM_DEFS.forEach(d=>{
    const el=document.getElementById('cval-'+d.key); if(!el) return;
    const m=marks[d.key];
    el.textContent=m?`(${Math.round(m[0])}, ${Math.round(m[1])})`: '—';
    el.className='val'+(m?' set':'');
  });
}

function selectLm(key){ activeLm=key; buildLmButtons(); updateStatus(); }

function updateStatus(){
  const d=LM_DEFS.find(x=>x.key===activeLm);
  const m=marks[activeLm];
  document.getElementById('status-lbl').textContent=
    m?`${d.label}: set — click mark to delete, click elsewhere to move`
     :`${d.label}: click on the image to place`;
}

// ── canvas / frame ────────────────────────────────────────────────────────
function resizeCanvas(){
  const w=document.getElementById('canvas-wrap');
  cv.width=w.clientWidth; cv.height=w.clientHeight;
  setMinimapSize();
}

function setMinimapSize(){
  const W=mmcv.parentElement.clientWidth-16;
  if(mapVertical){ mmcv.width=Math.round(W*SIDELINE*2/FULL_Y); mmcv.height=W; }
  else           { mmcv.width=W; mmcv.height=Math.round(W*SIDELINE*2/FULL_Y); }
}

async function loadFrame(idx){
  fi=Math.max(0,Math.min(idx,state.total-1));
  document.getElementById('frame-slider').value=fi;
  document.getElementById('frame-lbl').textContent=`${fi} / ${state.total-1}`;
  curImg=await loadImg(`/frame/${fi}?overlay=${overlay?1:0}&t=${Date.now()}`);
  imgW=curImg.naturalWidth; imgH=curImg.naturalHeight;
  render();
}

function loadImg(url){return new Promise(r=>{const i=new Image();i.onload=()=>r(i);i.src=url;});}

// ── coordinate transform ──────────────────────────────────────────────────
function bs(){return Math.min(cv.width/imgW,cv.height/imgH);}
function imgToCanvas(ix,iy){
  const s=bs()*zoom,ox=(cv.width-imgW*bs())/2+panX,oy=(cv.height-imgH*bs())/2+panY;
  const dx=(bs()-s)/bs()*imgW/2,dy=(bs()-s)/bs()*imgH/2;
  return[ox+(ix-dx)*s,oy+(iy-dy)*s];
}
function canvasToImg(cx,cy){
  const s=bs()*zoom,ox=(cv.width-imgW*bs())/2+panX,oy=(cv.height-imgH*bs())/2+panY;
  const dx=(bs()-s)/bs()*imgW/2,dy=(bs()-s)/bs()*imgH/2;
  return[(cx-ox)/s+dx,(cy-oy)/s+dy];
}
function distToMark(cx,cy,ip){const[mx,my]=imgToCanvas(...ip);return Math.hypot(cx-mx,cy-my);}

// ── render ────────────────────────────────────────────────────────────────
function render(){
  if(!curImg) return;
  ctx.clearRect(0,0,cv.width,cv.height);
  const s=bs()*zoom,ox=(cv.width-imgW*bs())/2+panX,oy=(cv.height-imgH*bs())/2+panY;
  const dx=(bs()-s)/bs()*imgW/2,dy=(bs()-s)/bs()*imgH/2;
  ctx.drawImage(curImg,ox+dx*s,oy+dy*s,imgW*s,imgH*s);
  LM_DEFS.forEach(d=>{
    if(marks[d.key]) drawMarker(marks[d.key],d.color,d.label,d.key===activeLm);
  });
}

function drawMarker(ip,col,label,active){
  const[cx,cy]=imgToCanvas(...ip), r=active?22:17;
  ctx.save();
  ctx.strokeStyle='#000'; ctx.lineWidth=4;
  ctx.beginPath(); ctx.arc(cx,cy,r,0,Math.PI*2); ctx.stroke();
  ctx.strokeStyle=col; ctx.lineWidth=active?2.5:1.5;
  ctx.beginPath(); ctx.arc(cx,cy,r,0,Math.PI*2); ctx.stroke();
  ctx.beginPath();
  ctx.moveTo(cx-r+4,cy);ctx.lineTo(cx+r-4,cy);
  ctx.moveTo(cx,cy-r+4);ctx.lineTo(cx,cy+r-4);
  ctx.stroke();
  ctx.fillStyle=col; ctx.beginPath(); ctx.arc(cx,cy,3,0,Math.PI*2); ctx.fill();
  if(active){
    ctx.shadowColor='#000'; ctx.shadowBlur=4;
    ctx.fillStyle=col; ctx.font='bold 12px system-ui';
    ctx.fillText(label,cx+r+5,cy+4);
  }
  ctx.restore();
}

// ── minimap ───────────────────────────────────────────────────────────────
function toggleMapOrient(){ mapVertical=!mapVertical; setMinimapSize(); drawMinimap(); }

function drawMinimap(){
  const W=mmcv.width, H=mmcv.height, pad=6;
  mmctx.fillStyle='#0e0e0e'; mmctx.fillRect(0,0,W,H);

  // c2p: court(cx,cy) → canvas pixel
  // Vertical  (portrait):  cy=0 (NEAR) at bottom, cy=FULL_Y (FAR) at top
  //                        cx=SIDELINE (LEFT) at left, cx=-SIDELINE (RIGHT) at right
  // Horizontal (landscape): cy=0 (NEAR) at left,  cy=FULL_Y (FAR) at right
  //                         cx=SIDELINE (LEFT) at top, cx=-SIDELINE (RIGHT) at bottom
  let c2p;
  if(mapVertical){
    const sx=(W-pad*2)/(SIDELINE*2), sy=(H-pad*2)/FULL_Y;
    c2p=(cx,cy)=>[pad+(SIDELINE-cx)*sx, pad+cy*sy];  // near=top? No: near=bottom
    // actually let's put NEAR at bottom: cy=0 → y=H-pad, cy=FULL_Y → y=pad
    c2p=(cx,cy)=>[pad+(SIDELINE-cx)*sx, H-pad-cy*sy];
  } else {
    const sx=(W-pad*2)/FULL_Y, sy=(H-pad*2)/(SIDELINE*2);
    // NEAR(cy=0) left, FAR(cy=FULL_Y) right
    // LEFT(cx=SIDELINE) top, RIGHT(cx=-SIDELINE) bottom
    c2p=(cx,cy)=>[pad+cy*sx, pad+(SIDELINE-cx)*sy];
  }

  function ml(x1,y1,x2,y2,col='#333',lw=1){
    const[ax,ay]=c2p(x1,y1),[bx,by]=c2p(x2,y2);
    mmctx.beginPath();mmctx.moveTo(ax,ay);mmctx.lineTo(bx,by);
    mmctx.strokeStyle=col;mmctx.lineWidth=lw;mmctx.stroke();
  }
  function mc(cx,cy,r,col,lw=1){
    const[px,py]=c2p(cx,cy);
    mmctx.beginPath();mmctx.arc(px,py,r,0,Math.PI*2);
    mmctx.strokeStyle=col;mmctx.lineWidth=lw;mmctx.stroke();
  }

  const WL='#555', G='#323232';
  // boundary
  ml(-SIDELINE,0,      SIDELINE,0,      WL,1.5);
  ml(-SIDELINE,FULL_Y, SIDELINE,FULL_Y, WL,1.5);
  ml(-SIDELINE,0,     -SIDELINE,FULL_Y, WL,1.5);
  ml( SIDELINE,0,      SIDELINE,FULL_Y, WL,1.5);
  ml(-SIDELINE,HALF_Y, SIDELINE,HALF_Y, WL,1);

  // center circle
  const scl=mapVertical?(W-pad*2)/(SIDELINE*2):(W-pad*2)/FULL_Y;
  // use actual scale for center circle radius
  const scl_cy=mapVertical?(H-pad*2)/FULL_Y:(W-pad*2)/FULL_Y;
  mc(0,HALF_Y,Math.max(1,CENTER_R*scl_cy),G);

  // paint near
  ml(-LANE_X,0,-LANE_X,FT_Y,G);ml(LANE_X,0,LANE_X,FT_Y,G);ml(-LANE_X,FT_Y,LANE_X,FT_Y,G);
  // paint far
  const FF=FULL_Y-FT_Y;
  ml(-LANE_X,FULL_Y,-LANE_X,FF,G);ml(LANE_X,FULL_Y,LANE_X,FF,G);ml(-LANE_X,FF,LANE_X,FF,G);

  // baskets
  const rimR=Math.max(1.5,23.75*scl_cy);
  mc(0,BASKET_Y,      rimR,'#3060c0',1.5);
  mc(0,FULL_Y-BASKET_Y,rimR,'#3060c0',1.5);

  // labels on all 4 sides
  mmctx.font='9px system-ui'; mmctx.fillStyle='#555';
  const [nearMidX,nearMidY]=c2p(0,0);
  const [farMidX, farMidY ]=c2p(0,FULL_Y);
  const [leftMidX,leftMidY]=c2p(SIDELINE, HALF_Y);
  const [rightMidX,rightMidY]=c2p(-SIDELINE,HALF_Y);
  mmctx.textAlign='center';
  mmctx.fillText('NEAR', nearMidX,  Math.min(nearMidY+10,  H-2));
  mmctx.fillText('FAR',  farMidX,   Math.max(farMidY-4,    8));
  mmctx.fillText('LEFT', Math.max(leftMidX+14,  20), leftMidY);
  mmctx.fillText('RIGHT',Math.min(rightMidX-14, W-20), rightMidY);
  mmctx.textAlign='left';

  // annotated landmark dots
  const lmCourtPos={
    'near_ring':     [0, BASKET_Y],
    'far_ring':      [0, FULL_Y-BASKET_Y],
    'center_circle': [0, HALF_Y],
  };
  LM_DEFS.forEach(d=>{
    const pos=lmCourtPos[d.key]; if(!pos) return;
    const[px,py]=c2p(...pos);
    const isSet=!!marks[d.key];
    mmctx.beginPath();mmctx.arc(px,py,rimR+3,0,Math.PI*2);
    mmctx.strokeStyle=isSet?d.color:'#333';
    mmctx.lineWidth=isSet?2:1; mmctx.stroke();
    if(isSet){
      mmctx.beginPath();mmctx.arc(px,py,3,0,Math.PI*2);
      mmctx.fillStyle=d.color; mmctx.fill();
    }
  });
}

// ── actions ───────────────────────────────────────────────────────────────
function navigate(d){zoom=1;panX=0;panY=0;loadFrame(fi+d);}
function goFrame(v){zoom=1;panX=0;panY=0;loadFrame(v);}

function toggleOverlay(){
  overlay=!overlay;
  const b=document.getElementById('overlay-btn');
  b.textContent=`Overlay: ${overlay?'ON':'OFF'}`;
  b.classList.toggle('on',overlay);
  loadFrame(fi);
}

function undoLast(){
  marks=copy(prevMarks);
  updateCoords(); buildLmButtons(); render(); drawMinimap(); updateStatus();
}

async function saveAndQuit(){
  const payload={};
  LM_DEFS.forEach(d=>{
    payload[d.key]=marks[d.key]?
      [Math.round(marks[d.key][0]),Math.round(marks[d.key][1])]:null;
  });
  const r=await fetch('/api/save',{method:'POST',
    headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
  const data=await r.json();
  if(data.ok){
    document.getElementById('status-lbl').textContent='Saved!';
    document.getElementById('save-btn').style.background='#0f3a0f';
    setTimeout(()=>window.close(),700);
  }
}
function cancelQuit(){window.close();}

// ── mouse ─────────────────────────────────────────────────────────────────
cv.addEventListener('mousedown',e=>{
  if(e.altKey){
    dragging=true;dragSX=e.clientX;dragSY=e.clientY;
    dragPX=panX;dragPY=panY;cv.style.cursor='grabbing';
  }
});
window.addEventListener('mousemove',e=>{
  if(dragging){panX=dragPX+(e.clientX-dragSX);panY=dragPY+(e.clientY-dragSY);render();}
  const rect=cv.getBoundingClientRect();
  const[ix,iy]=canvasToImg(e.clientX-rect.left,e.clientY-rect.top);
  if(ix>=0&&iy>=0&&ix<imgW&&iy<imgH)
    document.getElementById('coord-cursor').textContent=`(${Math.round(ix)}, ${Math.round(iy)})`;
});
window.addEventListener('mouseup',()=>{dragging=false;cv.style.cursor='crosshair';});

cv.addEventListener('click',e=>{
  if(e.altKey) return;
  const rect=cv.getBoundingClientRect();
  const cx=e.clientX-rect.left, cy=e.clientY-rect.top;
  const[ix,iy]=canvasToImg(cx,cy);
  if(ix<0||iy<0||ix>=imgW||iy>=imgH) return;
  const HIT=26;
  // click on existing mark → delete
  for(const d of LM_DEFS){
    if(marks[d.key]&&distToMark(cx,cy,marks[d.key])<HIT){
      prevMarks=copy(marks);
      marks[d.key]=null;
      refreshLmButton(d.key); updateCoords(); render(); drawMinimap(); updateStatus();
      return;
    }
  }
  // place new mark for active landmark
  prevMarks=copy(marks);
  marks[activeLm]=[ix,iy];
  refreshLmButton(activeLm); updateCoords(); render(); drawMinimap(); updateStatus();
});

cv.addEventListener('wheel',e=>{
  e.preventDefault();
  const rect=cv.getBoundingClientRect();
  const mx=e.clientX-rect.left,my=e.clientY-rect.top;
  const[ix,iy]=canvasToImg(mx,my);
  const f=e.deltaY<0?1.15:1/1.15;
  zoom=Math.max(1,Math.min(10,zoom*f));
  const s=bs()*zoom,ox=(cv.width-imgW*bs())/2,oy=(cv.height-imgH*bs())/2;
  const dx=(bs()-s)/bs()*imgW/2,dy=(bs()-s)/bs()*imgH/2;
  panX=mx-ox-(ix-dx)*s; panY=my-oy-(iy-dy)*s;
  render();
},{passive:false});

document.addEventListener('keydown',e=>{
  if(['INPUT','TEXTAREA'].includes(document.activeElement.tagName)) return;
  if(e.key==='ArrowLeft' ||e.key==='a'){
    if(e.shiftKey) navigate(-450); else if(e.ctrlKey||e.metaKey) navigate(-150); else navigate(-1);
  }
  if(e.key==='ArrowRight'||e.key==='d'){
    if(e.shiftKey) navigate(+450); else if(e.ctrlKey||e.metaKey) navigate(+150); else navigate(+1);
  }
  if(e.key==='t'||e.key==='T') toggleOverlay();
  if(e.key==='r'||e.key==='R') toggleMapOrient();
  if(e.key==='Backspace') undoLast();
  if(e.key==='s'||e.key==='S') saveAndQuit();
  if(e.key==='Escape') cancelQuit();
});

window.addEventListener('resize',()=>{resizeCanvas();render();drawMinimap();});
init();
</script>
</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):
    def log_message(self,*_): pass
    def send_json(self,obj,code=200):
        body=json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type","application/json")
        self.send_header("Content-Length",len(body))
        self.end_headers(); self.wfile.write(body)

    def do_GET(self):
        p=urlparse(self.path); qs=parse_qs(p.query)
        if p.path=="/":
            # inject LM_DEFS into HTML
            lm_json=json.dumps([{"key":d["key"],"label":d["label"],"color":d["color_hex"]}
                                 for d in LANDMARKS])
            body=HTML.replace("__LM_DEFS__",lm_json).encode()
            self.send_response(200)
            self.send_header("Content-Type","text/html;charset=utf-8")
            self.send_header("Content-Length",len(body))
            self.end_headers(); self.wfile.write(body)
        elif p.path.startswith("/frame/"):
            fi=int(p.path.split("/")[-1]); ov=qs.get("overlay",["0"])[0]=="1"
            data=get_frame(fi,ov)
            self.send_response(200)
            self.send_header("Content-Type","image/jpeg")
            self.send_header("Content-Length",len(data))
            self.end_headers(); self.wfile.write(data)
        elif p.path=="/api/state":
            # near_ring: prefer near_ring_image_xy override, else pairs[ring]
            near_xy=prof.get("near_ring_image_xy")
            if not near_xy:
                for pair in prof.get("pairs",[]):
                    if pair["landmark_id"]=="ring":
                        near_xy=pair["image_xy"]; break
            lm_coords={}
            for d in LANDMARKS:
                val=prof.get(d["field"])
                if not val and d["key"]=="near_ring": val=near_xy
                lm_coords[d["key"]]=val
            self.send_json({"total":total,"fi":prof.get("frame_idx",0),
                            "near_xy":near_xy,"lm_coords":lm_coords})
        else:
            self.send_response(404); self.end_headers()

    def do_POST(self):
        if self.path=="/api/save":
            body=json.loads(self.rfile.read(int(self.headers.get("Content-Length",0))))
            for d in LANDMARKS:
                val=body.get(d["key"])
                if val:
                    prof[d["field"]]=val
                    # also update pairs[ring] if near_ring changed
                    if d["key"]=="near_ring":
                        for pair in prof.get("pairs",[]):
                            if pair["landmark_id"]=="ring":
                                pair["image_xy"]=val
                    print(f"Saved: {d['field']} = {val}")
                elif d["field"] in prof:
                    del prof[d["field"]]
                    print(f"Cleared: {d['field']}")
            with open(profile_path,"w") as f:
                json.dump(prof,f,ensure_ascii=False,indent=2)
            self.send_json({"ok":True})
        else:
            self.send_response(404); self.end_headers()


def main():
    global prof,cap,total,H_mat,profile_path
    ap=argparse.ArgumentParser()
    ap.add_argument("--profile",default="outputs/venue_profiles/game2-1.json")
    args=ap.parse_args(); profile_path=args.profile
    with open(profile_path) as f: prof=json.load(f)
    video=f"data/videos/{prof['video']}"
    cap=cv2.VideoCapture(video); total=int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    H_mat=np.array(prof["H_court_to_image"])
    url=f"http://localhost:{PORT}"; print(f"Opening {url}")
    threading.Thread(target=lambda:(__import__('time').sleep(0.6),webbrowser.open(url)),daemon=True).start()
    httpd=HTTPServer(("",PORT),Handler)
    print("Ctrl-C to stop.")
    try: httpd.serve_forever()
    except KeyboardInterrupt: print("Stopped.")
    finally: cap.release()

if __name__=="__main__": main()
