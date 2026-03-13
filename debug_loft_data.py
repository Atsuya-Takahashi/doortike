import asyncio
from datetime import datetime, timedelta
from playwright.async_api import async_playwright
import os
import sys

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from models import SessionLocal, Event, LiveHouse

async def debug_single_event(url):
    print(f"\n--- Debugging Detail Page: {url} ---")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        try:
            await page.goto(url)
            await page.wait_for_load_state("networkidle")
            
            full_text = await page.content()
            print("\n--- FULL HTML (first 500 chars) ---")
            print(full_text[:500])
            
            # Print all text found on page
            body_text = await page.inner_text('body')
            print("\n--- BODY TEXT ---")
            print(body_text)

            # 1. Title
            title = "Not Found"
            for selector in ['h1.c_title span', 'h1.c_title', 'h1.mainTitle', 'h1']:
                title_elem = await page.query_selector(selector)
                if title_elem:
                    title_text = await title_elem.inner_text()
                    if title_text.strip():
                        title = title_text.strip()
                        print(f"Selector '{selector}' matched Title: {title}")
                        break
            
            # 2. Performers
            performers_str = "Not Found"
            performers_elems = await page.query_selector_all('.actList li')
            if performers_elems:
                performers = [ (await p_elem.inner_text()).strip() for p_elem in performers_elems if (await p_elem.inner_text()).strip() ]
                performers_str = ", ".join(performers)
                print(f"Selector '.actList li' matched Performers: {performers_str}")
            
            if performers_str == "Not Found":
                # Fallback selectors
                for p_selector in ['.entry p span strong', '.entry p', '.entry']:
                    entry_elem = await page.query_selector(p_selector)
                    if entry_elem:
                        p_text = await entry_elem.inner_text()
                        if p_text.strip():
                            performers_str = p_text.replace("ACT:", "").replace("出演:", "").strip()
                            print(f"Selector '{p_selector}' matched Performers (Raw): {p_text[:50]}...")
                            break
            
            # 3. Time (Open/Start) Trace
            print("\n--- Time Trace ---")
            time_search = await page.evaluate("""() => {
                const results = [];
                const walk = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, null, false);
                let node;
                while (node = walk.nextNode()) {
                    if (node.textContent.includes('OPEN')) {
                        let parent = node.parentElement;
                        results.push({
                            text: node.textContent.trim(),
                            tag: parent.tagName,
                            className: parent.className,
                            id: parent.id
                        });
                    }
                }
                return results;
            }""")
            for res in time_search:
                print(f"Found 'OPEN' in <{res['tag']} class='{res['className']}'>: {res['text']}")

            # 4. Price Trace
            print("\n--- Price Trace ---")
            price_search = await page.evaluate("""() => {
                const results = [];
                const walk = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, null, false);
                let node;
                while (node = walk.nextNode()) {
                    if (node.textContent.includes('ADV')) {
                        let parent = node.parentElement;
                        results.push({
                            text: node.textContent.trim(),
                            tag: parent.tagName,
                            className: parent.className,
                            id: parent.id
                        });
                    }
                }
                return results;
            }""")
            for res in price_search:
                print(f"Found 'ADV' in <{res['tag']} class='{res['className']}'>: {res['text']}")

            # 5. Database Check
            db = SessionLocal()
            print("\n--- DB Check ---")
            # We need to know venue name to check duplicate correctly
            # But let's just check if THIS title exists at all for recent dates
            duplicates = db.query(Event).filter(Event.title == title).all()
            if duplicates:
                print(f"Found {len(duplicates)} events with same title in DB:")
                for d in duplicates:
                    print(f"  - ID: {d.id}, Date: {d.date}, VenueID: {d.livehouse_id}")
            else:
                print("No duplicate title found in DB.")
            db.close()

        except Exception as e:
            print(f"Error during debug: {e}")
        finally:
            await browser.close()

if __name__ == "__main__":
    urls = [
        "https://www.loft-prj.co.jp/schedule/loft/schedule/348138",
        "https://www.loft-prj.co.jp/schedule/shelter/339435"
    ]
    for url in urls:
        asyncio.run(debug_single_event(url))
