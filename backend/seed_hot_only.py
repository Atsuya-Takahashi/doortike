from models import SessionLocal, LiveHouse, Event
from datetime import datetime, date
import sys
import os

# Add parent directory to path to import models
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def seed_hot_only():
    db = SessionLocal()
    try:
        # Today is 2026-03-17
        target_date = date(2026, 3, 17)
        lh = db.query(LiveHouse).filter(LiveHouse.name == "下北沢SHELTER").first()
        if not lh:
            print("Livehouse '下北沢SHELTER' not found")
            return

        # HOT only (no pickup)
        event = Event(
            livehouse_id=lh.id,
            date=target_date,
            title="TEST: HOT ONLY (DE-PRIORITIZED)",
            performers="Just a Popular Band",
            open_time="18:30",
            start_time="19:00",
            price_info="前売 ¥2,000",
            is_pr=False,
            is_pickup=False,
            bookmark_count=15,
            image_url="https://images.unsplash.com/photo-1514525253344-f814d074e015?w=800&auto=format&fit=crop"
        )
        db.add(event)
        db.commit()
        print(f"Successfully added HOT-only dummy event: {event.title}")
    except Exception as e:
        print(f"Error: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    seed_hot_only()
