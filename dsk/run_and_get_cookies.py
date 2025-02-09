# run_and_get_cookies.py
import subprocess
import os
import sys
import time
import requests
import json

def get_and_save_cookies(server_url, cookie_file_path):
    for attempt in range(5):
        try:
            response = requests.get(server_url)
            response.raise_for_status()
            cookies_data = response.json()

            cookies_to_save = {
                'cookies': cookies_data.get('cookies', {}),
                'user_agent': cookies_data.get('user_agent', '')
            }

            os.makedirs(os.path.dirname(cookie_file_path), exist_ok=True)
            with open(cookie_file_path, 'w', encoding='utf-8') as f:
                json.dump(cookies_to_save, f, indent=4, ensure_ascii=False)
            return

        except requests.exceptions.ConnectionError as e:
            if attempt < 4:
                time.sleep(5)
            else:
                raise

def run_server_background():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    server_script = os.path.abspath(os.path.join(script_dir, "server.py"))
    server_dir = os.path.dirname(server_script)

    os.makedirs(server_dir, exist_ok=True)

    try:
        process = subprocess.Popen(
            [sys.executable, server_script],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            cwd=server_dir,
            start_new_session=True
        )
        return process
    except Exception:
        return None

if __name__ == "__main__":
    print("Getting the cookies...")
    server_process = run_server_background()

    if server_process:
        time.sleep(5)
        server_url = "http://localhost:8000/cookies?url=https://chat.deepseek.com"
        cookie_file = "dsk/cookies.json"
        get_and_save_cookies(server_url, cookie_file)
    else:
        print("Failed to start server.")