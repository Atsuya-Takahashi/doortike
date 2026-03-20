"""
YouTube Search Service
- アーティスト名でYouTubeを検索し、最適な動画IDを返す
- タイトル一致チェックで無関係な動画が紐づくのを防ぐ
- 2分〜8分の動画のみを採用するフィルタリング機能
"""
import os
import re
from dotenv import load_dotenv
from datetime import datetime, timedelta
from googleapiclient.discovery import build
from typing import Optional, List

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")

def parse_duration(duration_str: str) -> int:
    """Parse ISO 8601 duration string (e.g., PT3M45S) into total seconds."""
    match = re.search(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', duration_str)
    if not match: return 0
    hours = int(match.group(1) or 0)
    minutes = int(match.group(2) or 0)
    seconds = int(match.group(3) or 0)
    return hours * 3600 + minutes * 60 + seconds

def get_video_from_playlist(youtube, channel_id: str, exclude_ids: List[str] = []) -> Optional[str]:
    """
    1. channels().list (1ユニット) で正式な "uploads" プレイリストIDを取得
    2. playlistItems.list (1ユニット) で最新動画を取得
    3. videos.list (1ユニット) で長さを確認
    合計 3ユニットで完了させる（search.list の 100ユニットを回避）
    """
    try:
        # 1. 正確なアップロード用プレイリストIDを取得 (1ユニット)
        c_request = youtube.channels().list(
            part="contentDetails",
            id=channel_id
        )
        c_response = c_request.execute()
        items = c_response.get("items", [])
        if not items: return None
        
        playlist_id = items[0]["contentDetails"]["relatedPlaylists"].get("uploads")
        if not playlist_id: return None
        
        # 2. プレイリスト内の最新動画リストを取得 (1ユニット)
        request = youtube.playlistItems().list(
            part="snippet",
            playlistId=playlist_id,
            maxResults=10
        )
        response = request.execute()
        items = response.get("items", [])
        if not items: return None

        video_ids = [item["snippet"]["resourceId"]["videoId"] for item in items]
        
        # 2. 動画の長さを一括取得 (1ユニット)
        v_request = youtube.videos().list(part="contentDetails", id=",".join(video_ids))
        v_response = v_request.execute()
        
        duration_map = {}
        for v_item in v_response.get("items", []):
            v_id = v_item["id"]
            d_str = v_item["contentDetails"]["duration"]
            duration_map[v_id] = parse_duration(d_str)

        negative_keywords = ["歌ってみた", "踊ってみた", "cover", "弾いてみた"]

        # 3. フィルタリング (2分〜8分)
        for item in items:
            v_id = item["snippet"]["resourceId"]["videoId"]
            title = item["snippet"]["title"].lower()
            duration = duration_map.get(v_id, 0)

            if v_id in exclude_ids: continue
            if any(k in title for k in negative_keywords): continue
            
            # 2分（120秒）〜8分（480秒）
            if 120 <= duration <= 480:
                print(f"UU-Hack Success: Found video {v_id} ({duration}s)")
                return v_id
                
        return None
    except Exception as e:
        print(f"UU-Hack Error: {e}")
        return None

def search_artist_video(artist_name: str, exclude_ids: List[str] = [], suffix: Optional[str] = None, channel_id: Optional[str] = None) -> Optional[str]:
    """
    アーティスト名でYouTube検索し、最適な動画IDを返す。
    channel_id がある場合は UUハック (2ユニット) を優先し、search.list (100ユニット) を回避する。
    """
    if not YOUTUBE_API_KEY:
        print("YOUTUBE_API_KEY が設定されていません")
        return None

    try:
        youtube = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)
        
        # --- A. channel_id がある場合は UUハックを試行 (節約モード) ---
        if channel_id:
            video_id = get_video_from_playlist(youtube, channel_id, exclude_ids)
            if video_id:
                return video_id
            print(f"UU-Hack で見つかりませんでした。Fallback検索を行います: {artist_name}")

        # --- B. Fallback または channel_id なしの場合は search.list (100ユニット) ---
        suffixes = [suffix] if suffix else ["MV", "official mv", "Music Video"]
        published_after = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%dT%H:%M:%SZ')
        artist_lower = artist_name.lower()

        for s in suffixes:
            search_params = {
                "part": "snippet",
                "q": f"{artist_name} {s}",
                "type": "video",
                "maxResults": 10,
                "videoEmbeddable": "true",
                "publishedAfter": published_after
            }
            if channel_id:
                search_params["channelId"] = channel_id

            request = youtube.search().list(**search_params)
            response = request.execute()
            items = response.get("items", [])
            if not items: continue

            video_ids = [item["id"]["videoId"] for item in items]
            v_request = youtube.videos().list(part="contentDetails", id=",".join(video_ids))
            v_response = v_request.execute()
            
            duration_map = {}
            for v_item in v_response.get("items", []):
                v_id = v_item["id"]
                d_str = v_item["contentDetails"]["duration"]
                duration_map[v_id] = parse_duration(d_str)

            negative_keywords = ["歌ってみた", "踊ってみた", "cover", "弾いてみた"]

            valid_items = []
            for item in items:
                v_id = item["id"]["videoId"]
                duration = duration_map.get(v_id, 0)
                if 120 <= duration <= 480:
                    valid_items.append(item)

            # ランク付け
            for item in valid_items:
                title = item["snippet"]["title"].lower()
                channel = item["snippet"]["channelTitle"].lower()
                video_id = item["id"]["videoId"]
                if video_id in exclude_ids: continue
                if any(k in title for k in negative_keywords): continue
                if artist_lower in channel and "official" in channel:
                    return video_id

            for item in valid_items:
                title = item["snippet"]["title"].lower()
                channel = item["snippet"]["channelTitle"].lower()
                video_id = item["id"]["videoId"]
                if video_id in exclude_ids: continue
                if any(k in title for k in negative_keywords): continue
                if artist_lower in title or artist_lower in channel:
                    return video_id

        return None

    except Exception as e:
        error_str = str(e).lower()
        if "quotaexceeded" in error_str or "quota exceeded" in error_str:
            print(f"YouTube API クォータ制限超過: {artist_name}")
            raise RuntimeError(f"YouTube Quota Exceeded: {e}")
        print(f"YouTube検索エラー ({artist_name}): {e}")
        return None

