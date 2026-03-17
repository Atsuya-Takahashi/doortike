from models import SessionLocal, LiveHouse, Event
from datetime import datetime, date
import sys
import os

# Add parent directory to path to import models
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def seed_staff_pick():
    db = SessionLocal()
    try:
        # Today is 2026-03-17
        target_date = date(2026, 3, 17)
        lh = db.query(LiveHouse).filter(LiveHouse.name == "下北沢MOSAiC").first()
        if not lh:
            print("Livehouse '下北沢MOSAiC' not found")
            return

        # STAFF PICK only (no PR, no HOT)
        event = event = Event(
            livehouse_id=lh.id,
            date=target_date,
            title="TEST: STAFF PICK (PRIORITY 2)",
            performers="Curated Artist",
            open_time="19:00",
            start_time="19:30",
            price_info="前売 ¥2,500",
            is_pr=False,
            is_pickup=True,
            bookmark_count=1, # Low count, not HOT
            image_url="https://images.unsplash.com/photo-1493225255756-d9584f8606e9?w=800&auto=format&fit=crop"
        )
        db.add(event)
        db.commit()
        print(f"Successfully added STAFF PICK dummy event: {event.title}")
    except Exception as e:
        print(f"Error: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    seed_staff_pick()
