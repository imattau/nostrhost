#!/usr/bin/env python3
"""Headless portal Nostr-login E2E against the VM testbed.

nip07: a real NIP-07 shim is injected; the challenge request passes through
to the real server; the login POST is intercepted, re-signed with the dave
key (the shim can't sign), then forwarded to the REAL login endpoint so the
server mints the passwordless cookie. This exercises the actual browser UI,
the actual challenge+login server flow, the cookie, and the dashboard.
"""

import base64
import hashlib
import json
import os
import ssl
import sys
import urllib.request

from coincurve import PrivateKey

from playwright.sync_api import sync_playwright

BASE = "https://nostrhost.test/yunohost/sso"
HOST = "nostrhost.test"
PORTAL_API = "https://127.0.0.1/yunohost/portalapi"


def ssl_ctx() -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def event_id(ev: dict) -> str:
    serial = json.dumps(
        [0, ev["pubkey"], ev["created_at"], ev["kind"], ev["tags"], ev["content"]],
        separators=(",", ":"),
    ).encode()
    return hashlib.sha256(serial).hexdigest()


def sign_event(sk: PrivateKey, ev: dict) -> dict:
    ev = dict(ev)
    ev["pubkey"] = xonly(sk)
    ev["id"] = event_id(ev)
    ev["sig"] = sk.sign_schnorr(bytes.fromhex(ev["id"])).hex()
    return ev


def xonly(sk: PrivateKey) -> str:
    """Nostr (BIP-340) x-only pubkey: the 32-byte x coordinate."""
    return sk.public_key.format().hex()[2:]


def http(method: str, path: str, body: dict | None = None) -> tuple[int, dict, list[str]]:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        f"{PORTAL_API}{path}", data=data, method=method,
        headers={"Host": HOST, "Content-Type": "application/json"},
    )
    cookies: list[str] = []
    try:
        with urllib.request.urlopen(req, context=ssl_ctx(), timeout=10) as r:
            cookies = r.headers.get_all("Set-Cookie") or []
            return r.status, json.loads(r.read()), cookies
    except urllib.error.HTTPError as e:
        cookies = e.headers.get_all("Set-Cookie") or []
        raw = e.read()
        try:
            return e.code, json.loads(raw), cookies
        except Exception:
            return e.code, {"raw": raw.decode(errors="replace")[:200]}, cookies


