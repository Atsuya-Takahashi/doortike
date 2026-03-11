import os
from scraper import run_all_scrapers
from youtube_service import batch_fetch_youtube_videos

def main():
    print("=== Starting Daily Scraper Routine ===")
    
    # Check if DATABASE_URL is set (required for Supabase connection)
    if not os.getenv('DATABASE_URL'):
        print("ERROR: DATABASE_URL environment variable is missing.")
        print("Please configure this in your GitHub Actions Secrets.")
        return

    # 1. Run all livehouse scrapers
    print("\n--- Phase 1: Scraping Livehouses ---")
    try:
        run_all_scrapers()
        print("Successfully scraped all livehouses and saved to database.")
    except Exception as e:
        print(f"Error during scraping: {e}")
        # Note: In production you might want to raise the error here to fail the CI step

    # 2. Run YouTube API updates
    print("\n--- Phase 2: Updating YouTube Links ---")
    if not os.getenv('YOUTUBE_API_KEY'):
        print("WARNING: YOUTUBE_API_KEY environment variable is missing.")
        print("Skipping YouTube updates. Configure this in GitHub Actions Secrets to enable.")
    else:
        try:
            batch_fetch_youtube_videos()
            print("Successfully updated YouTube links for artists.")
        except Exception as e:
            print(f"Error during YouTube API update: {e}")

    print("\n=== Daily Scraper Routine Completed ===")

if __name__ == "__main__":
    main()
