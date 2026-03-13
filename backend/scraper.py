from typing import Optional, List, Dict
import asyncio
from datetime import datetime, timedelta
from playwright.async_api import async_playwright
try:
    from models import SessionLocal, LiveHouse, Event, Artist, VideoReport
    from youtube_service import search_artist_video
except ImportError:
    # Handle direct execution vs module execution context
    import sys
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    from models import SessionLocal, LiveHouse, Event, Artist, VideoReport
    from youtube_service import search_artist_video
import re
import os
import requests
from bs4 import BeautifulSoup
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

def fetch_og_image(url):
    """
    Fetch OGP image from a URL.
    """
    if not url: return None
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        response = requests.get(url, headers=headers, timeout=5)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Try og:image first
        og_image = soup.find('meta', property='og:image') or soup.find('meta', attrs={'name': 'og:image'})
        if og_image and og_image.get('content'):
            img_url = og_image.get('content')
            # Handle relative URLs
            if img_url.startswith('//'):
                img_url = 'https:' + img_url
            elif img_url.startswith('/'):
                from urllib.parse import urljoin
                img_url = urljoin(url, img_url)
            return img_url
            
        # Fallback to twitter:image
        twitter_image = soup.find('meta', name='twitter:image') or soup.find('meta', attrs={'property': 'twitter:image'})
        if twitter_image and twitter_image.get('content'):
            return twitter_image.get('content')
            
    except Exception as e:
        print(f"[OGP] Error fetching {url}: {e}")
    return None


def get_artist_video_info(db_session, performers_str: str, youtube_fetch_count: int, pending_reports: Optional[Dict] = None) -> tuple[list, int]:
    """
    performers文字列を分割し、アーティスト名とYouTube IDのリストを返す。
    必要に応じて外部APIを叩き、キャッシュ（artistsテーブル）も更新する。
    pending_reports: {artist_name: VideoReport object}
    """
    if not performers_str:
        return [], youtube_fetch_count

    artist_list = []
    # 区切り文字（、, ／ / \n）で分割
    names = [a.strip() for a in re.split(r'[、,／/\n]', performers_str) if a.strip()]

    for artist_name in names:
        artist = db_session.query(Artist).filter(Artist.name == artist_name).first()
        video_id = None
        report = pending_reports.get(artist_name) if pending_reports else None

        # 1. 報告あり (Priority 1)
        if report and youtube_fetch_count < DAILY_FETCH_LIMIT:
            exclude_ids = []
            if artist and artist.reported_video_ids:
                exclude_ids = [vid for vid in artist.reported_video_ids.split(",") if vid]
            
            # キーワードを強化して検索
            video_id = search_artist_video(artist_name, exclude_ids=exclude_ids, suffix="official MV")
            youtube_fetch_count += 1
            
            # statusをresolvedに変更
            report.status = 'resolved'
            
            if not artist:
                artist = Artist(name=artist_name)
                db_session.add(artist)
            
            artist.youtube_video_id = video_id
            artist.youtube_updated_at = datetime.now()
            artist.is_reported = False
            
            try:
                db_session.commit()
                print(f"[YouTube][Report Resolved] {artist_name} → {video_id} (本日{youtube_fetch_count}件目)")
            except Exception as db_err:
                db_session.rollback()
                print(f"[YouTube] Error updating reported artist {artist_name}: {db_err}")

        # 2. 新規 or 期限切れ (90日)
        elif (not artist or not artist.youtube_updated_at or (datetime.now() - artist.youtube_updated_at) > timedelta(days=90)):
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
                # 上限に達している場合はキャッシュがあれば使い、なければNone
                video_id = artist.youtube_video_id if artist else None
        else:
            # 3. キャッシュ利用 (有効期限内)
            video_id = artist.youtube_video_id

        artist_list.append({"name": artist_name, "youtube_id": video_id})

    return artist_list, youtube_fetch_count


