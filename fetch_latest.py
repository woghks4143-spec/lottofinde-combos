"""
동행복권에서 최신 회차 자동 수집 → rounds.json 업데이트.
실패해도 종료 코드 0 (워크플로 계속 진행).
"""
import json
import sys
import urllib.request
import ssl
from datetime import datetime, timezone, timedelta

SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE

KST = timezone(timedelta(hours=9))

def expected_latest_round(now=None):
    """1회는 2002-12-07 토 추첨. 매주 토요일이 1회씩."""
    now = now or datetime.now(KST)
    base = datetime(2002, 12, 7, 21, 0, 0, tzinfo=KST)
    diff = (now - base).total_seconds() / 86400
    if diff < 0: return 1
    return int(diff // 7) + 1

def fetch_round(r):
    url = f"https://www.dhlottery.co.kr/common.do?method=getLottoNumber&drwNo={r}"
    req = urllib.request.Request(url, headers={
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'application/json, text/javascript, */*; q=0.01',
        'Accept-Language': 'ko-KR,ko;q=0.9,en;q=0.8',
        'Accept-Encoding': 'identity',  # gzip 비활성화로 단순화
        'Referer': 'https://www.dhlottery.co.kr/gameResult.do?method=byWin',
        'X-Requested-With': 'XMLHttpRequest',
    })
    try:
        with urllib.request.urlopen(req, timeout=15, context=SSL_CTX) as resp:
            raw = resp.read().decode('utf-8', errors='replace')
        data = json.loads(raw)
        if data.get('returnValue') != 'success':
            return None
        return {
            'round': data['drwNo'],
            'nums': sorted([data[f'drwtNo{i}'] for i in range(1, 7)]),
            'bonus': data['bnusNo'],
            'firstWinAmount': data.get('firstWinamnt', 0),
            'firstWinners': data.get('firstPrzwnerCo', 0),
            'date': data['drwNoDate'],
        }
    except Exception as e:
        print(f"  [{r}회] fetch 실패: {type(e).__name__}: {e}", file=sys.stderr)
        return None

def main():
    try:
        with open('rounds.json', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        print(f"rounds.json 로드 실패: {e}")
        return

    latest = data.get('latestRound', 0)
    expected = expected_latest_round()
    print(f"현재 최신: {latest}회 / 예상 최신: {expected}회")

    if latest >= expected:
        print("이미 최신 상태.")
        return

    added = 0
    for r in range(latest + 1, expected + 1):
        result = fetch_round(r)
        if result is None:
            print(f"{r}회 가져오기 실패 → 중단.")
            break
        data['rounds'].append(result)
        data['latestRound'] = result['round']
        data['count'] = len(data['rounds'])
        added += 1
        print(f"+ {result['round']}회 추가: {result['nums']} (보너스 {result['bonus']})")

    if added > 0:
        data['fetchedAt'] = datetime.now(KST).isoformat()
        with open('rounds.json', 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"✅ rounds.json 업데이트 (+{added}회)")
    else:
        print("새 회차 추가 없음 (수동 업데이트 필요할 수 있음).")

if __name__ == "__main__":
    main()
