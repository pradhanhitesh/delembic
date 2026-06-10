"""
Localhost web server — visualizes Alembic + Delembic migration history.

    delembic serve [--port 8800] [--no-browser]
    python -m delembic.server
"""
from __future__ import annotations

import http.server
import json
import threading
import webbrowser
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

# ---------------------------------------------------------------------------
# HTML template — DATA_PLACEHOLDER replaced server-side with embedded JSON
# ---------------------------------------------------------------------------

_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Delembic — Migration History</title>
<style>
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif;font-size:14px;line-height:1.5;color:#1f2328;background:#f6f8fa}

/* Header */
.hdr{background:#24292f;color:#f0f6fc;padding:12px 24px;display:flex;align-items:center;gap:12px}
.hdr-logo{font-weight:700;font-size:16px;letter-spacing:-.3px}
.hdr-logo em{color:#58a6ff;font-style:normal}
.hdr-space{flex:1}
.upd{font-size:12px;color:#8b949e}
.btn-refresh{background:#21262d;border:1px solid #30363d;color:#c9d1d9;padding:5px 14px;border-radius:6px;cursor:pointer;font-size:13px}
.btn-refresh:hover{background:#30363d}

/* Stats */
.stats{background:#fff;border-bottom:1px solid #d0d7de;padding:10px 24px;display:flex;align-items:center;gap:20px;flex-wrap:wrap}
.stat{display:flex;align-items:center;gap:8px;font-size:13px}
.stat-lbl{color:#656d76}
.b{display:inline-flex;align-items:center;padding:1px 8px;border-radius:12px;font-size:12px;font-weight:600;line-height:20px}
.b-g{background:#dafbe1;color:#1a7f37}
.b-r{background:#ffebe9;color:#cf222e}
.b-y{background:#fff8c5;color:#9a6700}
.b-n{background:#f6f8fa;color:#656d76;border:1px solid #d0d7de}
.db-hint{margin-left:auto;font-size:12px;color:#8b949e;font-family:monospace}

/* Tabs */
.tabs{background:#fff;border-bottom:1px solid #d0d7de;padding:0 24px;display:flex}
.tab{padding:12px 16px;cursor:pointer;color:#656d76;border-bottom:2px solid transparent;margin-bottom:-1px;font-size:14px;user-select:none}
.tab:hover{color:#1f2328}
.tab.on{color:#1f2328;border-bottom-color:#fd8c73;font-weight:600}

/* Content */
.content{max-width:1200px;margin:0 auto;padding:20px 24px}

/* Two-panel grid */
.grid{display:grid;grid-template-columns:1fr 1fr;gap:16px}
@media(max-width:800px){.grid{grid-template-columns:1fr}}

/* Panel */
.panel{background:#fff;border:1px solid #d0d7de;border-radius:6px;overflow:hidden}
.ph{padding:10px 16px;background:#f6f8fa;border-bottom:1px solid #d0d7de;font-weight:600;font-size:13px;display:flex;align-items:center;gap:8px}
.ph .lbl{color:#656d76;font-weight:400}

/* Timeline rows */
.row{padding:11px 16px;border-bottom:1px solid #f0f3f6;display:flex;gap:10px;align-items:flex-start}
.row:last-child{border-bottom:none}
.row:hover{background:#f6f8fa}
.dot{width:10px;height:10px;border-radius:50%;flex-shrink:0;margin-top:4px}
.dg{background:#1a7f37}
.dr{background:#cf222e}
.dy{background:#d4a72c}
.dp{background:#d0d7de;box-shadow:0 0 0 2px #8c959f}
.rbody{flex:1;min-width:0}
.rtop{display:flex;align-items:center;gap:6px;flex-wrap:wrap}
.rev{font-family:"SFMono-Regular",Consolas,"Liberation Mono",Menlo,monospace;font-size:12px;color:#0969da;font-weight:600}
.desc{font-size:13px;color:#1f2328;margin:1px 0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.meta{font-size:12px;color:#8c959f;margin-top:1px}
.deps{font-size:11px;color:#8c959f;font-family:monospace;margin-top:3px}
.err{font-size:11px;color:#cf222e;background:#ffebe9;padding:3px 8px;border-radius:4px;margin-top:5px;font-family:monospace;white-space:pre-wrap;max-height:54px;overflow:hidden;cursor:pointer;line-height:1.4}
.err.open{max-height:300px}

/* Empty */
.empty{padding:28px 16px;text-align:center;color:#8c959f;font-size:13px}

/* Error banner */
.errbanner{background:#ffebe9;border:1px solid #ffc1c0;border-radius:6px;padding:10px 14px;color:#cf222e;font-size:13px;margin-bottom:12px}
</style>
</head>
<body>

<div class="hdr">
  <div class="hdr-logo">◈ <em>Delembic</em></div>
  <span style="color:#8b949e;font-size:13px">Migration History</span>
  <div class="hdr-space"></div>
  <span class="upd" id="upd"></span>
  <button class="btn-refresh" onclick="doRefresh()">↻ Refresh</button>
</div>

<div class="stats" id="stats"></div>

<div class="tabs">
  <div class="tab on"  id="t-overview" onclick="showTab('overview')">Overview</div>
  <div class="tab"     id="t-schema"   onclick="showTab('schema')">Schema</div>
  <div class="tab"     id="t-data"     onclick="showTab('data')">Data</div>
</div>

<div class="content">
  <div id="v-overview"></div>
  <div id="v-schema"   style="display:none"></div>
  <div id="v-data"     style="display:none"></div>
</div>

<script>
const INIT = DATA_PLACEHOLDER;
let D = INIT;

const esc = s => s == null ? '' : String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');

function badge(status) {
  const cls = {success:'b-g',applied:'b-g',failed:'b-r',pending:'b-y'}[status] || 'b-n';
  const lbl = status === 'success' ? 'applied' : status;
  return `<span class="b ${cls}">${lbl}</span>`;
}

function dotCls(status) {
  return {success:'dg',applied:'dg',failed:'dr',pending:'dp'}[status] || 'dp';
}

function fmtTs(iso) {
  if (!iso) return '';
  try { return new Date(iso).toLocaleString(undefined,{month:'short',day:'numeric',year:'numeric',hour:'2-digit',minute:'2-digit'}); }
  catch { return iso; }
}

function fmtDur(s) {
  if (s == null) return '';
  return s >= 60 ? `${(s/60).toFixed(1)}m` : `${Number(s).toFixed(2)}s`;
}

function row(item) {
  const deps = (item.depends_on||[]).filter(Boolean);
  const depsHtml = deps.length
    ? `<div class="deps">depends on: ${deps.map(d=>`<code>${esc(String(d).slice(0,12))}</code>`).join(', ')}</div>`
    : '';

  let errHtml = '';
  if (item.exception) {
    const lines = item.exception.split('\n').filter(Boolean);
    const preview = lines.slice(-4).join('\n');
    errHtml = `<div class="err" onclick="this.classList.toggle('open')">${esc(preview)}</div>`;
  }

  const dur = fmtDur(item.execution_time_seconds ?? item.duration_seconds);
  const ts  = fmtTs(item.applied_at);
  const who = [item.username, item.hostname].filter(Boolean).join('@');
  const meta = [ts, dur, who].filter(Boolean).join(' · ');

  return `<div class="row">
    <div class="dot ${dotCls(item.status)}"></div>
    <div class="rbody">
      <div class="rtop">
        <span class="rev">${esc(item.revision)}</span>
        ${badge(item.status)}
      </div>
      <div class="desc" title="${esc(item.description)}">${esc(item.description)}</div>
      ${meta ? `<div class="meta">${esc(meta)}</div>` : ''}
      ${depsHtml}${errHtml}
    </div>
  </div>`;
}

function panel(title, subtitle, rows) {
  const body = rows.length ? rows.join('') : '<div class="empty">None found.</div>';
  return `<div class="panel">
    <div class="ph">${esc(title)} <span class="lbl">${esc(subtitle)}</span></div>
    <div>${body}</div>
  </div>`;
}

function renderStats() {
  const al = D.alembic||[], dl = D.delembic||[];
  const alA = al.filter(r=>r.status==='applied').length;
  const alP = al.filter(r=>r.status==='pending').length;
  const dlA = dl.filter(r=>['success','applied'].includes(r.status)).length;
  const dlF = dl.filter(r=>r.status==='failed').length;
  const dlP = dl.filter(r=>r.status==='pending').length;

  const schemaHtml = al.length === 0
    ? `<span class="b b-n">not configured</span>`
    : `<span class="b b-g">${alA} applied</span>${alP?` <span class="b b-y">${alP} pending</span>`:''}`;

  const dataHtml = `<span class="b b-g">${dlA} applied</span>`
    + (dlF ? ` <span class="b b-r">${dlF} failed</span>` : '')
    + (dlP ? ` <span class="b b-y">${dlP} pending</span>` : '');

  const hint = D.meta?.db_hint ? `<span class="db-hint">${esc(D.meta.db_hint)}</span>` : '';

  document.getElementById('stats').innerHTML =
    `<div class="stat"><span class="stat-lbl">Schema</span>${schemaHtml}</div>` +
    `<div class="stat"><span class="stat-lbl">Data</span>${dataHtml}</div>` +
    hint;
}

function errBanner(errors) {
  if (!errors?.length) return '';
  return errors.map(e=>`<div class="errbanner">⚠ ${esc(e)}</div>`).join('');
}

function renderOverview() {
  const al = D.alembic||[], dl = D.delembic||[];
  const banners = errBanner(D.meta?.errors);
  document.getElementById('v-overview').innerHTML =
    banners +
    `<div class="grid">
      ${panel('Schema Migrations','(Alembic)', al.map(row))}
      ${panel('Data Migrations','(Delembic)', dl.map(row))}
    </div>`;
}

function renderSchema() {
  const al = D.alembic||[];
  const body = al.length ? al.map(row).join('') : '<div class="empty">Alembic not configured. Set alembic_config in delembic.ini.</div>';
  document.getElementById('v-schema').innerHTML =
    `<div class="panel"><div class="ph">Schema Migrations <span class="lbl">(Alembic)</span></div>${body}</div>`;
}

function renderData() {
  const dl = D.delembic||[];
  const body = dl.length ? dl.map(row).join('') : '<div class="empty">No Delembic migrations found.</div>';
  document.getElementById('v-data').innerHTML =
    `<div class="panel"><div class="ph">Data Migrations <span class="lbl">(Delembic)</span></div>${body}</div>`;
}

function render() {
  renderStats();
  renderOverview();
  renderSchema();
  renderData();
  const ts = D.meta?.generated_at;
  document.getElementById('upd').textContent = ts ? `Updated ${new Date(ts).toLocaleTimeString()}` : '';
}

function showTab(name) {
  ['overview','schema','data'].forEach(n => {
    document.getElementById(`v-${n}`).style.display = n === name ? '' : 'none';
    document.getElementById(`t-${n}`).className = 'tab' + (n === name ? ' on' : '');
  });
}

async function doRefresh() {
  try {
    const r = await fetch('/api/data');
    D = await r.json();
    render();
  } catch(e) { console.error(e); }
}

render();
</script>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Data collection
# ---------------------------------------------------------------------------

def _mask_url(cfg) -> str:
    url = cfg.url or ""
    if not url:
        return "env.py"
    try:
        p = urlparse(url)
        if p.password:
            url = url.replace(f":{p.password}@", ":***@")
        return url
    except Exception:
        return url


def collect_data(cfg) -> dict[str, Any]:
    errors: list[str] = []
    data: dict[str, Any] = {
        "alembic": [],
        "delembic": [],
        "meta": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "db_hint": _mask_url(cfg),
            "errors": errors,
        },
    }

    _collect_delembic(cfg, data, errors)
    _collect_alembic(cfg, data, errors)
    return data


def _collect_delembic(cfg, data: dict, errors: list) -> None:
    import sqlalchemy as sa

    from delembic.dag import topological_sort
    from delembic.db import (
        ensure_tables,
        get_applied,
        history_table,
        version_table,
    )
    from delembic.registry import load_migrations

    migrations = load_migrations(cfg.versions_dir)
    order = topological_sort(migrations) if migrations else []

    # Per-revision DB record: status, timing
    ver_rows: dict[str, dict] = {}
    # Latest exception per failed revision
    exc_rows: dict[str, str] = {}

    try:
        engine = cfg.engine()
        with engine.connect() as conn:
            ensure_tables(conn)
            conn.commit()

            rows = conn.execute(
                sa.select(
                    version_table.c.revision,
                    version_table.c.status,
                    version_table.c.applied_at,
                    version_table.c.execution_time_seconds,
                )
            ).fetchall()
            for r in rows:
                ver_rows[r[0]] = {
                    "status": r[1],
                    "applied_at": r[2].isoformat() if r[2] else None,
                    "execution_time_seconds": r[3],
                }

            # Latest username/hostname per revision from history
            uh_rows = conn.execute(
                sa.select(
                    history_table.c.revision,
                    history_table.c.username,
                    history_table.c.hostname,
                ).order_by(history_table.c.ended_at.desc())
            ).fetchall()
            uh_seen: set[str] = set()
            for r in uh_rows:
                if r[0] not in uh_seen:
                    if r[0] in ver_rows:
                        ver_rows[r[0]]["username"] = r[1]
                        ver_rows[r[0]]["hostname"] = r[2]
                    uh_seen.add(r[0])

            # Latest exception per failed revision
            exc = conn.execute(
                sa.select(
                    history_table.c.revision,
                    history_table.c.exception,
                ).where(history_table.c.status == "failed")
                .order_by(history_table.c.ended_at.desc())
            ).fetchall()
            exc_seen: set[str] = set()
            for r in exc:
                if r[0] not in exc_seen and r[1]:
                    exc_rows[r[0]] = r[1]
                    exc_seen.add(r[0])

    except Exception as e:
        errors.append(f"DB unavailable: {e}")

    for rev in order:
        cls = migrations[rev]
        info = ver_rows.get(rev, {})
        status = info.get("status", "pending")
        if status == "success":
            status = "applied"

        data["delembic"].append({
            "revision": rev,
            "description": cls.description,
            "status": status,
            "applied_at": info.get("applied_at"),
            "execution_time_seconds": info.get("execution_time_seconds"),
            "username": info.get("username"),
            "hostname": info.get("hostname"),
            "depends_on": list(cls.depends_on),
            "exception": exc_rows.get(rev),
        })


def _collect_alembic(cfg, data: dict, errors: list) -> None:
    if not cfg.alembic_config or not cfg.alembic_config.exists():
        return

    try:
        from alembic.config import Config as AlembicConfig
        from alembic.runtime.migration import MigrationContext
        from alembic.script import ScriptDirectory
    except ImportError:
        errors.append("alembic not installed — Schema tab unavailable.")
        return

    try:
        alembic_cfg = AlembicConfig(str(cfg.alembic_config))
        script = ScriptDirectory.from_config(alembic_cfg)
        heads = script.get_heads()
    except Exception as e:
        errors.append(f"Could not read Alembic scripts: {e}")
        return

    if not heads:
        return

    # Applied revisions from DB
    applied: set[str] = set()
    try:
        engine = cfg.engine()
        with engine.connect() as conn:
            ctx = MigrationContext.configure(conn)
            for head in ctx.get_current_heads():
                for rev_obj in script.iterate_revisions(head, "base"):
                    applied.add(rev_obj.revision)
    except Exception as e:
        errors.append(f"Could not read Alembic DB state: {e}")

    try:
        revisions = list(script.iterate_revisions(heads[0], "base"))
        revisions.reverse()  # base → head
    except Exception as e:
        errors.append(f"Could not walk Alembic chain: {e}")
        return

    for rev_obj in revisions:
        doc = (rev_obj.doc or "").strip() or "(no description)"
        data["alembic"].append({
            "revision": rev_obj.revision,
            "description": doc,
            "status": "applied" if rev_obj.revision in applied else "pending",
            "down_revision": (
                list(rev_obj.down_revision)
                if isinstance(rev_obj.down_revision, tuple)
                else rev_obj.down_revision
            ),
        })


# ---------------------------------------------------------------------------
# HTTP server
# ---------------------------------------------------------------------------

def _make_handler(cfg):
    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            if self.path in ("/", "/index.html"):
                data = collect_data(cfg)
                safe = json.dumps(data, ensure_ascii=True).replace("</", "<\\/")
                body = _HTML.replace("DATA_PLACEHOLDER", safe).encode("utf-8")
                self._respond(200, "text/html; charset=utf-8", body)
            elif self.path == "/api/data":
                data = collect_data(cfg)
                body = json.dumps(data, ensure_ascii=True).encode("utf-8")
                self._respond(200, "application/json", body)
            elif self.path == "/favicon.ico":
                self.send_response(204)
                self.end_headers()
            else:
                self.send_response(404)
                self.end_headers()

        def _respond(self, code: int, ct: str, body: bytes) -> None:
            self.send_response(code)
            self.send_header("Content-Type", ct)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt, *args) -> None:  # silence access logs
            pass

    return Handler


def serve(cfg, port: int = 8800, open_browser: bool = True) -> None:
    handler = _make_handler(cfg)
    httpd = http.server.HTTPServer(("127.0.0.1", port), handler)
    url = f"http://localhost:{port}"
    print(f"Delembic UI → {url}")
    print("Ctrl+C to stop.")
    if open_browser:
        threading.Timer(0.4, webbrowser.open, args=[url]).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        httpd.server_close()


# ---------------------------------------------------------------------------
# python -m delembic.server
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    from delembic.config import find_config

    ap = argparse.ArgumentParser(description="Delembic migration history UI")
    ap.add_argument("--port", type=int, default=8800)
    ap.add_argument("--no-browser", action="store_true")
    args = ap.parse_args()

    cfg = find_config()
    serve(cfg, port=args.port, open_browser=not args.no_browser)
