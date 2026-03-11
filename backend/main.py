from fastapi import FastAPI, Depends, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import date
from models import SessionLocal, LiveHouse, Event, Artist
from youtube_service import search_artist_video
from dotenv import load_dotenv
import os
load_dotenv()


app = FastAPI(title="Livehouse Events API")

# Setup CORS to allow requests from the Vercel frontend (and localhost for testing)
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")
origins = [
    "http://localhost:5173",  # Local React dev server
    FRONTEND_URL,             # Production frontend URL
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health_check():
    """Endpoint for Render to verify the app is running."""
    return {"status": "ok"}

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/api/areas")
def get_areas(db: Session = Depends(get_db)):
    # Return sub-areas (frontend handles "All" automatically)
    return {
        "東京": ["渋谷", "新宿", "下北沢"]
    }

@app.get("/api/events")
def get_events(
    target_date: date = Query(..., description="Target date (e.g. 2026-03-04)"),
    end_date: Optional[date] = Query(None, description="End date for range (optional)"),
    prefecture: Optional[str] = Query(None, description="Filter by prefecture"),
    area: Optional[str] = Query(None, description="Filter by area"),
    db: Session = Depends(get_db)
):
    if end_date:
        query = db.query(Event).join(LiveHouse).filter(Event.date >= target_date, Event.date <= end_date)
    else:
        query = db.query(Event).join(LiveHouse).filter(Event.date == target_date)
    # Get the main list of events filtered by prefecture/area
    filtered_query = query
    if prefecture:
        filtered_query = filtered_query.filter(LiveHouse.prefecture == prefecture)
    if area:
        filtered_query = filtered_query.filter(LiveHouse.area == area)
    
    events = filtered_query.all()

    # Always include ALL PR events for the selected prefecture if we are filtering by a specific area
    # This ensures "Tokyo PR" shows up even when "Shibuya" is selected.
    if area and prefecture:
        pr_events = query.filter(
            Event.is_pr == True,
            LiveHouse.prefecture == prefecture
        ).all()
        
        # Merge and avoid duplicates
        existing_ids = {e.id for e in events}
        for pr_ev in pr_events:
            if pr_ev.id not in existing_ids:
                events.append(pr_ev)
    
    result = []
    for evt in events:
        # performers文字列を分割してアーティストごとのhas_videoフラグを生成
        performers_info = []
        if evt.performers:
            import re
            artist_names = [a.strip() for a in re.split(r'[、,／/]', evt.performers) if a.strip()]
            for aname in artist_names:
                artist_row = db.query(Artist).filter(Artist.name == aname).first()
                has_video = bool(
                    artist_row and
                    artist_row.youtube_video_id and
                    not artist_row.is_reported
                )
                performers_info.append({"name": aname, "has_video": has_video})

        result.append({
            "id": evt.id,
            "title": evt.title,
            "performers": evt.performers,
            "performers_info": performers_info,
            "date": str(evt.date),
            "open_time": evt.open_time,
            "start_time": evt.start_time,
            "price_info": evt.price_info,
            "ticket_url": evt.ticket_url,
            "blog_url": evt.blog_url,
            "coupon_url": evt.coupon_url,
            "is_pr": evt.is_pr,
            "pr_type": evt.pr_type,
            "is_pickup": evt.is_pickup,
            "is_midnight": evt.is_midnight,
            "livehouse": {
                "id": evt.livehouse.id,
                "name": evt.livehouse.name,
                "area": evt.livehouse.area,
                "prefecture": evt.livehouse.prefecture,
                "latitude": evt.livehouse.latitude,
                "longitude": evt.livehouse.longitude,
                "url": evt.livehouse.url,
                "drink_fee": getattr(evt.livehouse, 'drink_fee', None)
            }
        })
    return result

@app.get("/api/nearest_area")
def get_nearest_area(
    lat: float = Query(..., description="User latitude"),
    lon: float = Query(..., description="User longitude"),
    db: Session = Depends(get_db)
):
    # Representative coordinates (Station Centers)
    hubs = [
        {"name": "渋谷", "lat": 35.6580, "lon": 139.7016},
        {"name": "新宿", "lat": 35.6896, "lon": 139.7005},
        {"name": "下北沢", "lat": 35.6616, "lon": 139.6670},
    ]
    
    import math
    def get_distance(lat1, lon1, lat2, lon2):
        # Rough distance calculation
        return math.sqrt((lat1 - lat2)**2 + (lon1 - lon2)**2)

    closest = None
    min_dist = float('inf')
    
    for hub in hubs:
        dist = get_distance(lat, lon, hub["lat"], hub["lon"])
        if dist < min_dist:
            min_dist = dist
            closest = hub
            
    # If more than approx 10km (0.09 degrees) from any hub, return "All"
    if closest and min_dist < 0.09:
        return {"prefecture": "東京", "area": closest["name"]}
    
    return {"prefecture": "東京", "area": "All"}

@app.get("/api/artist_video")
def get_artist_video(
    name: str = Query(..., description="Artist name"),
    db: Session = Depends(get_db)
):
    """
    アーティスト名からYouTube動画IDを返す。
    DBキャッシュのみを参照し、YouTube APIは呼ばない（スクレイパーが事前取得）。
    """
    artist = db.query(Artist).filter(Artist.name == name).first()
    if artist and not artist.is_reported:
        return {"video_id": artist.youtube_video_id}
    return {"video_id": None}


@app.post("/api/report_video")
def report_video(
    name: str = Query(..., description="Artist name to report"),
    db: Session = Depends(get_db)
):
    """
    誤った動画が紐づいている場合の報告エンドポイント。
    報告済みIDを蓄積し、次回の再検索で同じ動画が返らないようにする。
    """
    artist = db.query(Artist).filter(Artist.name == name).first()
    if not artist:
        raise HTTPException(status_code=404, detail="Artist not found")

    # 報告された動画IDを累積リストに追加
    if artist.youtube_video_id:
        existing = artist.reported_video_ids or ""
        reported_list = [vid for vid in existing.split(",") if vid]
        if artist.youtube_video_id not in reported_list:
            reported_list.append(artist.youtube_video_id)
        artist.reported_video_ids = ",".join(reported_list)

    artist.youtube_video_id = None
    artist.is_reported = True
    db.commit()

    return {"message": "報告を受け付けました。動画は非表示になります。"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
