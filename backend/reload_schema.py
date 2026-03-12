import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

def main():
    try:
        load_dotenv()
        db_url = os.environ.get('DATABASE_URL')
        if not db_url:
            print("DATABASE_URL not found!")
            return
            
        if db_url.startswith("postgres://"):
            db_url = db_url.replace("postgres://", "postgresql://", 1)
            
        if "?pgbouncer=" in db_url:
            db_url = db_url.split("?")[0]
            
        print("Reloading Supabase schema cache & permissions...")
        engine = create_engine(db_url)
        with engine.connect() as conn:
            conn.execute(text("GRANT SELECT ON ALL TABLES IN SCHEMA public TO anon;"))
            conn.execute(text("GRANT SELECT ON ALL TABLES IN SCHEMA public TO authenticated;"))
            conn.execute(text("NOTIFY pgrst, 'reload schema';"))
            conn.commit()
            print("Successfully granted permissions and reloaded schema!")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
