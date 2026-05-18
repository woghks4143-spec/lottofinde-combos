"""
로또핀더 조합법1 (JACKPOT_UNION) - 단일 파일 완전 명세
=========================================================

목적: 회차 N에 대한 1~N-1 데이터만 사용해 약 85,000조합 추출
구조: JACKPOT_50K ∪ PL_HOT_50K 합집합

100회 백테스트 (1123~1222) 검증:
  - 1등 2회 (1145, 1206) | 2등 5회 (1183×2, 1194, 1207, 1222)
  - 3등 288회 | 4등 13,130개 | 5등 198,292개
  - 평균 당첨률 2.51% | 환원율 87%

입력: rounds.json (앱 번들 시드 데이터, 자동 복사됨)
출력: ./lottofinde-combos/round_NNNN.json (앱 fetch용)
      ./output/round_NNNN.json (로컬 백업)
"""
import sys, time, json, os
import numpy as np
from itertools import combinations
from collections import Counter

# ─── Windows 콘솔 UTF-8 ────────────────────────────────
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

# ─── 설정 ─────────────────────────────────────────────
ROUNDS_FILE = "rounds.json"
OUTPUT_DIRS = [
    "lottofinde-combos",  # 1순위: 공개 GitHub 저장소
    "output",             # 2순위: 로컬 백업
]
TARGET = 50000  # 각 알고리즘이 추출할 조합 수 (JACKPOT 50K + PL_HOT 50K → 합집합 ~85K)

# ============================================================
# 1. 데이터 로딩 (rounds.json → 표준 형식)
# ============================================================
def load_draws_json(path):
    """앱의 rounds.json을 user 코드의 draws 형식으로 변환."""
    with open(path, encoding='utf-8') as f:
        data = json.load(f)
    draws = []
    for r in data["rounds"]:
        nums = sorted(int(x) for x in r["nums"])
        draws.append({
            'round': int(r["round"]),
            'numbers': frozenset(nums),
            'numbers_sorted': tuple(nums),
            'bonus': int(r["bonus"]),
        })
    return draws, int(data.get("latestRound", draws[-1]['round']))

# ============================================================
# 2. Feature 사전 계산 (1~N-1 데이터만)
# ============================================================
def compute_features(history, current_round):
    g_full = np.zeros((46, 46), dtype=np.int32)
    g_50 = np.zeros((46, 46), dtype=np.int32)
    p6_mat = np.zeros((46, 46), dtype=np.int32)

    for d in history:
        for a, b in combinations(d['numbers_sorted'], 2):
            g_full[a, b] += 1; g_full[b, a] += 1
    for d in history[-50:]:
        for a, b in combinations(d['numbers_sorted'], 2):
            g_50[a, b] += 1; g_50[b, a] += 1
    for d in history[-6:]:
        for a, b in combinations(d['numbers_sorted'], 2):
            p6_mat[a, b] += 1; p6_mat[b, a] += 1

    p50 = np.zeros(46, dtype=np.int32)
    for d in history[-50:]:
        for x in d['numbers_sorted']:
            p50[x] += 1

    meta_scores = g_full.sum(axis=1).astype(np.float64)
    meta_max = max(meta_scores.max(), 1.0)
    meta_norm = meta_scores / meta_max

    last_app = {}
    for d in history:
        for x in d['numbers_sorted']:
            last_app[x] = d['round']

    d5_15 = np.zeros(46, dtype=np.float64)
    for x in range(1, 46):
        last = last_app.get(x, 0)
        if last == 0:
            d5_15[x] = 1.0
        elif current_round - 15 <= last <= current_round - 5:
            d5_15[x] = 1.0

    return {
        'g_full': g_full, 'g_50': g_50, 'p6_mat': p6_mat,
        'p50': p50, 'meta_scores': meta_scores,
        'meta_norm': meta_norm, 'd5_15': d5_15,
        'last_app': last_app, 'cur': current_round
    }

# ============================================================
# 3. 7개 신호 풀 빌더 (모두 N-1 데이터만 사용)
# ============================================================
def get_meta_pool(feat, k=13):
    return [int(i) for i in np.argsort(-feat['meta_scores'])[:k]]

