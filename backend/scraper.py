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
import random
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()

# --- Load Management Settings ---
# Randomized delay range between requests to avoid server load (seconds)
SCRAPE_RANDOM_DELAY_RANGE = (1.5, 4.0)
# Longer sleep between venue changes (seconds)
VENUE_INTERVAL_SLEEP = 5.0

async def wait_random(multiplier: float = 1.0):
    """Wait for a random duration to mimic human behavior."""
    delay = random.uniform(*SCRAPE_RANDOM_DELAY_RANGE) * multiplier
    # print(f"[Scraper] Waiting {delay:.2f}s...")
    await asyncio.sleep(delay)

def sanitize_price_info(text):
    if not text: return ""
    lines = text.split('\n')
    clean_lines = []
    
    # Noise words to skip ONLY if the line doesn't look like a price line
    skip_keywords = [
        "学割", "学生証", "チケット予約", "【TICKET】", "チケット販売", 
        "販売中", "予約受付中", "ぴあ", "ローソン", "ローチケ", "e+", "イープラス"
    ]
    
    # Keywords that signal the start of sales info (we stop here)
    stop_keywords = [
        "[発売]", "【発売日】", "【入場順】", "[発売日]", "【発売】", "［発売］",
        "プレオーダー", "一般発売", "発売開始", "e+プレオーダー", "先行予約", "販売開始"
    ]

    for line in lines:
        line_clean = line.strip()
        if not line_clean:
            continue
            
        # Break if we hit details about sales dates/methods
        if any(label in line_clean for label in stop_keywords):
            break
            
        # Heuristic to identify price lines
        is_price_line = any(p in line_clean.upper() for p in ["¥", "ADV", "DOOR", "当日", "前売", "FREE", "無料"])
        
        # Skip if it's a known noise line AND it's not a price line
        if any(label in line_clean for label in skip_keywords) and not is_price_line:
            continue
            
        clean_lines.append(line_clean)
        
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
            # Skip generic platform icons
            if "ticketdive" in img_url and "ogp.webp" in img_url:
                print(f"[OGP] Skipping generic TicketDive icon: {img_url}")
            else:
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
            
            # statusをresolvedに変更 (該当アーティストの全pending報告を解決)
            db_session.query(VideoReport).filter(
                VideoReport.artist_name == artist_name,
                VideoReport.status == 'pending'
            ).update({"status": "resolved"})
            
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
                
                try:
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
                except RuntimeError as re_err:
                    print(f"[YouTube] 検索中断 (エラー): {re_err}")
                    # クォータ制限などの致命的なエラーの場合はループを抜ける
                    break
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
            year_str = await (await time_divs[0].get_property("textContent")).json_value()
            month_str = await (await time_divs[1].get_property("textContent")).json_value()
            day_str = await (await time_divs[2].get_property("textContent")).json_value()
            event_date_str = f"{year_str.strip()}-{month_str.strip()}-{day_str.strip()}"
            event_date = datetime.strptime(event_date_str, "%Y-%m-%d")
        except Exception as e:
            print(f"[{venue_name}] Failed to parse date: {e}")
            continue
            
        # Get Image from list page if available (Handle lazy loading)
        image_url = None
        fig_img = await link.query_selector('figure img')
        if fig_img:
            # Check data-src first for lazy-loaded images, then fallback to src
            image_url = await fig_img.get_attribute('data-src') or await fig_img.get_attribute('src')
        else:
            # Check for background images in span elements
            fig_bg = await link.query_selector('figure .bg')
            if fig_bg:
                image_url = await fig_bg.get_attribute('data-bg')
        
        if image_url:
            # Ignore placeholders/data URIs
            if image_url.startswith('data:image') or 'pixel.gif' in image_url or 'placeholder' in image_url:
                image_url = None
            elif not image_url.startswith('http'):
                image_url = f"https://www.loft-prj.co.jp{image_url}"
        
        found_date = None
        for target_date in target_dates:
            if event_date.date() == target_date.date():
                found_date = target_date
                break
        
        if not found_date: continue
        
        # Wait for load management before each detail page
        await wait_random()
        
        detail_page = await page.context.browser.new_page()
        try:
            await detail_page.goto(href)
            await detail_page.wait_for_load_state("networkidle")
            
            # Title extraction
            title = "Unknown Title"
            for selector in ['h1.c_title span', 'h1.c_title', 'h1.mainTitle', 'h1']:
                title_elem = await detail_page.query_selector(selector)
                if title_elem:
                    try:
                        title_text = await title_elem.text_content()
                        if title_text and title_text.strip():
                            title = title_text.strip()
                            break
                    except Exception as te:
                        print(f"[{venue_name}] Title extraction error with {selector}: {te}")
            
            # Performers extraction
            performers_str = ""
            performers_list = []
            
            # 1. NEW: Try Taxonomies/Tags (Hashtags) - Highly reliable for artist names on Loft Project
            tag_elems = await detail_page.query_selector_all('.taxList a, .taxList li, .taxonomies a, ul.tag a, ul.tag li')
            for tag_elem in tag_elems:
                tag_text = await tag_elem.text_content()
                if tag_text and tag_text.strip().startswith('#'):
                    # Remove the # and strip
                    p_name = tag_text.strip()[1:].strip()
                    # Filter out non-artist tags if any
                    if p_name and p_name.upper() not in ["GOODS", "TICKET", "ACCESS", "SCHEDULE", "NEWS", "CONTACT"]:
                        performers_list.append(p_name)
            
            if performers_list:
                performers_str = " / ".join(performers_list)
            
            # 2. Try .actList (Standard UL/LI) - if tags failed
            if not performers_str:
                performers_elems = await detail_page.query_selector_all('.actList li')
                if performers_elems:
                    performers = []
                    for p in performers_elems:
                        try:
                            t = await p.text_content()
                            t = t.strip() if t else ""
                            if t: performers.append(t)
                        except Exception as pe:
                            print(f"[{venue_name}] Performer extraction error: {pe}")
                    performers_str = " / ".join(performers)
            
            # 3. Try various text patterns in the Main Content description with <br> consideration
            if not performers_str:
                # Restrict search area
                content_elem = await detail_page.query_selector('.schedule-detail') or \
                               await detail_page.query_selector('.post-content') or \
                               await detail_page.query_selector('.entry')
                
                if content_elem:
                    # Get text but preserve <br> by replacing it with \n in JS
                    content_text = await content_elem.evaluate("""node => {
                        const clone = node.cloneNode(true);
                        clone.querySelectorAll('br').forEach(br => br.replaceWith('\\n'));
                        return clone.innerText;
                    }""")
                    
                    # Search for ACT or 出演 labels
                    act_match = re.search(r'(?:ACT|出演)[:：\s]+(.*?)(?:\n\n|\r\n\r\n|$|※)', content_text, re.DOTALL | re.IGNORECASE)
                    if act_match:
                        raw_performers = act_match.group(1).strip()
                        # Split by newline or slashes
                        p_splits = [p.strip() for p in re.split(r'[\n／/]', raw_performers) if p.strip()]
                        # Filter blacklist
                        blacklist = ["GOODS", "TICKET", "ACCESS", "SCHEDULE", "NEWS", "CONTACT"]
                        p_splits = [p for p in p_splits if not any(word in p.upper() for word in blacklist)]
                        if p_splits:
                            performers_str = " / ".join(p_splits)

            # 4. Fallback to Meta OGP Description (Last resort due to space delimiter ambiguity)
            if not performers_str:
                og_desc_elem = await detail_page.query_selector('meta[property="og:description"]')
                if og_desc_elem:
                    og_desc = await og_desc_elem.get_attribute('content')
                    if og_desc:
                        generic_descriptions = ["新宿LOFT", "下北沢SHELTER", "Flowers LOFT", "LOFT PROJECT"]
                        if not any(generic in og_desc for generic in generic_descriptions):
                            if "出演：" in og_desc:
                                # og:description is often "ネムレス めろん畑a go go ..." (space separated)
                                # We try to use it as is if nothing else worked
                                p_raw = og_desc.split("出演：")[1].strip().split(" | ")[0].strip()
                                performers_str = p_raw
                            else:
                                performers_str = og_desc.strip().split(" | ")[0].strip()
            
            # 3. Special handling for Birthday/Solo events: Include title if it contains artist-like names
            # If still empty or if it's a "B-Day" event, title often has the main name
            if "生誕" in title or "BD" in title or "BIRTHDAY" in title.upper():
                main_name = title.split('生誕')[0].split('BIRTHDAY')[0].strip()
                if main_name and main_name not in performers_str:
                    if performers_str:
                        performers_str = f"{main_name}, {performers_str}"
                    else:
                        performers_str = main_name
            
            # Time extraction
            time_elem = await detail_page.query_selector('.open') or \
                        await detail_page.query_selector('.openStart') or \
                        await detail_page.query_selector('.open-start')
            
            time_text = (await time_elem.text_content() if time_elem else "") or ""
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
            # Fixed illegal selector call (await price_elem.inner_text())
            price_info = sanitize_price_info(await price_elem.text_content()) if price_elem else ""
            
            # Ticket URL
            ticket_url = None
            for t_selector in ['.ticketList a', '.ticketWrap a', '.entry a']:
                ticket_link_elem = await detail_page.query_selector(t_selector)
                if ticket_link_elem:
                    t_href = await ticket_link_elem.get_attribute('href')
                    if t_href and any(domain in t_href for domain in ['eplus.jp', 'pia.jp', 'l-tike.com', 'tiget.net', 'livepocket.jp', 't-dv.com']):
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



