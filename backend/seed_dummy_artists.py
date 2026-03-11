from models import SessionLocal, Artist
from datetime import datetime

def seed_artists():
    db = SessionLocal()
    try:
        # Artist names from seed_dummy_events.py
        artist_names = [
            "Amairo-Flip", "BLUE REGRET。", "Cheriecla", "Claire♡Dolls", "Ep!codE",
            "Fancy Film*", "FIRST DREAM", "INOiZe↯", "Lovlis", "MISS MY NOTES",
            "Poppin' Parade", "pureran story", "Red Radiance", "Tiara Palette",
            "アイドルキャリア", "あまいものつめあわせ", "イイトコドリ", "オトメルキュール",
            "きみパレ", "しろくまいんど", "なないろパンダちゃん。", "ぺりきゅらむ",
            "ミリフェア", "ゆえない", "ゆるっと革命団", "らびゅあたっく。",
            "ラプラス", "愛♡きゃっち", "甘いものには毒がある。", "白地図プロローグ",
            "無名上京アイドル", "インディーズ・スターズ", "ギター・ヒーローズ",
            "横濱パンクス", "THE DRIVER", "GEAR HEADS", "MATH ROCKERS",
            "Nagoya Chiken", "Fried Boys", "Tako-Yaki", "Mentsuyu Metal",
            "DJ TECH", "BEAT MAKER", "SYNTH MASTER", "DANCE MONSTERS",
            "キラキラガールズ", "ぴょんぴょん隊", "メロディック・ハート",
            "GOTHIC VAMPIRES", "NIGHTMARE", "DREAMY SOUNDS", "NOISE CLOUD"
        ]

        now = datetime.now()
        count = 0
        for name in artist_names:
            existing = db.query(Artist).filter(Artist.name == name).first()
            if not existing:
                artist = Artist(
                    name=name,
                    youtube_video_id="dQw4w9WgXcQ", # Dummy video ID (RickRoll for testing)
                    youtube_updated_at=now
                )
                db.add(artist)
                count += 1
        
        db.commit()
        print(f"Successfully added {count} dummy artists with YouTube links.")
    except Exception as e:
        print(f"Error seeding artists: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    seed_artists()