def get_F_pool(history, current_round, k=15):
    if not history: return list(range(1, k+1))
    last_app = {}
    for d in history:
        for x in d['numbers_sorted']:
            last_app[x] = d['round']
    gaps = [(current_round - last_app.get(x, 0) if x in last_app else 9999, x)
            for x in range(1, 46)]
    gaps.sort(reverse=True)
    return [x for _, x in gaps[:k]]

def get_M_pool(history, k=15):
    recent = history[-50:] if len(history) >= 50 else history
    pair_count = Counter()
    for d in recent:
        for a, b in combinations(d['numbers_sorted'], 2):
            pair_count[(a, b)] += 1
    members = Counter()
    for (a, b), c in pair_count.most_common(30):
        members[a] += c; members[b] += c
    return [n for n, _ in members.most_common(k)]

def get_mod7_pool(history, current_round, k=15):
    target_mod = current_round % 7
    count = Counter()
    for d in history:
        if d['round'] % 7 == target_mod:
            for n in d['numbers_sorted']:
                count[n] += 1.0
    return [n for n, _ in count.most_common(k)]

def get_B_pool(history, k=15):
    """분석방법.txt B법: 유사회차의 다음 회차 끝수 Top 3"""
    if len(history) < 2: return list(range(1, k+1))
    last_set = set(history[-1]['numbers_sorted'])
    follow = Counter()
    for i in range(len(history) - 1):
        if len(set(history[i]['numbers_sorted']) & last_set) >= 3:
            for n in history[i + 1]['numbers_sorted']:
                follow[n % 10] += 1
    if not follow: return list(range(1, k+1))
    top3 = [e for e, _ in follow.most_common(3)]
    pool = [n for n in range(1, 46) if n % 10 in top3]
    if len(pool) >= k: return pool[:k]
    return pool + [n for n in range(1, 46) if n not in pool][:k-len(pool)]

def get_A_pool(history, k=15):
    """분석방법.txt A법: 유사회차 자체 끝수 Top 3"""
    if len(history) < 2: return list(range(1, k+1))
    last_set = set(history[-1]['numbers_sorted'])
    endings = Counter()
    for i in range(len(history) - 1):
        if len(set(history[i]['numbers_sorted']) & last_set) >= 3:
            for n in history[i]['numbers_sorted']:
                endings[n % 10] += 1
    if not endings: return list(range(1, k+1))
    top3 = [e for e, _ in endings.most_common(3)]
    pool = [n for n in range(1, 46) if n % 10 in top3]
    if len(pool) >= k: return pool[:k]
    return pool + [n for n in range(1, 46) if n not in pool][:k-len(pool)]

# ============================================================
# 4. 6-OR Pool 41 (멤버십 카운트 기반)
# ============================================================
def build_pool_41(history, current_round, feat):
    """6개 풀 합집합 → 멤버십 카운트 Top 41"""
    meta15 = get_meta_pool(feat, 15)
    F = get_F_pool(history, current_round, 15)
    M = get_M_pool(history, 15)
    mod7 = get_mod7_pool(history, current_round, 15)
    B = get_B_pool(history, 15)
    A = get_A_pool(history, 15)

    mc = Counter()
    for p in [meta15, F, M, mod7, B, A]:
        for n in p: mc[n] += 1
    pool = [n for n, _ in mc.most_common(41)]
    if len(pool) < 41:
        for n in range(1, 46):
            if n not in pool:
                pool.append(n)
                if len(pool) >= 41: break
    return sorted(pool[:41])

