from models import SessionLocal, LiveHouse, Event
from datetime import datetime, timedelta

db = SessionLocal()
today = datetime.now()
tomorrow = today + timedelta(days=1)

dummy_venues = [
    {"name": "下北沢SHELTER", "area": "下北沢", "prefecture": "東京", "latitude": 35.6616, "longitude": 139.6670},
    {"name": "新宿LOFT", "area": "新宿", "prefecture": "東京", "latitude": 35.6951, "longitude": 139.7018},
    {"name": "渋谷CLUB QUATTRO", "area": "渋谷", "prefecture": "東京", "latitude": 35.6611, "longitude": 139.6997},
    {"name": "吉祥寺CLUB SEATA", "area": "吉祥寺", "prefecture": "東京", "latitude": 35.7032, "longitude": 139.5795},
    {"name": "秋葉原CLUB GOODMAN", "area": "秋葉原", "prefecture": "東京", "latitude": 35.6983, "longitude": 139.7731},
    {"name": "池袋手刀", "area": "池袋", "prefecture": "東京", "latitude": 35.7335, "longitude": 139.7153},
    {"name": "高円寺HIGH", "area": "高円寺", "prefecture": "東京", "latitude": 35.7042, "longitude": 139.6496},
    {"name": "名古屋CLUB QUATTRO", "area": "名古屋", "prefecture": "愛知", "latitude": 35.1601, "longitude": 136.9070},
    {"name": "梅田Zeela", "area": "梅田", "prefecture": "大阪", "latitude": 34.7040, "longitude": 135.5020},
]

for v in dummy_venues:
    lh = db.query(LiveHouse).filter(LiveHouse.name == v["name"]).first()
    if not lh:
        lh = LiveHouse(
            name=v["name"], 
            area=v["area"], 
            prefecture=v["prefecture"],
            latitude=v["latitude"],
            longitude=v["longitude"],
            url="https://example.com"
        )
        db.add(lh)
        db.commit()
        
        # Add dummy events for today and tomorrow
        for d in [today.date(), tomorrow.date()]:
            db.add(Event(
                livehouse_id=lh.id, 
                date=d, 
                title=f"{v['name']} SPECIAL LIVE", 
                performers="Dummy Band", 
                open_time="18:00", 
                start_time="18:30", 
                price_info="¥3000",
                ticket_url="https://eplus.jp/" if v["name"] == "下北沢SHELTER" else None,
                blog_url="https://example.com/blog/shinjuku-loft-report" if v["name"] == "新宿LOFT" else None,
                coupon_url="https://example.com/coupon/123" if v["name"] == "新宿LOFT" else None
            ))
        db.commit()

print("Dummy areas and events added successfully!")
db.close()
