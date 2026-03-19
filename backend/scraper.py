from typing import Optional, List, Dict
import asyncio
from datetime import datetime, timedelta, timezone
from playwright.async_api import async_playwright
try:
    from models import SessionLocal, LiveHouse, Event, Artist, VideoReport
    from youtube_service import search_artist_video
except ImportError:
    # Handle direct execution vs module execution context
    import sys
    import os
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
    await asyncio.sleep(delay)

def sanitize_price_info(text):
    if not text: return ""
    lines = text.split('\n')
    clean_lines = []
    
    skip_keywords = [
        "学割", "学生証", "チケット予約", "【TICKET】", "チケット販売", 
        "販売中", "予約受付中", "ぴあ", "ローソン", "ローチケ", "e+", "イープラス"
    ]
    
    stop_keywords = [
        "[発売]", "【発売日】", "【入場順】", "[発売日]", "【発売】", "［発売］",
        "プレオーダー", "一般発売", "発売開始", "e+プレオーダー", "先行予約", "販売開始"
    ]

    for line in lines:
        line_clean = line.strip()
        if not line_clean:
            continue
            
        if any(label in line_clean for label in stop_keywords):
            break
            
        is_price_line = any(p in line_clean.upper() for p in ["¥", "ADV", "DOOR", "当日", "前売", "FREE", "無料"])
        
        if any(label in line_clean for label in skip_keywords) and not is_price_line:
            continue
            
        clean_lines.append(line_clean)
        
    return "\n".join(clean_lines).strip()

DAILY_FETCH_LIMIT = 90

def fetch_og_image(url):
    """Fetch OGP image from a URL."""
    if not url: return None
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        response = requests.get(url, headers=headers, timeout=5)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        og_image = soup.find('meta', property='og:image') or soup.find('meta', attrs={'name': 'og:image'})
        if og_image and og_image.get('content'):
            img_url = og_image.get('content')
            if "ticketdive" in img_url and "ogp.webp" in img_url:
                pass 
            else:
                if img_url.startswith('//'):
                    img_url = 'https:' + img_url
                elif img_url.startswith('/'):
                    from urllib.parse import urljoin
                    img_url = urljoin(url, img_url)
                return img_url
            
        twitter_image = soup.find('meta', name='twitter:image') or soup.find('meta', attrs={'property': 'twitter:image'})
        if twitter_image and twitter_image.get('content'):
            return twitter_image.get('content')
            
    except Exception as e:
        print(f"[OGP] Error fetching {url}: {e}")
    return None

def determine_pickup_status(performers: str, bookmark_count: int = 0, current_is_pickup: bool = False, current_pickup_type: Optional[str] = None):
    if current_is_pickup and current_pickup_type == 'staff':
        return True, 'staff'
    return current_is_pickup, current_pickup_type

def upsert_event(db_session, event_data: dict, livehouse_id: int):
    now = datetime.now(timezone.utc)
    existing_event = None
    if event_data.get('ticket_url'):
        existing_event = db_session.query(Event).filter(
            Event.livehouse_id == livehouse_id,
            Event.date == event_data['date'],
            Event.ticket_url == event_data['ticket_url']
        ).first()
    
    if not existing_event:
        existing_event = db_session.query(Event).filter(
            Event.livehouse_id == livehouse_id,
            Event.date == event_data['date'],
            Event.is_midnight == event_data.get('is_midnight', False),
            Event.title == event_data['title']
        ).first()

    if existing_event:
        existing_event.title = event_data['title']
        existing_event.performers = event_data.get('performers', "")
        existing_event.open_time = event_data.get('open_time', "")
        existing_event.start_time = event_data.get('start_time', "")
        existing_event.price_info = event_data.get('price_info', "")
        existing_event.ticket_url = event_data.get('ticket_url')
        existing_event.is_midnight = event_data.get('is_midnight', False)
        existing_event.artists_data = event_data.get('artists_data', [])
        existing_event.image_url = event_data.get('image_url')
        existing_event.last_scraped_at = now
        existing_event.status = 'published'
        
        is_p, p_t = determine_pickup_status(
            existing_event.performers, 
            existing_event.bookmark_count, 
            existing_event.is_pickup, 
            existing_event.pickup_type
        )
        existing_event.is_pickup = is_p
        existing_event.pickup_type = p_t
        print(f"[Upsert] Updated: {event_data['title']} ({event_data['date']})")
    else:
        is_p, p_t = determine_pickup_status(event_data.get('performers', ""))
        new_event = Event(
            livehouse_id=livehouse_id,
            date=event_data['date'],
            title=event_data['title'],
            performers=event_data.get('performers', ""),
            open_time=event_data.get('open_time', ""),
            start_time=event_data.get('start_time', ""),
            price_info=event_data.get('price_info', ""),
            ticket_url=event_data.get('ticket_url'),
            is_midnight=event_data.get('is_midnight', False),
            artists_data=event_data.get('artists_data', []),
            image_url=event_data.get('image_url'),
            last_scraped_at=now,
            status='published',
            is_pickup=is_p,
            pickup_type=p_t
        )
        db_session.add(new_event)
        print(f"[Upsert] Added: {event_data['title']} ({event_data['date']})")
    
    db_session.commit()

