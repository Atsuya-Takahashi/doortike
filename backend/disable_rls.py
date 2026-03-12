import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

def main():
    try:
        load_dotenv()
        db_url = os.environ.get('DATABASE_URL')
        if db_url.startswith("postgres://"):
            db_url = db_url.replace("postgres://", "postgresql://", 1)
        if "?pgbouncer=" in db_url:
            db_url = db_url.split("?")[0]
            
        print("Disabling RLS...")
        engine = create_engine(db_url)
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE events DISABLE ROW LEVEL SECURITY;"))
            conn.execute(text("ALTER TABLE livehouses DISABLE ROW LEVEL SECURITY;"))
            conn.execute(text("ALTER TABLE artists DISABLE ROW LEVEL SECURITY;"))
            conn.commit()
            print("Successfully disabled RLS!")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
