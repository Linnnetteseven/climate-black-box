"""Capture the README screenshots from the running site.

Usage: start the API and `make web`, then

    .venv/bin/python scripts/capture_screenshots.py desktop
    .venv/bin/python scripts/capture_screenshots.py mobile

Offsets are measured against the current page; if a section is added or
removed they need re-measuring, which `measure` prints.


The page is scroll-driven, so a plain --screenshot only ever gets the hero.
This scrolls to a given offset, waits for the scroll-linked animation to
settle, and captures what a visitor would actually be looking at.
"""
import asyncio, base64, json, os, pathlib, subprocess, sys, time, urllib.request
import websockets

# Playwright's bundled Chromium, if it is present. Override with CBB_CHROME.
CHROME = os.environ.get("CBB_CHROME") or next(
    (str(p) for p in sorted(
        pathlib.Path.home().glob(".cache/ms-playwright/chromium-*/chrome-linux64/chrome"))),
    "chromium")
PORT = 9222
OUT = str(pathlib.Path(__file__).resolve().parents[1] / "docs" / "screenshots")


def launch(width, height):
    p = subprocess.Popen(
        [CHROME, "--headless=new", f"--remote-debugging-port={PORT}",
         "--no-sandbox", "--disable-gpu", "--hide-scrollbars",
         f"--window-size={width},{height}", "--force-device-scale-factor=2",
         "about:blank"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(60):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json/version", timeout=1)
            return p
        except Exception:
            time.sleep(0.5)
    raise SystemExit("chrome did not come up")


async def run(shots, url, width, height):
    tabs = json.load(urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json"))
    ws_url = [t for t in tabs if t["type"] == "page"][0]["webSocketDebuggerUrl"]
    async with websockets.connect(ws_url, max_size=120 * 1024 * 1024) as ws:
        n = 0
        async def send(method, params=None):
            nonlocal n
            n += 1
            await ws.send(json.dumps({"id": n, "method": method, "params": params or {}}))
            while True:
                msg = json.loads(await ws.recv())
                if msg.get("id") == n:
                    return msg.get("result", {})

        await send("Page.enable")
        await send("Emulation.setDeviceMetricsOverride",
                   {"width": width, "height": height, "deviceScaleFactor": 2,
                    "mobile": width < 768})
        await send("Page.navigate", {"url": url})
        await asyncio.sleep(9)  # fonts, imagery, first paint of the globe

        for name, y, settle in shots:
            await send("Runtime.evaluate",
                       {"expression": f"window.scrollTo({{top:{y},behavior:'instant'}})"})
            await asyncio.sleep(settle)
            r = await send("Page.captureScreenshot", {"format": "png"})
            path = f"{OUT}/{name}.png"
            open(path, "wb").write(base64.b64decode(r["data"]))
            print(f"  {name}.png  (y={y})")


async def measure(url, width, height):
    """Print the scroll offset of every heading, so the lists below can be fixed."""
    tabs = json.load(urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json"))
    ws_url = [t for t in tabs if t["type"] == "page"][0]["webSocketDebuggerUrl"]
    async with websockets.connect(ws_url, max_size=120 * 1024 * 1024) as ws:
        n = 0
        async def send(m, p=None):
            nonlocal n
            n += 1
            await ws.send(json.dumps({"id": n, "method": m, "params": p or {}}))
            while True:
                r = json.loads(await ws.recv())
                if r.get("id") == n:
                    return r.get("result", {})
        await send("Page.enable")
        await send("Emulation.setDeviceMetricsOverride",
                   {"width": width, "height": height, "deviceScaleFactor": 1,
                    "mobile": width < 768})
        await send("Page.navigate", {"url": url})
        await asyncio.sleep(10)
        r = await send("Runtime.evaluate", {"returnByValue": True, "expression": """
            (()=>{const o=['doc height: '+document.body.scrollHeight];
            document.querySelectorAll('h2,h3').forEach(e=>{
              const t=e.textContent.trim().slice(0,44);
              const y=Math.round(e.getBoundingClientRect().top+scrollY);
              if(t)o.push(String(y).padStart(6)+'  '+t)});return o.join('\\n')})()"""})
        print(r["result"]["value"])


if __name__ == "__main__":
    mode = sys.argv[1]
    if mode == "measure":
        W, H = (390, 844) if len(sys.argv) > 2 and sys.argv[2] == "mobile" else (1440, 900)
        proc = launch(W, H)
        try:
            asyncio.run(measure("http://localhost:3000", W, H))
        finally:
            proc.terminate()
        raise SystemExit
    if mode == "desktop":
        W, H = 1440, 900
        shots = [("01-hero", 0, 2.5), ("02-promise", 900, 3.0),
                 ("03-landsat", 3400, 3.5), ("04-boundary", 5900, 3.0),
                 ("05-forest-observe", 7400, 3.5), ("06-forest-detect", 9200, 3.5),
                 ("07-forest-investigate", 10600, 3.5), ("08-chart", 11780, 3.0),
                 ("09-alert", 12300, 3.0), ("10-investigation", 13060, 3.0),
                 ("11-hypotheses", 13380, 3.0), ("12-intervention", 14250, 3.0),
                 ("13-verify", 15150, 3.0), ("14-evidence-chain", 15450, 3.0)]
    else:
        W, H = 390, 844
        shots = [("mobile-01-hero", 0, 3.0), ("mobile-02-alert", 7850, 3.0),
                 ("mobile-03-verify", 13560, 3.0)]
    proc = launch(W, H)
    try:
        asyncio.run(run(shots, "http://localhost:3000", W, H))
    finally:
        proc.terminate()