def get_artist_video_info(db_session, performers_str: str, youtube_fetch_count: int, pending_reports: Optional[Dict] = None, only_cache: bool = False) -> tuple[list, int]:
    if not performers_str:
        return [], youtube_fetch_count

    artist_list = []
    patterns = r'[、,／/\n]'
    names = [a.strip() for a in re.split(patterns, performers_str) if a.strip()]
    
    final_names = []
    for n in names:
        if ' ' in n and any(ord(c) > 127 for c in n):
            sub_names = [sn.strip() for sn in n.split(' ') if sn.strip()]
            final_names.extend(sub_names)
        else:
            final_names.append(n)
    names = final_names

    for artist_name in names:
        artist_name = re.sub(r'^[【\[\(](出演|会場|開場|開演|O\.A\.|OA|Opening Act)[】\]\)]\s*', '', artist_name, flags=re.IGNORECASE)
        artist_name = re.sub(r'^(出演|会場|開場|開演|O\.A\.|OA|Opening Act)[:：]\s*', '', artist_name, flags=re.IGNORECASE)
        artist_name = re.sub(r'\s*[（\(\[【](O\.A\.|OA|Opening Act)[）\)\]】]$', '', artist_name, flags=re.IGNORECASE)
        artist_name = re.sub(r'\s*[（\(\[【](Vo|Gt|Ba|Dr|Key|Per|Syn|Vj|DJ|Cho|Vocal|Guitar|Bass|Drums|Keyboard|Percussion)[\.\-]?.*?[）\)\]】]', '', artist_name, flags=re.IGNORECASE)
        artist_name = artist_name.strip()
        
        if not artist_name or len(artist_name) <= 1: continue
        
        skip_keywords = [
            'チケット', '予約', '詳細はこちら', 'http', '公式HP', '※', 'お問い合わせ', 
            'STAGE', 'HALL', 'LIVEHOUSE', 'LOFT', 'SHELTER', 'ERA', 'MOSAiC', '251',
            '整理番号', 'ドリンク代', '再入場', '配信', 'アーカイブ'
        ]
        if any(k.lower() in artist_name.lower() for k in skip_keywords): continue
        if re.match(r'^(Vo|Gt|Ba|Dr|Key|Per|Syn|Vj|DJ|Cho)[\.\-]?$', artist_name, re.IGNORECASE): continue

        artist = db_session.query(Artist).filter(Artist.name == artist_name).first()
        video_id = None
        report = pending_reports.get(artist_name) if pending_reports else None

        if artist and artist.official_channel_id and not only_cache:
            is_stale = not artist.youtube_updated_at or (datetime.now() - artist.youtube_updated_at) > timedelta(days=30)
            if (is_stale or report) and youtube_fetch_count < DAILY_FETCH_LIMIT:
                exclude_ids = [vid for vid in artist.reported_video_ids.split(",") if vid] if artist.reported_video_ids else []
                video_id = search_artist_video(artist_name, exclude_ids=exclude_ids, channel_id=artist.official_channel_id)
                youtube_fetch_count += 1
                if report:
                    db_session.query(VideoReport).filter(VideoReport.artist_name == artist_name, VideoReport.status == 'pending').update({"status": "resolved"})
                if report and artist.youtube_video_id and artist.youtube_video_id != video_id:
                    reported_ids = set([vid for vid in (artist.reported_video_ids or "").split(",") if vid])
                    reported_ids.add(artist.youtube_video_id)
                    artist.reported_video_ids = ",".join(reported_ids)
                artist.youtube_video_id = video_id
                artist.youtube_updated_at = datetime.now()
                artist.is_reported = False
                try:
                    db_session.commit()
                except:
                    db_session.rollback()
            else:
                video_id = artist.youtube_video_id

        elif report and youtube_fetch_count < DAILY_FETCH_LIMIT and not only_cache:
            exclude_ids = [vid for vid in artist.reported_video_ids.split(",") if vid] if artist and artist.reported_video_ids else []
            video_id = search_artist_video(artist_name, exclude_ids=exclude_ids, suffix="official MV")
            youtube_fetch_count += 1
            db_session.query(VideoReport).filter(VideoReport.artist_name == artist_name, VideoReport.status == 'pending').update({"status": "resolved"})
            if not artist:
                artist = Artist(name=artist_name)
                db_session.add(artist)
            if artist.youtube_video_id and artist.youtube_video_id != video_id:
                reported_ids = set([vid for vid in (artist.reported_video_ids or "").split(",") if vid])
                reported_ids.add(artist.youtube_video_id)
                artist.reported_video_ids = ",".join(reported_ids)
            artist.youtube_video_id = video_id
            artist.youtube_updated_at = datetime.now()
            artist.is_reported = False
            try:
                db_session.commit()
            except:
                db_session.rollback()

        elif (not artist or not artist.youtube_updated_at or (datetime.now() - artist.youtube_updated_at) > timedelta(days=90)) and not only_cache:
            if youtube_fetch_count < DAILY_FETCH_LIMIT:
                exclude_ids = [vid for vid in artist.reported_video_ids.split(",") if vid] if artist and artist.reported_video_ids else []
                try:
                    video_id = search_artist_video(artist_name, exclude_ids=exclude_ids)
                    youtube_fetch_count += 1
                    if not artist:
                        artist = Artist(name=artist_name)
                        db_session.add(artist)
                    artist.youtube_video_id = video_id
                    artist.youtube_updated_at = datetime.now()
                    artist.is_reported = False
                    db_session.commit()
                except:
                    db_session.rollback()
            else:
                video_id = artist.youtube_video_id if artist else None
        else:
            video_id = artist.youtube_video_id if artist else None

        artist_list.append({"name": artist_name, "youtube_id": video_id})

    return artist_list, youtube_fetch_count