async def scrape_era_events(page, db_session, youtube_fetch_count: int, pending_reports: Optional[Dict] = None) -> int:
    """
    Scraper for Shimokitazawa ERA (http://s-era.jp/schedule)
    """
    venue_name = "下北沢ERA"
    base_url = "http://s-era.jp/schedule"
    print(f"Scraping {venue_name} at {base_url}")
    
    # JST logic (same as run_all)
    now_jst = datetime.utcnow() + timedelta(hours=9)
    target_dates = [now_jst, now_jst + timedelta(days=1)]
    
    try:
        livehouse = db_session.query(LiveHouse).filter(LiveHouse.name == venue_name).first()
        if not livehouse:
            print(f"[{venue_name}] Livehouse not found in DB!")
            return youtube_fetch_count
        livehouse_id = livehouse.id
    except Exception as e:
        print(f"[{venue_name}] Error fetching livehouse: {e}")
        return youtube_fetch_count

    # Try main schedule page
    try:
        await page.goto(base_url, wait_until="load", timeout=30000)
        # Extra wait for any lazy loading/heavy JS
        await asyncio.sleep(3)
        await page.wait_for_selector('article.schedule-box', timeout=15000)
        print(f"[{venue_name}] Successfully loaded schedule page.")
    except Exception as e:
        print(f"[{venue_name}] Wait for selector failed: {e}")
        return youtube_fetch_count

    items = await page.query_selector_all('article.schedule-box')
    print(f"[{venue_name}] Found {len(items)} items on page.")
    
    for item in items:
        try:
            # Date parsing using time[datetime]
            time_elem = await item.query_selector('time')
            if not time_elem: continue
            
            datetime_str = await time_elem.get_attribute('datetime') # e.g. "2026-03-16"
            if not datetime_str: continue
            
            try:
                event_date = datetime.strptime(datetime_str, "%Y-%m-%d")
            except Exception as de:
                print(f"[{venue_name}] Date parse error for '{datetime_str}': {de}")
                continue
            
            # Check if it's today or tomorrow
            found_date = None
            for target_date in target_dates:
                if event_date.date() == target_date.date():
                    found_date = target_date
                    break
            if not found_date: continue

            # Title & Performers
            title_elem = await item.query_selector('h4')
            title = (await title_elem.text_content()).strip() if title_elem else "Unknown Title"
            
            # Skip non-public events or rental info
            skip_titles = ["HALL RENTAL", "レンタル"]
            if any(st in title.upper() for st in skip_titles):
                print(f"[{venue_name}] Skipping non-public event: {title}")
                continue
            
            # Performers often in .w-flyer
            flyer_div = await item.query_selector('.w-flyer')
            performers_str = ""
            if flyer_div:
                # Use inner_html to preserve <br> as delimiters
                flyer_html = await flyer_div.inner_html()
                # Split by <br> or other common separators and join with " / "
                p_text = flyer_html.split('<div')[0].split('[チケット')[0].split('［チケット')[0]
                # Replace <br> and <br/> with " / "
                p_text = re.sub(r'<br\s*/?>', ' / ', p_text, flags=re.IGNORECASE)
                # Remove any remaining tags
                p_text = re.sub(r'<[^>]+>', '', p_text).strip()
                # Clean up multiple slashes or spaces
                performers_str = re.sub(r'\s*/\s*', ' / ', p_text)
                performers_str = re.sub(r'\s{2,}', ' ', performers_str).strip()
            
            if not performers_str:
                performers_str = title

            # Get more details
            # Time and Price are in .notes-wrapper or similar
            notes_wrapper = await item.query_selector('.notes-wrapper')
            time_text = ""
            price_info = ""
            if notes_wrapper:
                text = await notes_wrapper.text_content()
                time_text = text if text else ""
                
                # Prettify Price Info for ERA
                # Example: "ADV ¥2,500DOOR ¥3,000" -> "ADV ¥2,500 / DOOR ¥3,000"
                price_match = re.search(r'(ADV.*?)(DOOR.*)', text, re.IGNORECASE)
                if price_match:
                    adv_part = price_match.group(1).strip()
                    door_part = price_match.group(2).strip()
                    
                    # Remove playguide noise (e.g., ●LivePocket) from the door part
                    # We look for common markers to stop at
                    door_part = re.split(r'[●■【]|[a-zA-Z\d\.\s]*?(LivePocket|e\+|ぴあ|ローソン|チケット)', door_part, flags=re.IGNORECASE)[0].strip()
                    
                    price_info = f"{adv_part} / {door_part}"
                else:
                    price_info = sanitize_price_info(text)
                
                # Final cleanup: remove trailing/leading noise
                price_info = price_info.strip()
            
            image_url = None
            ticket_url = None

            # Flyer image
            img_elem = await item.query_selector('.flyer img')
            if img_elem:
                image_url = await img_elem.get_attribute('src')
            
            # Ticket link in .playguides
            ticket_link = await item.query_selector('.playguides a')
            if ticket_link:
                ticket_url = await ticket_link.get_attribute('href')

            # OGP Fallback if needed
            if not image_url and ticket_url:
                image_url = fetch_og_image(ticket_url)

            # Time parsing from time_text
            open_time, start_time = "", ""
            if time_text:
                match_open = re.search(r'OPEN\s*(\d{2}:\d{2})', time_text, re.IGNORECASE)
                if match_open: open_time = match_open.group(1)
                match_start = re.search(r'START\s*(\d{2}:\d{2})', time_text, re.IGNORECASE)
                if match_start: start_time = match_start.group(1)

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

            # Artist Video Data
            artist_info_list, youtube_fetch_count = get_artist_video_info(
                db_session, performers_str, youtube_fetch_count, pending_reports
            )

            # Upsert
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

        except Exception as ie:
            print(f"[{venue_name}] Error in item loop: {ie}")
            db_session.rollback()

    return youtube_fetch_count


