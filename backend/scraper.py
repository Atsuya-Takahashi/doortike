import asyncio
from datetime import datetime, timedelta
from playwright.async_api import async_playwright
from models import SessionLocal, LiveHouse, Event, Artist
from youtube_service import search_artist_video
import re
import os
from dotenv import load_dotenv

load_dotenv()

def sanitize_price_info(text):
    if not text: return ""
    lines = text.split('\n')
    clean_lines = []
    for line in lines:
        # Stop collecting lines if any of these "on-sale" or "order" labels are encountered
        if any(label in line for label in ["[発売]", "【発売日】", "【入場順】", "[発売日]", "【発売】", "［発売］"]):
            break
        clean_lines.append(line)
    return "\n".join(clean_lines).strip()

# 1回のスクレイパー実行で呼べるYouTube APIの上限（100ユニット×90=9,000ユニット/日）
DAILY_FETCH_LIMIT = 90


def get_artist_video_info(db_session, performers_str: str, youtube_fetch_count: int) -> tuple[list, int]:
    """
    performers文字列を分割し、アーティスト名とYouTube IDのリストを返す。
    必要に応じて外部APIを叩き、キャッシュ（artistsテーブル）も更新する。
    """
    if not performers_str:
        return [], youtube_fetch_count

    artist_list = []
    # 区切り文字（、, ／ / \n）で分割
    names = [a.strip() for a in re.split(r'[、,／/\n]', performers_str) if a.strip()]

    for artist_name in names:
        artist = db_session.query(Artist).filter(Artist.name == artist_name).first()
        video_id = None

        # キャッシュのチェック（30日以内のデータがあれば採用）
        if artist and artist.youtube_updated_at and (datetime.now() - artist.youtube_updated_at) < timedelta(days=30):
            video_id = artist.youtube_video_id
        else:
            # キャッシュがない、または古い場合はYouTube APIを叩く（上限内であれば）
            if youtube_fetch_count < DAILY_FETCH_LIMIT:
                exclude_ids = []
                if artist and artist.reported_video_ids:
                    exclude_ids = [vid for vid in artist.reported_video_ids.split(",") if vid]
                
                video_id = search_artist_video(artist_name, exclude_ids=exclude_ids)
                youtube_fetch_count += 1

                if not artist:
                    artist = Artist(name=artist_name)
                    db_session.add(artist)
                
                artist.youtube_video_id = video_id
                artist.youtube_updated_at = datetime.now()
                artist.is_reported = False
                
                try:
                    db_session.commit()
                    status = f"動画あり: {video_id}" if video_id else "動画なし"
                    print(f"[YouTube] {artist_name} → {status} (本日{youtube_fetch_count}件目)")
                except Exception as db_err:
                    db_session.rollback()
                    print(f"[YouTube] Error updating artist {artist_name}: {db_err}")
            else:
                # 上限に達している場合はキャッシュがあれば古いものでも使い、なければNone
                video_id = artist.youtube_video_id if artist else None

        artist_list.append({"name": artist_name, "youtube_id": video_id})

    return artist_list, youtube_fetch_count


