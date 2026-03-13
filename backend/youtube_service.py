"""
YouTube Search Service
- アーティスト名でYouTubeを検索し、最適な動画IDを返す
- タイトル一致チェックで無関係な動画が紐づくのを防ぐ
"""
import os
from dotenv import load_dotenv
from googleapiclient.discovery import build

load_dotenv()

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")


from typing import Optional, List

def search_artist_video(artist_name: str, exclude_ids: List[str] = [], suffix: str = "MV") -> Optional[str]:
    """
    アーティスト名でYouTube検索し、最適な動画IDを返す。
    タイトルにアーティスト名が含まれない場合はNoneを返す。
    exclude_ids: 除外する動画IDのリスト（報告済み動画）
    suffix: 検索ワードの末尾に追加する文字列（デフォルトは "MV"）
    """
    if not YOUTUBE_API_KEY:
        print("YOUTUBE_API_KEY が設定されていません")
        return None

    try:
        youtube = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)
        
        # 指定されたサフィックスで検索（より多くの候補を取得して除外に対応）
        request = youtube.search().list(
            part="snippet",
            q=f"{artist_name} {suffix}",
            type="video",
            maxResults=10,
            videoEmbeddable="true",
        )
        response = request.execute()
        items = response.get("items", [])

        if not items:
            return None

        artist_lower = artist_name.lower()

        for item in items:
            title = item["snippet"]["title"].lower()
            channel = item["snippet"]["channelTitle"].lower()
            video_id = item["id"]["videoId"]

            # 報告済み動画はスキップ
            if video_id in exclude_ids:
                continue

            # タイトルまたはチャンネル名にアーティスト名が含まれるか確認
            if artist_lower in title or artist_lower in channel:
                return video_id

        # 一致するものがなければNone（無関係な動画を弾く）
        return None

    except Exception as e:
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