async def scrape_loft_project_venue(page, venue_name: str, venue_slug: str, target_dates: list, db_session, youtube_fetch_count: int, pending_reports: Optional[Dict] = None) -> int:
    base_url = f"https://www.loft-prj.co.jp/schedule/{venue_slug}/schedule"
    print(f"Scraping {venue_name} at {base_url}")
    await page.goto(base_url)
    try:
        await page.wait_for_selector('a.js-cursor-elm', timeout=10000)
    except:
        return youtube_fetch_count
    
    try:
        livehouse = db_session.query(LiveHouse).filter(LiveHouse.name == venue_name).first()
        if not livehouse:
            print(f"[Warning] LiveHouse '{venue_name}' not found in database. Skipping.")
            return youtube_fetch_count
        livehouse_id = livehouse.id
    except Exception as e:
        print(f"[Error] Database error finding livehouse '{venue_name}': {e}")
        db_session.rollback()
        return youtube_fetch_count

    event_links = await page.query_selector_all('a.js-cursor-elm')
    processed_hrefs = set()
    
    for link in event_links:
        href = await link.get_attribute('href')
        if not href or href in processed_hrefs: continue
        processed_hrefs.add(href)
        
        time_elem = await link.query_selector('.time')
        if not time_elem: continue
        
        try:
            full_date_text = await time_elem.text_content()
            date_match = re.search(r'(\d{4})[./\s]*(\d{1,2})[./\s]*(\d{1,2})', full_date_text)
            if date_match:
                year_str, month_str, day_str = date_match.groups()
                event_date = datetime.strptime(f"{year_str}-{month_str.zfill(2)}-{day_str.zfill(2)}", "%Y-%m-%d")
            else:
                continue
        except:
            continue
            
        found_date = None
        for target_date in target_dates:
            if event_date.date() == target_date.date():
                found_date = target_date
                break
        if not found_date: continue
        
        image_url = None
        fig_img = await link.query_selector('figure img')
        if fig_img:
            image_url = await fig_img.get_attribute('data-src') or await fig_img.get_attribute('src')
        if image_url:
            if image_url.startswith('data:image') or 'pixel.gif' in image_url or 'placeholder' in image_url:
                image_url = None
            elif not image_url.startswith('http'):
                image_url = f"https://www.loft-prj.co.jp{image_url}"

        await wait_random()
        detail_page = await page.context.browser.new_page()
        try:
            await detail_page.goto(href)
            await detail_page.wait_for_load_state("networkidle")
            
            title = "Unknown Title"
            for selector in ['h1.c_title span', 'h1.c_title', 'h1.mainTitle', 'h1']:
                title_elem = await detail_page.query_selector(selector)
                if title_elem:
                    t_text = await title_elem.text_content()
                    if t_text:
                        title = t_text.strip()
                        break
            
            performers_str = ""
            performers_list = []
            tag_elems = await detail_page.query_selector_all('.taxList a, .taxList li, .taxonomies a, ul.tag a, ul.tag li')
            for tag_elem in tag_elems:
                tag_text = await tag_elem.text_content()
                if tag_text and tag_text.strip().startswith('#'):
                    p_name = tag_text.strip()[1:].strip()
                    if p_name and p_name.upper() not in ["GOODS", "TICKET", "ACCESS", "SCHEDULE", "NEWS", "CONTACT"]:
                        performers_list.append(p_name)
            
            if performers_list:
                performers_str = " / ".join(performers_list)
            else:
                performers_elems = await detail_page.query_selector_all('.actList li')
                if performers_elems:
                    performers = [ (await p.text_content()).strip() for p in performers_elems if (await p.text_content()) ]
                    performers_str = " / ".join(performers)
            
            if not performers_str:
                content_elem = await detail_page.query_selector('.schedule-detail') or await detail_page.query_selector('.post-content')
                if content_elem:
                    content_text = await content_elem.inner_text()
                    act_match = re.search(r'(?:ACT|出演)[:：\s]+(.*?)(?:\n\n|\r\n\r\n|$|※)', content_text, re.DOTALL | re.IGNORECASE)
                    if act_match:
                        performers_str = " / ".join([p.strip() for p in re.split(r'[\n／/]', act_match.group(1)) if p.strip()])

            if "生誕" in title or "BD" in title or "BIRTHDAY" in title.upper():
                main_name = title.split('生誕')[0].split('BIRTHDAY')[0].strip()
                if main_name and main_name not in performers_str:
                    performers_str = f"{main_name}, {performers_str}" if performers_str else main_name
            
            open_time, start_time = "", ""
            time_dt_elem = await detail_page.query_selector('.open, .open-start')
            if time_dt_elem:
                time_text = await time_dt_elem.text_content()
                match_open = re.search(r'OPEN\s*(\d{2}:\d{2})', time_text, re.IGNORECASE)
                if match_open: open_time = match_open.group(1)
                match_start = re.search(r'START\s*(\d{2}:\d{2})', time_text, re.IGNORECASE)
                if match_start: start_time = match_start.group(1)
                
            price_elem = await detail_page.query_selector('.ticket_detail_box, .price')
            price_info = sanitize_price_info(await price_elem.text_content()) if price_elem else ""
            
            ticket_url = None
            for t_selector in ['.ticketList a', '.ticketWrap a', '.entry a']:
                ticket_link_elem = await detail_page.query_selector(t_selector)
                if ticket_link_elem:
                    t_href = await ticket_link_elem.get_attribute('href')
                    if t_href and any(domain in t_href for domain in ['eplus.jp', 'pia.jp', 'l-tike.com', 'tiget.net', 'livepocket.jp', 't-dv.com']):
                        ticket_url = t_href
                        break

            if not image_url and ticket_url:
                image_url = fetch_og_image(ticket_url)

            is_midnight = False
            time_to_check = start_time or open_time
            if time_to_check:
                try:
                    hour = int(time_to_check.split(':')[0])
                    if hour >= 21 or hour < 4: is_midnight = True
                except: pass

            artist_info_list, youtube_fetch_count = get_artist_video_info(db_session, performers_str, youtube_fetch_count, pending_reports, only_cache=True)
            event_data = {
                'title': title, 'date': found_date.date(), 'performers': performers_str,
                'open_time': open_time, 'start_time': start_time, 'price_info': price_info,
                'ticket_url': ticket_url, 'is_midnight': is_midnight, 'artists_data': artist_info_list, 'image_url': image_url
            }
            upsert_event(db_session, event_data, livehouse_id)
        except:
            db_session.rollback()
        finally:
            await detail_page.close()

    return youtube_fetch_count

