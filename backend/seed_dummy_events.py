from models import SessionLocal, LiveHouse, Event
from datetime import datetime, timedelta

def seed_events():
    db = SessionLocal()
    try:
        # Clear old events to avoid confusion
        db.query(Event).delete()
        
        # Use simple calendar today for dummy data
        today = datetime.now().date()
            
        tomorrow = today + timedelta(days=1)
        yesterday = today - timedelta(days=1)
        
        livehouses = db.query(LiveHouse).all()
        if not livehouses:
            print("No livehouses found in DB. Please run add_dummy_areas.py first.")
            return

        # Helper to get ID by name
        def get_lh_id(name):
            lh = db.query(LiveHouse).filter(LiveHouse.name == name).first()
            return lh.id if lh else None

        # Ensure livehouses have drink fees for testing
        hubs = ["下北沢SHELTER", "新宿LOFT", "渋谷CLUB QUATTRO"]
        for name in hubs:
            lh = db.query(LiveHouse).filter(LiveHouse.name == name).first()
            if lh:
                lh.drink_fee = 600

        dummy_events = [
            # --- Today's Events ---
            {
                "livehouse_id": get_lh_id("下北沢SHELTER"),
                "date": today,
                "title": "FEATURED: ROCK GENERATION",
                "performers": "Amairo-Flip/BLUE REGRET。/Cheriecla/Claire♡Dolls/Ep!codE/Fancy Film*/FIRST DREAM/INOiZe↯/Lovlis/MISS MY NOTES/Poppin' Parade/pureran story/Red Radiance/Tiara Palette/アイドルキャリア/あまいものつめあわせ/イイトコドリ/オトメルキュール/きみパレ/しろくまいんど/なないろパンダちゃん。/ぺりきゅらむ/ミリフェア/ゆえない/ゆるっと革命団/らびゅあたっく。/ラプラス/愛♡きゃっち/甘いものには毒がある。/白地図プロローグ/無名上京アイドル",
                "open_time": "18:00", "start_time": "18:30",
                "price_info": "前売 ¥3,000 / 当日 ¥3,500 (+1D)",
                "is_pr": True, "pr_type": "featured"
            },
            {
                "livehouse_id": get_lh_id("渋谷CLUB QUATTRO"),
                "date": today,
                "title": "SHIBUYA SONIC BLOOM",
                "performers": "Sonic Bloom, Flower Beats",
                "open_time": "18:30", "start_time": "19:00",
                "price_info": "前売 ¥3,500 (+1D)",
                "is_pr": False
            },
            {
                "livehouse_id": get_lh_id("新宿LOFT"),
                "date": today,
                "title": "SHINJUKU PUNK RIOT",
                "performers": "The Rioters, Punk Spirits",
                "open_time": "19:00", "start_time": "19:30",
                "price_info": "前売 ¥2,800 / 当日 ¥3,300",
                "is_pr": False
            },
            {
                "livehouse_id": get_lh_id("吉祥寺CLUB SEATA"),
                "date": today,
                "title": "KICHIJOJI INDIE NIGHT",
                "performers": "Indie Stars, Guitar Heroes",
                "open_time": "18:00", "start_time": "18:45",
                "price_info": "予約 ¥3,000",
                "is_pickup": True
            },
            # --- Tomorrow's Events ---
            {
                "livehouse_id": get_lh_id("下北沢SHELTER"),
                "date": tomorrow,
                "title": "SHELTER LOUNGE: TECHNO SESSIONS",
                "performers": "DJ TECH, BEAT MAKER, SYNTH MASTER",
                "open_time": "22:00",
                "start_time": "22:30",
                "price_info": "当日のみ ¥2,000 (1D込)",
                "ticket_url": ""
            },
            {
                "livehouse_id": get_lh_id("高円寺HIGH"),
                "date": tomorrow,
                "title": "KOENJI SHOEGAZER FEST",
                "performers": "DREAMY SOUNDS, NOISE CLOUD",
                "open_time": "17:00",
                "start_time": "17:30",
                "price_info": "前売 ¥3,000 (+1D ¥600)"
            }
        ]
        
        # Filter out cases where livehouse_id is None
        dummy_events = [e for e in dummy_events if e.get("livehouse_id") is not None]

        # --- Midnight Keywords etc remains same ---
        midnight_keywords = ["オールナイト", "ALL NIGHT", "ALLNIGHT", "MIDNIGHT", "深夜"]

        for ev_data in dummy_events:
            # Auto-detect midnight events
            is_midnight = False
            open_time = ev_data.get("open_time", "")
            if open_time:
                try:
                    hour = int(open_time.split(':')[0])
                    if hour >= 21:
                        is_midnight = True
                except:
                    pass
            
            title = ev_data.get("title", "")
            if not is_midnight:
                if any(kw in title.upper() for kw in midnight_keywords):
                    is_midnight = True
            
            ev_data["is_midnight"] = is_midnight
            event = Event(**ev_data)
            db.add(event)
        
        db.commit()
        print(f"Successfully seeded {len(dummy_events)} events for {yesterday}, {today} and {tomorrow}.")
    
    except Exception as e:
        print(f"Error seeding events: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    seed_events()
