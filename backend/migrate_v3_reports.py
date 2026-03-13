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
        print("Creating 'video_reports' table...")
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS video_reports (
                id SERIAL PRIMARY KEY,
                event_id INTEGER REFERENCES events(id) ON DELETE CASCADE,
                artist_name TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMPTZ DEFAULT NOW()
            );
        """))
        conn.commit()
        print("Successfully created 'video_reports' table!")
        
        # Grant permissions
        conn.execute(text("GRANT ALL ON video_reports TO anon;"))
        conn.execute(text("GRANT ALL ON video_reports TO authenticated;"))
        
        # RLS Policies
        conn.execute(text("ALTER TABLE video_reports ENABLE ROW LEVEL SECURITY;"))
        conn.execute(text("""
            DO $$ 
            BEGIN 
                IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'video_reports' AND policyname = 'Allow anonymous insert') THEN 
                    CREATE POLICY "Allow anonymous insert" ON video_reports FOR INSERT TO anon WITH CHECK (true); 
                END IF; 
                IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'video_reports' AND policyname = 'Allow authenticated select') THEN 
                    CREATE POLICY "Allow authenticated select" ON video_reports FOR SELECT TO authenticated USING (true); 
                END IF;
            END $$;
        """))
        
        conn.execute(text("NOTIFY pgrst, 'reload schema';"))
        conn.commit()
        print("Permissions and RLS policies granted, schema reloaded.")
except Exception as e:
    print(f"Error creating table: {e}")
