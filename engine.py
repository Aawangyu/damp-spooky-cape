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
    
    # 加入 user_id 字段实现多用户隔离
    conn.execute("""CREATE TABLE IF NOT EXISTS predictions (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT, target_period TEXT, 
        front_numbers TEXT, back_numbers TEXT, front_probs TEXT, back_probs TEXT, 
        created_at TEXT, hit_level TEXT DEFAULT '待开奖', hit_front INTEGER DEFAULT 0, hit_back INTEGER DEFAULT 0
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS lessons (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT, period TEXT, 
        pred_sum INTEGER, actual_sum INTEGER, sum_delta INTEGER, 
        pred_odd INTEGER, actual_odd INTEGER, odd_delta INTEGER,
        reason TEXT, created_at TEXT
    )""")
    
    # 兼容处理：如果旧表没有 user_id，自动加上
    try: conn.execute("ALTER TABLE predictions ADD COLUMN user_id TEXT DEFAULT 'default'")
    except: pass
    try: conn.execute("ALTER TABLE lessons ADD COLUMN user_id TEXT DEFAULT 'default'")
    except: pass
    
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

def comb(n, m):
    if n < m: return 0
    if m == 0 or m == n: return 1
    return math.factorial(n) // (math.factorial(m) * math.factorial(n - m))

# 🔥 读取当前用户的历史经验
def get_global_correction(user_id):
    init_db()
    conn = get_conn()
    rows = conn.execute("SELECT sum_delta, odd_delta FROM lessons WHERE user_id = ?", (user_id,)).fetchall()
    conn.close()
    
    if not rows: 
        return {"avg_sum_delta": 0, "avg_odd_delta": 0, "total_lessons": 0}
    
    total_sum_delta = sum(r[0] for r in rows)
    total_odd_delta = sum(r[1] for r in rows)
    n = len(rows)
    
    return {
        "avg_sum_delta": round(total_sum_delta / n, 2),
        "avg_odd_delta": round(total_odd_delta / n, 2),
        "total_lessons": n
    }

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

    bayes_prob = {}
    for n in range(1, 36):
        alpha = 1 + f_freq[n]
        beta_param = 1 + (total * 5 / 35) - f_freq[n]
        if beta_param < 1: beta_param = 1
        bayes_prob[n] = alpha / (alpha + beta_param)
        
    dirichlet_prob = {}
    total_b_draws = total * 2
    for n in range(1, 13):
        dirichlet_prob[n] = (b_freq[n] + 1) / (total_b_draws + 12)

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

# 🔥 传入 user_id，只调取该用户的经验
def generate_scientific(weights, last_front, user_id):
    fw = weights["front_prob"]
    bw = weights["back_prob"]
    correction = get_global_correction(user_id) 
    
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
        dynamic_lower = 75 + correction["avg_sum_delta"]
        dynamic_upper = 110 + correction["avg_sum_delta"]
        
        if s < dynamic_lower or s > dynamic_upper: continue
        
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

def save_prediction(weights, target_period, front, back, user_id):
    init_db()
    conn = get_conn()
    target_period = target_period.strip() or "未指定"
    fp = {str(n): weights["front_prob"][n] for n in front}
    bp = {str(n): weights["back_prob"][n] for n in back}
    conn.execute("INSERT INTO predictions (user_id, target_period, front_numbers, back_numbers, front_probs, back_probs, created_at) VALUES (?,?,?,?,?,?,?)",
        (user_id, target_period, json.dumps(front), json.dumps(back), json.dumps(fp, ensure_ascii=False), json.dumps(bp, ensure_ascii=False), datetime.now().strftime("%Y-%m-%d %H:%M")))
    conn.commit()
    conn.close()

# 🔥 复盘时，把教训记在对应 user_id 的头上
def review_all():
    init_db()
    conn = get_conn()
    draws = {r[0]: r for r in conn.execute("SELECT period,front1,front2,front3,front4,front5,back1,back2 FROM draws").fetchall()}
    pending = conn.execute("SELECT id, user_id, target_period, front_numbers, back_numbers FROM predictions WHERE hit_level='待开奖'").fetchall()

    for pid, uid, tp, fj, bj in pending:
        if tp not in draws: continue
        actual_front_list = draws[tp][1:6]
        actual_back_list = draws[tp][6:8]
        
        actual_front = set(actual_front_list)
        actual_back = set(actual_back_list)
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
        
        if level == "未中":
            pred_f_list = json.loads(fj)
            p_sum, a_sum = sum(pred_f_list), sum(actual_front_list)
            p_odd = sum(1 for n in pred_f_list if n%2==1)
            a_odd = sum(1 for n in actual_front_list if n%2==1)
            
            reason = []
            if abs(p_sum - a_sum) > 15: reason.append("和值偏差大")
            if p_odd != a_odd: reason.append("奇偶比例不符")
            if not reason: reason.append("独立随机事件")
            
            conn.execute("""INSERT INTO lessons 
                (user_id, period, pred_sum, actual_sum, sum_delta, pred_odd, actual_odd, odd_delta, reason, created_at) 
                VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (uid, tp, p_sum, a_sum, a_sum - p_sum, p_odd, a_odd, a_odd - p_odd, "，".join(reason), datetime.now().strftime("%Y-%m-%d %H:%M")))
            
    conn.commit()
    conn.close()

def get_predictions(user_id):
    init_db()
    conn = get_conn()
    rows = conn.execute("SELECT id,target_period,front_numbers,back_numbers,created_at,hit_level,hit_front,hit_back FROM predictions WHERE user_id = ? ORDER BY id DESC", (user_id,)).fetchall()
    conn.close()
    return rows

def get_all_lessons(user_id):
    init_db()
    conn = get_conn()
    rows = conn.execute("SELECT period, pred_sum, actual_sum, sum_delta, pred_odd, actual_odd, odd_delta, reason FROM lessons WHERE user_id = ? ORDER BY id DESC", (user_id,)).fetchall()
    conn.close()
    return rows