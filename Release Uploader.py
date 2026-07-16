from __future__ import annotations

import sys
import time
import threading
import mimetypes
import json
import secrets
from pathlib import Path
from urllib.parse import quote
from concurrent.futures import ThreadPoolExecutor

import requests as req
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from flask import Flask, request, jsonify, Response

try:
    import webview
except ImportError:
    sys.exit("Install pywebview: pip install pywebview flask requests")

API_VER = "2022-11-28"


def make_session(token):
    s = req.Session()
    s.headers.update({
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": API_VER
    })
    retry = Retry(
        total=5,
        backoff_factor=0.5,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET", "POST", "DELETE"],
        raise_on_status=False
    )
    a = HTTPAdapter(max_retries=retry, pool_connections=8, pool_maxsize=16)
    s.mount("https://", a)
    s.mount("http://", a)
    return s


def get_release(sess, repo, tag):
    r = sess.get(f"https://api.github.com/repos/{repo}/releases/tags/{quote(tag)}", timeout=30)
    if not r.ok:
        raise RuntimeError(r.text)
    return r.json()


def human_size(v):
    for u in ("B", "KB", "MB", "GB", "TB"):
        if v < 1024:
            return f"{v:.1f} {u}"
        v /= 1024
    return f"{v:.1f} PB"


class ProgressReader:
    def __init__(self, f, total, cb, update_interval=0.2):
        self._f = f
        self.total = max(int(total), 1)
        self._r = 0
        self._cb = cb
        self._t = time.monotonic()
        self._last_cb = 0.0
        self._update_interval = max(float(update_interval), 0.05)

    def _emit(self, pct, spd, eta, force=False):
        now = time.monotonic()
        if force or now - self._last_cb >= self._update_interval:
            self._cb(pct, spd, eta)
            self._last_cb = now

    def read(self, n=-1):
        c = self._f.read(n)
        if not c:
            self._emit(100.0 if self._r >= self.total else min(self._r / self.total * 100, 100.0), 0, 0, force=True)
            return c
        self._r += len(c)
        el = max(time.monotonic() - self._t, 1e-9)
        sp = self._r / el
        self._emit(
            min(self._r / self.total * 100, 100.0),
            sp,
            max(self.total - self._r, 0) / sp if sp > 0 else 0,
            force=self._r >= self.total,
        )
        return c

    def __len__(self):
        return self.total


import queue as _queue
_event_q: _queue.Queue = _queue.Queue()


_last_push = {}

def push(kind, **data):

    now = time.monotonic()

    key = kind + str(data.get("id", ""))

    if kind == "file":

        if now - _last_push.get(key, 0) < 0.15:
            return

        _last_push[key] = now


    _event_q.put(
        json.dumps(
            {
                "kind": kind,
                **data
            },
            separators=(",", ":")
        )
    )


flask_app = Flask(__name__)
flask_app.secret_key = secrets.token_hex(16)


@flask_app.get("/")
def index():
    return HTML


@flask_app.get("/events")
def events():
    def stream():
        while True:
            try:
                msg = _event_q.get(timeout=30)
                yield f"data: {msg}\n\n"
            except _queue.Empty:
                yield ": ping\n\n"

    return Response(
        stream(),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    )


@flask_app.post("/upload")
def api_upload():

    d = request.json or {}

    token = d.get("token", "").strip()
    repo = d.get("repo", "").strip()
    tag = d.get("tag", "").strip()
    paths = d.get("paths", [])

    workers = int(d.get("workers", 4))

    if not token or not repo or not tag or not paths:
        return jsonify(error="All fields required"), 400

    threading.Thread(
        target=_upload_worker,
        args=(token, repo, tag, paths, workers),
        daemon=True
    ).start()

    return jsonify(ok=True)


@flask_app.post("/assets")
def api_assets():
    d = request.json
    token = d.get("token", "").strip()
    repo = d.get("repo", "").strip()
    tag = d.get("tag", "").strip()
    if not all([token, repo, tag]):
        return jsonify(error="Token, repo, tag required"), 400
    threading.Thread(
        target=_assets_worker,
        args=(token, repo, tag),
        daemon=True
    ).start()
    return jsonify(ok=True)


@flask_app.post("/delete")
def api_delete():
    d = request.json
    token = d.get("token", "").strip()
    url = d.get("url", "")
    name = d.get("name", "")
    if not all([token, url]):
        return jsonify(error="Token + asset URL required"), 400
    threading.Thread(
        target=_delete_worker,
        args=(token, url, name),
        daemon=True
    ).start()
    return jsonify(ok=True)


