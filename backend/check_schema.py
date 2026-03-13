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
        res = conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name = 'events'"))
        columns = [r[0] for r in res]
        print(f"Columns in 'events': {columns}")
        
        res = conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name = 'artists'"))
        columns_artists = [r[0] for r in res]
        print(f"Columns in 'artists': {columns_artists}")
except Exception as e:
    print(f"Error: {e}")