async def scrape_era_events(page, db_session, youtube_fetch_count: int, pending_reports: Optional[Dict] = None) -> int:
    venue_name = "下北沢ERA"
    base_url = "http://s-era.jp/schedule"
    now_jst = datetime.utcnow() + timedelta(hours=9)
    target_dates = [now_jst, now_jst + timedelta(days=1)]
    
    livehouse = db_session.query(LiveHouse).filter(LiveHouse.name == venue_name).first()
    if not livehouse: return youtube_fetch_count
    livehouse_id = livehouse.id

    try:
        await page.goto(base_url, timeout=30000)
        await asyncio.sleep(2)
        await page.wait_for_selector('article.schedule-box', timeout=15000)
    except:
        return youtube_fetch_count

    items = await page.query_selector_all('article.schedule-box')
    for item in items:
        try:
            time_elem = await item.query_selector('time')
            if not time_elem: continue
            datetime_str = await time_elem.get_attribute('datetime')
            if not datetime_str: continue
            event_date = datetime.strptime(datetime_str, "%Y-%m-%d")
            
            found_date = None
            for target_date in target_dates:
                if event_date.date() == target_date.date():
                    found_date = target_date
                    break
            if not found_date: continue

            title_elem = await item.query_selector('h4')
            title = (await title_elem.text_content()).strip() if title_elem else "Unknown Title"
            if any(st in title.upper() for st in ["HALL RENTAL", "レンタル"]): continue
            
            performers_str = ""
            flyer_div = await item.query_selector('.w-flyer')
            if flyer_div:
                flyer_html = await flyer_div.inner_html()
                p_text = flyer_html.split('<div')[0].split('[チケット')[0]
                p_text = re.sub(r'<br\s*/?>', ' / ', p_text, flags=re.IGNORECASE)
                performers_str = re.sub(r'<[^>]+>', '', p_text).strip()
            if not performers_str: performers_str = title

            notes_wrapper = await item.query_selector('.notes-wrapper')
            time_text = (await notes_wrapper.text_content()) if notes_wrapper else ""
            price_info = sanitize_price_info(time_text)
            
            open_time, start_time = "", ""
            if time_text:
                match_open = re.search(r'OPEN\s*(\d{2}:\d{2})', time_text, re.IGNORECASE)
                if match_open: open_time = match_open.group(1)
                match_start = re.search(r'START\s*(\d{2}:\d{2})', time_text, re.IGNORECASE)
                if match_start: start_time = match_start.group(1)

            image_url = None
            img_elem = await item.query_selector('.flyer img')
            if img_elem: image_url = await img_elem.get_attribute('src')
            
            ticket_url = None
            ticket_link = await item.query_selector('.playguides a')
            if ticket_link: ticket_url = await ticket_link.get_attribute('href')

            if not image_url and ticket_url: image_url = fetch_og_image(ticket_url)

            is_midnight = False
            if start_time or open_time:
                try:
                    hour = int((start_time or open_time).split(':')[0])
                    if hour >= 21 or hour < 4: is_midnight = True
                except: pass

            artist_info_list, youtube_fetch_count = get_artist_video_info(db_session, performers_str, youtube_fetch_count, pending_reports, only_cache=True)
            event_data = {
                'title': title, 'date': found_date.date(), 'performers': performers_str,
                'open_time': open_time, 'start_time': start_time, 'price_info': price_info,
                'ticket_url': ticket_url, 'is_midnight': is_midnight, 'artists_data': artist_info_list, 'image_url': image_url
            }
            upsert_event(db_session, event_data, livehouse_id)
        except:
            db_session.rollback()

    return youtube_fetch_count

