from __future__ import annotations

import asyncio
import base64
import json
import shutil
import socket
import subprocess
import time
import urllib.request
from pathlib import Path

import websockets


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = PROJECT_ROOT / "발표자료" / "streamlit_imgs"
CHROME = Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")
STREAMLIT_URL = "http://localhost:8501"
DEBUG_PORT = 9223

PAGES = [
    ("00_home", "중고차 데이터 분석 서비스", None),
    ("01_eda", "EDA", "EDA"),
    ("02_visualization", "시각화", "시각화"),
    ("03_model_service", "모델 서비스", "모델/서비스"),
    ("04_price_game", "가격 예측 게임", "가격 예측 게임"),
    ("05_external_data", "외부 데이터", "외부 데이터"),
    ("06_recommendation", "추천", "추천"),
    ("07_vehicle_check", "구입 판독", "구입 판독"),
    ("08_korea_adjustment", "한국 기준 보정", "한국 기준 보정"),
    ("09_my_car_prediction", "내 차 가격 예측", "내 차 가격 예측"),
]


class CdpClient:
    def __init__(self, ws_url: str) -> None:
        self.ws_url = ws_url
        self.next_id = 1
        self.ws = None

    async def __aenter__(self) -> "CdpClient":
        self.ws = await websockets.connect(self.ws_url, max_size=64 * 1024 * 1024)
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self.ws:
            await self.ws.close()

    async def send(self, method: str, params: dict | None = None) -> dict:
        assert self.ws is not None
        message_id = self.next_id
        self.next_id += 1
        await self.ws.send(json.dumps({"id": message_id, "method": method, "params": params or {}}))
        while True:
            raw = await self.ws.recv()
            data = json.loads(raw)
            if data.get("id") == message_id:
                if "error" in data:
                    raise RuntimeError(f"{method}: {data['error']}")
                return data.get("result", {})


def wait_for_port(host: str, port: int, timeout: float = 25.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=1):
                return True
        except OSError:
            time.sleep(0.3)
    return False


