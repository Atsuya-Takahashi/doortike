import os
import sys
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

# Add backend to sys.path
sys.path.append(os.path.join(os.getcwd(), 'backend'))
from models import SessionLocal

load_dotenv('backend/.env')

def migrate():
    engine = SessionLocal().get_bind()
    with engine.connect() as conn:
        print("1. Adding report_count column if it doesn't exist...")
        try:
            conn.execute(text("ALTER TABLE video_reports ADD COLUMN report_count INTEGER DEFAULT 1"))
            conn.commit()
            print("Column added.")
        except Exception as e:
            print(f"Column might already exist: {e}")
            conn.rollback()

        print("2. Merging existing duplicate reports...")
        # Find duplicates (same event_id, artist_name, status='pending')
        # We'll sum their counts (assuming 1 for old rows) and keep the oldest created_at
        merge_query = text("""
            WITH duplicates AS (
                SELECT event_id, artist_name, status, MIN(id) as keep_id, COUNT(*) as actual_count
                FROM video_reports
                WHERE status = 'pending'
                GROUP BY event_id, artist_name, status
                HAVING COUNT(*) > 1
            )
            UPDATE video_reports v
            SET report_count = d.actual_count
            FROM duplicates d
            WHERE v.id = d.keep_id;
        """)
        
        delete_query = text("""
            WITH duplicates AS (
                SELECT event_id, artist_name, status, MIN(id) as keep_id
                FROM video_reports
                WHERE status = 'pending'
                GROUP BY event_id, artist_name, status
                HAVING COUNT(*) > 1
            )
            DELETE FROM video_reports
            WHERE status = 'pending'
            AND id NOT IN (SELECT keep_id FROM duplicates)
            AND (event_id, artist_name) IN (SELECT event_id, artist_name FROM duplicates);
        """)
        
        try:
            conn.execute(merge_query)
            conn.execute(delete_query)
            conn.commit()
            print("Duplicates merged.")
        except Exception as e:
            print(f"Error merging duplicates: {e}")
            conn.rollback()

        print("3. Creating partial unique index for duplicate prevention...")
        try:
            conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS idx_video_reports_unique_pending ON video_reports (event_id, artist_name) WHERE status = 'pending'"))
            conn.commit()
            print("Index created.")
        except Exception as e:
            print(f"Index creation error: {e}")
            conn.rollback()

        print("4. Creating RPC function 'report_video'...")
        rpc_function = """
CREATE OR REPLACE FUNCTION report_video(p_event_id INT, p_artist_name TEXT)
RETURNS VOID AS $$
BEGIN
    INSERT INTO video_reports (event_id, artist_name, status, report_count, created_at)
    VALUES (p_event_id, p_artist_name, 'pending', 1, NOW())
    ON CONFLICT (event_id, artist_name) WHERE status = 'pending'
    DO UPDATE SET report_count = video_reports.report_count + 1;
END;
$$ LANGUAGE plpgsql;
"""
        try:
            conn.execute(text(rpc_function))
            conn.commit()
            print("RPC function created.")
        except Exception as e:
            print(f"RPC function creation error: {e}")
            conn.rollback()

if __name__ == "__main__":
    migrate()