def resolve_video_reports(db):
    """
    Process pending video reports:
    1. Update Artist table (clear youtube_video_id, add to exclusion list)
    2. Mark reports as 'resolved'
    """
    from backend.models import VideoReport, Artist
    
    pending_reports = db.query(VideoReport).filter(VideoReport.status == 'pending').all()
    if not pending_reports:
        return
    
    print(f"Resolving {len(pending_reports)} pending video reports...")
    
    for report in pending_reports:
        artist = db.query(Artist).filter(Artist.name == report.artist_name).first()
        if artist:
            # Add current bad ID to exclusion list
            if artist.youtube_video_id:
                reported_ids = artist.reported_video_ids.split(",") if artist.reported_video_ids else []
                if artist.youtube_video_id not in reported_ids:
                    reported_ids.append(artist.youtube_video_id)
                artist.reported_video_ids = ",".join(reported_ids)
            
            # Reset ID to trigger priority re-fetch
            artist.youtube_video_id = None
            artist.youtube_updated_at = None
            artist.is_reported = False
            
        report.status = 'resolved'
    
    db.commit()
    print("Reports resolved successfully.")

def batch_fetch_youtube_videos(limit=90):
    """
    定期実行用：未キャッシュのアーティストをDBから取得し、YouTube APIで動画IDを検索して更新する。
    limit: 1回に実行するAPI呼び出しの最大回数（デフォルト90件）
    """
    from backend.models import SessionLocal, Artist
    from datetime import datetime
    
    db = SessionLocal()
    fetched_count = 0
    
    try:
        # まず報告解決などでIDがリセットされたもの（None かつ updated_at が古いもの）を優先
        artists_to_update = db.query(Artist).filter(
            Artist.youtube_video_id == None,
            Artist.is_reported == False
        ).order_by(Artist.youtube_updated_at.asc()).limit(limit).all()
        
        if not artists_to_update:
            print("No artists need YouTube ID updates.")
            return

        print(f"Targeting {len(artists_to_update)} artists for YouTube search update (Prioritizing reported/newly added).")
        
        for artist in artists_to_update:
            exclude_ids = artist.reported_video_ids.split(",") if artist.reported_video_ids else []
            
            video_id = search_artist_video(artist.name, exclude_ids=exclude_ids, channel_id=artist.official_channel_id)
            fetched_count += 1
            
            artist.youtube_video_id = video_id
            artist.youtube_updated_at = datetime.now()
            
            status = f"Found: {video_id}" if video_id else "Not Found"
            print(f"[{fetched_count}/{len(artists_to_update)}] {artist.name} -> {status}")
            
            db.commit()
            
    except Exception as e:
        print(f"Error in batch_fetch_youtube_videos: {e}")
        db.rollback()
    finally:
        db.close()
        print(f"Batch fetch completed. Total API calls: {fetched_count}")