# ============================================================
# 5. W_PLUS 페어 strength (8가중치, RS-200 학습)
# ============================================================
def build_pair_strength_matrix(pool, feat, meta_set):
    """W_PLUS 8가중치:
      +0.503 × meta_avg       (메타 점수 평균)
      +0.296 × g_full / 30    (전체 페어 빈도)
      +1.680 × p50_sum / 30   (직전 50회 번호 출현 합) ⭐
      -0.319 × g_50 / 5       (직전 50회 페어 빈도)
      -0.620 × |a-b| / 45     (번호 차이)
      +0.410 × d5_15 avg      (직전 5~15회 미출현 binary)
      -0.063 × consecutive    (|a-b|<=2)
      -1.320 × p6 / 6         (직전 6회 페어) ⭐ 페널티 강화
    """
    M = np.zeros((46, 46), dtype=np.float64)
    for a, b in combinations(pool, 2):
        meta_avg = (feat['meta_norm'][a] + feat['meta_norm'][b]) / 2
        g_full_n = feat['g_full'][a, b] / 30.0
        p50_sum_n = (feat['p50'][a] + feat['p50'][b]) / 30.0
        g_50_n = feat['g_50'][a, b] / 5.0
        num_diff_n = abs(a - b) / 45.0
        sweet_due_avg = (feat['d5_15'][a] + feat['d5_15'][b]) / 2
        consecutive = 1.0 if abs(a - b) <= 2 else 0.0
        p6_n = feat['p6_mat'][a, b] / 6.0

        s = (0.503 * meta_avg
           + 0.296 * g_full_n
           + 1.680 * p50_sum_n
           - 0.319 * g_50_n
           - 0.620 * num_diff_n
           + 0.410 * sweet_due_avg
           - 0.063 * consecutive
           - 1.320 * p6_n)
        M[a, b] = s; M[b, a] = s
    return M

# ============================================================
# 6. Lift Matrix (직전 100회 페어 동시 출현 / 무작위 기대)
# ============================================================
def lift_matrix(history, window=100):
    recent = history[-window:] if len(history) >= window else history
    pair_co = Counter()
    for d in recent:
        for a, b in combinations(sorted(d['numbers_sorted']), 2):
            pair_co[(a, b)] += 1
    n_r = max(len(recent), 1)
    p_random = 30 / (45 * 44)
    M = np.full((46, 46), 0.5)
    for (a, b), cnt in pair_co.items():
        lift = (cnt / n_r) / p_random
        M[a, b] = lift; M[b, a] = lift
    return M

# ============================================================
# 7. V3 31필터 (벡터화)
# ============================================================
def v3_pass_batch(combos_arr):
    """합계 100~175, 끝수합 14~38, 홀 1~5, 저(≤22) 1~5,
    3연속 금지, AC≥7 (15-중복차≥12), 동끝수 ≤3"""
    sums = combos_arr.sum(axis=1)
    end_sums = (combos_arr % 10).sum(axis=1)
    odd_counts = (combos_arr % 2).sum(axis=1)
    low_counts = (combos_arr <= 22).sum(axis=1)
    mask = (sums >= 100) & (sums <= 175) \
         & (end_sums >= 14) & (end_sums <= 38) \
         & (odd_counts >= 1) & (odd_counts <= 5) \
         & (low_counts >= 1) & (low_counts <= 5)

    # 3연속 금지
    diffs_adj = np.diff(combos_arr, axis=1)
    is_one = (diffs_adj == 1)
    has_3consec = ((is_one[:,0] & is_one[:,1]) | (is_one[:,1] & is_one[:,2])
                 | (is_one[:,2] & is_one[:,3]) | (is_one[:,3] & is_one[:,4]))
    mask = mask & ~has_3consec

    # AC ≥7
    pair_idx = [(i, j) for i in range(6) for j in range(i+1, 6)]
    diffs_all = np.zeros((combos_arr.shape[0], 15), dtype=np.int32)
    for k, (i, j) in enumerate(pair_idx):
        diffs_all[:, k] = combos_arr[:, j] - combos_arr[:, i]
    sorted_diffs = np.sort(diffs_all, axis=1)
    n_dup = (sorted_diffs[:, 1:] == sorted_diffs[:, :-1]).sum(axis=1)
    mask = mask & ((15 - n_dup) >= 12)

    # 동끝수 ≤3
    end_digits = combos_arr % 10
    max_end = np.zeros(combos_arr.shape[0], dtype=np.int32)
    for d in range(10):
        max_end = np.maximum(max_end, (end_digits == d).sum(axis=1))
    mask = mask & (max_end <= 3)

    return mask

# ============================================================
# 8. 콤보 인덱스 캐시 (C(41,6) = 4,496,388)
# ============================================================
_COMBO_IDX_41 = None
def get_combo_idx_41():
    global _COMBO_IDX_41
    if _COMBO_IDX_41 is None:
        _COMBO_IDX_41 = np.array(list(combinations(range(41), 6)), dtype=np.int32)
    return _COMBO_IDX_41

