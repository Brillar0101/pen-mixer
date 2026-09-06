"""Live web dashboard for the Pen Mixer bridge.

Serves a page on http://localhost:8080 that shows the sensor channels and the
audio parameters they drive, updating in real time.  Stdlib only - the stream
is Server-Sent Events, so no websocket library is needed.
"""

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

LATEST = {"tilt": 0.0, "roll": 0.0, "energy": 0.0,
          "cutoff": 0.0, "gain": 0.0, "wet": 0.0,
          "fps": 0, "bad": 0, "mode": "-"}
_lock = threading.Lock()


def publish(**kw):
    with _lock:
        LATEST.update(kw)


PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Pen Mixer</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Roboto:wght@400;500;700&family=Roboto+Mono:wght@400;500;700&family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@24,400,0,0&display=swap">
<style>
/* ---- Material 3 baseline tokens, light scheme ---- */
:root{
  --md-primary:#6750A4; --md-on-primary:#FFFFFF;
  --md-primary-container:#EADDFF; --md-on-primary-container:#21005D;
  --md-secondary:#625B71; --md-on-secondary:#FFFFFF;
  --md-secondary-container:#E8DEF8; --md-on-secondary-container:#1D192B;
  --md-tertiary:#7D5260; --md-tertiary-container:#FFD8E4;
  --md-on-tertiary-container:#31111D;
  --md-error:#B3261E; --md-error-container:#F9DEDC;
  --md-surface:#FEF7FF; --md-on-surface:#1D1B20;
  --md-surface-container-lowest:#FFFFFF;
  --md-surface-container-low:#F7F2FA;
  --md-surface-container:#F3EDF7;
  --md-surface-container-high:#ECE6F0;
  --md-surface-container-highest:#E6E0E9;
  --md-on-surface-variant:#49454F;
  --md-outline:#79747E; --md-outline-variant:#CAC4D0;
  --md-scrim:rgba(0,0,0,.32);
  /* custom color roles for the audio channels */
  --ch-tilt:#6750A4; --ch-roll:#7D5260; --ch-energy:#625B71;
  --ch-cutoff:#286C3A; --ch-gain:#8C4A5E; --ch-wet:#00639B;
  --md-elev-1:0 1px 2px rgba(0,0,0,.30),0 1px 3px 1px rgba(0,0,0,.15);
  --md-elev-2:0 1px 2px rgba(0,0,0,.30),0 2px 6px 2px rgba(0,0,0,.15);
  --shape-s:8px; --shape-m:12px; --shape-l:16px; --shape-xl:28px;
  --sans:"Roboto","Helvetica Neue",Arial,sans-serif;
  --mono:"Roboto Mono",ui-monospace,Menlo,monospace;
}
@media (prefers-color-scheme:dark){
  :root:not([data-theme="light"]){
    --md-primary:#D0BCFF; --md-on-primary:#381E72;
    --md-primary-container:#4F378B; --md-on-primary-container:#EADDFF;
    --md-secondary:#CCC2DC; --md-on-secondary:#332D41;
    --md-secondary-container:#4A4458; --md-on-secondary-container:#E8DEF8;
    --md-tertiary:#EFB8C8; --md-tertiary-container:#633B48;
    --md-on-tertiary-container:#FFD8E4;
    --md-error:#F2B8B5; --md-error-container:#8C1D18;
    --md-surface:#141218; --md-on-surface:#E6E0E9;
    --md-surface-container-lowest:#0F0D13;
    --md-surface-container-low:#1D1B20;
    --md-surface-container:#211F26;
    --md-surface-container-high:#2B2930;
    --md-surface-container-highest:#36343B;
    --md-on-surface-variant:#CAC4D0;
    --md-outline:#938F99; --md-outline-variant:#49454F;
    --ch-tilt:#D0BCFF; --ch-roll:#EFB8C8; --ch-energy:#CCC2DC;
    --ch-cutoff:#7ADB92; --ch-gain:#FFB1C4; --ch-wet:#8DCDFF;
    --md-elev-1:0 1px 3px rgba(0,0,0,.60),0 1px 2px rgba(0,0,0,.40);
    --md-elev-2:0 2px 6px rgba(0,0,0,.60),0 1px 2px rgba(0,0,0,.40);
  }
}
:root[data-theme="dark"]{
  --md-primary:#D0BCFF; --md-on-primary:#381E72;
  --md-primary-container:#4F378B; --md-on-primary-container:#EADDFF;
  --md-secondary:#CCC2DC; --md-on-secondary:#332D41;
  --md-secondary-container:#4A4458; --md-on-secondary-container:#E8DEF8;
  --md-tertiary:#EFB8C8; --md-tertiary-container:#633B48;
  --md-on-tertiary-container:#FFD8E4;
  --md-error:#F2B8B5; --md-error-container:#8C1D18;
  --md-surface:#141218; --md-on-surface:#E6E0E9;
  --md-surface-container-lowest:#0F0D13;
  --md-surface-container-low:#1D1B20;
  --md-surface-container:#211F26;
  --md-surface-container-high:#2B2930;
  --md-surface-container-highest:#36343B;
  --md-on-surface-variant:#CAC4D0;
  --md-outline:#938F99; --md-outline-variant:#49454F;
  --ch-tilt:#D0BCFF; --ch-roll:#EFB8C8; --ch-energy:#CCC2DC;
  --ch-cutoff:#7ADB92; --ch-gain:#FFB1C4; --ch-wet:#8DCDFF;
  --md-elev-1:0 1px 3px rgba(0,0,0,.60),0 1px 2px rgba(0,0,0,.40);
  --md-elev-2:0 2px 6px rgba(0,0,0,.60),0 1px 2px rgba(0,0,0,.40);
}