async def scrape_loft_project_venue(page, venue_name: str, venue_slug: str, target_dates: list, db_session, youtube_fetch_count: int) -> int:
    """
    Generic scraper for LOFT PROJECT venues (LOFT, SHELTER, etc.)
    """
    # Use the general schedule page to find events
    base_url = f"https://www.loft-prj.co.jp/schedule/{venue_slug}/schedule"
    print(f"Scraping {venue_name} at {base_url}")
    
    await page.goto(base_url)
    # Wait for the content to be loaded
    try:
        await page.wait_for_selector('a.js-cursor-elm', timeout=10000)
    except:
        print(f"[{venue_name}] No events found or page structure mismatch.")
        return youtube_fetch_count
    
    try:
        livehouse = db_session.query(LiveHouse).filter(LiveHouse.name == venue_name).first()
        if not livehouse:
            # This shouldn't happen if areas were seeded
            livehouse = LiveHouse(name=venue_name, area="Unknown", latitude=0, longitude=0, url=f"https://www.loft-prj.co.jp/{venue_slug}/")
            db_session.add(livehouse)
            db_session.commit()
            # Re-fetch to get ID
            livehouse = db_session.query(LiveHouse).filter(LiveHouse.name == venue_name).first()
        
        livehouse_id = livehouse.id # Capture ID to avoid lazy loading later
    except Exception as e:
        db_session.rollback()
        print(f"[{venue_name}] Error initializing livehouse: {e}")
        return youtube_fetch_count

    # Find all event links on the schedule page
    event_links = await page.query_selector_all('a.js-cursor-elm')
    
    processed_hrefs = set()
    
    for link in event_links:
        href = await link.get_attribute('href')
        if not href or href in processed_hrefs: continue
        processed_hrefs.add(href)
        
        # Date is inside <time> element as separate divs
        time_elem = await link.query_selector('time')
        if not time_elem: continue
        
        time_divs = await time_elem.query_selector_all('div')
        if len(time_divs) < 3: continue
        
        try:
            year_str = await time_divs[0].inner_text()
            month_str = await time_divs[1].inner_text()
            day_str = await time_divs[2].inner_text()
            
            event_date_str = f"{year_str.strip()}-{month_str.strip()}-{day_str.strip()}"
            event_date = datetime.strptime(event_date_str, "%Y-%m-%d")
        except Exception as e:
            print(f"[{venue_name}] Failed to parse date: {e}")
            continue
        
        found_date = None
        for target_date in target_dates:
            if event_date.date() == target_date.date():
                found_date = target_date
                break
        
        if not found_date: continue
        
        print(f"[{venue_name}] Found event for {found_date.date()}: {href}")
        
        # Go to detail page in the same page object to avoid context issues
        detail_page = await page.context.browser.new_page()
        try:
            await detail_page.goto(href)
            await detail_page.wait_for_load_state("networkidle")
            
            # Robust Title extraction
            title = "Unknown Title"
            for selector in ['h1.c_title span', 'h1.c_title', 'h1.mainTitle', 'h1']:
                title_elem = await detail_page.query_selector(selector)
                if title_elem:
                    title_text = await title_elem.inner_text()
                    if title_text.strip():
                        title = title_text.strip()
                        break
            
            # Robust Performers extraction
            performers_str = ""
            # Try list first
            performers_elems = await detail_page.query_selector_all('.actList li')
            if performers_elems:
                performers = []
                for p_elem in performers_elems:
                    p_text = await p_elem.inner_text()
                    if p_text.strip(): performers.append(p_text.strip())
                performers_str = ", ".join(performers)
            
            # Fallback to .entry p (found by subagent recently)
            if not performers_str:
                for p_selector in ['.entry p span strong', '.entry p', '.entry']:
                    entry_elem = await detail_page.query_selector(p_selector)
                    if entry_elem:
                        p_text = await entry_elem.inner_text()
                        if p_text.strip():
                            performers_str = p_text.replace("ACT:", "").replace("出演:", "").strip()
                            break
            
            time_elem = await detail_page.query_selector('.open')
            if not time_elem:
                time_elem = await detail_page.query_selector('.openStart')
            if not time_elem:
                time_elem = await detail_page.query_selector('.open-start')
            
            time_text = await time_elem.inner_text() if time_elem else ""
            open_time, start_time = "", ""
            if time_text:
                # Handle spaces and newlines between label and time
                match_open = re.search(r'OPEN\s*(\d{2}:\d{2})', time_text, re.IGNORECASE)
                if match_open: open_time = match_open.group(1)
                match_start = re.search(r'START\s*(\d{2}:\d{2})', time_text, re.IGNORECASE)
                if match_start: start_time = match_start.group(1)
                
            price_elem = await detail_page.query_selector('.ticket_detail_box')
            if not price_elem:
                price_elem = await detail_page.query_selector('.price')
            if not price_elem:
                price_elem = await detail_page.query_selector('.ticketWrap .price')
            price_info = await price_elem.inner_text() if price_elem else ""
            
            ticket_url = None
            for t_selector in ['.ticketList a', '.ticketWrap a', '.entry a']:
                ticket_link_elem = await detail_page.query_selector(t_selector)
                if ticket_link_elem:
                    t_href = await ticket_link_elem.get_attribute('href')
                    if t_href and any(domain in t_href for domain in ['eplus.jp', 't.pia.jp', 'l-tike.com', 'tiget.net', 't.livepocket.jp']):
                        ticket_url = t_href
                        break

            # Determine if it's a late-night event (is_midnight)
            is_midnight = False
            time_to_check = start_time or open_time
            if time_to_check:
                try:
                    hour = int(time_to_check.split(":")[0])
                    # 21:00 or later, or early morning (club events)
                    if hour >= 21 or hour < 5:
                        is_midnight = True
                except:
                    pass

            try:
                # Ensure session is clean for a new event
                db_session.rollback() 

                # Check if event already exists using ID variable
                existing_event = db_session.query(Event).filter(
                    Event.livehouse_id == livehouse_id, Event.date == found_date.date(), Event.title == title
                ).first()

                if not existing_event:
                    # Create initial event record
                    existing_event = Event(
                        livehouse_id=livehouse.id,
                        date=found_date.date(),
                        title=title,
                        performers=performers_str,
                        open_time=open_time,
                        start_time=start_time,
                        price_info=sanitize_price_info(price_info),
                        ticket_url=ticket_url,
                        is_midnight=is_midnight
                    )
                    db_session.add(existing_event)
                    db_session.commit()
                    print(f"[{venue_name}] Added new event: {title}")
                else:
                    # Update basic info
                    if existing_event.is_midnight != is_midnight:
                        existing_event.is_midnight = is_midnight
                        db_session.commit()
                        print(f"[{venue_name}] Updated tag: {title}")

                # External API call (YouTube)
                artists_data, youtube_fetch_count = get_artist_video_info(
                    db_session, performers_str, youtube_fetch_count
                )

                # Re-fetch event using ID variable
                existing_event = db_session.query(Event).filter(
                    Event.livehouse_id == livehouse_id, Event.date == found_date.date(), Event.title == title
                ).first()

                if existing_event and existing_event.artists_data != artists_data:
                    existing_event.artists_data = artists_data
                    db_session.commit()
                    print(f"[{venue_name}] Updated performers data: {title}")
                else:
                    print(f"[{venue_name}] Checked: {title}")

            except Exception as e:
                db_session.rollback()
                print(f"[{venue_name}] Error processing event {title}: {e}")
                continue
        except Exception as outer_e:
            db_session.rollback()
            print(f"[{venue_name}] Outer error scraping detail page {href}: {outer_e}")
        finally:
            await detail_page.close()

    return youtube_fetch_count


