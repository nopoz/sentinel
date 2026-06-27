import copy
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse

from soc_console.seed import SCENARIOS

app = FastAPI(title="SOC Console")

# In-process mutable state seeded at import time
_alerts = {a["id"]: copy.deepcopy(a) for a in SCENARIOS["alerts"]}
_assets = copy.deepcopy(SCENARIOS["assets"])


# ---- Alert queue ----

@app.get("/", response_class=HTMLResponse)
@app.get("/alerts", response_class=HTMLResponse)
def alert_queue():
    rows = ""
    for alert in _alerts.values():
        severity_badge = f'<span class="badge badge-{alert["severity"]}">{alert["severity"].upper()}</span>'
        rows += (
            f'<tr data-testid="alert-row-{alert["id"]}">'
            f'<td>{alert["id"]}</td>'
            f'<td><a href="/alerts/{alert["id"]}">{alert["title"]}</a></td>'
            f'<td>{severity_badge}</td>'
            f'<td><a href="/assets/{alert["asset_id"]}">{alert["asset_id"]}</a></td>'
            f'</tr>\n'
        )
    html = f"""<!DOCTYPE html>
<html>
<head><title>SOC Alert Queue</title></head>
<body>
<h1>Alert Queue</h1>
<table>
  <thead><tr><th>ID</th><th>Title</th><th>Severity</th><th>Asset</th></tr></thead>
  <tbody>
    {rows}
  </tbody>
</table>
</body>
</html>"""
    return HTMLResponse(content=html)


# ---- Alert detail ----

@app.get("/alerts/{alert_id}", response_class=HTMLResponse)
def alert_detail(alert_id: str):
    alert = _alerts.get(alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail="Alert not found")

    evidence_items = ""
    for n, ev in enumerate(alert["evidence"], start=1):
        evidence_items += f'<li data-testid="evidence-{n}">{ev}</li>\n'

    html = f"""<!DOCTYPE html>
<html>
<head><title>Alert {alert_id}</title></head>
<body>
<h1>Alert {alert_id}: {alert["title"]}</h1>
<p>Severity: {alert["severity"]}</p>
<p>Recommended action: {alert["recommended"]}</p>
<h2>Evidence</h2>
<ul>
  {evidence_items}
</ul>
<p>Asset: <a data-testid="asset-link-{alert["asset_id"]}" href="/assets/{alert["asset_id"]}">{alert["asset_id"]}</a></p>
</body>
</html>"""
    return HTMLResponse(content=html)


# ---- Asset detail ----

@app.get("/assets/{asset_id}", response_class=HTMLResponse)
def asset_detail(asset_id: str):
    asset = _assets.get(asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="Asset not found")

    # Find the alert that belongs to this asset so the resolve button posts to the right URL
    matching_alert = next((a for a in _alerts.values() if a["asset_id"] == asset_id), None)
    resolve_action = f"/alerts/{matching_alert['id']}/resolve" if matching_alert else f"/assets/{asset_id}"

    html = f"""<!DOCTYPE html>
<html>
<head><title>Asset {asset_id}</title></head>
<body>
<h1>Asset: {asset["hostname"]}</h1>
<p>IP: {asset["ip"]}</p>
<p>Status: <span data-testid="asset-status">{asset["status"]}</span></p>
<h2>Remediation</h2>
<form method="post" action="/assets/{asset_id}/quarantine">
  <button type="submit" data-testid="btn-quarantine">Quarantine</button>
</form>
<form method="post" action="/assets/{asset_id}/block-ip">
  <button type="submit" data-testid="btn-block-ip">Block IP</button>
</form>
<form method="post" action="{resolve_action}">
  <button type="submit" data-testid="btn-resolve">Resolve</button>
</form>
</body>
</html>"""
    return HTMLResponse(content=html)


# ---- Remediation POST endpoints ----

def _status_badge_html(asset: dict) -> str:
    return f'<span data-testid="asset-status">{asset["status"]}</span>'


@app.post("/assets/{asset_id}/quarantine", response_class=HTMLResponse)
def quarantine_asset(asset_id: str):
    asset = _assets.get(asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="Asset not found")
    asset["status"] = "quarantined"
    return HTMLResponse(content=_status_badge_html(asset))


@app.post("/assets/{asset_id}/block-ip", response_class=HTMLResponse)
def block_ip(asset_id: str):
    asset = _assets.get(asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="Asset not found")
    asset["status"] = "blocked"
    return HTMLResponse(content=_status_badge_html(asset))


@app.post("/alerts/{alert_id}/resolve", response_class=HTMLResponse)
def resolve_alert(alert_id: str):
    alert = _alerts.get(alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail="Alert not found")
    alert["status"] = "resolved"
    return HTMLResponse(content='<span data-testid="alert-status">resolved</span>')


# ---- Demo reset ----

@app.post("/reset")
def reset_console():
    """Reseed the in-memory alert/asset state so a new demo starts clean."""
    global _alerts, _assets
    _alerts = {a["id"]: copy.deepcopy(a) for a in SCENARIOS["alerts"]}
    _assets = copy.deepcopy(SCENARIOS["assets"])
    return JSONResponse(content={"ok": True})


# ---- JSON API ----

@app.get("/api/asset/{asset_id}")
def api_asset(asset_id: str):
    asset = _assets.get(asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="Asset not found")
    return JSONResponse(content={
        "id": asset["id"],
        "hostname": asset["hostname"],
        "ip": asset["ip"],
        "status": asset["status"],
    })
