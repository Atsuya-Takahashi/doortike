import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()
db_url = os.getenv("DATABASE_URL")
if not db_url:
    print("DATABASE_URL not found!")
    exit(1)

if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

if "?pgbouncer=" in db_url:
    db_url = db_url.split("?")[0]

engine = create_engine(db_url)
try:
    with engine.connect() as conn:
        print("Adding 'artists_data' column to 'events' table...")
        conn.execute(text("ALTER TABLE events ADD COLUMN IF NOT EXISTS artists_data JSONB;"))
        conn.commit()
        print("Successfully added 'artists_data' column!")
        
        # Also need to grant permissions again just in case
        conn.execute(text("GRANT SELECT ON ALL TABLES IN SCHEMA public TO anon;"))
        conn.execute(text("GRANT SELECT ON ALL TABLES IN SCHEMA public TO authenticated;"))
        conn.execute(text("NOTIFY pgrst, 'reload schema';"))
        conn.commit()
        print("Permissions granted and schema reloaded.")
except Exception as e:
    print(f"Error during migration: {e}")
