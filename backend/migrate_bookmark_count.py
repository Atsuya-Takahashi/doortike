import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

if "?pgbouncer=" in DATABASE_URL:
    DATABASE_URL = DATABASE_URL.split("?")[0]

def migrate():
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    
    try:
        # Add bookmark_count column with default 0
        print("Adding bookmark_count column to events table...")
        cur.execute("ALTER TABLE events ADD COLUMN IF NOT EXISTS bookmark_count INTEGER DEFAULT 0 NOT NULL;")
        conn.commit()
        print("Migration successful: bookmark_count column added.")
    except Exception as e:
        print(f"Migration failed: {e}")
        conn.rollback()
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    migrate()
