import asyncio
from playwright.async_api import async_playwright

async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        try:
            print("Navigating to LOFT schedule...")
            await page.goto('https://www.loft-prj.co.jp/schedule/loft/schedule', timeout=60000)
            await page.wait_for_selector('a.js-cursor-elm', timeout=10000)
            links = await page.query_selector_all('a.js-cursor-elm')
            print(f"Found {len(links)} links.")
            for i, l in enumerate(links[:15]):
                text = await l.inner_text()
                print(f"[{i}] {repr(text)}")
        except Exception as e:
            print(f"Error: {e}")
        finally:
            await browser.close()

asyncio.run(run())