async def scrape_mosaic_events(page, db_session, youtube_fetch_count, pending_reports):
    venue_name = "下北沢MOSAiC"
    url = "https://mu-seum.co.jp/schedule.html"
    now_jst = datetime.utcnow() + timedelta(hours=9)
    target_dates = [now_jst, now_jst + timedelta(days=1)]
    livehouse = db_session.query(LiveHouse).filter(LiveHouse.name == venue_name).first()
    if not livehouse: return youtube_fetch_count
    livehouse_id = livehouse.id

    try:
        await page.goto(url, timeout=60000)
        await page.wait_for_selector('div.centerCont.bottomLiner', timeout=10000)
    except: return youtube_fetch_count

    containers = await page.query_selector_all('div.centerCont.bottomLiner')
    for container in containers:
        try:
            day_id = await container.get_attribute('id')
            if not day_id or not day_id.isdigit(): continue
            event_date = now_jst.replace(day=int(day_id))
            found_date = next((td for td in target_dates if td.date() == event_date.date()), None)
            if not found_date: continue

            table = await container.query_selector('table.listCal')
            if not table: continue
            title_elem = await table.query_selector('.live_title')
            title = (await title_elem.text_content()).strip() if title_elem else "Unknown Title"
            if any(st in title.upper() for st in ["HALL RENTAL", "レンタル"]): continue

            performers_str, open_time, start_time, price_info, ticket_url = title, "", "", "", None
            menu_elem = await table.query_selector('.live_menu')
            if menu_elem:
                strong_elem = await menu_elem.query_selector('strong')
                if strong_elem: performers_str = (await strong_elem.text_content()).strip()
                menu_text = await menu_elem.text_content()
                m_open = re.search(r'OPEN\s*(\d{2}:\d{2})', menu_text, re.IGNORECASE)
                if m_open: open_time = m_open.group(1)
                m_start = re.search(r'START\s*(\d{2}:\d{2})', menu_text, re.IGNORECASE)
                if m_start: start_time = m_start.group(1)
                price_info = sanitize_price_info(menu_text)
                t_link = await menu_elem.query_selector('a')
                if t_link: ticket_url = await t_link.get_attribute('href')

            image_url = None
            img_elem = await container.query_selector('img')
            if img_elem:
                src = await img_elem.get_attribute('src')
                image_url = src if src.startswith('http') else "https://mu-seum.co.jp/" + src.lstrip('/')
            if not image_url and ticket_url: image_url = fetch_og_image(ticket_url)

            is_midnight = False
            if start_time or open_time:
                try:
                    hour = int((start_time or open_time).split(':')[0])
                    if hour >= 21 or hour < 4: is_midnight = True
                except: pass

            artist_info_list, youtube_fetch_count = get_artist_video_info(db_session, performers_str, youtube_fetch_count, pending_reports, only_cache=True)
            event_data = {
                'title': title, 'date': found_date.date(), 'performers': performers_str,
                'open_time': open_time, 'start_time': start_time, 'price_info': price_info,
                'ticket_url': ticket_url, 'is_midnight': is_midnight, 'artists_data': artist_info_list, 'image_url': image_url
            }
            upsert_event(db_session, event_data, livehouse_id)
        except: db_session.rollback()
    return youtube_fetch_count

