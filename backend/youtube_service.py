"""
YouTube Search Service
- アーティスト名でYouTubeを検索し、最適な動画IDを返す
- タイトル一致チェックで無関係な動画が紐づくのを防ぐ
"""
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta
from googleapiclient.discovery import build

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")


from typing import Optional, List

def search_artist_video(artist_name: str, exclude_ids: List[str] = [], suffix: Optional[str] = None, channel_id: Optional[str] = None) -> Optional[str]:
    """
    アーティスト名でYouTube検索し、最適な動画IDを返す。
    fallback: MVでヒットしなければ official mv で再試行。
    """
    if not YOUTUBE_API_KEY:
        print("YOUTUBE_API_KEY が設定されていません")
        return None

    # デフォルトの検索ワード順
    suffixes = [suffix] if suffix else ["MV", "official mv", "Music Video"]
    
    try:
        # 1年以内の動画に限定（アイドルの体制変更等への配慮）
        published_after = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%dT%H:%M:%SZ')
        youtube = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)
        
        artist_lower = artist_name.lower()

        for s in suffixes:
            search_params = {
                "part": "snippet",
                "q": f"{artist_name} {s}",
                "type": "video",
                "maxResults": 5,
                "videoEmbeddable": "true",
                "publishedAfter": published_after
            }
            if channel_id:
                search_params["channelId"] = channel_id

            request = youtube.search().list(**search_params)
            response = request.execute()
            items = response.get("items", [])

            # 無関係な動画（歌ってみた、踊ってみた等）を除外するキーワード
            negative_keywords = ["歌ってみた", "踊ってみた", "cover", "弾いてみた"]

            # 1. Official チャンネルを優先
            for item in items:
                title = item["snippet"]["title"].lower()
                channel = item["snippet"]["channelTitle"].lower()
                video_id = item["id"]["videoId"]

                if video_id in exclude_ids:
                    continue
                
                # 除外キーワードが含まれる場合はスキップ
                if any(k in title for k in negative_keywords):
                    continue

                # チャンネル名にアーティスト名が含まれ、かつ "official" という単語がある場合を最優先
                if artist_lower in channel and "official" in channel:
                    return video_id

            # 2. 次にタイトルにアーティスト名が含まれるものを確認
            for item in items:
                title = item["snippet"]["title"].lower()
                channel = item["snippet"]["channelTitle"].lower()
                video_id = item["id"]["videoId"]

                if video_id in exclude_ids:
                    continue

                if any(k in title for k in negative_keywords):
                    continue

                if artist_lower in title or artist_lower in channel:
                    return video_id

        return None

    except Exception as e:
        # Check for quota exceeded error in the exception message or type
        error_str = str(e).lower()
        if "quotaexceeded" in error_str or "quota exceeded" in error_str:
            print(f"YouTube API クォータ制限超過: {artist_name}")
            raise RuntimeError(f"YouTube Quota Exceeded: {e}")
            
        print(f"YouTube検索エラー ({artist_name}): {e}")
        return None

def batch_fetch_youtube_videos(limit=90):
    """
    定期実行用：未キャッシュのアーティストをDBから取得し、YouTube APIで動画IDを検索して更新する。
    limit: 1回に実行するAPI呼び出しの最大回数（デフォルト90件）
    """
    from models import SessionLocal, Artist
    from datetime import datetime
    
    db = SessionLocal()
    fetched_count = 0
    
    try:
        # 動画IDがnull、かつ直近で検索エラー報告されていない、かつ過去30日更新されていないものを優先
        artists_to_update = db.query(Artist).filter(
            Artist.youtube_video_id == None,
            Artist.is_reported == False
        ).limit(limit).all()
        
        print(f"Targeting {len(artists_to_update)} artists for YouTube search update.")
        
        for artist in artists_to_update:
            exclude_ids = [vid for vid in artist.reported_video_ids.split(",")] if artist.reported_video_ids else []
            
            video_id = search_artist_video(artist.name, exclude_ids=exclude_ids)
            fetched_count += 1
            
            artist.youtube_video_id = video_id
            artist.youtube_updated_at = datetime.now()
            
            status = f"Found: {video_id}" if video_id else "Not Found"
            print(f"[{fetched_count}/{limit}] {artist.name} -> {status}")
            
            db.commit()
            
    except Exception as e:
        print(f"Error in batch_fetch_youtube_videos: {e}")
        db.rollback()
    finally:
        db.close()
        print(f"Batch fetch completed. Total API calls: {fetched_count}")
