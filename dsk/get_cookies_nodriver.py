import asyncio
import json
import os
import nodriver as uc

async def main():
    browser = await uc.start(browser_executable_path='/usr/bin/brave', headless=False)
    page = await browser.get('https://chat.deepseek.com')
    await asyncio.to_thread(input, "Press Enter after logging in to chat.deepseek.com in the browser window...")

    raw_cookies = await browser.cookies.get_all(requests_cookie_format=False)
    cookies_dict = {c.name: c.value for c in raw_cookies}

    user_token_raw = await page.evaluate('localStorage.getItem("userToken")')
    if user_token_raw:
        try:
            user_token = json.loads(user_token_raw).get('value', user_token_raw)
        except json.JSONDecodeError:
            user_token = user_token_raw
        cookies_dict['userToken'] = user_token

    user_agent = await page.evaluate('navigator.userAgent')

    cookie_file = os.path.join(os.path.dirname(__file__), 'cookies.json')
    with open(cookie_file, 'w') as f:
        json.dump({'cookies': cookies_dict, 'user_agent': user_agent}, f, indent=2)

    print(f"Cookies saved to {cookie_file}")
    print(f"Cookies: {list(cookies_dict.keys())}")

    browser.stop()

if __name__ == '__main__':
    asyncio.run(main())
