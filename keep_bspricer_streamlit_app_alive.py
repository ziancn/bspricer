"""
Keep streamlit app awake by periodic visits.
"""

from playwright.sync_api import (
    sync_playwright,
    TimeoutError as PlaywrightTimeoutError
)
import time
import datetime
import re

APP_URL = "https://bspricer.streamlit.app/"
EXPECTED_TITLE = "Naïve Option Pricer"
TIMEOUT_SEC = 60
IFRAME_TIMEOUT_SEC = 60
INTERVAL_HOURS = 2

# If page goes hibernation
HIBERNATION_KEYWORDS = ["asleep", "hibernating", "wake up", "get this app back up", "zzz", "sleep mode"]

def is_hibernation_page(page):
    body_text = page.inner_text("body").lower()
    return any(kw in body_text for kw in HIBERNATION_KEYWORDS)

def keep_app_awake():
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{now}] start to visit: {APP_URL}")

    with sync_playwright() as p:
        browser = p.chromium.launch(
            channel="chrome",
            headless=False
        )
        context = browser.new_context(
            viewport={'width': 1280, 'height': 800},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0'
        )
        page = context.new_page()

        success = False
        try:
            print("Navigating（there might be redircting）...")
            page.goto(APP_URL, timeout=TIMEOUT_SEC*1_000, wait_until="networkidle")

            # Check hibernation
            if is_hibernation_page(page):
                print("Hibernation page detected → bring to live again...")
                try:
                    wake_button = page.get_by_role("button", name=re.compile("wake up|get.*back up", re.I))
                    if wake_button.count() > 0:
                        wake_button.first.click(timeout=15000)
                        print("Clicked the wake up button!")
                    else:
                        print("Button not found, wait for auto wake up...")
                except:
                    print("Failed to click the button, continue waiting...")
                page.wait_for_timeout(TIMEOUT_SEC*1_000)
            else:
                print("None hibernation page → already awake.")

            # Iframe
            print("Awaiting Streamlit main iframe to load...")
            iframe_element = page.wait_for_selector('iframe[src*="/~/+/"]', timeout=IFRAME_TIMEOUT_SEC*1_000)
            iframe = iframe_element.content_frame()
            if not iframe:
                raise Exception("Cannot enter iframe context")

            print("In iframe, waiting for title...")
            try:
                iframe.get_by_role(
                    "heading",
                    name=EXPECTED_TITLE,
                    exact=False
                ).wait_for(
                    state="visible", timeout=TIMEOUT_SEC*1_000
                )
                print(f"Found expected heading: '{EXPECTED_TITLE}'")
                success = True
            except PlaywrightTimeoutError:
                print("Heading locator timeout")
                iframe_body_text = iframe.inner_text("body").lower()
                if "naïve option pricer" in iframe_body_text or "naive option pricer" in iframe_body_text:
                    print("Found expected type in iframe body")
                    success = True
                else:
                    print("Keywords not found in iframe body → load might have issues")
                    print(f"First 300 characters in body: {iframe.inner_text('body')[:300]}")

            time.sleep(5)

        except PlaywrightTimeoutError as te:
            print(f"Timeout: {te}")
        except Exception as e:
            print(f"Exception: {type(e).__name__}: {e}")
        finally:
            if not success:
                print("Saving screenshot for debugging...")
                screenshot_path = f"logs/debug_fail_{int(time.time())}.png"
                page.screenshot(path=screenshot_path)
            browser.close()

    return success



if __name__ == "__main__":
    while True:
        keep_app_awake()
        print(f"\nNext Visit is {INTERVAL_HOURS} hours...\n{'='*60}\n")
        time.sleep(INTERVAL_HOURS * 3600)