async def async_run_all_scrapers():
    # Handle JST time (+9h from UTC)
    now_jst = datetime.utcnow() + timedelta(hours=9)
    today = now_jst
    tomorrow = now_jst + timedelta(days=1)
    
    target_dates = [today, tomorrow]
    youtube_fetch_count = 0
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        # 1. Shinjuku LOFT
        db_loft = SessionLocal()
        try:
            youtube_fetch_count = await scrape_loft_project_venue(page, "新宿LOFT", "loft", target_dates, db_loft, youtube_fetch_count)
        except Exception as e:
            db_loft.rollback()
            print(f"Error scraping Shinjuku LOFT: {e}")
        finally:
            db_loft.close()

        # 2. Shimokitazawa SHELTER
        db_shelter = SessionLocal()
        try:
            youtube_fetch_count = await scrape_loft_project_venue(page, "下北沢SHELTER", "shelter", target_dates, db_shelter, youtube_fetch_count)
        except Exception as e:
            db_shelter.rollback()
            print(f"Error scraping Shimokitazawa SHELTER: {e}")
        finally:
            db_shelter.close()
                
        await browser.close()

    print(f"\n[完了] 本日のYouTube取得数: {youtube_fetch_count}件 / 上限{DAILY_FETCH_LIMIT}件")

def run_all_scrapers():
    """Wrapper to run the async scraper synchronously."""
    asyncio.run(async_run_all_scrapers())

if __name__ == "__main__":
    run_all_scrapers()