async def scrape_club251_events(page, db_session, youtube_fetch_count, pending_reports):
    venue_name = "下北沢CLUB251"
    url = "https://club251.com/schedule/"
    now_jst = datetime.utcnow() + timedelta(hours=9)
    target_dates = [now_jst, now_jst + timedelta(days=1)]
    livehouse = db_session.query(LiveHouse).filter(LiveHouse.name == venue_name).first()
    if not livehouse: return youtube_fetch_count
    livehouse_id = livehouse.id

    try:
        await page.goto(url, timeout=60000)
        await page.wait_for_selector('.schedule-in', state='attached', timeout=10000)
    except: return youtube_fetch_count

    containers = await page.query_selector_all('.schedule-in')
    for container in containers:
        try:
            date_elem = await container.query_selector('tr.list_date th, th')
            if not date_elem: continue
            match = re.search(r'(\d+)', await date_elem.text_content())
            if not match: continue
            event_date = now_jst.replace(day=int(match.group(1)))
            found_date = next((td for td in target_dates if td.date() == event_date.date()), None)
            if not found_date: continue

            title_elem = await container.query_selector('h2.eventname')
            if not title_elem: continue
            title = (await title_elem.text_content()).strip()
            if any(st in title.upper() for st in ["HALL RENTAL", "レンタル"]): continue

            performers_str = title
            p_elem = await container.query_selector('p.fw-bold')
            if p_elem: performers_str = (await p_elem.text_content()).strip()
            
            text = await container.text_content()
            open_time, start_time = "", ""
            m_open = re.search(r'OPEN\s*(\d{2}:\d{2})', text, re.IGNORECASE)
            if m_open: open_time = m_open.group(1)
            m_start = re.search(r'START\s*(\d{2}:\d{2})', text, re.IGNORECASE)
            if m_start: start_time = m_start.group(1)
            price_info = ""
            m_charge = re.search(r'CHARGE\s*:(.*)', text, re.IGNORECASE)
            if m_charge: price_info = sanitize_price_info(m_charge.group(1))
            
            t_link = await container.query_selector('a[href*="tiget"], a[href*="livepocket"], a[href*="eplus"]') or await container.query_selector('a')
            ticket_url = await t_link.get_attribute('href') if t_link else None
            if ticket_url and ticket_url.startswith('/'): ticket_url = "https://club251.com" + ticket_url
            
            img_elem = await container.query_selector('img')
            image_url = (await img_elem.get_attribute('data-src') or await img_elem.get_attribute('src')) if img_elem else None
            if not image_url and ticket_url: image_url = fetch_og_image(ticket_url)
            
            is_midnight = False
            if start_time or open_time:
                try:
                    hour = int((start_time or open_time).split(':')[0])
                    if hour >= 21 or hour < 4: is_midnight = True
                except: pass

            artist_info_list, youtube_fetch_count = get_artist_video_info(db_session, performers_str, youtube_fetch_count, pending_reports, only_cache=True)
            event_data = {
                'title': title, 'date': found_date.date(), 'performers': performers_str,
                'open_time': open_time, 'start_time': start_time, 'price_info': price_info,
                'ticket_url': ticket_url, 'is_midnight': is_midnight, 'artists_data': artist_info_list, 'image_url': image_url
            }
            upsert_event(db_session, event_data, livehouse_id)
        except: db_session.rollback()
    return youtube_fetch_count

