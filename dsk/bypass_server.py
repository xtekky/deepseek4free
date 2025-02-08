import json
import re
import os
import sys
import platform
import time
from pathlib import Path
from urllib.parse import urlparse

from CloudflareBypasser import CloudflareBypasser
from DrissionPage import ChromiumPage, ChromiumOptions
from fastapi import FastAPI, HTTPException, Response
from pydantic import BaseModel
from typing import Dict, Optional
import argparse

from pyvirtualdisplay import Display
import uvicorn
import atexit
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Check if running in Docker mode
DOCKER_MODE = os.getenv("DOCKERMODE", "false").lower() == "true"
SERVER_PORT = int(os.getenv("SERVER_PORT", 8000))

def find_chrome_windows():
    """Find Chrome executable on Windows."""
    possible_paths = [
        # Local App Data path
        os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Google/Chrome/Application/chrome.exe'),
        # Program Files paths
        os.path.join(os.environ.get('PROGRAMFILES', 'C:/Program Files'), 'Google/Chrome/Application/chrome.exe'),
        os.path.join(os.environ.get('PROGRAMFILES(X86)', 'C:/Program Files (x86)'), 'Google/Chrome/Application/chrome.exe'),
        # Direct paths
        'C:/Program Files/Google/Chrome/Application/chrome.exe',
        'C:/Program Files (x86)/Google/Chrome/Application/chrome.exe'
    ]

    for path in possible_paths:
        if os.path.isfile(path):
            logger.info(f"Found Chrome at: {path}")
            return path
    return None

# Set browser path based on platform
IS_WINDOWS = platform.system() == "Windows"
if IS_WINDOWS:
    browser_path = find_chrome_windows()
    if not browser_path:
        logger.error("Chrome not found on Windows. Please install Google Chrome from: https://www.google.com/chrome/")
        sys.exit(1)
else:
    browser_path = "/usr/bin/google-chrome"  # Default for Linux/Docker

# Common Chrome arguments
common_arguments = [
    "-no-first-run",
    "-force-color-profile=srgb",
    "-metrics-recording-only",
    "-password-store=basic",
    "-use-mock-keychain",
    "-export-tagged-pdf",
    "-no-default-browser-check",
    "-disable-background-mode",
    "-enable-features=NetworkService,NetworkServiceInProcess",
    "-disable-features=FlashDeprecationWarning",
    "-deny-permission-prompts",
    "-disable-gpu",
    "--disable-dev-shm-usage",
    "--disable-web-security",
    "--allow-running-insecure-content"
]

# Windows-specific arguments
windows_arguments = [
    "--no-sandbox",
    "--disable-software-rasterizer",
    "--ignore-certificate-errors",
    "--disable-direct-composition"
]

app = FastAPI()

class CookieResponse(BaseModel):
    cookies: Dict[str, str]
    user_agent: str

def is_safe_url(url: str) -> bool:
    parsed_url = urlparse(url)
    ip_pattern = re.compile(
        r"^(127\.0\.0\.1|localhost|0\.0\.0\.0|::1|10\.\d+\.\d+\.\d+|172\.1[6-9]\.\d+\.\d+|172\.2[0-9]\.\d+\.\d+\.\d+|172\.3[0-1]\.\d+\.\d+|192\.168\.\d+\.\d+)$"
    )
    hostname = parsed_url.hostname
    if (hostname and ip_pattern.match(hostname)) or parsed_url.scheme == "file":
        return False
    return True

def get_chrome_options(use_proxy: Optional[str] = None) -> ChromiumOptions:
    """Configure Chrome options based on platform and environment."""
    options = ChromiumOptions().auto_port()

    # Add common arguments
    for arg in common_arguments:
        options.set_argument(arg)

    # Add Windows-specific arguments
    if IS_WINDOWS:
        for arg in windows_arguments:
            options.set_argument(arg)

    # Configure paths and mode
    options.set_paths(browser_path=browser_path)

    # Set proxy if provided
    if use_proxy:
        options.set_proxy(use_proxy)

    return options

