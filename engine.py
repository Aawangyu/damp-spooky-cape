import sqlite3
import random
import json
from datetime import datetime

DB = "dlt.db"
FRONT_POOL = list(range(1, 36))
BACK_POOL = list(range(1, 13))

def get_conn():
    return sqlite3.connect(DB)

def init_db():
    conn = get_conn()
    conn.execute("CREATE TABLE IF NOT EXISTS draws (period TEXT PRIMARY KEY, date TEXT, front1 INTEGER, front2 INTEGER, front3 INTEGER, front4 INTEGER, front5 INTEGER, back1 INTEGER, back2 INTEGER)")
    conn.execute("CREATE TABLE IF NOT EXISTS predictions (id INTEGER PRIMARY KEY AUTOINCREMENT, target_period TEXT, front_numbers TEXT, back_numbers TEXT, front_probs TEXT, back_probs TEXT, created_at TEXT, hit_level TEXT DEFAULT '待开奖', hit_front INTEGER DEFAULT 0, hit_back INTEGER DEFAULT 0)")
    
    # 核心保底方案：如果数据库为空，自动塞入 100 期模拟数据！
    count = conn.execute("SELECT COUNT(*) FROM draws").fetchone()[0]
    if count == 0:
        for i in range(1, 101):
            period = str(24000 + i)
            f = sorted(random.sample(FRONT_POOL, 5))
            b = sorted(random.sample(BACK_POOL, 2))
            conn.execute("INSERT INTO draws VALUES (?,?,?,?,?,?,?,?,?)", (period, "2024-01-01", f[0], f[1], f[2], f[3], f[4], b[0], b[1]))
    
    conn.commit()
    conn.close()

def draw_count():
    init_db()
    conn = get_conn()
    n = conn.execute("SELECT COUNT(*) FROM draws").fetchone()[0]
    conn.close()
    return n

def compute_weights():
    init_db()
    conn = get_conn()
    rows = conn.execute("SELECT front1,front2,front3,front4,front5,back1,back2 FROM draws ORDER BY period DESC").fetchall()
    conn.close()
    if not rows: return None

    front_freq = {n: 0 for n in FRONT_POOL}
    back_freq = {n: 0 for n in BACK_POOL}
    for r in rows:
        for n in r[:5]: front_freq[n] += 1
        for n in r[5:]: back_freq[n] += 1

    front_rows = [r[:5] for r in rows]
    back_rows = [r[5:] for r in rows]

    def omission(nums_list, max_num):
        result = {}
        for n in range(1, max_num + 1):
            for i, row in enumerate(nums_list):
                if n in row:
                    result[n] = i
                    break
            else:
                result[n] = len(nums_list)
        return result

    front_omit = omission(front_rows, 35)
    back_omit = omission(back_rows, 12)

    total_f = sum(front_freq.values()) or 1
    total_fo = sum(front_omit.values()) or 1
    front_weight = {n: 0.6 * (front_freq[n] / total_f) + 0.4 * (front_omit[n] / total_fo) for n in FRONT_POOL}

    total_b = sum(back_freq.values()) or 1
    total_bo = sum(back_omit.values()) or 1
    back_weight = {n: 0.6 * (back_freq[n] / total_b) + 0.4 * (back_omit[n] / total_bo) for n in BACK_POOL}

    sum_fw = sum(front_weight.values()) or 1
    sum_bw = sum(back_weight.values()) or 1

    return {
        "front_freq": front_freq, "back_freq": back_freq,
        "front_omit": front_omit, "back_omit": back_omit,
        "front_weight": front_weight, "back_weight": back_weight,
        "front_prob": {n: round(front_weight[n] / sum_fw * 100, 2) for n in FRONT_POOL},
        "back_prob": {n: round(back_weight[n] / sum_bw * 100, 2) for n in BACK_POOL},
        "total_draws": len(rows),
    }