def _upload_worker(token, repo, tag, paths, workers):
    try:
        sess = make_session(token)
        push("log", msg="Fetching release info…", cls="muted")
        rel = get_release(sess, repo, tag)

        files = []

        for item in paths:
          p = Path(item)

          if p.is_file():
              files.append(p)

          elif p.is_dir():
              files.extend(
                  x for x in p.iterdir()
                  if x.is_file()
              )
        if not files:
            raise RuntimeError("No files in folder.")

        total = len(files)
        done = 0
        lock = threading.Lock()

        push("log", msg=f"Uploading {total} file(s) · {workers} workers", cls="muted")
        push("overall", pct=0, label=f"0 / {total}")

        def one(fp):
            nonlocal done
            fn = fp.name
            job_id = secrets.token_hex(4)

            for a in rel.get("assets", []):
                if a["name"] == fn:
                    push("log", msg=f"⚠ {fn} — already exists, skipped", cls="warn")
                    with lock:
                        done += 1
                        push("overall", pct=done / total * 100, label=f"{done} / {total}")
                    return

            url = rel["upload_url"].replace("{?name,label}", "") + f"?name={quote(fn)}"
            ct = mimetypes.guess_type(fn)[0] or "application/octet-stream"
            sz = fp.stat().st_size

            push("current", id=job_id, name=fn)
            push("file", id=job_id, name=fn, pct=0, speed="0 B/s", eta="—")

            try:
                def cb(pct, spd, eta):
                    push(
                        "file",
                        id=job_id,
                        name=fn,
                        pct=round(pct, 1),
                        speed=f"{spd/1048576:.2f} MB/s",
                        eta=f"{eta:.1f}s",
                        eta_seconds=eta
                    )

                with open(fp, "rb") as f:
                    r = sess.post(
                        url,
                        data=ProgressReader(f, sz, cb),
                        headers={"Content-Type": ct},
                        timeout=None
                    )

                if r.status_code not in (200, 201):
                    raise RuntimeError(f"HTTP {r.status_code}")

                push("log", msg=f"✓ {fn}  ({human_size(sz)})", cls="success")
                push("done-file", id=job_id, name=fn)

            except Exception as e:
                push("log", msg=f"✗ {fn}: {e}", cls="danger")
                push("done-file", id=job_id, name=fn)

            with lock:
                done += 1
                push("overall", pct=done / total * 100, label=f"{done} / {total}")

        with ThreadPoolExecutor(max_workers=workers) as pool:
            list(pool.map(one, files))

        push("log", msg=f"All {total} upload(s) complete.", cls="success")
        push("done", msg=f"All {total} upload(s) complete.")
    except Exception as e:
        push("log", msg=f"Error: {e}", cls="danger")
        push("error", msg=str(e))


def _assets_worker(token, repo, tag):
    try:
        sess = make_session(token)
        rel = get_release(sess, repo, tag)
        assets = rel.get("assets", [])
        push(
            "assets",
            items=[
                {
                    "name": a["name"],
                    "size": human_size(a.get("size", 0)),
                    "url": a["url"],
                    "id": a["id"]
                }
                for a in assets
            ]
        )
        push("log", msg=f"Loaded {len(assets)} asset(s).", cls="muted")
    except Exception as e:
        push("log", msg=f"Error: {e}", cls="danger")
        push("error", msg=str(e))


def _delete_worker(token, url, name):
    try:
        push("log", msg=f"Deleting {name}…", cls="warn")
        r = make_session(token).delete(url, timeout=30)
        if not r.ok:
            raise RuntimeError(r.text)
        push("log", msg=f"✓ Deleted {name}", cls="success")
        push("deleted", name=name)
    except Exception as e:
        push("log", msg=f"Error: {e}", cls="danger")
        push("error", msg=str(e))


HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>GitHub Release Uploader</title>
<style>
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
:root{
  --bg:#0A0F1A;
  --surface:#0F1623;
  --card:#131B2B;
  --card2:#182035;
  --border:#1E2D45;
  --border2:#273A58;
  --accent:#60CDFF;
  --accent2:#3A9FD8;
  --accent-glow:rgba(96,205,255,0.18);
  --success:#4EC994;
  --danger:#F87272;
  --warn:#F0C060;
  --muted:#4A6080;
  --txt:#D0DCF0;
  --txt2:#7A9AB8;
  --txt3:#4A6080;
  --nav-w:210px;
  --hdr-h:48px;
  --radius:10px;
  --radius-sm:5px;
  --font:"Segoe UI Variable","Segoe UI",system-ui,sans-serif;
  --mono:"Cascadia Code","Consolas","Courier New",monospace;
}
body{
  background:var(--bg);
  color:var(--txt);
  font-family:var(--font);
  font-size:13px;
  height:100vh;
  overflow:hidden;
  display:flex;
  flex-direction:column;
  user-select:none;
  contain:layout paint;
}
#titlebar{
  height:var(--hdr-h);
  background:var(--surface);
  border-bottom:1px solid var(--border);
  display:flex;
  align-items:center;
  padding:0 16px;
  gap:10px;
  flex-shrink:0;
  -webkit-app-region:drag;
  contain:layout paint;
}
#titlebar button{-webkit-app-region:no-drag}
.tb-dot{
  width:10px;height:10px;border-radius:50%;
  background:var(--accent);
  flex-shrink:0;
  box-shadow:none;
}
#tb-title{font-size:13px;font-weight:600;color:var(--txt);flex:1}
#tb-status{font-size:11px;color:var(--txt3)}
#shell{display:flex;flex:1;overflow:hidden}
nav{
  width:var(--nav-w);
  background:var(--surface);
  border-right:1px solid var(--border);
  display:flex;
  flex-direction:column;
  padding:8px 8px 16px;
  gap:2px;
  flex-shrink:0;
  overflow:hidden;
}
.nav-section{
  font-size:9px;font-weight:700;
  letter-spacing:1.8px;text-transform:uppercase;
  color:var(--txt3);
  padding:14px 10px 6px;
}
.nav-item{
  display:flex;align-items:center;gap:10px;
  padding:9px 10px;border-radius:var(--radius-sm);
  cursor:pointer;
  color:var(--txt2);
  font-size:13px;font-weight:400;
  transition:none;
  position:relative;
}
.nav-item:hover{background:rgba(96,205,255,0.06);color:var(--txt)}
.nav-item.active{background:rgba(96,205,255,0.10);color:var(--txt);font-weight:500}
.nav-item.active::before{
  content:'';
  position:absolute;left:0;top:50%;transform:translateY(-50%);
  width:3px;height:16px;border-radius:2px;
  background:var(--accent);
}
.nav-icon{width:18px;text-align:center;font-size:14px;flex-shrink:0;opacity:0.7}
.nav-item.active .nav-icon{opacity:1}
nav .spacer{flex:1}
.nav-footer{font-size:10px;color:var(--txt3);padding:4px 10px}
#content{flex:1;overflow-y:auto;overflow-x:hidden;padding:24px 28px}
#content::-webkit-scrollbar{width:6px}
#content::-webkit-scrollbar-track{background:transparent}
#content::-webkit-scrollbar-thumb{background:var(--border);border-radius:3px}
#content::-webkit-scrollbar-thumb:hover{background:var(--border2)}
.page{display:none;flex-direction:column;gap:16px}
.page.active{display:flex}
.card{
  background:var(--card);
  border:1px solid var(--border);
  border-radius:var(--radius);
  padding:20px 22px;
}
.card-title{
  font-size:15px;font-weight:600;
  color:var(--txt);
  margin-bottom:16px;
  display:flex;align-items:center;gap:8px;
}
.card-title .ct-icon{color:var(--accent);font-size:13px}
.field-grid{display:grid;grid-template-columns:auto 1fr;gap:10px 16px;align-items:center}
.field-grid.two-col{grid-template-columns:auto 1fr auto 1fr}
.field-label{color:var(--txt2);font-size:12px;font-weight:500;white-space:nowrap}
input[type=text],input[type=password]{
  width:100%;
  background:var(--surface);
  color:var(--txt);
  border:1px solid var(--border);
  border-radius:var(--radius-sm);
  padding:7px 11px;
  font-family:var(--font);font-size:13px;
  outline:none;
  transition:border-color 0.15s,box-shadow 0.15s;
  caret-color:var(--accent);
}
input[type=text]:focus,input[type=password]:focus{
  border-color:var(--accent);
  box-shadow:0 0 0 2px var(--accent-glow);
}
input[type=text]::placeholder,input[type=password]::placeholder{color:var(--txt3)}
input[type=number]{
  width:68px;
  background:var(--surface);
  color:var(--txt);
  border:1px solid var(--border);
  border-radius:var(--radius-sm);
  padding:7px 8px;
  font-family:var(--font);font-size:13px;
  outline:none;
  caret-color:var(--accent);
}
input[type=number]:focus{border-color:var(--accent);box-shadow:0 0 0 2px var(--accent-glow)}
.folder-row{display:flex;gap:8px;width:100%}
.folder-row input{flex:1}
.action-row{display:flex;align-items:center;gap:14px;margin-top:4px}
.workers-cell{display:flex;align-items:center;gap:8px;color:var(--txt2);font-size:12px}
.btn{
  display:inline-flex;align-items:center;gap:6px;
  padding:7px 18px;
  border-radius:var(--radius-sm);
  border:1px solid var(--border);
  background:var(--card2);
  color:var(--txt);
  font-family:var(--font);font-size:13px;font-weight:500;
  cursor:pointer;
  transition:background 0.14s,border-color 0.14s,transform 0.08s,box-shadow 0.14s;
  white-space:nowrap;
  user-select:none;
}
.btn:hover{background:var(--border);border-color:var(--border2)}
.btn:active{transform:scale(0.97)}
.btn:disabled{opacity:0.4;cursor:not-allowed;transform:none}
.btn-accent{
  background:linear-gradient(135deg,var(--accent),var(--accent2));
  border:none;
  color:#001828;
  font-weight:600;
  box-shadow:0 2px 16px rgba(96,205,255,0.25);
}
.btn-accent:hover{
  background:linear-gradient(135deg,#7ADAFF,#4AAFEA);
  box-shadow:0 4px 24px rgba(96,205,255,0.4);
}
.btn-sm{padding:5px 12px;font-size:12px}
.btn-danger{
  background:transparent;
  color:var(--danger);
  border-color:rgba(248,114,114,0.3);
}
.btn-danger:hover{background:rgba(248,114,114,0.1);border-color:var(--danger)}
.stat-tiles{display:grid;grid-template-columns:1fr auto auto;gap:8px;margin-bottom:12px}
.stat-tile{
  background:var(--surface);
  border:1px solid var(--border);
  border-radius:var(--radius-sm);
  padding:10px 14px;
}
.stat-val{
  font-family:var(--mono);font-size:14px;font-weight:600;
  color:var(--txt);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;
}
.stat-cap{font-size:10px;color:var(--txt3);margin-top:2px;letter-spacing:0.5px}
.bar-label{font-size:10px;color:var(--txt3);margin-bottom:4px;font-weight:500}
.bar-track{
  height:4px;
  background:var(--border);
  border-radius:2px;
  overflow:hidden;
  margin-bottom:10px;
}
.bar-fill{
  height:100%;border-radius:2px;
  background:linear-gradient(90deg,var(--accent),var(--accent2));
  width:0%;
  transition:width 0.25s ease;
  position:relative;
}
.bar-fill.green{background:linear-gradient(90deg,#4EC994,#38E890)}
.bar-fill::after{
  content:'';
  position:absolute;right:0;top:-2px;
  width:8px;height:8px;border-radius:50%;
  background:var(--accent);
  box-shadow:0 0 8px var(--accent);
  opacity:0;transition:opacity 0.2s;
}
.bar-fill.active::after{opacity:1}
.bar-fill.green::after{background:#4EC994;box-shadow:0 0 8px #4EC994}
.status-txt{font-size:11px;color:var(--txt3);margin-top:4px}
.log-box{
  background:var(--surface);
  border:1px solid var(--border);
  border-radius:var(--radius-sm);
  padding:12px;
  font-family:var(--mono);font-size:11.5px;
  line-height:1.7;
  height:160px;
  overflow-y:auto;
  color:var(--txt2);
}
.log-box::-webkit-scrollbar{width:4px}
.log-box::-webkit-scrollbar-thumb{background:var(--border);border-radius:2px}
.log-line{padding:0;display:block}
.log-line.success{color:#4EC994}
.log-line.danger{color:var(--danger)}
.log-line.warn{color:var(--warn)}
.log-line.muted{color:var(--txt3)}
.upload-list{
  display:flex;
  flex-direction:column;
  gap:8px;
}
.upload-row{
  background:var(--surface);
  border:1px solid var(--border);
  border-radius:var(--radius-sm);
  padding:10px 12px;
}
.upload-top{
  display:flex;
  justify-content:space-between;
  gap:10px;
  margin-bottom:6px;
  font-size:12px;
}
.upload-name{
  font-family:var(--mono);
  color:var(--txt);
  overflow:hidden;
  text-overflow:ellipsis;
  white-space:nowrap;
}
.upload-meta{
  color:var(--txt3);
  font-size:11px;
  white-space:nowrap;
}
.upload-track{
  height:4px;
  background:var(--border);
  border-radius:2px;
  overflow:hidden;
}
.upload-fill{
  height:100%;
  width:0%;
  background:linear-gradient(90deg,var(--accent),var(--accent2));
  transition:width .2s ease;
}
.assets-toolbar{display:flex;align-items:center;gap:12px;margin-bottom:12px}
.assets-summary{flex:1;font-size:12px;color:var(--txt2)}
.asset-list{display:flex;flex-direction:column;gap:6px}
.asset-row{
  display:flex;align-items:center;gap:12px;
  background:var(--surface);
  border:1px solid var(--border);
  border-radius:var(--radius-sm);
  padding:10px 14px;
  transition:border-color 0.15s,background 0.15s;
}
.asset-row:hover{border-color:var(--border2);background:var(--card2)}
.asset-icon{color:var(--txt3);font-size:15px;flex-shrink:0}
.asset-info{flex:1;min-width:0}
.asset-name{
  font-family:var(--mono);font-size:12px;color:var(--txt);
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis;
}
.asset-size{font-size:10px;color:var(--txt3);margin-top:2px}
.empty-state{
  text-align:center;padding:48px 0;
  color:var(--txt3);font-size:13px;
}
.empty-icon{font-size:32px;margin-bottom:10px;opacity:0.4}
.log-page-box{
  background:var(--card);
  border:1px solid var(--border);
  border-radius:var(--radius);
  padding:14px;
  font-family:var(--mono);font-size:12px;
  line-height:1.8;
  flex:1;
  overflow-y:auto;
  color:var(--txt2);
  height: calc(100vh - var(--hdr-h) - 100px);
}
.log-page-box::-webkit-scrollbar{width:6px}
.log-page-box::-webkit-scrollbar-thumb{background:var(--border);border-radius:3px}
.divider{height:1px;background:var(--border);margin:14px 0}
#toast{
  position:fixed;bottom:24px;right:24px;
  background:var(--card2);
  border:1px solid var(--border2);
  border-radius:var(--radius);
  padding:12px 18px;
  font-size:13px;color:var(--txt);
  box-shadow:none;
  transform:translateY(80px);opacity:0;
  transition:none;
  pointer-events:none;
  z-index:999;
  max-width:340px;
}
#toast.show{transform:translateY(0);opacity:1}
#toast.success{border-color:rgba(78,201,148,0.4)}
#toast.error{border-color:rgba(248,114,114,0.4)}
</style>
</head>
<body>
<div id="titlebar">
  <div class="tb-dot"></div>
  <div id="tb-title">GitHub Release Uploader</div>
  <div id="tb-status"></div>
</div>

<div id="shell">
<nav>
  <div class="nav-section">Navigation</div>
  <div class="nav-item active" data-page="upload" onclick="switchPage('upload',this)">
    <span class="nav-icon">↑</span> Upload
  </div>
  <div class="nav-item" data-page="assets" onclick="switchPage('assets',this)">
    <span class="nav-icon">▤</span> Assets
  </div>
  <div class="nav-item" data-page="log" onclick="switchPage('log',this)">
    <span class="nav-icon">≡</span> Activity log
  </div>
  <div class="spacer"></div>
  <div class="nav-footer">GitHub API 2022-11-28</div>
</nav>

<div id="content">
  <div class="page active" id="page-upload">
    <div class="card">
      <div class="card-title"><span class="ct-icon">⬡</span> Connection</div>
      <div class="field-grid two-col">
        <span class="field-label">GitHub token</span>
        <input type="password" id="token" placeholder="ghp_xxxxxxxxxxxxxxxxxxxx">
        <span class="field-label">Repository</span>
        <input type="text" id="repo" placeholder="owner/repository">
        <span class="field-label">Release tag</span>
        <input type="text" id="tag" placeholder="v1.0.0">
        <span></span><span></span>
      </div>
    </div>

    <div class="card">
      <div class="card-title"><span class="ct-icon">↑</span> Upload</div>
      <div class="field-grid" style="margin-bottom:14px">
        <span class="field-label">Files / Folder</span>
        <div class="folder-row">
          <input type="text" id="folder" placeholder="Select files or folder…" readonly>
          <button class="btn" id="browse-btn" onclick="browseFiles()">Browse…</button>
        </div>
      </div>
      <div class="action-row">
        <div class="workers-cell">
          <span>Workers</span>
          <input type="number" id="workers" value="4" min="1" max="16">
        </div>
        <button class="btn btn-accent" id="upload-btn" onclick="startUpload()">
          ↑ Upload files
        </button>
      </div>
    </div>

    <div class="card">
      <div class="card-title"><span class="ct-icon">◎</span> Progress</div>
      <div class="stat-tiles">
        <div class="stat-tile">
          <div class="stat-val" id="st-file">—</div>
          <div class="stat-cap">CURRENT FILE</div>
        </div>
        <div class="stat-tile">
          <div class="stat-val" id="st-speed">—</div>
          <div class="stat-cap">SPEED</div>
        </div>
        <div class="stat-tile">
          <div class="stat-val" id="st-eta">—</div>
          <div class="stat-cap">TOTAL ETA</div>
        </div>
      </div>

      <div class="bar-label">Overall</div>
      <div class="bar-track"><div class="bar-fill green" id="overall-bar"></div></div>
      <div class="status-txt" id="status-txt">Ready</div>

      <div class="divider"></div>
      <div class="card-title" style="margin-bottom:10px">
        <span class="ct-icon">▤</span> Active uploads
      </div>
      <div id="active-uploads" class="upload-list"></div>
    </div>

    <div class="card">
      <div class="card-title" style="margin-bottom:10px">
        <span class="ct-icon">≡</span> Log
        <span style="margin-left:auto">
          <button class="btn btn-sm" onclick="clearLog('upload-log')">Clear</button>
        </span>
      </div>
      <div class="log-box" id="upload-log"></div>
    </div>
  </div>

  <div class="page" id="page-assets">
    <div class="assets-toolbar">
      <span class="assets-summary" id="asset-summary">No assets loaded</span>
      <button class="btn" id="load-btn" onclick="loadAssets()">Refresh</button>
    </div>
    <div class="card" style="flex:1">
      <div id="asset-list" class="asset-list">
        <div class="empty-state">
          <div class="empty-icon">▤</div>
          Click Refresh to load assets from this release.
        </div>
      </div>
    </div>
  </div>

  <div class="page" id="page-log">
    <div style="display:flex;align-items:center;gap:12px;margin-bottom:4px">
      <span style="font-size:15px;font-weight:600;color:var(--txt)">Activity log</span>
      <button class="btn btn-sm" style="margin-left:auto" onclick="clearLog('full-log')">Clear</button>
    </div>
    <div class="log-page-box" id="full-log"></div>
  </div>
</div>
</div>

<div id="toast"></div>

<script>
function switchPage(id, el) {
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
  document.getElementById('page-' + id).classList.add('active');
  el.classList.add('active');
}

let selectedPaths = [];

async function browseFiles() {
  try {
    const result = await window.pywebview.api.browse_files();

    if (result && result.length) {
      selectedPaths = result;

      document.getElementById('folder').value =
        result.length === 1
          ? result[0]
          : `${result.length} items selected`;
    }
  } catch(e) {}
}

function getFields() {
  return {
    token: document.getElementById('token').value.trim(),
    repo: document.getElementById('repo').value.trim(),
    tag: document.getElementById('tag').value.trim(),
    paths: selectedPaths,
    workers: parseInt(document.getElementById('workers').value) || 2,
  };
}

async function startUpload() {
  const f = getFields();
  if (!f.token || !f.repo || !f.tag || !f.paths.length) {
    showToast('All fields are required.', 'error');
    return;
  }
  setBusy(true);
  resetProgress();
  document.getElementById('active-uploads').innerHTML = '';
  uploads.clear();
  speeds.clear();
  updateTotalSpeed();
  const r = await fetch('/upload', {
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify(f)
  });
  if (!r.ok) {
    const d = await r.json();
    showToast(d.error, 'error');
    setBusy(false);
  }
}

async function loadAssets() {
  const f = getFields();

  if (!f.token || !f.repo || !f.tag) {
    showToast('Token, repo, and tag required.', 'error');
    return;
  }

  document.getElementById('load-btn').disabled = true;

  try {
    await fetch('/assets', {
      method:'POST',
      headers:{
        'Content-Type':'application/json'
      },
      body:JSON.stringify({
        token:f.token,
        repo:f.repo,
        tag:f.tag
      })
    });
  } catch(e) {
    showToast(e.message,'error');
    document.getElementById('load-btn').disabled = false;
  }
}

async function deleteAsset(url, name) {
  if (!confirm(`Delete "${name}" from this release?\n\nThis cannot be undone.`)) return;
  const token = document.getElementById('token').value.trim();
  if (!token) { showToast('Enter token first.', 'error'); return; }
  setBusy(true);
  await fetch('/delete', {
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({token,url,name})
  });
}

function ensureUploadRow(id, name) {
  if (uploads.has(id)) return uploads.get(id);

  const list = document.getElementById('active-uploads');
  const row = document.createElement('div');
  row.className = 'upload-row';
  row.id = 'upload-' + id;
  row.innerHTML = `
    <div class="upload-top">
      <div class="upload-name"></div>
      <div class="upload-meta">0%</div>
    </div>
    <div class="upload-track"><div class="upload-fill"></div></div>
  `;
  row.querySelector('.upload-name').textContent = name || 'Uploading...';
  list.appendChild(row);

  const obj = {
    row,
    nameEl: row.querySelector('.upload-name'),
    metaEl: row.querySelector('.upload-meta'),
    fillEl: row.querySelector('.upload-fill')
  };
  uploads.set(id, obj);
  return obj;
}

function removeUploadRow(id) {
  const obj = uploads.get(id);
  if (!obj) return;
  obj.row.remove();
  uploads.delete(id);
}

function renderAssets(items) {
  const list = document.getElementById('asset-list');
  const sum = document.getElementById('asset-summary');
  list.innerHTML = '';
  if (!items.length) {
    sum.textContent = 'No assets on this release.';
    list.innerHTML = '<div class="empty-state"><div class="empty-icon">▤</div>No assets on this release.</div>';
    return;
  }
  sum.textContent = `${items.length} asset${items.length!==1 ? 's' : ''}`;
  items.forEach(a => {
    const row = document.createElement('div');
    row.className = 'asset-row';
    row.innerHTML = `
      <span class="asset-icon">▪</span>
      <div class="asset-info">
        <div class="asset-name">${escHtml(a.name)}</div>
        <div class="asset-size">${a.size}</div>
      </div>
      <button class="btn btn-sm btn-danger" onclick="deleteAsset(${JSON.stringify(a.url)},${JSON.stringify(a.name)})">Delete</button>
    `;
    list.appendChild(row);
  });
}

function appendLog(id, msg, cls='') {
  const box = document.getElementById(id);
  const line = document.createElement('span');
  line.className = 'log-line ' + (cls || '');
  line.textContent = msg + '\n';
  box.appendChild(line);
  box.scrollTop = box.scrollHeight;
}

function clearLog(id) {
  document.getElementById(id).innerHTML = '';
}

function resetProgress() {
  const b = document.getElementById('overall-bar');
  b.style.width = '0%';
  b.classList.remove('active');
  ['st-file','st-speed','st-eta'].forEach(id => document.getElementById(id).textContent = '—');
  document.getElementById('status-txt').textContent = 'Starting…';
}

let _busy = false;
function setBusy(v) {
  _busy = v;
  const ids = ['upload-btn','browse-btn','token','repo','tag','folder','workers'];
  ids.forEach(id => {
    const el = document.getElementById(id);
    if (el) el.disabled = v;
  });
  document.getElementById('tb-status').textContent = v ? 'Working…' : '';
}

let _toastTimer;
function showToast(msg, type='') {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.className = 'show ' + (type || '');
  clearTimeout(_toastTimer);
  _toastTimer = setTimeout(() => t.className = '', 3500);
}

function escHtml(s) {
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function parseSpeedToBps(text) {
  const m = String(text || '0 B/s').match(/^([\d.]+)\s*([KMGTP]?B)\/s$/i);
  if (!m) return 0;
  const v = parseFloat(m[1]);
  const u = m[2].toUpperCase();
  const mult = {B:1, KB:1024, MB:1024**2, GB:1024**3, TB:1024**4, PB:1024**5}[u] || 1;
  return v * mult;
}

function formatSpeed(bps) {
  if (!bps || bps < 1) return '0 B/s';
  const units = ['B/s','KB/s','MB/s','GB/s','TB/s'];
  let i = 0;
  let v = bps;
  while (v >= 1024 && i < units.length - 1) {
    v /= 1024;
    i++;
  }
  return `${v.toFixed(i === 0 ? 0 : 2)} ${units[i]}`;
}

function parseEtaToSeconds(text) {
  const m = String(text || '').match(/^([\d.]+)s$/i);
  return m ? parseFloat(m[1]) : 0;
}

function formatSeconds(sec) {
  if (!sec || sec <= 0) return '—';
  const seconds = Math.round(sec);
  const mins = Math.floor(seconds / 60);
  if (mins > 0) {
    return `${mins}m ${seconds % 60}s`;
  }
  return `${seconds}s`;
}

function updateTotalSpeed() {
  const total = [...speeds.values()].reduce((a, b) => a + b, 0);
  document.getElementById('st-speed').textContent = formatSpeed(total);
}

function updateTotalEta() {
  const total = [...etas.values()].reduce((a, b) => a + b, 0);
  document.getElementById('st-eta').textContent = formatSeconds(total);
}

const uploads = new Map();
const speeds = new Map();
const etas = new Map();

let eventQueue = [];
let rendering = false;

function processEvents(){

    if(rendering) return;

    rendering = true;

    requestAnimationFrame(()=>{

        while(eventQueue.length){

            handleEvent(
                eventQueue.shift()
            );

        }

        rendering=false;

    });
}

const es = new EventSource('/events');
es.onmessage = e => {

    eventQueue.push(
        JSON.parse(e.data)
    );

    processEvents();
};


function handleEvent(d){

  switch(d.kind) {
    case 'log':
      appendLog('upload-log', d.msg, d.cls);
      appendLog('full-log', d.msg, d.cls);
      break;

    case 'current': {
      const obj = ensureUploadRow(d.id, d.name);
      const nextName = d.name || 'Uploading...';
      if (document.getElementById('st-file').textContent !== nextName) {
        document.getElementById('st-file').textContent = nextName;
      }
      const nextStatus = 'Uploading ' + nextName;
      if (document.getElementById('status-txt').textContent !== nextStatus) {
        document.getElementById('status-txt').textContent = nextStatus;
      }
      if (obj.nameEl.textContent !== nextName) obj.nameEl.textContent = nextName;
      speeds.set(d.id, 0);
      etas.set(d.id, 0);
      updateTotalSpeed();
      updateTotalEta();
      break;
    }

    case 'file': {
      const obj = ensureUploadRow(d.id, d.name || 'Uploading...');
      const pctText = `${d.pct}% • ${d.speed} • ${d.eta}`;
      if (obj.fillEl.style.width !== d.pct + '%') obj.fillEl.style.width = d.pct + '%';
      if (obj.metaEl.textContent !== pctText) obj.metaEl.textContent = pctText;
      speeds.set(d.id, parseSpeedToBps(d.speed));
      const etaSeconds = typeof d.eta_seconds === 'number' ? d.eta_seconds : parseEtaToSeconds(d.eta);
      etas.set(d.id, etaSeconds);
      updateTotalSpeed();
      updateTotalEta();
      const nextName = d.name || document.getElementById('st-file').textContent;
      if (document.getElementById('st-file').textContent !== nextName) {
        document.getElementById('st-file').textContent = nextName;
      }
      break;
    }

    case 'done-file':
      speeds.delete(d.id);
      etas.delete(d.id);
      removeUploadRow(d.id);
      updateTotalSpeed();
      updateTotalEta();
      break;

    case 'overall': {
      const bar = document.getElementById('overall-bar');
      if (bar.style.width !== d.pct + '%') bar.style.width = d.pct + '%';
      bar.classList.toggle('active', d.pct > 0 && d.pct < 100);
      const nextStatus = 'Completed ' + d.label;
      if (document.getElementById('status-txt').textContent !== nextStatus) {
        document.getElementById('status-txt').textContent = nextStatus;
      }
      break;
    }

    case 'assets':
      renderAssets(d.items);
      setBusy(false);
      document.getElementById('load-btn').disabled = false;
      break;

    case 'deleted':
      loadAssets();
      break;

    case 'done':
      showToast(d.msg, 'success');
      setBusy(false);
      document.getElementById('overall-bar').style.width = '100%';
      document.getElementById('overall-bar').classList.remove('active');
      break;

    case 'error':
      showToast(d.msg, 'error');
      setBusy(false);
      document.getElementById('load-btn').disabled = false;
      break;
  }
};
</script>
</body>
</html>"""


class PyWebViewAPI:

    def browse_files(self):

      win = webview.windows[0]

      try:
          open_dialog = (
              webview.FileDialog.OPEN
              if hasattr(webview, "FileDialog")
              else webview.OPEN_DIALOG
          )

          result = win.create_file_dialog(
              open_dialog,
              allow_multiple=True
          )

          if result:
              return list(result)

      except Exception:
          pass


      try:
          folder_dialog = (
              webview.FileDialog.FOLDER
              if hasattr(webview, "FileDialog")
              else webview.FOLDER_DIALOG
          )

          folder = win.create_file_dialog(
              folder_dialog,
              allow_multiple=False
          )

          if folder:
              return list(folder)

      except Exception:
          pass


      return []


def _find_port():
    import socket
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def _run_flask(port):
    import logging
    log = logging.getLogger("werkzeug")
    log.setLevel(logging.ERROR)
    flask_app.run(host="127.0.0.1", port=port, threaded=True, use_reloader=False)


def main():
    port = _find_port()
    t = threading.Thread(target=_run_flask, args=(port,), daemon=True)
    t.start()
    time.sleep(0.4)

    webview.create_window(
        title="GitHub Release Uploader",
        url=f"http://127.0.0.1:{port}/",
        js_api=PyWebViewAPI(),
        width=1060,
        height=740,
        min_size=(800, 560),
        frameless=False,
        easy_drag=False,
        background_color="#0A0F1A",
    )
    webview.start(debug=False)


if __name__ == "__main__":
    main()