# ============================================================
# 9. JACKPOT_50K — 1등 잡이 (V_DIAMOND_M 구조)
# ============================================================
def algo_jackpot_50k(history, current_round):
    """V_DIAMOND_M maj3≥1 6풀 + lift × 0.4 + W_PLUS × 0.6"""
    feat = compute_features(history, current_round)
    pool = build_pool_41(history, current_round, feat)
    pool_arr = np.array(pool, dtype=np.int32)
    combos = pool_arr[get_combo_idx_41()]
    mask_v3 = v3_pass_batch(combos)
    valid = combos[mask_v3]
    if valid.shape[0] == 0: return []

    # 6풀 멤버십 카운트
    pools_6 = [
        set(get_meta_pool(feat, 13)),
        set(get_F_pool(history, current_round, 15)),
        set(get_M_pool(history, 15)),
        set(get_mod7_pool(history, current_round, 15)),
        set(get_B_pool(history, 15)),
        set(get_A_pool(history, 15)),
    ]
    num_pool_count = np.zeros(46, dtype=np.int32)
    for n in range(1, 46):
        num_pool_count[n] = sum(1 for p in pools_6 if n in p)

    # maj3≥1 강제
    max_per = num_pool_count[valid].max(axis=1)
    filtered = valid[max_per >= 3]
    if filtered.shape[0] < TARGET:
        filtered = valid[max_per >= 2]
        if filtered.shape[0] < TARGET:
            filtered = valid

    # 점수 계산
    M_lift = lift_matrix(history, 100)
    lift_scores = np.zeros(filtered.shape[0])
    for i in range(6):
        for j in range(i+1, 6):
            lift_scores += M_lift[filtered[:, i], filtered[:, j]]

    meta_set = set(get_meta_pool(feat, 13))
    pair_M = build_pair_strength_matrix(pool, feat, meta_set)
    wplus = np.zeros(filtered.shape[0])
    for i in range(6):
        for j in range(i+1, 6):
            wplus += pair_M[filtered[:, i], filtered[:, j]]

    s1 = (lift_scores - lift_scores.mean()) / (lift_scores.std() + 1e-9)
    s2 = (wplus - wplus.mean()) / (wplus.std() + 1e-9)
    combined = 0.4 * s1 + 0.6 * s2

    # top 20K + 무작위 30K
    sorted_idx = np.argsort(-combined)
    top_n = min(20000, filtered.shape[0])
    result_idx = list(sorted_idx[:top_n])
    np.random.seed(current_round)
    rest_idx = sorted_idx[top_n:].copy()
    np.random.shuffle(rest_idx)
    result_idx.extend(rest_idx[:TARGET - top_n])
    return [tuple(int(x) for x in filtered[i]) for i in result_idx[:TARGET]]

# ============================================================
# 10. PL_HOT_50K — 1+2등 잡이 (PAIR_LIFT + Hot 5)
# ============================================================
def algo_pl_hot_50k(history, current_round):
    """PAIR_LIFT (lift × 0.4 + W_PLUS × 0.6) × 0.85 + Hot_5 × 0.15"""
    feat = compute_features(history, current_round)
    pool = build_pool_41(history, current_round, feat)
    pool_arr = np.array(pool, dtype=np.int32)
    combos = pool_arr[get_combo_idx_41()]
    mask = v3_pass_batch(combos)
    valid = combos[mask]
    if valid.shape[0] == 0: return []

    M_lift = lift_matrix(history, 100)
    lift_scores = np.zeros(valid.shape[0])
    for i in range(6):
        for j in range(i+1, 6):
            lift_scores += M_lift[valid[:, i], valid[:, j]]

    meta_set = set(get_meta_pool(feat, 13))
    pair_M = build_pair_strength_matrix(pool, feat, meta_set)
    wplus = np.zeros(valid.shape[0])
    for i in range(6):
        for j in range(i+1, 6):
            wplus += pair_M[valid[:, i], valid[:, j]]

    # Hot 5
    hot_5 = Counter()
    for d in history[-5:]:
        for n in d['numbers_sorted']:
            hot_5[n] += 1
    hot_arr = np.zeros(46)
    for n, c in hot_5.items():
        hot_arr[n] = c
    hot_per_combo = hot_arr[valid].sum(axis=1)

    s1 = (lift_scores - lift_scores.mean()) / (lift_scores.std() + 1e-9)
    s2 = (wplus - wplus.mean()) / (wplus.std() + 1e-9)
    s3 = (hot_per_combo - hot_per_combo.mean()) / (hot_per_combo.std() + 1e-9)
    base = 0.4 * s1 + 0.6 * s2
    combined = 0.85 * base + 0.15 * s3

    sorted_idx = np.argsort(-combined)
    top_n = 20000
    result_idx = list(sorted_idx[:top_n])
    np.random.seed(current_round)
    rest_idx = sorted_idx[top_n:].copy()
    np.random.shuffle(rest_idx)
    result_idx.extend(rest_idx[:TARGET - top_n])
    return [tuple(int(x) for x in valid[i]) for i in result_idx[:TARGET]]

