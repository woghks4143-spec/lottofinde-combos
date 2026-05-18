# lottofinde-combos

로또핀더 주간 조합 풀 데이터.

## 자동 업데이트 일정

| 시간 (KST) | 동작 |
|---|---|
| 매주 토요일 20:35 | 로또 추첨 |
| 매주 일요일 ~ | 동행복권에 새 회차 게시 |
| **매주 월요일 09:00** | **GitHub Actions가 자동 분석** → 새 `round_NNNN.json` 추가 |
| 수~토 20:00 | 앱 사용자가 50조합씩 받기 |

## 폰만 있을 때

1. **자동 모드**: 아무것도 안 해도 됨. 월요일 아침에 자동 실행됨.
2. **수동 실행**: GitHub 모바일 웹 → `Actions` 탭 → `Weekly Combo Generation` → `Run workflow` 버튼.
3. **상태 확인**: 메인 페이지에 `round_NNNN.json` 새 파일이 있으면 OK.

## 컴퓨터에서

`로또 1등/로또핀더_분석/실행.bat` 더블클릭 → 6초 → 끝.

## 파일 구성

- `round_NNNN.json` — N회차 분석 결과 (~85,000 조합)
- `rounds.json` — 입력 데이터 (역대 당첨번호)
- `lotto_pinder.py` — JACKPOT_UNION 알고리즘
- `cloud_run.py` — GitHub Actions 실행기
- `fetch_latest.py` — 동행복권 자동 페치 (best-effort)
- `.github/workflows/weekly.yml` — 매주 월요일 자동 스케줄