async def scrape_shangrila_events(page, db_session, youtube_fetch_count: int, pending_reports: Optional[Dict] = None) -> int:
    venue_name = "下北沢シャングリラ"
    base_url = "https://www.shan-gri-la.jp/tokyo/category/schedule/"
    now_jst = datetime.utcnow() + timedelta(hours=9)
    target_dates = [now_jst, now_jst + timedelta(days=1)]
    livehouse = db_session.query(LiveHouse).filter(LiveHouse.name == venue_name).first()
    if not livehouse: return youtube_fetch_count
    livehouse_id = livehouse.id

    try:
        await page.goto(base_url, wait_until="networkidle", timeout=30000)
        await page.wait_for_selector('div[id^="post-"]', timeout=15000)
    except: return youtube_fetch_count

    posts = await page.query_selector_all('div[id^="post-"]')
    for post in posts:
        try:
            date_elem = await post.query_selector("h2.post-title")
            if not date_elem: continue
            date_match = re.search(r'(\d{1,2})/(\d{1,2})', await date_elem.text_content())
            if not date_match: continue
            event_date = now_jst.replace(month=int(date_match.group(1)), day=int(date_match.group(2)))
            found_date = next((td for td in target_dates if td.date() == event_date.date()), None)
            if not found_date: continue

            content_elem = await post.query_selector(".post-content-content")
            if not content_elem: continue
            content_text = await content_elem.inner_text()
            
            # Split by parts if they exist (e.g., 【1部】, 【2部】)
            # If no part markers, we still check for multiple time patterns
            part_markers = list(re.finditer(r'【\d部】', content_text))
            
            event_slots = []
            if part_markers:
                # Get base performers (text before the first marker)
                base_text = content_text[:part_markers[0].start()].strip()
                lines = [l.strip() for l in base_text.split('\n') if l.strip()]
                base_title = lines[0] if lines else "Unknown"
                # For performers, exclude the title if there are other lines
                real_p_list = lines[1:] if len(lines) > 1 else lines
                base_performers = " / ".join(real_p_list)
                
                for i in range(len(part_markers)):
                    start_idx = part_markers[i].start()
                    end_idx = part_markers[i+1].start() if i+1 < len(part_markers) else len(content_text)
                    part_label = part_markers[i].group()
                    part_content = content_text[start_idx:end_idx]
                    
                    event_slots.append({
                        'title_prefix': f"{base_title} {part_label}",
                        'content': part_content,
                        'base_performers': base_performers
                    })
            else:
                # Check for multiple OPEN/START patterns even without 【X部】
                time_matches = list(re.finditer(r'OPEN\s*\d{2}:\d{2}\s*/\s*START\s*\d{2}:\d{2}', content_text, re.IGNORECASE))
                if len(time_matches) > 1:
                    lines = [l.strip() for l in content_text.split('\n') if l.strip()]
                    base_title = lines[0] if lines else "Unknown"
                    for i in range(len(time_matches)):
                        start_idx = time_matches[i].start()
                        end_idx = time_matches[i+1].start() if i+1 < len(time_matches) else len(content_text)
                        part_content = content_text[start_idx:end_idx]
                        event_slots.append({
                            'title_prefix': f"{base_title} (公演{i+1})",
                            'content': part_content,
                            'base_performers': base_title
                        })
                else:
                    # Single event
                    event_slots.append({'title_prefix': None, 'content': content_text, 'base_performers': None})

            img_elem = await post.query_selector("img")
            image_url = await img_elem.get_attribute("src") if img_elem else None

            for slot in event_slots:
                slot_content = slot['content']
                lines = [l.strip() for l in slot_content.split('\n') if l.strip()]
                
                # Title and performers
                if slot['title_prefix']:
                    title = slot['title_prefix']
                    performers_str = slot['base_performers'] or title
                else:
                    title = lines[0] if lines else "Unknown"
                    performers_str = title
                    if len(lines) > 1:
                        p_cand = []
                        for line in lines[1:]:
                            if any(k in line.upper() for k in ["OPEN", "START", "ADV", "DOOR"]): break
                            p_cand.append(line)
                        if p_cand: performers_str = " / ".join(p_cand)

                # Times
                open_time, start_time = "", ""
                m_time = re.search(r'OPEN\s*(\d{2}:\d{2})\s*/\s*START\s*(\d{2}:\d{2})', slot_content, re.IGNORECASE)
                if m_time: open_time, start_time = m_time.groups()
                
                # Price
                price_info = ""
                for line in lines:
                    if any(k in line for k in ["前売", "当日", "ADV", "DOOR", "￥", "¥"]):
                        price_info = sanitize_price_info(line)
                        break
                
                # Ticket URL (inside this slot)
                # Note: We need to find the link within the specific part of content_elem if possible, 
                # but inner_text doesn't give links. We should use the slot's relative position or search in HTML.
                ticket_url = None
                # Simple approach: if there's only one link in the whole post, use it. 
                # If multiple, this is tricky with inner_text splitting.
                # Let's try to find a link that appears near the price/times in the HTML.
                t_links = await content_elem.query_selector_all('a[href*="livepocket"], a[href*="ticketdive"], a[href*="tiget"], a[href*="eplus"]')
                if len(t_links) == len(event_slots):
                    idx = event_slots.index(slot)
                    ticket_url = await t_links[idx].get_attribute("href")
                elif t_links:
                    ticket_url = await t_links[0].get_attribute("href")

                curr_image_url = image_url
                if not curr_image_url and ticket_url: curr_image_url = fetch_og_image(ticket_url)

                is_midnight = False
                if start_time or open_time:
                    try:
                        hour = int((start_time or open_time).split(':')[0])
                        if hour >= 21 or hour < 4: is_midnight = True
                    except: pass

                artist_info_list, youtube_fetch_count = get_artist_video_info(db_session, performers_str, youtube_fetch_count, pending_reports, only_cache=True)
                event_data = {
                    'title': title, 'date': found_date.date(), 'performers': performers_str,
                    'open_time': open_time, 'start_time': start_time, 'price_info': price_info,
                    'ticket_url': ticket_url, 'is_midnight': is_midnight, 'artists_data': artist_info_list, 'image_url': curr_image_url
                }
                upsert_event(db_session, event_data, livehouse_id)
        except: db_session.rollback()
    return youtube_fetch_count

