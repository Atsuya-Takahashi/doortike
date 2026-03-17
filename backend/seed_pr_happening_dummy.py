from models import SessionLocal, LiveHouse, Event
from datetime import datetime, date
import sys
import os

# Add parent directory to path to import models
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def seed_pr_happening_fix():
    db = SessionLocal()
    try:
        # Today is 2026-03-17
        target_date = date(2026, 3, 17)
        lh = db.query(LiveHouse).filter(LiveHouse.name == "下北沢MOSAiC").first()
        if not lh:
            print("Livehouse '下北沢MOSAiC' not found")
            return

        # Start time at 00:05 (today). Current time is ~00:11.
        # This is within the 3-hour window.
        event = Event(
            livehouse_id=lh.id,
            date=target_date,
            title="PR TEST: GOLD + GLOW (00:05 START)",
            performers="Luxury Glow Band / Golden Pulse Project",
            open_time="23:30", # yesterday but technically listed under 3/17 if we want it today
            start_time="00:05",
            price_info="前売 ¥4,000 / 当日 ¥4,500 (+1D)",
            is_pr=True,
            pr_type="tokyo",
            is_pickup=True,
            bookmark_count=0,
            image_url="https://images.unsplash.com/photo-1470225620780-dba8ba36b745?w=800&auto=format&fit=crop"
        )
        db.add(event)
        db.commit()
        print(f"Successfully added happening PR dummy event: {event.title}")
    except Exception as e:
        print(f"Error: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    seed_pr_happening_fix()