def ensure_page_loaded(driver: ChromiumPage, url: str, timeout: int = 30) -> bool:
    """Ensure the page is properly loaded."""
    try:
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                # Wait for page load to complete
                driver.wait.load_complete()

                # Check if we can access the page content
                driver.html
                current_url = driver.url

                # If we got redirected to a different domain, something went wrong
                if urlparse(current_url).netloc != urlparse(url).netloc:
                    logger.warning(f"Unexpected redirect to: {current_url}")
                    return False

                return True
            except Exception as e:
                logger.debug(f"Page load check failed: {str(e)}")
                time.sleep(1)

        return False
    except Exception as e:
        logger.error(f"Error ensuring page load: {str(e)}")
        return False

def bypass_cloudflare(url: str, retries: int = 5, log: bool = True, proxy: str = None) -> tuple[ChromiumPage, bool]:
    """Bypass Cloudflare protection with improved error handling."""
    options = get_chrome_options(proxy)
    driver = None
    max_attempts = 5  # Increased max attempts
    required_cookies = ["cf_clearance"]

    for attempt in range(max_attempts):
        try:
            if driver:
                try:
                    driver.quit()
                except:
                    pass

            driver = ChromiumPage(addr_or_opts=options)
            logger.info(f"Attempt {attempt + 1}/{max_attempts}: Accessing URL: {url}")

            # Set page load timeout and strategy
            driver.set.load_strategy('eager')  # Use eager loading strategy
            driver.get(url)

            # Ensure page is properly loaded
            if not ensure_page_loaded(driver, url):
                logger.warning(f"Page failed to load properly on attempt {attempt + 1}")
                continue

            # Initialize CloudflareBypasser
            cf_bypasser = CloudflareBypasser(driver, retries, log)

            # If we're not on a challenge page and already have cf_clearance, we're done
            if not cf_bypasser.is_on_challenge_page() and cf_bypasser.has_required_cookies():
                logger.info("No Cloudflare challenge detected and required cookies present")
                return driver, True

            # Otherwise, attempt the bypass
            if cf_bypasser.bypass():
                cookies = {cookie.get("name"): cookie.get("value") for cookie in driver.cookies()}
                if all(cookie in cookies for cookie in required_cookies):
                    logger.info("Successfully obtained cf_clearance cookie")
                    return driver, True
                else:
                    logger.warning(f"Bypass succeeded but not all required cookies found: {cookies.keys()}")
            else:
                logger.warning(f"Bypass failed on attempt {attempt + 1}")

        except Exception as e:
            error_msg = str(e)
            if "chrome not reachable" in error_msg.lower():
                logger.error("Chrome browser could not be started. Retrying...")
            elif "failed to launch chrome" in error_msg.lower():
                logger.error("Failed to launch Chrome. Retrying...")
            else:
                logger.error(f"Error during bypass attempt {attempt + 1}: {error_msg}")

            if driver:
                try:
                    driver.quit()
                except:
                    pass
            driver = None

            if attempt < max_attempts - 1:
                time.sleep(5)  # Wait before next attempt

    # If we get here, all attempts failed
    if driver:
        try:
            driver.quit()
        except:
            pass

    error_msg = "Failed to bypass Cloudflare protection after multiple attempts"
    logger.error(error_msg)
    raise HTTPException(status_code=500, detail=error_msg)