*{box-sizing:border-box}
body{margin:0;background:var(--md-surface);color:var(--md-on-surface);
     font-family:var(--sans)}
.ms{font-family:"Material Symbols Outlined";font-weight:400;font-style:normal;
    font-size:24px;line-height:1;letter-spacing:normal;display:inline-block;
    -webkit-font-feature-settings:'liga';font-feature-settings:'liga'}

/* ---- top app bar (small) ---- */
.appbar{height:64px;display:flex;align-items:center;gap:12px;padding:0 16px;
        background:var(--md-surface);position:sticky;top:0;z-index:5}
.appbar .leading{width:40px;height:40px;display:grid;place-items:center;
        border-radius:var(--shape-l);background:var(--md-primary-container);
        color:var(--md-on-primary-container)}
.title-large{font-size:22px;line-height:28px;font-weight:400}
.appbar .spacer{flex:1}
.icon-btn{width:40px;height:40px;border:0;border-radius:20px;cursor:pointer;
     background:transparent;color:var(--md-on-surface-variant);display:grid;
     place-items:center;position:relative;overflow:hidden}
.icon-btn::before{content:"";position:absolute;inset:0;background:currentColor;
     opacity:0;transition:opacity .12s}
.icon-btn:hover::before{opacity:.08}
.icon-btn:focus-visible{outline:3px solid var(--md-primary);outline-offset:1px}

/* ---- assist chip ---- */
.chip{display:inline-flex;align-items:center;gap:8px;height:32px;padding:0 12px;
   border-radius:var(--shape-s);border:1px solid var(--md-outline);
   background:transparent;color:var(--md-on-surface-variant);
   font-size:14px;line-height:20px;font-weight:500;font-family:var(--mono);
   white-space:nowrap}
.chip.on{background:var(--md-secondary-container);border-color:transparent;
   color:var(--md-on-secondary-container)}
.chip .dot{width:8px;height:8px;border-radius:50%;background:currentColor}

/* ---- layout ---- */
main{padding:8px 16px 32px;max-width:1200px;margin:0 auto;display:grid;gap:16px}
.cols{display:grid;grid-template-columns:1fr 1fr;gap:16px}
@media(max-width:900px){.cols{grid-template-columns:1fr}}

/* ---- cards: filled, elevation level 1 ---- */
.card{background:var(--md-surface-container-low);border-radius:var(--shape-l);
      padding:20px;box-shadow:var(--md-elev-1)}
.card > header{display:flex;align-items:center;gap:10px;margin-bottom:20px}
.title-medium{font-size:16px;line-height:24px;font-weight:500;
      letter-spacing:.15px}
.label-medium{font-size:12px;line-height:16px;font-weight:500;
      letter-spacing:.5px;color:var(--md-on-surface-variant)}

/* ---- channel meter ---- */
.ch{padding:12px 0}
.ch + .ch{border-top:1px solid var(--md-outline-variant)}
.ch-top{display:flex;justify-content:space-between;align-items:baseline;
        gap:12px;margin-bottom:10px}
.ch-name{font-size:14px;line-height:20px;font-weight:500;letter-spacing:.1px}
.ch-val{font-family:var(--mono);font-size:20px;line-height:24px;font-weight:500;
        font-variant-numeric:tabular-nums}
/* linear progress indicator */
.track{height:8px;border-radius:4px;background:var(--md-surface-container-highest);
       overflow:hidden;position:relative}
.ind{height:100%;width:0%;border-radius:4px;transition:width .06s linear}
.ch-hint{font-size:12px;line-height:16px;color:var(--md-on-surface-variant);
        margin-top:8px;letter-spacing:.4px}