def main() -> None:
    mode = sys.argv[1] if len(sys.argv) > 1 else "nip07"
    secret = os.environ.get("NOSTR_TEST_SECRET")
    if not secret:
        raise SystemExit("NOSTR_TEST_SECRET env required (dave hex key)")
    sk = PrivateKey(bytes.fromhex(secret))
    pubkey = xonly(sk)

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage",
                "--disable-software-rasterizer", "--ignore-certificate-errors",
                f"--host-resolver-rules=MAP {HOST} 127.0.0.1",
                "--no-zygote", "--single-process",
            ],
        )
        ctx = browser.new_context(ignore_https_errors=True)
        page = ctx.new_page()

        if mode == "nip07":
            page.add_init_script(f"""
                window.nostr = {{
                  getPublicKey: async () => {json.dumps(pubkey)},
                  signEvent: async (event) => ({{ ...event, pubkey: {json.dumps(pubkey)}, sig: "shim-placeholder" }})
                }};
            """)

            real_challenge = {"value": None}

            def on_request(route):
                req = route.request
                if req.method == "GET":
                    status, data, _ = http("GET", "/nostr/challenge")
                    real_challenge["value"] = data.get("challenge")
                    route.fulfill(status=status, content_type="application/json",
                                  body=json.dumps(data))
                elif req.method == "POST":
                    post = json.loads(req.post_data or "{}")
                    ev = post.get("event", {})
                    # ensure the event carries the real challenge we just minted
                    ev["tags"] = [[t[0], t[1]] for t in ev.get("tags", [])]
                    if real_challenge["value"]:
                        ev["tags"] = [[t[0], real_challenge["value"] if t[0] == "challenge" else t[1]]
                                      for t in ev["tags"]]
                    signed = sign_event(sk, ev)
                    status, data, cookies = http("POST", "/nostr/login", {"event": signed})
                    print(f"[nip07] login POST -> {status} {json.dumps(data)[:160]} cookies={cookies}", flush=True)
                    route.fulfill(status=status, content_type="application/json",
                                  headers={"Set-Cookie": "; ".join(cookies)} if cookies else None,
                                  body=json.dumps(data))
                else:
                    route.continue_()

            page.route("**/portalapi/nostr/challenge", on_request)
            page.route("**/portalapi/nostr/login", on_request)

            page.goto(f"{BASE}/nostr-login/", wait_until="domcontentloaded")
            try:
                page.wait_for_load_state("networkidle", timeout=15000)
            except Exception:
                pass
            page.wait_for_timeout(1500)
            print("[nip07] page:", page.url)
            print("[nip07] title:", repr(page.title()))

            btn = page.query_selector("button:has-text('Sign in with Nostr')")
            if not btn:
                raise SystemExit("[nip07] FAIL: no NIP-07 button")
            print("[nip07] NIP-07 button present; clicking")
            btn.click()
            page.wait_for_timeout(4000)
            print("[nip07] post-click url:", page.url)
            logged = page.evaluate("localStorage.getItem('isLoggedIn')")
            print("[nip07] isLoggedIn:", logged)
            print("[nip07] cookies:", [(c["name"], c["value"][:16]) for c in ctx.cookies()])
            print("[nip07] challenge used:", bool(real_challenge["value"]))
            body = page.inner_text("body")
            print("[nip07] post-login body:", body[:300].replace("\n", " | "))

        elif mode == "passkey":
            page.goto(f"{BASE}/nostr-login/", wait_until="domcontentloaded")
            try:
                page.wait_for_load_state("networkidle", timeout=15000)
            except Exception:
                pass
            page.wait_for_timeout(1500)
            txt = page.inner_text("body")
            has_lib = page.evaluate("typeof window.NostrPasskey !== 'undefined'")
            btn = page.query_selector("button:has-text('passkey')")
            print("[passkey] window.NostrPasskey loaded:", has_lib)
            print("[passkey] passkey button present:", bool(btn))
            if has_lib:
                print("[passkey] hasStoredPasskeyIdentity:",
                      page.evaluate("window.NostrPasskey.hasStoredPasskeyIdentity()"))
            print("[passkey] body mentions passkey:", "passkey" in txt.lower())

        elif mode == "connect":
            page.goto(f"{BASE}/nostr-login/", wait_until="domcontentloaded")
            try:
                page.wait_for_load_state("networkidle", timeout=15000)
            except Exception:
                pass
            page.wait_for_timeout(1500)
            print("[connect] title:", repr(page.title()))
            print("[connect] window.NostrConnectUI:", page.evaluate("typeof window.NostrConnectUI"))
            inp = page.query_selector("input[placeholder*='bunker']")
            print("[connect] bunker input present:", bool(inp))
            btn = page.query_selector("button:has-text('remote signer')")
            print("[connect] remote signer button present:", bool(btn))
            if inp:
                inp.fill("nostrconnect://127.0.0.1:7448")
                print("[connect] filled bunker URI")

        elif mode == "nip46":
            # Drive the full NIP-46 remote-signer login against the local
            # bunker on the 7448 test relay. The challenge+login API calls go
            # to the REAL server (no interception) — the bunker signs the
            # kind-22242 for dave.
            import urllib.request as _ur
            bunker_uri = "bunker://6532b6701f56a96248627755863ec494ba3ccd3a0cdf1ce349ba7f8081513e86?relay=ws://127.0.0.1:7448"
            page.goto(f"{BASE}/nostr-login/", wait_until="domcontentloaded")
            try:
                page.wait_for_load_state("networkidle", timeout=15000)
            except Exception:
                pass
            page.wait_for_timeout(1500)
            print("[nip46] page:", page.url, "| title:", repr(page.title()))
            inp = page.query_selector("input[placeholder*='bunker']")
            if not inp:
                raise SystemExit("[nip46] FAIL: no bunker input")
            inp.fill(bunker_uri)
            print("[nip46] filled bunker URI")
            btn = page.query_selector("button:has-text('remote signer')")
            if not btn:
                raise SystemExit("[nip46] FAIL: no remote signer button")
            btn.click()
            # NIP-46 connect + challenge + sign + login round-trip
            page.wait_for_timeout(6000)
            logged = page.evaluate("localStorage.getItem('isLoggedIn')")
            print("[nip46] isLoggedIn:", logged)
            print("[nip46] post-click url:", page.url)
            print("[nip46] cookies:", [(c["name"], c["value"][:16]) for c in ctx.cookies()])
            body = page.inner_text("body")
            print("[nip46] post-login body:", body[:220].replace("\n", " | "))

        elif mode == "launch":
            # Full portal milestone: NIP-07 login -> dashboard -> open an
            # SSO-protected app URL with the passwordless session cookie.
            page.add_init_script(f"""
                window.nostr = {{
                  getPublicKey: async () => {json.dumps(pubkey)},
                  signEvent: async (event) => ({{ ...event, pubkey: {json.dumps(pubkey)}, sig: "shim-placeholder" }})
                }};
            """)
            real_challenge = {"value": None}

            def on_request(route):
                req = route.request
                if req.method == "GET" and req.url.rstrip("/").endswith("/nostr/challenge"):
                    status, data, _ = http("GET", "/nostr/challenge")
                    real_challenge["value"] = data.get("challenge")
                    route.fulfill(status=status, content_type="application/json",
                                  body=json.dumps(data))
                elif req.method == "POST" and req.url.rstrip("/").endswith("/nostr/login"):
                    post = json.loads(req.post_data or "{}")
                    ev = post.get("event", {})
                    ev["tags"] = [[t[0], real_challenge["value"] if t[0] == "challenge" else t[1]]
                                  for t in ev.get("tags", [])]
                    signed = sign_event(sk, ev)
                    status, data, cookies = http("POST", "/nostr/login", {"event": signed})
                    route.fulfill(status=status, content_type="application/json",
                                  headers={"Set-Cookie": "; ".join(cookies)} if cookies else None,
                                  body=json.dumps(data))
                else:
                    route.continue_()

            page.route("**/portalapi/nostr/**", on_request)
            page.goto(f"{BASE}/nostr-login/", wait_until="domcontentloaded")
            try:
                page.wait_for_load_state("networkidle", timeout=15000)
            except Exception:
                pass
            page.wait_for_timeout(1500)
            btn = page.query_selector("button:has-text('Sign in with Nostr')")
            btn.click()
            page.wait_for_timeout(4000)
            logged = page.evaluate("localStorage.getItem('isLoggedIn')")
            print("[launch] post-login isLoggedIn:", logged, "| url:", page.url)
            print("[launch] dashboard apps:", [a.strip() for a in page.inner_text("body").split("|") if "Nostrhost" in a])
            # Now open the SSO-protected app URL with the session cookie.
            app_url = "https://nostrhost.test/nostrhost-test-catalog/"
            r = page.goto(app_url, wait_until="domcontentloaded", timeout=25000)
            page.wait_for_timeout(2000)
            print("[launch] app url:", page.url)
            print("[launch] app status:", r.status if r else "n/a")
            print("[launch] app title:", repr(page.title()))
            print("[launch] app body:", page.inner_text("body")[:300].replace("\n", " | "))

        browser.close()


if __name__ == "__main__":
    main()