@app.get("/cookies", response_model=CookieResponse)
async def get_cookies(url: str, retries: int = 5, proxy: str = None):
    """Get cookies for a URL with Cloudflare bypass."""
    if not is_safe_url(url):
        raise HTTPException(status_code=400, detail="Invalid URL")

    try:
        driver, success = bypass_cloudflare(url, retries, True, proxy)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to obtain required cookies")

        cookies = {cookie.get("name"): cookie.get("value")
                  for cookie in driver.cookies()
                  if cookie.get("name") and cookie.get("value")}

        # Verify cf_clearance cookie is present, retry if not found
        if "cf_clearance" not in cookies:
            logger.warning("Required cf_clearance cookie not found, retrying...")
            driver.quit()
            driver, success = bypass_cloudflare(url, retries, True, proxy)
            if not success:
                raise HTTPException(status_code=500, detail="Failed to obtain required cookies after retry")
            cookies = {cookie.get("name"): cookie.get("value")
                      for cookie in driver.cookies()
                      if cookie.get("name") and cookie.get("value")}
            if "cf_clearance" not in cookies:
                logger.warning("Required cf_clearance cookie not found after retry")
                driver.quit()
                raise HTTPException(status_code=500, detail="Required cf_clearance cookie not found after retry")

        user_agent = driver.user_agent
        driver.quit()
        return CookieResponse(cookies=cookies, user_agent=user_agent)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting cookies: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/html")
async def get_html(url: str, retries: int = 5, proxy: str = None):
    """Get HTML content and cookies for a URL."""
    if not is_safe_url(url):
        raise HTTPException(status_code=400, detail="Invalid URL")

    try:
        driver, success = bypass_cloudflare(url, retries, True, proxy)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to obtain required cookies")

        html = driver.html
        cookies = {cookie.get("name"): cookie.get("value")
                  for cookie in driver.cookies()
                  if cookie.get("name") and cookie.get("value")}

        # Verify cf_clearance cookie is present, retry if not found
        if "cf_clearance" not in cookies:
            logger.warning("Required cf_clearance cookie not found, retrying...")
            driver.quit()
            driver, success = bypass_cloudflare(url, retries, True, proxy)
            if not success:
                raise HTTPException(status_code=500, detail="Failed to obtain required cookies after retry")
            cookies = {cookie.get("name"): cookie.get("value")
                      for cookie in driver.cookies()
                      if cookie.get("name") and cookie.get("value")}
            if "cf_clearance" not in cookies:
                logger.warning("Required cf_clearance cookie not found after retry")
                driver.quit()
                raise HTTPException(status_code=500, detail="Required cf_clearance cookie not found after retry")

        response = Response(content=html, media_type="text/html")
        response.headers["cookies"] = json.dumps(cookies)
        response.headers["user_agent"] = driver.user_agent
        driver.quit()
        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting HTML: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Cloudflare bypass API")
    parser.add_argument("--nolog", action="store_true", help="Disable logging")
    parser.add_argument("--headless", action="store_true", help="Run in headless mode")
    args = parser.parse_args()

    # Configure logging
    if args.nolog:
        logging.getLogger().setLevel(logging.WARNING)

    # Virtual display setup (skip on Windows)
    display = None
    if (args.headless or DOCKER_MODE) and not IS_WINDOWS:
        try:
            display = Display(visible=0, size=(1920, 1080))
            display.start()

            def cleanup_display():
                if display:
                    display.stop()
            atexit.register(cleanup_display)
        except Exception as e:
            logger.warning(f"Could not start virtual display: {e}")
            logger.warning("Continuing without virtual display...")

    try:
        import socket
        def find_available_port(start_port: int, max_attempts: int = 10) -> int:
            """
            Finds an available port starting from start_port.
            If the port is in use, it tries the next port until a free port is found or max_attempts is reached.
            """
            for port in range(start_port, start_port + max_attempts):
                try:
                    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                        s.bind(('0.0.0.0', port))
                        return port
                except OSError:
                    logger.debug(f"Port {port} is in use, trying next port...")
                    continue
            raise RuntimeError(f"Could not find an available port after {max_attempts} attempts")

        try:
            port = find_available_port(SERVER_PORT)
            if port != SERVER_PORT:
                logger.info(f"Port {SERVER_PORT} is in use, using port {port} instead")
            else:
                logger.info(f"Starting server on port {port}")

            uvicorn.run(app, host="0.0.0.0", port=port)
        except RuntimeError as e:
            logger.error(f"Failed to find a free port: {e}")
            sys.exit(1)
    except Exception as e:
        logger.error(f"Failed to start server: {e}")
        if display:
            display.stop()
        sys.exit(1)