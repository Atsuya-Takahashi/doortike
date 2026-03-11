import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        # let's try a date that might have events
        await page.goto("https://www.loft-prj.co.jp/schedule/loft/date/2024/11/01")
        await page.wait_for_load_state("networkidle")
        events = await page.query_selector_all('.schedule-box')
        print(f"Found {len(events)} events")
        for evt in events:
            html = await evt.inner_html()
            print("---")
            print(html)
        await browser.close()

asyncio.run(main())
