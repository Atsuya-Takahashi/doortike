import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# Load .env from backend directory
load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

db_url = os.getenv('DATABASE_URL')
if not db_url:
    print("Error: DATABASE_URL not found in environment")
    exit(1)

# Clean pgbouncer suffix if present (models.py logic)
if "?pgbouncer=" in db_url:
    db_url = db_url.split("?")[0]

# SQLAlchemy requires postgresql:// instead of postgres://
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

engine = create_engine(db_url)

with engine.connect() as conn:
    try:
        conn.execute(text('ALTER TABLE events ADD COLUMN IF NOT EXISTS image_url TEXT;'))
        conn.commit()
        print("Successfully added image_url column to events table.")
    except Exception as e:
        print(f"Error adding column: {e}")