/* ---- scope ---- */
canvas{width:100%;height:240px;display:block;
       border-radius:var(--shape-m);background:var(--md-surface-container-lowest)}
.legend{display:flex;flex-wrap:wrap;gap:8px;margin-top:16px}
.legend .chip{height:28px;font-size:12px;padding:0 10px;border-style:solid}
.legend i{width:12px;height:3px;border-radius:2px;display:inline-block}
.support{font-size:14px;line-height:20px;color:var(--md-on-surface-variant);
         letter-spacing:.25px;padding:0 4px}
</style></head><body>

<div class="appbar">
  <span class="leading"><span class="ms">stylus_note</span></span>
  <span class="title-large">Pen Mixer</span>
  <span class="chip" id="stat"><span class="dot"></span><span id="statl">connecting</span></span>
  <span class="spacer"></span>
  <span class="chip" id="rate">-- fps</span>
  <button class="icon-btn" id="theme" title="Toggle theme" aria-label="Toggle theme">
    <span class="ms" id="themeicon">dark_mode</span></button>
</div>

<main>
  <div class="cols">
    <section class="card">
      <header><span class="ms" style="color:var(--md-primary)">sensors</span>
        <span class="title-medium">Sensor input</span></header>
      <div class="ch"><div class="ch-top"><span class="ch-name">Tilt</span>
        <span class="ch-val" id="v_tilt" style="color:var(--ch-tilt)">0</span></div>
        <div class="track"><div class="ind" id="b_tilt" style="background:var(--ch-tilt)"></div></div>
        <div class="ch-hint">&minus;45&deg; to +45&deg; &middot; forward and back</div></div>
      <div class="ch"><div class="ch-top"><span class="ch-name">Roll</span>
        <span class="ch-val" id="v_roll" style="color:var(--ch-roll)">0</span></div>
        <div class="track"><div class="ind" id="b_roll" style="background:var(--ch-roll)"></div></div>
        <div class="ch-hint">&minus;90&deg; to +90&deg; &middot; barrel twist</div></div>
      <div class="ch"><div class="ch-top"><span class="ch-name">Energy</span>
        <span class="ch-val" id="v_energy" style="color:var(--ch-energy)">0</span></div>
        <div class="track"><div class="ind" id="b_energy" style="background:var(--ch-energy)"></div></div>
        <div class="ch-hint">0 to 1 &middot; how fast it is moving</div></div>
    </section>

    <section class="card">
      <header><span class="ms" style="color:var(--ch-cutoff)">graphic_eq</span>
        <span class="title-medium">Audio output</span></header>
      <div class="ch"><div class="ch-top"><span class="ch-name">Cutoff</span>
        <span class="ch-val" id="v_cutoff" style="color:var(--ch-cutoff)">0</span></div>
        <div class="track"><div class="ind" id="b_cutoff" style="background:var(--ch-cutoff)"></div></div>
        <div class="ch-hint">80 Hz to 12 kHz &middot; lowpass filter</div></div>
      <div class="ch"><div class="ch-top"><span class="ch-name">Gain</span>
        <span class="ch-val" id="v_gain" style="color:var(--ch-gain)">0</span></div>
        <div class="track"><div class="ind" id="b_gain" style="background:var(--ch-gain)"></div></div>
        <div class="ch-hint">0.25&times; to 1.75&times; &middot; level</div></div>
      <div class="ch"><div class="ch-top"><span class="ch-name">Wet</span>
        <span class="ch-val" id="v_wet" style="color:var(--ch-wet)">0</span></div>
        <div class="track"><div class="ind" id="b_wet" style="background:var(--ch-wet)"></div></div>
        <div class="ch-hint">0 to 1 &middot; effect send</div></div>
    </section>
  </div>

  <section class="card">
    <header><span class="ms" style="color:var(--md-on-surface-variant)">timeline</span>
      <span class="title-medium">Last 12 seconds</span></header>
    <canvas id="scope"></canvas>
    <div class="legend">
      <span class="chip"><i style="background:var(--ch-tilt)"></i>tilt</span>
      <span class="chip"><i style="background:var(--ch-roll)"></i>roll</span>
      <span class="chip"><i style="background:var(--ch-energy)"></i>energy</span>
      <span class="chip"><i style="background:var(--ch-cutoff)"></i>cutoff</span>
      <span class="chip"><i style="background:var(--ch-gain)"></i>gain</span>
    </div>
  </section>

  <p class="support">Flat traces mean the board is not sending. Move the pen to
     drive the channels.</p>
</main>

<script>
const RANGE={tilt:[-45,45],roll:[-90,90],energy:[0,1],
             cutoff:[80,12000],gain:[0.25,1.75],wet:[0,1]};
