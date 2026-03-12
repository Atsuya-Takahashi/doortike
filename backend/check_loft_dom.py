import asyncio
from playwright.async_api import async_playwright

async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        try:
            await page.goto('https://www.loft-prj.co.jp/schedule/loft/schedule', timeout=30000)
            await page.wait_for_load_state("networkidle")
            content = await page.content()
            print(f"Content length: {len(content)}")
            # Print a snippet of the page to see if we reached it
            print(content[:500])
            
            # Check for ANY links
            links = await page.query_selector_all('a')
            print(f"Total links found: {len(links)}")
            
            # Check for LOFT specific classes
            special_links = await page.query_selector_all('.js-cursor-elm')
            print(f"Links with .js-cursor-elm: {len(special_links)}")
            
            if special_links:
                print(f"First special link text: {repr(await special_links[0].inner_text())}")
        except Exception as e:
            print(f"Error: {e}")
        finally:
            await browser.close()

asyncio.run(run())
