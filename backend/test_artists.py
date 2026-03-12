import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()
db_url = os.environ.get('DATABASE_URL')
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)
if "?pgbouncer=" in db_url:
    db_url = db_url.split("?")[0]

engine = create_engine(db_url)
with engine.connect() as conn:
    result = conn.execute(text("SELECT count(*) FROM artists"))
    count = result.scalar()
    print("Artists count:", count)
    
    result = conn.execute(text("SELECT name, youtube_video_id, youtube_updated_at FROM artists ORDER BY youtube_updated_at DESC LIMIT 5"))
    rows = result.fetchall()
    print("Latest Artists:", rows)