async def scrape_mosaic_events(page, db_session, youtube_fetch_count, pending_reports):
    venue_name = "下北沢MOSAiC"
    url = "https://mu-seum.co.jp/schedule.html"
    print(f"[{venue_name}] Fetching {url}...")
    
    # Handle JST time
    now_jst = datetime.utcnow() + timedelta(hours=9)
    target_dates = [now_jst, now_jst + timedelta(days=1)]
    
    livehouse = db_session.query(LiveHouse).filter(LiveHouse.name == venue_name).first()
    if not livehouse:
        print(f"[{venue_name}] Livehouse not found in DB.")
        return youtube_fetch_count
    livehouse_id = livehouse.id

    try:
        await page.goto(url, timeout=60000)
        await page.wait_for_selector('div.centerCont.bottomLiner', timeout=10000)
    except Exception as e:
        print(f"[{venue_name}] Wait for selector failed: {e}")
        return youtube_fetch_count

    containers = await page.query_selector_all('div.centerCont.bottomLiner')
    print(f"[{venue_name}] Found {len(containers)} day containers.")

    for container in containers:
        try:
            # MOSAiC uses id="1", id="2" etc. for days of the current month
            day_id = await container.get_attribute('id')
            if not day_id or not day_id.isdigit(): continue
            
            # Construct date (simplistic: assumes current month)
            event_day = int(day_id)
            event_date = now_jst.replace(day=event_day)
            
            # Handle month rollover if necessary (if a container for next month exists)
            found_date = None
            for td in target_dates:
                if td.year == event_date.year and td.month == event_date.month and td.day == event_date.day:
                    found_date = td
                    break
            if not found_date: continue

            table = await container.query_selector('table.listCal')
            if not table: continue

            # Title: .live_title
            title_elem = await table.query_selector('.live_title')
            title = (await title_elem.text_content()).strip() if title_elem else "Unknown Title"
            
            # Skip non-public
            if any(st in title.upper() for st in ["HALL RENTAL", "レンタル"]):
                continue

            # Menu contains Performers, Time, Price, Tickets
            menu_elem = await table.query_selector('.live_menu')
            performers_str = ""
            open_time, start_time = "", ""
            price_info = ""
            ticket_url = None
            
            if menu_elem:
                # Performers: usually inside <strong>
                strong_elem = await menu_elem.query_selector('strong')
                if strong_elem:
                    performers_str = (await strong_elem.text_content()).strip()
                
                menu_text = await menu_elem.text_content()
                
                # Times: OPEN 00:00 / START 00:00
                match_open = re.search(r'OPEN\s*(\d{2}:\d{2})', menu_text, re.IGNORECASE)
                if match_open: open_time = match_open.group(1)
                match_start = re.search(r'START\s*(\d{2}:\d{2})', menu_text, re.IGNORECASE)
                if match_start: start_time = match_start.group(1)
                
                # Price: Look for ¥
                price_lines = []
                for line in menu_text.split('\n'):
                    if '¥' in line or '￥' in line or 'ADV' in line.upper() or 'DOOR' in line.upper():
                        price_lines.append(line.strip())
                price_info = " / ".join(price_lines)
                price_info = sanitize_price_info(price_info)
                
                # Ticket URL: First link in menu
                ticket_link = await menu_elem.query_selector('a')
                if ticket_link:
                    ticket_url = await ticket_link.get_attribute('href')

            if not performers_str: performers_str = title

            # Late night check
            is_midnight = False
            time_to_check = start_time or open_time
            if time_to_check:
                try:
                    hour = int(time_to_check.split(':')[0])
                    if hour >= 21 or hour < 4: is_midnight = True
                except: pass

            # OGP for Image
            image_url = fetch_og_image(ticket_url) if ticket_url else None

            # Video Data
            artist_info_list, youtube_fetch_count = get_artist_video_info(
                db_session, performers_str, youtube_fetch_count, pending_reports
            )

            # Upsert
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

        except Exception as ie:
            print(f"[{venue_name}] Error in item loop: {ie}")
            db_session.rollback()

    return youtube_fetch_count


