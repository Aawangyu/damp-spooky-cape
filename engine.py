import sqlite3
import random
import json
import math
from datetime import datetime
from collections import Counter

DB = "dlt.db"
FRONT_POOL = list(range(1, 36))
BACK_POOL = list(range(1, 13))

def get_conn():
    return sqlite3.connect(DB)

def init_db():
    conn = get_conn()
    conn.execute("CREATE TABLE IF NOT EXISTS draws (period TEXT PRIMARY KEY, date TEXT, front1 INTEGER, front2 INTEGER, front3 INTEGER, front4 INTEGER, front5 INTEGER, back1 INTEGER, back2 INTEGER)")
    conn.execute("CREATE TABLE IF NOT EXISTS predictions (id INTEGER PRIMARY KEY AUTOINCREMENT, target_period TEXT, front_numbers TEXT, back_numbers TEXT, front_probs TEXT, back_probs TEXT, created_at TEXT, hit_level TEXT DEFAULT '待开奖', hit_front INTEGER DEFAULT 0, hit_back INTEGER DEFAULT 0)")
    conn.commit()
    conn.close()

def draw_count():
    init_db()
    conn = get_conn()
    n = conn.execute("SELECT COUNT(*) FROM draws").fetchone()[0]
    conn.close()
    return n

def get_all_draws():
    init_db()
    conn = get_conn()
    rows = conn.execute("SELECT period, date, front1, front2, front3, front4, front5, back1, back2 FROM draws ORDER BY period DESC").fetchall()
    conn.close()
    return rows

# 超几何分布组合数计算
def comb(n, m):
    if m == 0 or m == n: return 1
    return math.factorial(n) // (math.factorial(m) * math.factorial(n - m))

# 全量高级数学模型
def get_advanced_weights():
    rows = get_all_draws()
    if len(rows) < 10: return None
    
    total = len(rows)
    
    f_freq = Counter()
    b_freq = Counter()
    for r in rows:
        f_freq.update(r[2:7])
        b_freq.update(r[7:9])

    f_omit = {n: total for n in range(1, 36)}
    b_omit = {n: total for n in range(1, 13)}
    for idx, r in enumerate(rows):
        for n in r[2:7]:
            if f_omit[n] == total: f_omit[n] = idx
        for n in r[7:9]:
            if b_omit[n] == total: b_omit[n] = idx

    f_trans = {n: 0 for n in range(1, 36)}
    for i in range(min(50, total - 1)):
        prev_nums = set(rows[i+1][2:7])
        curr_nums = set(rows[i][2:7])
        for n in curr_nums:
            if n in prev_nums: f_trans[n] += 1

    # 贝叶斯后验估计
    bayes_prob = {}
    for n in range(1, 36):
        alpha = 1 + f_freq[n]
        beta_param = 1 + (total * 5 / 35) - f_freq[n]
        if beta_param < 1: beta_param = 1
        bayes_prob[n] = alpha / (alpha + beta_param)
        
    # 后区 Dirichlet 平滑
    dirichlet_prob = {}
    total_b_draws = total * 2
    for n in range(1, 13):
        dirichlet_prob[n] = (b_freq[n] + 1) / (total_b_draws + 12)

    # 综合权重融合
    f_score = {}
    for n in range(1, 36):
        omit_score = 1.0 / (f_omit[n] + 1.5)
        trans_score = f_trans[n] / 50.0
        f_score[n] = (bayes_prob[n] * 100) * 0.3 + omit_score * 20 + trans_score * 20 + (f_freq[n]/total)*30
        
    sum_f = sum(f_score.values())
    f_prob = {n: round((f_score[n] / sum_f) * 100, 2) for n in range(1, 36)}
    
    b_score = {}
    for n in range(1, 13):
        b_omit_score = 1.0 / (b_omit[n] + 1.5)
        b_score[n] = dirichlet_prob[n] * 100 * 0.6 + b_omit_score * 30
    sum_b = sum(b_score.values())
    b_prob = {n: round((b_score[n] / sum_b) * 100, 2) for n in range(1, 13)}

    return {
        "front_freq": f_freq, "back_freq": b_freq,
        "front_omit": f_omit, "back_omit": b_omit,
        "front_trans": f_trans,
        "front_prob": f_prob, "back_prob": b_prob,
        "bayes_prob": bayes_prob, "dirichlet_prob": dirichlet_prob,
        "total_draws": total
    }

# 科学模拟生成
def generate_scientific(weights, last_front):
    fw = weights["front_prob"]
    bw = weights["back_prob"]
    
    best_candidate = None
    highest_score = -1

    for _ in range(8000):
        available = list(range(1, 36))
        front = []
        for _ in range(5):
            w = [fw[n] + 0.01 for n in available]
            pick = random.choices(available, weights=w, k=1)[0]
            front.append(pick)
            available.remove(pick)
        front.sort()

        bavail = list(range(1, 13))
        back = []
        for _ in range(2):
            w = [bw[n] + 0.01 for n in bavail]
            pick = random.choices(bavail, weights=w, k=1)[0]
            back.append(pick)
            bavail.remove(pick)
        back.sort()

        s = sum(front)
        if s < 75 or s > 110: continue
        odd = sum(1 for n in front if n % 2 == 1)
        if odd not in (2, 3): continue
        
        if last_front:
            repeats = len(set(front) & set(last_front))
            neighbors = 0
            for n in front:
                if (n-1 in last_front) or (n+1 in last_front): neighbors += 1
            if repeats > 2 or neighbors > 2: continue

        score = sum([fw[n] for n in front]) + sum([bw[n] for n in back])
        if score > highest_score:
            highest_score = score
            best_candidate = (front, back)

    if not best_candidate:
        return sorted(random.sample(range(1, 36), 5)), sorted(random.sample(range(1, 13), 2))
    return best_candidate

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

def get_predictions():
    init_db()
    conn = get_conn()
    rows = conn.execute("SELECT id,target_period,front_numbers,back_numbers,created_at,hit_level,hit_front,hit_back FROM predictions ORDER BY id DESC").fetchall()
    conn.close()
    return rows