from models import SessionLocal, LiveHouse, Event
from datetime import datetime

db = SessionLocal()
today = datetime.now()

lh = db.query(LiveHouse).first()
if lh:
    extreme_event = Event(
        livehouse_id=lh.id,
        date=today.date(),
        title="【超絶長文表示テスト】第1回 限界突破スーパーウルトラアルティメットフェスティバル2026 〜サブタイトルが長すぎて改行されるかどうかを本気で検証するためのダミーイベント、果たしてこのスマホ向けカードUIは崩れずに耐えきれるのか！？〜",
        performers="バンド1、バンド2、バンド3、バンド4、バンド5、バンド6、バンド7、バンド8、バンド9、バンド10、バンド11、バンド12、バンド13、バンド14、バンド15、バンド16、バンド17、バンド18、バンド19、バンド20、バンド21、バンド22、バンド23、バンド24、バンド25、バンド26、バンド27、バンド28、バンド29、バンド30",
        open_time="11:00",
        start_time="11:30",
        price_info="前売 ¥10,000 / 当日 ¥12,000\n(Drink代別途¥600 / 3日間通し券あり)",
        ticket_url="https://eplus.jp/",
        blog_url="https://example.com/extreme",
        coupon_url="https://example.com/extreme"
    )
    db.add(extreme_event)
    db.commit()
    print("Extreme event added successfully!")
else:
    print("No livehouse found.")
db.close()