async def scrape_loft_project_venue(page, venue_name: str, venue_slug: str, target_dates: list, db_session, youtube_fetch_count: int, pending_reports: Optional[Dict] = None) -> int:
    """
    Generic scraper for LOFT PROJECT venues (LOFT, SHELTER, etc.)
    """
    base_url = f"https://www.loft-prj.co.jp/schedule/{venue_slug}/schedule"
    print(f"Scraping {venue_name} at {base_url}")
    
    await page.goto(base_url)
    try:
        await page.wait_for_selector('a.js-cursor-elm', timeout=10000)
    except:
        print(f"[{venue_name}] No events found or page structure mismatch.")
        return youtube_fetch_count
    
    try:
        livehouse = db_session.query(LiveHouse).filter(LiveHouse.name == venue_name).first()
        if not livehouse:
            livehouse = LiveHouse(name=venue_name, area="Unknown", latitude=0, longitude=0, url=f"https://www.loft-prj.co.jp/{venue_slug}/")
            db_session.add(livehouse)
            db_session.commit()
            livehouse = db_session.query(LiveHouse).filter(LiveHouse.name == venue_name).first()
        livehouse_id = livehouse.id
    except Exception as e:
        db_session.rollback()
        print(f"[{venue_name}] Error initializing livehouse: {e}")
        return youtube_fetch_count

    event_links = await page.query_selector_all('a.js-cursor-elm')
    processed_hrefs = set()
    
    for link in event_links:
        href = await link.get_attribute('href')
        if not href or href in processed_hrefs: continue
        processed_hrefs.add(href)
        
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
            
        # Get Image from list page if available
        image_url = None
        fig_img = await link.query_selector('figure img')
        if fig_img:
            image_url = await fig_img.get_attribute('src')
            if image_url and not image_url.startswith('http'):
                image_url = f"https://www.loft-prj.co.jp{image_url}"
        
        found_date = None
        for target_date in target_dates:
            if event_date.date() == target_date.date():
                found_date = target_date
                break
        
        if not found_date: continue
        
        print(f"[{venue_name}] Processing event for {found_date.date()}: {href}")
        
        detail_page = await page.context.browser.new_page()
        try:
            await detail_page.goto(href)
            await detail_page.wait_for_load_state("networkidle")
            
            # Title extraction
            title = "Unknown Title"
            for selector in ['h1.c_title span', 'h1.c_title', 'h1.mainTitle', 'h1']:
                title_elem = await detail_page.query_selector(selector)
                if title_elem:
                    title_text = await title_elem.inner_text()
                    if title_text.strip():
                        title = title_text.strip()
                        break
            
            # Performers extraction
            performers_str = ""
            performers_elems = await detail_page.query_selector_all('.actList li')
            if performers_elems:
                performers = [ (await p.inner_text()).strip() for p in performers_elems if (await p.inner_text()).strip() ]
                performers_str = ", ".join(performers)
            
            if not performers_str:
                for p_selector in ['.entry p span strong', '.entry p', '.entry']:
                    entry_elem = await detail_page.query_selector(p_selector)
                    if entry_elem:
                        p_text = await entry_elem.inner_text()
                        if p_text.strip():
                            performers_str = p_text.replace("ACT:", "").replace("出演:", "").strip()
                            break
            
            # Time extraction
            time_elem = await detail_page.query_selector('.open') or \
                        await detail_page.query_selector('.openStart') or \
                        await detail_page.query_selector('.open-start')
            
            time_text = await time_elem.inner_text() if time_elem else ""
            open_time, start_time = "", ""
            if time_text:
                match_open = re.search(r'OPEN\s*(\d{2}:\d{2})', time_text, re.IGNORECASE)
                if match_open: open_time = match_open.group(1)
                match_start = re.search(r'START\s*(\d{2}:\d{2})', time_text, re.IGNORECASE)
                if match_start: start_time = match_start.group(1)
                
            # Price info
            price_elem = await detail_page.query_selector('.ticket_detail_box') or \
                         await detail_page.query_selector('.price') or \
                         await detail_page.query_selector('.ticketWrap .price')
            price_info = sanitize_price_info(await price_elem.inner_text()) if price_elem else ""
            
            # Ticket URL
            ticket_url = None
            for t_selector in ['.ticketList a', '.ticketWrap a', '.entry a']:
                ticket_link_elem = await detail_page.query_selector(t_selector)
                if ticket_link_elem:
                    t_href = await ticket_link_elem.get_attribute('href')
                    if t_href and any(domain in t_href for domain in ['eplus.jp', 't.pia.jp', 'l-tike.com', 'tiget.net', 't.livepocket.jp']):
                        ticket_url = t_href
                        break

            # OGP Fallback
            if not image_url and ticket_url:
                print(f"[{venue_name}] Fetching OGP image for {ticket_url}")
                image_url = fetch_og_image(ticket_url)

            # Late night check
            is_midnight = False
            time_to_check = start_time or open_time
            if time_to_check:
                try:
                    hour = int(time_to_check.split(':')[0])
                    if hour >= 21 or hour < 4:
                        is_midnight = True
                except:
                    pass

            try:
                # Get artist/video data
                artist_info_list, youtube_fetch_count = get_artist_video_info(
                    db_session, performers_str, youtube_fetch_count, pending_reports
                )

                # Upsert event
                existing_event = db_session.query(Event).filter(
                    Event.livehouse_id == livehouse_id,
                    Event.date == found_date.date(),
                    Event.title == title
                ).first()
                
                if existing_event:
                    existing_event.performers = performers_str
                    existing_event.open_time = open_time
                    existing_event.start_time = start_time
                    existing_event.price_info = price_info
                    existing_event.ticket_url = ticket_url
                    existing_event.is_midnight = is_midnight
                    existing_event.artists_data = artist_info_list
                    existing_event.image_url = image_url
                    print(f"[{venue_name}] Updated: {title}")
                else:
                    new_event = Event(
                        livehouse_id=livehouse_id,
                        date=found_date.date(),
                        title=title,
                        performers=performers_str,
                        open_time=open_time,
                        start_time=start_time,
                        price_info=price_info,
                        ticket_url=ticket_url,
                        is_midnight=is_midnight,
                        artists_data=artist_info_list,
                        image_url=image_url
                    )
                    db_session.add(new_event)
                    print(f"[{venue_name}] Added: {title}")
                
                db_session.commit()

            except Exception as e:
                db_session.rollback()
                print(f"[{venue_name}] DB Error for {title}: {e}")
        except Exception as outer_e:
            print(f"[{venue_name}] Error processing details for {href}: {outer_e}")
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
        
        # 0. Fetch pending reports
        db_reports = SessionLocal()
        pending_reports = {}
        try:
            reports = db_reports.query(VideoReport).filter(VideoReport.status == 'pending').all()
            for r in reports:
                pending_reports[r.artist_name] = r
            if pending_reports:
                print(f"[Scraper] Found {len(pending_reports)} pending video reports to fix.")
        except Exception as e:
            print(f"Error fetching pending reports: {e}")
        finally:
            db_reports.close()

        # 1. Shinjuku LOFT
        db_loft = SessionLocal()
        try:
            youtube_fetch_count = await scrape_loft_project_venue(page, "新宿LOFT", "loft", target_dates, db_loft, youtube_fetch_count, pending_reports)
        except Exception as e:
            db_loft.rollback()
            print(f"Error scraping Shinjuku LOFT: {e}")
        finally:
            db_loft.close()

        # 2. Shimokitazawa SHELTER
        db_shelter = SessionLocal()
        try:
            youtube_fetch_count = await scrape_loft_project_venue(page, "下北沢SHELTER", "shelter", target_dates, db_shelter, youtube_fetch_count, pending_reports)
        except Exception as e:
            db_shelter.rollback()
            print(f"Error scraping Shimokitazawa SHELTER: {e}")
        finally:
            db_shelter.close()

        # 3. LOFT9 Shibuya
        db_loft9 = SessionLocal()
        try:
            youtube_fetch_count = await scrape_loft_project_venue(page, "LOFT9 Shibuya", "loft9", target_dates, db_loft9, youtube_fetch_count, pending_reports)
        except Exception as e:
            db_loft9.rollback()
            print(f"Error scraping LOFT9 Shibuya: {e}")
        finally:
            db_loft9.close()

        # 4. LOFT HEAVEN (Shibuya)
        db_heaven = SessionLocal()
        try:
            youtube_fetch_count = await scrape_loft_project_venue(page, "LOFT HEAVEN", "heaven", target_dates, db_heaven, youtube_fetch_count, pending_reports)
        except Exception as e:
            db_heaven.rollback()
            print(f"Error scraping LOFT HEAVEN: {e}")
        finally:
            db_heaven.close()

        # 5. Flowers LOFT (Shimokitazawa)
        db_flowers = SessionLocal()
        try:
            youtube_fetch_count = await scrape_loft_project_venue(page, "Flowers LOFT", "flowersloft", target_dates, db_flowers, youtube_fetch_count, pending_reports)
        except Exception as e:
            db_flowers.rollback()
            print(f"Error scraping Flowers LOFT: {e}")
        finally:
            db_flowers.close()
                
        await browser.close()

    print(f"\n[完了] 本日のYouTube取得数: {youtube_fetch_count}件 / 上限{DAILY_FETCH_LIMIT}件")

def run_all_scrapers():
    """Wrapper to run the async scraper synchronously."""
    asyncio.run(async_run_all_scrapers())

if __name__ == "__main__":
    run_all_scrapers()
