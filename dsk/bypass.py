import subprocess
import os
import sys
import time
import requests
import json
from pathlib import Path

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

            # Convert to Path object and resolve to absolute path
            cookie_path = Path(cookie_file_path).resolve()
            cookie_path.parent.mkdir(parents=True, exist_ok=True)

            # Write cookies using Path object
            cookie_path.write_text(
                json.dumps(cookies_to_save, indent=4, ensure_ascii=False),
                encoding='utf-8'
            )
            return

        except requests.exceptions.ConnectionError as e:
            if attempt < 4:
                print(f"Connection attempt {attempt + 1} failed, retrying in 5 seconds...")
                time.sleep(5)
            else:
                print("Error: Could not connect to the local server. Make sure Chrome is installed and the server is running.")
                raise

def run_server_background():
    script_dir = Path(__file__).parent.resolve()
    server_script = script_dir / "server.py"

    try:
        # Use shell=True on Windows to properly handle Python script execution
        is_windows = sys.platform.startswith('win')

        process = subprocess.Popen(
            [sys.executable, str(server_script)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            cwd=str(script_dir),
            shell=is_windows,
            start_new_session=True
        )
        return process
    except Exception as e:
        print(f"Error starting server: {e}")
        return None

if __name__ == "__main__":
    print("Getting the cookies...")
    server_process = run_server_background()

    if server_process:
        try:
            print("Starting local server...")
            time.sleep(5)  # Give the server time to start

            server_url = "http://localhost:8000/cookies?url=https://chat.deepseek.com"
            cookie_file = Path("dsk/cookies.json")

            print("Requesting cookies from deepseek.com...")
            get_and_save_cookies(server_url, cookie_file)
            print("Cookies saved successfully!")

        except Exception as e:
            print(f"Error: {e}")
        finally:
            # Cleanup
            try:
                server_process.terminate()
            except:
                pass
    else:
        print("Failed to start server. Make sure Python and Chrome are properly installed.")