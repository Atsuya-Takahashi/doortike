import os
import sys
from datetime import date

# Add backend to sys.path to import models
sys.path.append(os.path.join(os.getcwd(), 'backend'))

try:
    from models import engine, Event, LiveHouse
    from sqlalchemy.orm import sessionmaker
except ImportError:
    print("Error: Could not import models. Please make sure you are in the project root.")
    sys.exit(1)

def show_latest_events(limit=10):
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        # Fetch upcoming events from today onwards
        today = date.today()
        events = session.query(Event, LiveHouse)\
            .join(LiveHouse)\
            .filter(Event.date >= today)\
            .order_by(Event.date.asc())\
            .limit(limit)\
            .all()
            
        print(f"\n--- Upcoming {len(events)} Events (from {today}) ---")
        if not events:
            print("No upcoming events found.")
            return

        for e, lh in events:
            print(f"[{e.date}] {e.title}")
            print(f"    Venue: {lh.name} ({lh.area})")
            if e.performers:
                print(f"    Performers: {e.performers}")
            print("-" * 30)
            
    except Exception as e:
        print(f"Error checking database: {e}")
    finally:
        session.close()

if __name__ == "__main__":
    show_latest_events()
