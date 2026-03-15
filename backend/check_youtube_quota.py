
import os
import sys
from googleapiclient.discovery import build
from dotenv import load_dotenv

# Path setup
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")

def check_quota():
    if not YOUTUBE_API_KEY:
        print("❌ Error: YOUTUBE_API_KEY is not set in .env")
        return

    try:
        youtube = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)
        # Try a very simple, low-cost search to see if it's allowed
        request = youtube.search().list(
            part="snippet",
            q="check",
            maxResults=1,
            type="video"
        )
        request.execute()
        print("✅ YouTube API is available. (Quota remaining)")
    except Exception as e:
        error_str = str(e).lower()
        if "quotaexceeded" in error_str or "quota exceeded" in error_str:
            print("🛑 YouTube API Quota Exceeded. (上限に達しています)")
        else:
            print(f"❓ Other Error: {e}")

if __name__ == "__main__":
    check_quota()
