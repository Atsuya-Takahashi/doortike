import requests
from bs4 import BeautifulSoup

url = 'https://www.loft-prj.co.jp/schedule/loft/schedule'
headers = {'User-Agent': 'Mozilla/5.0'}
response = requests.get(url, headers=headers)
soup = BeautifulSoup(response.text, 'html.parser')

links = soup.select('a.js-cursor-elm')
print(f"Found {len(links)} links via BS4.")
for i, l in enumerate(links[:15]):
    print(f"[{i}] {l.get('href')} | {repr(l.get_text(strip=True))}")
