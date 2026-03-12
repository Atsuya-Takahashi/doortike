import asyncio
from playwright.async_api import async_playwright

async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.goto('https://www.loft-prj.co.jp/schedule/loft/schedule')
        await page.wait_for_selector('a.js-cursor-elm')
        links = await page.query_selector_all('a.js-cursor-elm')
        for i, l in enumerate(links[:10]):
            text = await l.inner_text()
            print(f"[{i}] {repr(text)}")
        await browser.close()

asyncio.run(run())
