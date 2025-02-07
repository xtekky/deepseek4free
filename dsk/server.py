import json
import re
import os
import sys
import platform
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
    "-disable-gpu"
]

# Windows-specific arguments
windows_arguments = [
    "--no-sandbox",
    "--disable-dev-shm-usage",
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
        r"^(127\.0\.0\.1|localhost|0\.0\.0\.0|::1|10\.\d+\.\d+\.\d+|172\.1[6-9]\.\d+\.\d+|172\.2[0-9]\.\d+\.\d+|172\.3[0-1]\.\d+\.\d+|192\.168\.\d+\.\d+)$"
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

def bypass_cloudflare(url: str, retries: int, log: bool = True, proxy: str = None) -> ChromiumPage:
    """Bypass Cloudflare protection with improved error handling."""
    options = get_chrome_options(proxy)
    driver = None

    try:
        driver = ChromiumPage(addr_or_opts=options)
        logger.info(f"Attempting to access URL: {url}")
        driver.get(url)

        cf_bypasser = CloudflareBypasser(driver, retries, log)
        cf_bypasser.bypass()
        return driver

    except Exception as e:
        if driver:
            driver.quit()

        error_msg = str(e)
        if "chrome not reachable" in error_msg.lower():
            error_msg = "Chrome browser could not be started. Please ensure Chrome is properly installed."
        elif "failed to launch chrome" in error_msg.lower():
            error_msg = "Failed to launch Chrome. Please ensure Chrome is not running in headless mode on Windows."

        logger.error(f"Bypass failed: {error_msg}")
        raise HTTPException(status_code=500, detail=error_msg)

@app.get("/cookies", response_model=CookieResponse)
async def get_cookies(url: str, retries: int = 5, proxy: str = None):
    """Get cookies for a URL with Cloudflare bypass."""
    if not is_safe_url(url):
        raise HTTPException(status_code=400, detail="Invalid URL")

    try:
        driver = bypass_cloudflare(url, retries, True, proxy)
        cookies = {cookie.get("name", ""): cookie.get("value", " ") for cookie in driver.cookies()}
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
        driver = bypass_cloudflare(url, retries, True, proxy)
        html = driver.html
        cookies_json = {cookie.get("name", ""): cookie.get("value", " ") for cookie in driver.cookies()}
        response = Response(content=html, media_type="text/html")
        response.headers["cookies"] = json.dumps(cookies_json)
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
        logger.info(f"Starting server on port {SERVER_PORT}")
        uvicorn.run(app, host="0.0.0.0", port=SERVER_PORT)
    except Exception as e:
        logger.error(f"Failed to start server: {e}")
        if display:
            display.stop()
        sys.exit(1)