from sqlalchemy import Column, Integer, String, Float, Boolean, Date, DateTime, ForeignKey, create_engine, JSON, text
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
import os
from dotenv import load_dotenv

load_dotenv()

Base = declarative_base()

class Artist(Base):
    __tablename__ = 'artists'
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
    youtube_video_id = Column(String, nullable=True)
    youtube_updated_at = Column(DateTime, nullable=True)
    is_reported = Column(Boolean, default=False)
    reported_video_ids = Column(String, nullable=True)  # カンマ区切りで報告済み動画IDを蓄積


class LiveHouse(Base):
    __tablename__ = 'livehouses'
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
    prefecture = Column(String, index=True, nullable=False, default="東京")
    area = Column(String, index=True, nullable=False)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    url = Column(String, nullable=True)
    has_discount = Column(Boolean, default=False)
    drink_fee = Column(Integer, nullable=True)
    blog_url = Column(String, nullable=True)
    
    events = relationship("Event", back_populates="livehouse")

class Event(Base):
    __tablename__ = 'events'
    
    id = Column(Integer, primary_key=True, index=True)
    livehouse_id = Column(Integer, ForeignKey('livehouses.id'), nullable=False)
    date = Column(Date, index=True, nullable=False)
    title = Column(String, nullable=False)
    performers = Column(String, nullable=True)
    open_time = Column(String, nullable=True)
    start_time = Column(String, nullable=True)
    price_info = Column(String, nullable=True)
    ticket_url = Column(String, nullable=True)
    blog_url = Column(String, nullable=True)
    coupon_url = Column(String, nullable=True)
    is_pr = Column(Boolean, default=False)
    pr_type = Column(String, nullable=True)  # 'featured' or 'fan_support'
    is_pickup = Column(Boolean, default=False)
    pickup_type = Column(String, nullable=True)  # 'staff', 'hot', etc.
    is_midnight = Column(Boolean, default=False)
    artists_data = Column(JSON, nullable=True)  # Store list of performers with their youtube_id: [{"name": "...", "youtube_id": "..."}]
    image_url = Column(String, nullable=True)
    bookmark_count = Column(Integer, default=0, nullable=False)
    
    livehouse = relationship("LiveHouse", back_populates="events")
    reports = relationship("VideoReport", back_populates="event")

class VideoReport(Base):
    __tablename__ = 'video_reports'
    
    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(Integer, ForeignKey('events.id'), nullable=False)
    artist_name = Column(String, nullable=False)
    status = Column(String, default='pending') # 'pending', 'resolved', 'ignored'
    report_count = Column(Integer, default=1) # number of times reported for this (event_id, artist_name)
    created_at = Column(DateTime, server_default=text("now()"))
    
    event = relationship("Event", back_populates="reports")

# Database setup
DATABASE_URL = os.getenv("DATABASE_URL")

if DATABASE_URL:
    # Use PostgreSQL (Supabase)
    SQLALCHEMY_DATABASE_URL = DATABASE_URL
    # Ensure correct dialect prefix if it's 'postgres://' (SQLAlchemy 1.4+ expects 'postgresql://')
    if SQLALCHEMY_DATABASE_URL.startswith("postgres://"):
        SQLALCHEMY_DATABASE_URL = SQLALCHEMY_DATABASE_URL.replace("postgres://", "postgresql://", 1)
    
    if "?pgbouncer=" in SQLALCHEMY_DATABASE_URL:
        SQLALCHEMY_DATABASE_URL = SQLALCHEMY_DATABASE_URL.split("?")[0]
    
    # pool_pre_ping ensures the connection hasn't been dropped
    engine = create_engine(SQLALCHEMY_DATABASE_URL, pool_pre_ping=True)
else:
    # Fallback to local SQLite
    SQLALCHEMY_DATABASE_URL = "sqlite:///./live_events.db"
    engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    Base.metadata.create_all(bind=engine)
    
if __name__ == "__main__":
    init_db()
    print("Database initialized.")