def sync_prioritized_artist_videos(db_session, youtube_fetch_count: int) -> int:
    print("\n[Sync] Starting prioritized artist video sync...")
    jst = timezone(timedelta(hours=9))
    today = datetime.now(jst).date()
    upcoming_events = db_session.query(Event).filter(Event.status == 'published', Event.date >= today).order_by(Event.date.asc()).all()
    if not upcoming_events: return youtube_fetch_count
    artist_priority, artist_events = {}, {}
    for event in upcoming_events:
        if not event.performers: continue
        names = [a.strip() for a in re.split(r'[、,／/\n]', event.performers) if a.strip()]
        for name in names:
            if name not in artist_priority:
                artist_priority[name], artist_events[name] = event.date, []
            artist_events[name].append(event)
    sorted_artists = sorted(artist_priority.keys(), key=lambda x: artist_priority[x])
    pending_reports_list = db_session.query(VideoReport).filter(VideoReport.status == 'pending').all()
    reported_names = {r.artist_name for r in pending_reports_list}
    sorted_artists = [n for n in sorted_artists if n in reported_names] + [n for n in sorted_artists if n not in reported_names]
    pending_reports_dict = {r.artist_name: r for r in pending_reports_list}

    for artist_name in sorted_artists:
        if youtube_fetch_count >= DAILY_FETCH_LIMIT: break
        res_list, new_count = get_artist_video_info(db_session, artist_name, youtube_fetch_count, pending_reports_dict, only_cache=False)
        if new_count > youtube_fetch_count or (res_list and res_list[0]['youtube_id']):
            vid = res_list[0]['youtube_id']
            for ev in artist_events[artist_name]:
                curr = ev.artists_data or []
                upd = False
                for item in curr:
                    if item['name'] == artist_name and item.get('youtube_id') != vid:
                        item['youtube_id'], upd = vid, True
                if upd:
                    from sqlalchemy.orm.attributes import flag_modified
                    ev.artists_data = list(curr)
                    flag_modified(ev, "artists_data")
            db_session.commit()
            youtube_fetch_count = new_count
    return youtube_fetch_count

def send_discord_notification(message: str):
    webhook_url = os.getenv("DISCORD_WEBHOOK_URL")
    if not webhook_url: return
    try:
        requests.post(webhook_url, json={"content": message}, timeout=10).raise_for_status()
        print("[Notification] Discord notification sent.")
    except Exception as e:
        print(f"[Notification] Failed: {e}")

async def async_run_all_scrapers():
    run_start_time = datetime.now(timezone.utc)
    now_jst = run_start_time + timedelta(hours=9)
    target_dates = [now_jst, now_jst + timedelta(days=1)]
    youtube_fetch_count, results = 0, []
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            db_reports = SessionLocal()
            pending_reports = {r.artist_name: r for r in db_reports.query(VideoReport).filter(VideoReport.status == 'pending').all()}
            db_reports.close()
            for v_key, v_label in [("loft", "新宿LOFT"), ("shelter", "下北沢SHELTER"), ("flowersloft", "Flowers LOFT")]:
                db_v = SessionLocal()
                try:
                    page = await browser.new_page()
                    youtube_fetch_count = await scrape_loft_project_venue(page, v_label, v_key, target_dates, db_v, youtube_fetch_count, pending_reports)
                    results.append((v_label, "✅ 完了", ""))
                except Exception as e:
                    db_v.rollback()
                    results.append((v_label, "❌ 失敗", str(e)))
                finally:
                    await page.close()
                    db_v.close()
                    await asyncio.sleep(VENUE_INTERVAL_SLEEP)
            for v_func, v_label in [(scrape_era_events, "下北沢ERA"), (scrape_mosaic_events, "下北沢MOSAiC"), (scrape_club251_events, "下北沢CLUB251"), (scrape_shangrila_events, "下北沢シャングリラ")]:
                db_v = SessionLocal()
                try:
                    page = await browser.new_page()
                    youtube_fetch_count = await v_func(page, db_v, youtube_fetch_count, pending_reports)
                    results.append((v_label, "✅ 完了", ""))
                except Exception as e:
                    db_v.rollback()
                    results.append((v_label, "❌ 失敗", str(e)))
                finally:
                    await page.close()
                    db_v.close()
                    await asyncio.sleep(VENUE_INTERVAL_SLEEP)
            db_sync = SessionLocal()
            try:
                youtube_fetch_count = sync_prioritized_artist_videos(db_sync, youtube_fetch_count)
            except Exception as e:
                results.append(("YouTube同期", "⚠️ 部分失敗", str(e)))
            finally: db_sync.close()
            await browser.close()
    except Exception as fatal_e:
        results.append(("システム全体", "🚨 致命的エラー", str(fatal_e)))
    finally:
        db_cl = SessionLocal()
        try:
            c_count = db_cl.query(Event).filter(Event.date >= (datetime.now(timezone(timedelta(hours=9))) - timedelta(days=1)).date(), Event.date <= (datetime.now(timezone(timedelta(hours=9))) + timedelta(days=45)).date(), Event.last_scraped_at < run_start_time, Event.status == 'published').update({"status": "cancelled"}, synchronize_session=False)
            db_cl.commit()
            if c_count > 0: print(f"[Cleanup] {c_count} events cancelled.")
        except: db_cl.rollback()
        finally: db_cl.close()
        msg = f"📅 **スクレイピング結果集計 ({datetime.now(timezone(timedelta(hours=9))).strftime('%Y/%m/%d %H:%M')})**\n\n"
        for v, s, e in results:
            msg += f"- {v}: {s}" + (f" (内容: {e})" if e else "") + "\n"
        msg += f"\n📹 YouTube取得数: {youtube_fetch_count}件 / 上限{DAILY_FETCH_LIMIT}件"
        send_discord_notification(msg)

def run_all_scrapers():
    asyncio.run(async_run_all_scrapers())

if __name__ == "__main__":
    run_all_scrapers()