def ensure_streamlit() -> subprocess.Popen | None:
    if wait_for_port("127.0.0.1", 8501, timeout=1.0):
        return None
    python_exe = PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"
    if not python_exe.exists():
        python_exe = Path(shutil.which("python") or "python")
    process = subprocess.Popen(
        [str(python_exe), "-m", "streamlit", "run", "app.py", "--server.headless=true"],
        cwd=PROJECT_ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    if not wait_for_port("127.0.0.1", 8501, timeout=35.0):
        raise RuntimeError("Streamlit server did not start on port 8501.")
    return process


def launch_chrome() -> subprocess.Popen:
    if not CHROME.exists():
        raise FileNotFoundError(f"Chrome not found: {CHROME}")
    profile_dir = PROJECT_ROOT / ".capture_chrome_profile"
    profile_dir.mkdir(exist_ok=True)
    args = [
        str(CHROME),
        "--headless=new",
        "--disable-gpu",
        "--hide-scrollbars",
        f"--remote-debugging-port={DEBUG_PORT}",
        f"--user-data-dir={profile_dir}",
        "--window-size=1920,1080",
        "about:blank",
    ]
    process = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if not wait_for_port("127.0.0.1", DEBUG_PORT, timeout=20.0):
        raise RuntimeError("Chrome debugging port did not open.")
    return process


def get_ws_url() -> str:
    for _ in range(30):
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{DEBUG_PORT}/json/list", timeout=2) as response:
                tabs = json.loads(response.read().decode("utf-8"))
            for tab in tabs:
                if tab.get("type") == "page":
                    return tab["webSocketDebuggerUrl"]
        except OSError:
            pass
        time.sleep(0.3)
    raise RuntimeError("Could not find Chrome page websocket.")


async def wait_for_streamlit_ready(cdp: CdpClient, expected_text: str | None = None) -> None:
    script = """
    (() => {
      const body = document.body ? document.body.innerText : "";
      const busy = !!document.querySelector('[data-testid="stSpinner"], .stSpinner');
      return {
        body,
        ready: body.length > 300 && !busy && !body.includes("Please wait")
      };
    })()
    """
    deadline = time.time() + 25
    while time.time() < deadline:
        result = await cdp.send("Runtime.evaluate", {"expression": script, "returnByValue": True})
        value = result.get("result", {}).get("value", {})
        body = value.get("body", "")
        if value.get("ready") and (expected_text is None or expected_text in body):
            await asyncio.sleep(2.0)
            return
        await asyncio.sleep(0.5)
    await asyncio.sleep(2)


async def click_page(cdp: CdpClient, label: str) -> None:
    expression = f"""
    (() => {{
      const label = {json.dumps(label, ensure_ascii=False)};
      const candidates = Array.from(document.querySelectorAll('a, button, [role="button"]'));
      const target = candidates.find((el) => (el.innerText || el.textContent || '').trim().includes(label));
      if (!target) {{
        return {{clicked: false, labels: candidates.map((el) => (el.innerText || el.textContent || '').trim()).filter(Boolean).slice(0, 40)}};
      }}
      target.click();
      return {{clicked: true, text: (target.innerText || target.textContent || '').trim()}};
    }})()
    """
    result = await cdp.send("Runtime.evaluate", {"expression": expression, "returnByValue": True})
    value = result.get("result", {}).get("value", {})
    if not value.get("clicked"):
        raise RuntimeError(f"Could not click page '{label}'. Visible labels: {value.get('labels')}")
    await asyncio.sleep(0.8)


async def dismiss_overlays(cdp: CdpClient) -> None:
    await cdp.send(
        "Runtime.evaluate",
        {
            "expression": """
            (() => {
              const menu = document.querySelector('[data-testid="stMainMenu"]');
              const deploy = document.querySelector('[data-testid="stStatusWidget"]');
              const toolbar = document.querySelector('[data-testid="stToolbar"]');
              [menu, deploy, toolbar].forEach((el) => { if (el) el.style.display = 'none'; });
            })()
            """,
            "returnByValue": True,
        },
    )


async def capture_page(cdp: CdpClient, filename: str) -> None:
    await dismiss_overlays(cdp)
    size_result = await cdp.send(
        "Runtime.evaluate",
        {
            "expression": """
            (() => {
              const candidates = [
                document.documentElement,
                document.body,
                document.querySelector('[data-testid="stAppViewContainer"]'),
                document.querySelector('[data-testid="stMain"]'),
                document.querySelector('.stMain'),
                document.querySelector('section.main')
              ].filter(Boolean);
              const heights = candidates.flatMap((el) => [el.scrollHeight, el.offsetHeight, el.clientHeight]);
              const widths = candidates.flatMap((el) => [el.scrollWidth, el.offsetWidth, el.clientWidth]);
              return {
                height: Math.max(...heights, window.innerHeight) + 520,
                width: Math.max(...widths, window.innerWidth)
              };
            })()
            """,
            "returnByValue": True,
        },
    )
    measured = size_result.get("result", {}).get("value", {})
    width = max(1440, int(measured.get("width", 1440)))
    height = min(24000, max(1400, int(measured.get("height", 1400))))
    await cdp.send(
        "Emulation.setDeviceMetricsOverride",
        {
            "width": width,
            "height": height,
            "deviceScaleFactor": 1,
            "mobile": False,
        },
    )
    await cdp.send(
        "Runtime.evaluate",
        {
            "expression": """
            (() => {
              window.scrollTo(0, document.documentElement.scrollHeight);
              const scrollers = [
                document.querySelector('[data-testid="stAppViewContainer"]'),
                document.querySelector('[data-testid="stMain"]'),
                document.querySelector('.stMain'),
                document.querySelector('section.main')
              ].filter(Boolean);
              scrollers.forEach((el) => { el.scrollTop = el.scrollHeight; });
            })()
            """,
            "returnByValue": True,
        },
    )
    await asyncio.sleep(1.0)
    await cdp.send(
        "Runtime.evaluate",
        {
            "expression": """
            (() => {
              window.scrollTo(0, 0);
              const scrollers = [
                document.querySelector('[data-testid="stAppViewContainer"]'),
                document.querySelector('[data-testid="stMain"]'),
                document.querySelector('.stMain'),
                document.querySelector('section.main')
              ].filter(Boolean);
              scrollers.forEach((el) => { el.scrollTop = 0; });
            })()
            """,
            "returnByValue": True,
        },
    )
    await asyncio.sleep(0.6)
    metrics = await cdp.send("Page.getLayoutMetrics")
    content = metrics["contentSize"]
    final_height = max(height, int(content.get("height", height)) + 260)
    clip = {
        "x": 0,
        "y": 0,
        "width": max(1440, content.get("width", width)),
        "height": min(24000, max(1400, final_height)),
        "scale": 1,
    }
    shot = await cdp.send(
        "Page.captureScreenshot",
        {
            "format": "png",
            "fromSurface": True,
            "captureBeyondViewport": True,
            "clip": clip,
        },
    )
    output_path = OUTPUT_DIR / f"{filename}.png"
    output_path.write_bytes(base64.b64decode(shot["data"]))
    print(output_path.relative_to(PROJECT_ROOT))


async def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    streamlit_process = ensure_streamlit()
    chrome_process = launch_chrome()
    try:
        async with CdpClient(get_ws_url()) as cdp:
            await cdp.send("Page.enable")
            await cdp.send("Runtime.enable")
            await cdp.send("Page.navigate", {"url": STREAMLIT_URL})
            await wait_for_streamlit_ready(cdp)
            await capture_page(cdp, PAGES[0][0])
            for filename, expected_text, nav_label in PAGES[1:]:
                assert nav_label is not None
                await click_page(cdp, nav_label)
                await wait_for_streamlit_ready(cdp, expected_text)
                await capture_page(cdp, filename)
    finally:
        chrome_process.terminate()
        if streamlit_process is not None:
            streamlit_process.terminate()


if __name__ == "__main__":
    asyncio.run(main())
