import asyncio
from datetime import datetime, timedelta
from playwright.async_api import async_playwright
from models import SessionLocal, LiveHouse, Event, Artist
from youtube_service import search_artist_video
import re

# 1回のスクレイパー実行で呼べるYouTube APIの上限（100ユニット×90=9,000ユニット/日）
DAILY_FETCH_LIMIT = 90


def fetch_youtube_for_new_artists(db_session, performers_str: str, youtube_fetch_count: int) -> int:
    """
    performers文字列を分割し、未キャッシュのアーティストにYouTube APIを呼ぶ。
    youtube_fetch_count: 今回の実行で既に消費したAPI呼び出し数
    返り値: 更新後のyoutube_fetch_count
    """
    if not performers_str or youtube_fetch_count >= DAILY_FETCH_LIMIT:
        return youtube_fetch_count

    artists = [a.strip() for a in re.split(r'[、,／/]', performers_str) if a.strip()]

    for artist_name in artists:
        if youtube_fetch_count >= DAILY_FETCH_LIMIT:
            print(f"[YouTube] 本日の取得上限({DAILY_FETCH_LIMIT}件)に達しました。残りは次回実行時に取得されます。")
            break

        artist = db_session.query(Artist).filter(Artist.name == artist_name).first()

        # 既にキャッシュあり（動画ありなし問わず、30日以内）はスキップ
        if artist and artist.youtube_updated_at:
            if (datetime.now() - artist.youtube_updated_at) < timedelta(days=30):
                continue

        # YouTube API で検索
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

        status = f"動画あり: {video_id}" if video_id else "動画なし"
        print(f"[YouTube] {artist_name} → {status} (本日{youtube_fetch_count}件目)")

    db_session.commit()
    return youtube_fetch_count


async def scrape_shinjuku_loft(page, date: datetime, db_session, youtube_fetch_count: int) -> int:
    # url format example: https://www.loft-prj.co.jp/schedule/loft/date/2026/03/04
    year = date.year
    month = f"{date.month:02d}"
    day = f"{date.day:02d}"
    url = f"https://www.loft-prj.co.jp/schedule/loft/date/{year}/{month}/{day}"
    print(f"Scraping {url}")
    
    await page.goto(url)
    await page.wait_for_load_state("networkidle")
    
    livehouse = db_session.query(LiveHouse).filter(LiveHouse.name == "新宿LOFT").first()
    if not livehouse:
        livehouse = LiveHouse(name="新宿LOFT", area="新宿", latitude=35.6953, longitude=139.7011, url="https://www.loft-prj.co.jp/loft/")
        db_session.add(livehouse)
        db_session.commit()
    
    events = await page.query_selector_all('.schedule-box')
    for evt in events:
        title_elem = await evt.query_selector('.title')
        if title_elem:
            title = await title_elem.inner_text()
            title = title.strip()
            
            performers_elem = await evt.query_selector('.act')
            performers = await performers_elem.inner_text() if performers_elem else ""
            
            time_elem = await evt.query_selector('.time')
            time_text = await time_elem.inner_text() if time_elem else ""
            open_time, start_time = "", ""
            if "OPEN" in time_text and "START" in time_text:
                parts = time_text.split("/")
                for p in parts:
                    if "OPEN" in p: open_time = p.replace("OPEN", "").strip()
                    if "START" in p: start_time = p.replace("START", "").strip()
            
            price_elem = await evt.query_selector('.adv-door')
            price_text = await price_elem.inner_text() if price_elem else ""
            
            ticket_url = None
            ticket_links = await evt.query_selector_all('a')
            for link in ticket_links:
                href = await link.get_attribute('href')
                if href:
                    text = await link.inner_text()
                    if any(domain in href for domain in ['eplus.jp', 't.pia.jp', 'l-tike.com', 'tiget.net', 't.livepocket.jp']) or any(kw in text for kw in ['チケット', '予約', '購入', 'e+', 'イープラス', 'ぴあ', 'ローソン', 'TIGET']):
                        ticket_url = href
                        break

            existing_event = db_session.query(Event).filter(
                Event.livehouse_id == livehouse.id, Event.date == date.date(), Event.title == title
            ).first()
            
            if not existing_event:
                new_event = Event(
                    livehouse_id=livehouse.id,
                    date=date.date(),
                    title=title,
                    performers=performers.strip(),
                    open_time=open_time,
                    start_time=start_time,
                    price_info=price_text.strip(),
                    ticket_url=ticket_url
                )
                db_session.add(new_event)
                db_session.commit()
                print(f"Added new event: {title}")

            # 新規・既存問わず、未キャッシュアーティストの動画を取得
            youtube_fetch_count = fetch_youtube_for_new_artists(
                db_session, performers.strip(), youtube_fetch_count
            )

    return youtube_fetch_count


async def async_run_all_scrapers():
    db = SessionLocal()
    today = datetime.now()
    tomorrow = today + timedelta(days=1)
    
    dates_to_scrape = [today, tomorrow]
    youtube_fetch_count = 0  # 本日のAPI呼び出しカウンター
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        for date in dates_to_scrape:
            shibuya_quattro = db.query(LiveHouse).filter(LiveHouse.name == "渋谷CLUB QUATTRO").first()
            if not shibuya_quattro:
                shibuya_quattro = LiveHouse(name="渋谷CLUB QUATTRO", area="渋谷", latitude=35.6611, longitude=139.6982, url="https://www.club-quattro.com/")
                db.add(shibuya_quattro)
                db.commit()

            try:
                youtube_fetch_count = await scrape_shinjuku_loft(page, date, db, youtube_fetch_count)
            except Exception as e:
                print(f"Error scraping Shinjuku LOFT on {date}: {e}")
            
            if db.query(Event).filter(Event.date == date.date()).count() == 0:
                print(f"Inserting fallback mock events for {date.date()}")
                dummy_events = [
                    Event(livehouse_id=1, date=date.date(), title="ROCK N ROLL NIGHT", performers="THE BAND, GUESTS", open_time="18:30", start_time="19:00", price_info="ADV ¥3,000 / DOOR ¥3,500"),
                    Event(livehouse_id=shibuya_quattro.id, date=date.date(), title="SHIBUYA INDIE FEST", performers="Indie Star, New Comer, Next Break", open_time="17:00", start_time="17:30", price_info="ADV ¥4,000 / DOOR ¥4,500")
                ]
                db.add_all(dummy_events)
                db.commit()
                
        await browser.close()

    print(f"\n[完了] 本日のYouTube取得数: {youtube_fetch_count}件 / 上限{DAILY_FETCH_LIMIT}件")
    db.close()

def run_all_scrapers():
    """Wrapper to run the async scraper synchronously."""
    asyncio.run(async_run_all_scrapers())

if __name__ == "__main__":
    run_all_scrapers()