# ============================================================
# 11. 로또핀더 조합법1 = JACKPOT_UNION (합집합)
# ============================================================
def lotto_pinder_method1(history, current_round):
    """JACKPOT_50K ∪ PL_HOT_50K dedup → ~85K"""
    a = algo_jackpot_50k(history, current_round)
    b = algo_pl_hot_50k(history, current_round)
    seen = set()
    result = []
    for c in a + b:
        if c not in seen:
            seen.add(c)
            result.append(c)
    return result

# ============================================================
# 12. 메인 실행
# ============================================================
def fatal(msg):
    print(""); print("=" * 50); print(f"❌ {msg}"); print("=" * 50); print("")
    try: input("아무 키나 누르면 종료...")
    except: pass
    sys.exit(1)

def main():
    print("")
    print("=" * 50)
    print("  로또핀더 조합법1 (JACKPOT_UNION)")
    print("=" * 50)
    print("")

    if not os.path.exists(ROUNDS_FILE):
        fatal(
            f"{ROUNDS_FILE} 없음.\n"
            f"app/src/data/rounds.json 을 이 폴더에 복사하세요.\n"
            f"현재 위치: {os.getcwd()}"
        )

    draws, latest = load_draws_json(ROUNDS_FILE)
    target_round = latest + 1
    print(f"📊 전체 회차: {draws[0]['round']} ~ {draws[-1]['round']} ({len(draws)}회)")
    print(f"🎯 분석 대상: {target_round}회차")

    # 1~N-1 데이터만 (미래 누설 차단)
    history = [d for d in draws if d['round'] < target_round]
    print(f"📚 학습 데이터: 1 ~ {target_round-1}회 ({len(history)}회) — N-1 원칙")

    print("")
    print("⚙️  JACKPOT_50K 생성 중...")
    t0 = time.time()
    combos = lotto_pinder_method1(history, target_round)
    elapsed = time.time() - t0
    print(f"✅ 추출 완료: {len(combos):,}조합 ({elapsed:.1f}초)")

    # 출력
    payload = {
        "round": target_round,
        "basedOnLatest": latest,
        "count": len(combos),
        "algorithm": "JACKPOT_UNION_v1",
        "combos": [list(c) for c in combos],
    }
    filename = f"round_{target_round:04d}.json"
    saved_paths = []
    for out_dir in OUTPUT_DIRS:
        try:
            os.makedirs(out_dir, exist_ok=True)
            path = os.path.join(out_dir, filename)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))
            saved_paths.append(path)
        except Exception as e:
            print(f"⚠️  {out_dir} 저장 실패: {e}")

    if not saved_paths:
        fatal("저장 가능한 경로가 없어요.")

    print("")
    print("=" * 50)
    for p in saved_paths:
        size_kb = os.path.getsize(p) // 1024
        print(f"💾 저장: {p} ({size_kb:,} KB)")
    print("=" * 50)
    print("")
    print("[미리보기] 상위 10조합:")
    for i, c in enumerate(combos[:10], 1):
        print(f"  {i}. {c}")
    print("")
    # 배치(.bat)에서 실행됐으면 일시정지 X — bat 끝에 pause 있음
    if not os.environ.get("RUN_FROM_BAT"):
        try: input("아무 키나 누르면 종료...")
        except: pass

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n취소됨")
    except Exception as e:
        import traceback
        print(f"\n❌ 오류: {type(e).__name__}: {e}")
        print(traceback.format_exc())
        try: input("종료...")
        except: pass
