"""
GHL Sub‑Account Automation – **CLI _and_ FastAPI micro‑service**
=============================================================
Automates creation of a new sub‑account in AcquisizioneClienti CRM via
Playwright **or** by exposing an HTTP endpoint so n8n (or anything else)
can POST the client payload and trigger the browser flow.

• **CLI mode** (default):

```bash
python ghl_sub_account_automation.py --payload client.json [--headless]
```

• **Server mode** (pass `--serve`):

```bash
python ghl_sub_account_automation.py --serve --port 8000
# …or docker run ghlauto:latest
```

`POST /create` with a JSON body identical to the payload example below → the
script launches Chromium, completes the steps, and returns `{"status":"ok"}`
or `{ "detail": "<error message>" }` on failure.

---------------------------------------------------------------------
Prerequisites
-------------
1. **Python ≥ 3.9** – Playwright + FastAPI need modern typing.
2. Install deps once:

   ```bash
   pip install playwright fastapi uvicorn python-dotenv
   playwright install
   ```
3. Export your agency credentials **securely** (env/secret manager):

   ```bash
   export GHL_EMAIL="agency.owner@example.com"
   export GHL_PASSWORD="SuperSecret123!"
   ```
4. Payload schema (same for CLI & API):

```json
{
  "first_name": "Alice",
  "last_name": "Smith",
  "email": "alice@wonderland.io",
  "business_name": "Wonderland Cakes",
  "business_niche": "Bakery",
  "business_phone": "+1 212 555‑0199",
  "address": "42 Wallaby Way",
  "city": "New York",
  "state": "NY",
  "zip": "10001",
  "country": "United States",
  "website": "https://wonderlandcakes.com"
}
```

---------------------------------------------------------------------
Source code
-----------
```python
from __future__ import annotations

import json
import os
import sys
import time
from argparse import ArgumentParser, Namespace
from typing import Any, Dict

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, EmailStr
from playwright.sync_api import Browser, Page, sync_playwright
import uvicorn

SELECTOR_TIMEOUT = 12_000  # ms

###############################################################################
# Playwright helpers
###############################################################################

def _wait_and_click(page: Page, selector: str) -> None:
    page.wait_for_selector(selector, timeout=SELECTOR_TIMEOUT, state="visible")
    page.locator(selector).click()


def _wait_and_fill(page: Page, selector: str, value: str) -> None:
    page.wait_for_selector(selector, timeout=SELECTOR_TIMEOUT, state="visible")
    locator = page.locator(selector)
    locator.fill("")
    locator.type(value, delay=25)

###############################################################################
# Main browser routine
###############################################################################

def _create_sub_account(playwright, payload: Dict[str, str], headless: bool = True) -> None:
    browser: Browser = playwright.chromium.launch(headless=headless)
    context = browser.new_context()
    page: Page = context.new_page()

    try:
        # 1. Login
        page.goto("https://crm.acquisizioneclienti.it/")
        _wait_and_fill(page, "input[type='email']", os.environ["GHL_EMAIL"])
        _wait_and_fill(page, "input[type='password']", os.environ["GHL_PASSWORD"])
        _wait_and_click(page, "button[type='submit']")

        # 2. Account secondari
        _wait_and_click(page, "text=Account secondari")

        # 3. Create Sub‑Account
        _wait_and_click(page, "text=Create Sub-Account")
        page.locator("text=Blank Snapshot").hover()
        _wait_and_click(page, "text=Select and Continue")

        # 3b. Close location popup if present
        try:
            popup_close = page.locator("div[role='dialog'] [aria-label='Close']")
            if popup_close.is_visible():
                popup_close.click()
        except Exception:
            pass

        # 4. Map ➜ Add manually
        _wait_and_click(page, "text=Add Manually")

        # 5. Fill form
        niche_selector = "label:has-text('Business Niche') + div"
        _wait_and_click(page, niche_selector)
        _wait_and_click(page, f"text={payload['business_niche']}")

        field_map = {
            "input[placeholder='First Name']": "first_name",
            "input[placeholder='Last Name']": "last_name",
            "input[placeholder='Email']": "email",
            "input[placeholder='Business Name']": "business_name",
            "input[placeholder='Business Phone']": "business_phone",
            "input[placeholder='Address']": "address",
            "input[placeholder='City']": "city",
            "input[placeholder='State']": "state",
            "input[placeholder='Postal Code']": "zip",
            "input[placeholder='Country']": "country",
            "input[placeholder='Website']": "website",
        }

        for selector, key in field_map.items():
            _wait_and_fill(page, selector, payload[key])

        # Scroll & submit
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        _wait_and_click(page, "text=Add Sub-Account")
        page.wait_for_load_state("networkidle")
    finally:
        context.close()
        browser.close()

###############################################################################
# FastAPI layer
###############################################################################

app = FastAPI(title="GHL Sub‑Account Bot", docs_url="/docs", redoc_url=None)

class ClientPayload(BaseModel):
    first_name: str = Field(..., example="Alice")
    last_name: str = Field(..., example="Smith")
    email: EmailStr
    business_name: str
    business_niche: str
    business_phone: str
    address: str
    city: str
    state: str
    zip: str
    country: str
    website: str | None = None

@app.post("/create")
def create(payload: ClientPayload) -> dict[str, Any]:
    """Launches the Playwright workflow and returns status JSON."""
    missing_env = [v for v in ("GHL_EMAIL", "GHL_PASSWORD") if v not in os.environ]
    if missing_env:
        raise HTTPException(status_code=500, detail=f"Missing env vars: {', '.join(missing_env)}")

    with sync_playwright() as pw:
        try:
            _create_sub_account(pw, payload.dict(), headless=True)
            return {"status": "ok"}
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

###############################################################################
# CLI entry‑point
###############################################################################

def _cli_args(argv: list[str] | None = None) -> Namespace:
    p = ArgumentParser(description="GHL Sub‑Account automation bot")
    p.add_argument("--payload", help="Path to JSON file with client data or '-' for STDIN")
    p.add_argument("--headless", action="store_true", help="Run browser headless (CLI mode)")
    p.add_argument("--serve", action="store_true", help="Run FastAPI server instead of CLI")
    p.add_argument("--host", default="0.0.0.0")
    p.add_argument("--port", type=int, default=8000)
    return p.parse_args(argv)

def main(argv: list[str] | None = None) -> None:
    cfg = _cli_args(argv)

    # Server mode
    if cfg.serve:
        uvicorn.run("ghl_sub_account_automation:app", host=cfg.host, port=cfg.port, workers=1)
        return

    # CLI mode – ensure payload
    if cfg.payload is None:
        sys.exit("--payload required unless --serve is specified")

    if cfg.payload == "-":
        payload: Dict[str, str] = json.load(sys.stdin)
    else:
        with open(cfg.payload, "r", encoding="utf-8") as fp:
            payload = json.load(fp)

    with sync_playwright() as pw:
        _create_sub_account(pw, payload, headless=cfg.headless)
        print("✅  Sub‑account created successfully.")

if __name__ == "__main__":
    main()
```