async def scrape_club251_events(page, db_session, youtube_fetch_count, pending_reports):
    venue_name = "下北沢CLUB251"
    url = "https://club251.com/schedule/"
    print(f"[{venue_name}] Fetching {url}...")
    
    # Handle JST time
    now_jst = datetime.utcnow() + timedelta(hours=9)
    target_dates = [now_jst, now_jst + timedelta(days=1)]
    
    livehouse = db_session.query(LiveHouse).filter(LiveHouse.name == venue_name).first()
    if not livehouse:
        print(f"[{venue_name}] Livehouse not found in DB.")
        return youtube_fetch_count
    livehouse_id = livehouse.id

    try:
        await page.goto(url, timeout=60000)
        await page.wait_for_selector('.schedule-in', state='attached', timeout=10000)
    except Exception as e:
        print(f"[{venue_name}] Wait for selector failed: {e}")
        # Continue anyway if elements might be there

    containers = await page.query_selector_all('.schedule-in')
    print(f"[{venue_name}] Found {len(containers)} event containers.")
    
    for container in containers:
        try:
            # Date Header: tr.list_date th (Wait, it might be within the container)
            date_elem = await container.query_selector('tr.list_date th')
            if not date_elem:
                # Fallback: maybe it's just a th or something else
                date_elem = await container.query_selector('th')
            
            if not date_elem: continue
            
            header_text = (await date_elem.text_content()).strip()
            # Handle non-breaking spaces and other noise
            match = re.search(r'(\d+)', header_text)
            if not match:
                # Debug print for failed date match
                # print(f"[{venue_name}] Date match failed for header: '{header_text}'")
                continue
            
            day = int(match.group(1))
            try:
                event_date = now_jst.replace(day=day)
            except Exception as de:
                # print(f"[{venue_name}] Date construction failed for day {day}: {de}")
                continue

            # Check if event_date is one of our target dates
            found_date = None
            for td in target_dates:
                if td.year == event_date.year and td.month == event_date.month and td.day == event_date.day:
                    found_date = td
                    break
            
            if not found_date: continue
            
            # print(f"[{venue_name}] Processing event for date: {found_date.date()}")

            # Title: h2.eventname is required for a public event
            title_elem = await container.query_selector('h2.eventname')
            if not title_elem:
                # If no eventname, it's likely an empty day (like March 16/17)
                continue
            
            title = (await title_elem.text_content()).strip()
            
            # Skip non-public
            if any(st in title.upper() for st in ["HALL RENTAL", "レンタル", "貸切"]):
                continue

            # Performers: p.fw-bold
            performers_str = title
            performers_elem = await container.query_selector('p.fw-bold')
            if performers_elem:
                performers_str = (await performers_elem.text_content()).strip()
            
            # Times and Price: search in container text
            text = await container.text_content()
            
            open_time, start_time = "", ""
            match_open = re.search(r'OPEN\s*(\d{2}:\d{2})', text, re.IGNORECASE)
            if match_open: open_time = match_open.group(1)
            match_start = re.search(r'START\s*(\d{2}:\d{2})', text, re.IGNORECASE)
            if match_start: start_time = match_start.group(1)
            
            price_info = ""
            charge_match = re.search(r'CHARGE\s*:(.*)', text, re.IGNORECASE)
            if charge_match:
                price_info = sanitize_price_info(charge_match.group(1))
            
            ticket_url = None
            link_elem = await container.query_selector('a[href*="tiget"], a[href*="livepocket"], a[href*="eplus"]')
            if not link_elem:
                link_elem = await container.query_selector('a')
            if link_elem:
                ticket_url = await link_elem.get_attribute('href')
                if ticket_url and ticket_url.startswith('/'):
                    ticket_url = "https://club251.com" + ticket_url
            
            # Image: img
            image_url = None
            img_elem = await container.query_selector('img')
            if img_elem:
                # Try data-src first if exists
                image_url = await img_elem.get_attribute('data-src') or await img_elem.get_attribute('src')
            
            # OGP Fallback
            if not image_url and ticket_url:
                image_url = fetch_og_image(ticket_url)
            
            # Late night check
            is_midnight = False
            time_to_check = start_time or open_time
            if time_to_check:
                try:
                    hour = int(time_to_check.split(':')[0])
                    if hour >= 21 or hour < 4: is_midnight = True
                except: pass

            # Video Data
            artist_info_list, youtube_fetch_count = get_artist_video_info(
                db_session, performers_str, youtube_fetch_count, pending_reports
            )

            # Upsert
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

        except Exception as ie:
            print(f"[{venue_name}] Error in item loop: {ie}")
            db_session.rollback()
    
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

        await asyncio.sleep(VENUE_INTERVAL_SLEEP)

        # 2. Shimokitazawa SHELTER
        db_shelter = SessionLocal()
        try:
            youtube_fetch_count = await scrape_loft_project_venue(page, "下北沢SHELTER", "shelter", target_dates, db_shelter, youtube_fetch_count, pending_reports)
        except Exception as e:
            db_shelter.rollback()
            print(f"Error scraping Shimokitazawa SHELTER: {e}")
        finally:
            db_shelter.close()
        
        await asyncio.sleep(VENUE_INTERVAL_SLEEP)

        # 3. LOFT9 Shibuya
        # db_loft9 = SessionLocal()
        # try:
        #     youtube_fetch_count = await scrape_loft_project_venue(page, "LOFT9 Shibuya", "loft9", target_dates, db_loft9, youtube_fetch_count, pending_reports)
        # except Exception as e:
        #     db_loft9.rollback()
        #     print(f"Error scraping LOFT9 Shibuya: {e}")
        # finally:
        #     db_loft9.close()

        # 4. LOFT HEAVEN (Shibuya)
        # db_heaven = SessionLocal()
        # try:
        #     youtube_fetch_count = await scrape_loft_project_venue(page, "LOFT HEAVEN", "heaven", target_dates, db_heaven, youtube_fetch_count, pending_reports)
        # except Exception as e:
        #     db_heaven.rollback()
        #     print(f"Error scraping LOFT HEAVEN: {e}")
        # finally:
        #     db_heaven.close()


        # 5. Flowers LOFT (Shimokitazawa)
        db_flowers = SessionLocal()
        try:
            youtube_fetch_count = await scrape_loft_project_venue(page, "Flowers LOFT", "flowersloft", target_dates, db_flowers, youtube_fetch_count, pending_reports)
        except Exception as e:
            db_flowers.rollback()
            print(f"Error scraping Flowers LOFT: {e}")
        finally:
            db_flowers.close()

        await asyncio.sleep(VENUE_INTERVAL_SLEEP)

        # 6. Shimokitazawa ERA
        db_era = SessionLocal()
        try:
            youtube_fetch_count = await scrape_era_events(page, db_era, youtube_fetch_count, pending_reports)
        except Exception as e:
            db_era.rollback()
            print(f"Error scraping Shimokitazawa ERA: {e}")
        finally:
            db_era.close()

        await asyncio.sleep(VENUE_INTERVAL_SLEEP)

        # 7. Shimokitazawa MOSAiC
        db_mosaic = SessionLocal()
        try:
            youtube_fetch_count = await scrape_mosaic_events(page, db_mosaic, youtube_fetch_count, pending_reports)
        except Exception as e:
            db_mosaic.rollback()
            print(f"Error scraping Shimokitazawa MOSAiC: {e}")
        finally:
            db_mosaic.close()

        await asyncio.sleep(VENUE_INTERVAL_SLEEP)

        # 8. Shimokitazawa CLUB251
        db_251 = SessionLocal()
        try:
            youtube_fetch_count = await scrape_club251_events(page, db_251, youtube_fetch_count, pending_reports)
        except Exception as e:
            db_251.rollback()
            print(f"Error scraping Shimokitazawa CLUB251: {e}")
        finally:
            db_251.close()
                
        await browser.close()

    print(f"\n[完了] 本日のYouTube取得数: {youtube_fetch_count}件 / 上限{DAILY_FETCH_LIMIT}件")

def run_all_scrapers():
    """Wrapper to run the async scraper synchronously."""
    asyncio.run(async_run_all_scrapers())

if __name__ == "__main__":
    run_all_scrapers()
