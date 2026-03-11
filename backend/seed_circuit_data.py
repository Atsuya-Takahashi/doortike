from models import SessionLocal, LiveHouse, Event
from datetime import datetime, timedelta

db = SessionLocal()
today = datetime.now().date()

# 1. Add LiveHouses for Otsuka
otsuka_venues = [
    {"name": "大塚Hearts +", "area": "大塚", "prefecture": "東京", "latitude": 35.7318, "longitude": 139.7291},
    {"name": "大塚Hearts Next", "area": "大塚", "prefecture": "東京", "latitude": 35.7315, "longitude": 139.7295},
]

venue_ids = []
for v in otsuka_venues:
    lh = db.query(LiveHouse).filter(LiveHouse.name == v["name"]).first()
    if not lh:
        lh = LiveHouse(
            name=v["name"], 
            area=v["area"], 
            prefecture=v["prefecture"],
            latitude=v["latitude"],
            longitude=v["longitude"],
            url="http://hearts-plus.com/"
        )
        db.add(lh)
        db.commit()
    venue_ids.append(lh.id)

# 2. Add Circuit Event (Same ticket URL, same date)
circuit_ticket_url = "https://eplus.jp/otsuka-circuit-2026/"
circuit_title = "大塚サーキットフェス 2026"

# Check if events already exist to avoid duplicates
existing = db.query(Event).filter(Event.ticket_url == circuit_ticket_url, Event.date == today).all()
if not existing:
    for vid in venue_ids:
        db.add(Event(
            livehouse_id=vid,
            date=today,
            title=circuit_title,
            performers="大塚オールスターズ, サーキット・ランナーズ",
            open_time="11:30",
            start_time="12:00",
            price_info="前売 ¥4,000 (+1D)",
            ticket_url=circuit_ticket_url,
            is_pickup=True
        ))
    db.commit()
    print(f"Added circuit events for {today}")
else:
    print("Circuit events already exist.")

db.close()