const FMT={tilt:v=>v.toFixed(1)+"\\u00b0",roll:v=>v.toFixed(1)+"\\u00b0",
           energy:v=>v.toFixed(2),cutoff:v=>Math.round(v)+" Hz",
           gain:v=>v.toFixed(2)+"\\u00d7",wet:v=>v.toFixed(2)};
const norm=(k,v)=>{const[a,b]=RANGE[k];return Math.max(0,Math.min(1,(v-a)/(b-a)));};
const KEYS=["tilt","roll","energy","cutoff","gain","wet"];
const TRACE=["tilt","roll","energy","cutoff","gain"];

let COL={};
function readColors(){
  const cs=getComputedStyle(document.documentElement);
  TRACE.forEach(k=>COL[k]=cs.getPropertyValue("--ch-"+k).trim());
  GRID=cs.getPropertyValue("--md-outline-variant").trim();
}
let GRID="#ccc";
readColors();

/* theme toggle */
const root=document.documentElement, ticon=document.getElementById("themeicon");
function applyTheme(t){
  if(t) root.setAttribute("data-theme",t); else root.removeAttribute("data-theme");
  const dark = t==="dark" || (!t && matchMedia("(prefers-color-scheme:dark)").matches);
  ticon.textContent = dark ? "light_mode" : "dark_mode";
  readColors();
}
try{ applyTheme(localStorage.getItem("theme")); }catch(e){ applyTheme(null); }
document.getElementById("theme").onclick=()=>{
  const dark = root.getAttribute("data-theme")==="dark" ||
    (!root.getAttribute("data-theme") && matchMedia("(prefers-color-scheme:dark)").matches);
  const next = dark ? "light" : "dark";
  applyTheme(next);
  try{ localStorage.setItem("theme",next); }catch(e){}
};

const N=360, hist={}; TRACE.forEach(k=>hist[k]=new Array(N).fill(null));
const cv=document.getElementById("scope"), cx=cv.getContext("2d");
function size(){const r=cv.getBoundingClientRect(),d=devicePixelRatio||1;
  cv.width=r.width*d; cv.height=r.height*d; cx.setTransform(d,0,0,d,0,0);}
addEventListener("resize",size); size();

function draw(){
  const r=cv.getBoundingClientRect(), w=r.width, h=r.height;
  cx.clearRect(0,0,w,h);
  cx.strokeStyle=GRID; cx.globalAlpha=.5; cx.lineWidth=1;
  for(let i=1;i<4;i++){const y=Math.round(h*i/4)+.5;
    cx.beginPath();cx.moveTo(0,y);cx.lineTo(w,y);cx.stroke();}
  cx.globalAlpha=1;
  TRACE.forEach(k=>{
    cx.strokeStyle=COL[k]; cx.lineWidth=k==="cutoff"?2.5:1.5;
    cx.globalAlpha=k==="cutoff"?1:.7;
    cx.lineJoin="round"; cx.beginPath();
    let started=false;
    for(let i=0;i<N;i++){const v=hist[k][i]; if(v===null)continue;
      const x=i/(N-1)*w, y=h-(v*(h-12))-6;
      if(!started){cx.moveTo(x,y);started=true;}else cx.lineTo(x,y);}
    cx.stroke();
  });
  cx.globalAlpha=1;
  requestAnimationFrame(draw);
}
draw();

const chip=document.getElementById("stat"), chipl=document.getElementById("statl");
const es=new EventSource("/stream");
es.onopen=()=>{chip.className="chip on";chipl.textContent="live";};
es.onerror=()=>{chip.className="chip";chipl.textContent="disconnected";};
es.onmessage=e=>{
  const d=JSON.parse(e.data);
  KEYS.forEach(k=>{
    const v=d[k]||0;
    document.getElementById("v_"+k).textContent=FMT[k](v);
    document.getElementById("b_"+k).style.width=(norm(k,v)*100)+"%";
  });
  TRACE.forEach(k=>{hist[k].push(norm(k,d[k]||0)); hist[k].shift();});
  document.getElementById("rate").textContent=
    (d.fps||0)+" fps \\u00b7 "+(d.bad||0)+" bad \\u00b7 "+(d.mode||"");
};
</script></body></html>"""


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        if self.path == "/stream":
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            try:
                while True:
                    with _lock:
                        payload = json.dumps(LATEST)
                    self.wfile.write(("data: %s\n\n" % payload).encode())
                    self.wfile.flush()
                    time.sleep(1 / 30.0)
            except (BrokenPipeError, ConnectionResetError):
                return
        else:
            body = PAGE.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)


def serve(port=8080):
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return port
