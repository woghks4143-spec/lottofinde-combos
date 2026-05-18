"""
GitHub Actions용 분석 실행기.
lottofinde-combos 저장소 루트에서 실행되며, 결과를 현재 디렉토리에 직접 저장.
"""
import json
import os
import sys
import time

# 같은 폴더의 lotto_pinder.py에서 알고리즘 import
from lotto_pinder import load_draws_json, lotto_pinder_method1

def main():
    print("=" * 50)
    print("  로또핀더 클라우드 분석 (GitHub Actions)")
    print("=" * 50)

    draws, latest = load_draws_json("rounds.json")
    target = latest + 1
    history = [d for d in draws if d['round'] < target]

    print(f"전체 회차: 1 ~ {latest} ({len(draws)}회)")
    print(f"분석 대상: {target}회차")
    print(f"학습 데이터: 1 ~ {target-1}회 ({len(history)}회)")

    t0 = time.time()
    combos = lotto_pinder_method1(history, target)
    elapsed = time.time() - t0
    print(f"추출 완료: {len(combos):,}조합 ({elapsed:.1f}초)")

    payload = {
        "round": target,
        "basedOnLatest": latest,
        "count": len(combos),
        "algorithm": "JACKPOT_UNION_v1",
        "combos": [list(c) for c in combos],
    }
    filename = f"round_{target:04d}.json"
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))

    size_kb = os.path.getsize(filename) // 1024
    print(f"저장: {filename} ({size_kb:,} KB)")
    print("=" * 50)

if __name__ == "__main__":
    main()
