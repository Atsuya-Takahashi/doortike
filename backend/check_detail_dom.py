import asyncio
from playwright.async_api import async_playwright

async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        try:
            url = 'https://www.loft-prj.co.jp/schedule/loft/schedule/348138'
            print(f"Navigating to {url}")
            await page.goto(url, timeout=60000)
            await page.wait_for_load_state("networkidle")
            
            # Print title
            title_elem = await page.query_selector('h1.mainTitle')
            if title_elem:
                print(f"Title: {repr(await title_elem.inner_text())}")
            else:
                print("Title element NOT found")
                # Fallback check
                h1s = await page.query_selector_all('h1')
                print(f"H1 tags found: {[await h.inner_text() for h in h1s]}")
            
            # Print performers
            acts = await page.query_selector_all('.actList li')
            print(f"Performers found: {[await a.inner_text() for a in acts]}")
            
            # Print whole body length
            body = await page.query_selector('body')
            text = await body.inner_text()
            print(f"Body text length: {len(text)}")
        except Exception as e:
            print(f"Error: {e}")
        finally:
            await browser.close()

asyncio.run(run())