def constraint_ok(front, back):
    s = sum(front)
    if s < 75 or s > 110: return False
    odd = sum(1 for n in front if n % 2 == 1)
    if odd not in (2, 3): return False
    z1 = sum(1 for n in front if 1 <= n <= 12)
    z2 = sum(1 for n in front if 13 <= n <= 24)
    z3 = 5 - z1 - z2
    if max(z1, z2, z3) - min(z1, z2, z3) > 2: return False
    return True

def generate_one(weights):
    fw = weights["front_weight"]
    bw = weights["back_weight"]
    for _ in range(5000):
        available = FRONT_POOL.copy()
        front = []
        for _ in range(5):
            w = [fw[n] for n in available]
            pick = random.choices(available, weights=w, k=1)[0]
            front.append(pick)
            available.remove(pick)
        front.sort()

        bavail = BACK_POOL.copy()
        back = []
        for _ in range(2):
            w = [bw[n] for n in bavail]
            pick = random.choices(bavail, weights=w, k=1)[0]
            back.append(pick)
            bavail.remove(pick)
        back.sort()
        if constraint_ok(front, back): return front, back

    while True:
        front = sorted(random.sample(FRONT_POOL, 5))
        back = sorted(random.sample(BACK_POOL, 2))
        if constraint_ok(front, back): return front, back

def save_prediction(weights, target_period, front, back):
    init_db()
    conn = get_conn()
    target_period = target_period.strip() or "未指定"
    fp = {str(n): weights["front_prob"][n] for n in front}
    bp = {str(n): weights["back_prob"][n] for n in back}
    conn.execute("INSERT INTO predictions (target_period, front_numbers, back_numbers, front_probs, back_probs, created_at) VALUES (?,?,?,?,?,?)",
        (target_period, json.dumps(front), json.dumps(back), json.dumps(fp, ensure_ascii=False), json.dumps(bp, ensure_ascii=False), datetime.now().strftime("%Y-%m-%d %H:%M")))
    conn.commit()
    conn.close()

def review_all():
    init_db()
    conn = get_conn()
    draws = {r[0]: r for r in conn.execute("SELECT period,front1,front2,front3,front4,front5,back1,back2 FROM draws").fetchall()}
    pending = conn.execute("SELECT id,target_period,front_numbers,back_numbers FROM predictions WHERE hit_level='待开奖'").fetchall()

    for pid, tp, fj, bj in pending:
        if tp not in draws: continue
        actual_front = set(draws[tp][1:6])
        actual_back = set(draws[tp][6:8])
        pred_front = set(json.loads(fj))
        pred_back = set(json.loads(bj))
        hit_f = len(pred_front & actual_front)
        hit_b = len(pred_back & actual_back)

        level = "未中"
        if hit_f == 5 and hit_b == 2: level = "一等奖"
        elif hit_f == 5 and hit_b == 1: level = "二等奖"
        elif hit_f == 5 and hit_b == 0: level = "三等奖"
        elif hit_f == 4 and hit_b == 2: level = "四等奖"
        elif hit_f == 4 and hit_b == 1: level = "五等奖"
        elif hit_f == 3 and hit_b == 2: level = "六等奖"
        elif hit_f == 4 and hit_b == 0: level = "七等奖"
        elif (hit_f == 3 and hit_b == 1) or (hit_f == 2 and hit_b == 2): level = "八等奖"
        elif (hit_f == 3 and hit_b == 0) or (hit_f == 1 and hit_b == 2) or (hit_f == 2 and hit_b == 1) or (hit_f == 0 and hit_b == 2): level = "九等奖"

        conn.execute("UPDATE predictions SET hit_level=?, hit_front=?, hit_back=? WHERE id=?", (level, hit_f, hit_b, pid))
    conn.commit()
    conn.close()

def get_predictions():
    init_db()
    conn = get_conn()
    rows = conn.execute("SELECT id,target_period,front_numbers,back_numbers,created_at,hit_level,hit_front,hit_back FROM predictions ORDER BY id DESC").fetchall()
    conn.close()
    return rows
