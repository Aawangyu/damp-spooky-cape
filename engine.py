import sqlite3
import random
import json
import math
from datetime import datetime
from collections import Counter
from itertools import combinations

DB = "dlt.db"
FRONT_POOL = list(range(1, 36))
BACK_POOL = list(range(1, 13))

def get_conn():
    return sqlite3.connect(DB)

def init_db():
    conn = get_conn()
    conn.execute("CREATE TABLE IF NOT EXISTS draws (period TEXT PRIMARY KEY, date TEXT, front1 INTEGER, front2 INTEGER, front3 INTEGER, front4 INTEGER, front5 INTEGER, back1 INTEGER, back2 INTEGER)")
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
    conn.execute("""CREATE TABLE IF NOT EXISTS backtest_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT, period TEXT, 
        simulations INTEGER, deep_analysis TEXT, created_at TEXT
    )""")
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

def get_global_correction(user_id):
    init_db()
    conn = get_conn()
    rows = conn.execute("SELECT sum_delta, odd_delta FROM lessons WHERE user_id = ?", (user_id,)).fetchall()
    conn.close()
    if not rows: return {"avg_sum_delta": 0, "avg_odd_delta": 0, "total_lessons": 0}
    total_sum_delta = sum(r[0] for r in rows)
    total_odd_delta = sum(r[1] for r in rows)
    n = len(rows)
    return {"avg_sum_delta": round(total_sum_delta / n, 2), "avg_odd_delta": round(total_odd_delta / n, 2), "total_lessons": n}

def get_advanced_weights():
    rows = get_all_draws()
    if len(rows) < 10: return None
    total = len(rows)
    f_freq, b_freq = Counter(), Counter()
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

    bayes_prob = {n: (1 + f_freq[n]) / ((1 + f_freq[n]) + max(1, 1 + (total * 5 / 35) - f_freq[n])) for n in range(1, 36)}
    dirichlet_prob = {n: (b_freq[n] + 1) / (total * 2 + 12) for n in range(1, 13)}

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

    sorted_nums = sorted(f_prob.items(), key=lambda x: x[1], reverse=True)
    return {
        "front_freq": f_freq, "back_freq": b_freq, "front_omit": f_omit, "back_omit": b_omit,
        "front_trans": f_trans, "front_prob": f_prob, "back_prob": b_prob,
        "bayes_prob": bayes_prob, "dirichlet_prob": dirichlet_prob, "total_draws": total,
        "hot_nums": [n for n, p in sorted_nums[:10]],
        "warm_nums": [n for n, p in sorted_nums[10:25]],
        "cold_nums": [n for n, p in sorted_nums[25:]]
    }

def generate_scientific(weights, last_front, last_back, user_id):
    fw, bw = weights["front_prob"], weights["back_prob"]
    correction = get_global_correction(user_id) 
    candidates = []

    # ================= 前区：8000次模拟选优 =================
    for _ in range(8000):
        available = list(range(1, 36))
        front = [random.choices(available, weights=[fw[n] + 0.01 for n in available], k=1)[0] for _ in range(5)]
        front = list(dict.fromkeys(front))
        if len(front) < 5: 
            front = sorted(random.sample(range(1, 36), 5))
        else:
            front.sort()

        score = sum([fw[n] for n in front])
        s = sum(front)
        if 75 <= s <= 110: score += 10.0
        odd = sum(1 for n in front if n % 2 == 1)
        if odd in (2, 3): score += 5.0

        if last_front:
            repeats = len(set(front) & set(last_front))
            if repeats in (1, 2): score += 8.0
            elif repeats > 2: score -= 15.0
        
        if abs(s - (90 + correction["avg_sum_delta"])) < 10: score += 3.0
        candidates.append({"front": front, "score": score})

    candidates.sort(key=lambda x: x["score"], reverse=True)
    pool_size = min(30, len(candidates))
    best_front = random.choice(candidates[:pool_size])["front"]

    # ================= 后区：全量组合打分，结合上期规律，随机择优 =================
    all_back_combos = list(combinations(range(1, 13), 2))
    back_candidates = []

    for combo in all_back_combos:
        b1, b2 = combo
        
        # 1. 基础权重分
        base_score = bw[b1] + bw[b2]
        
        # 2. 上期规律联系分（重号/邻号机制）
        trend_score = 0
        if last_back:
            for num in combo:
                if num in last_back:
                    trend_score += 1.5  # 重号加分（符合落号规律）
                if (num - 1 in last_back) or (num + 1 in last_back):
                    trend_score += 2.5  # 邻号给更高分（符合边号规律）
                    
        total_score = base_score + trend_score
        
        # 3. 惩罚机制：禁止完全复制上期的后区组合
        if last_back and set(combo) == set(last_back):
            total_score -= 20.0
            
        back_candidates.append({"back": list(combo), "score": total_score})

    # 对后区所有组合排序
    back_candidates.sort(key=lambda x: x["score"], reverse=True)
    
    # 在排名前 5 的后区神仙组合里，随机抽一个给你！
    # 这样既保证了绝对的合理性（包含上期邻号/重号），又不会死板地每次出 09, 11
    top_back_pool = random.choice(back_candidates[:5])["back"]

    return best_front, top_back_pool

def simulate_hit_test(weights, target_period, user_id):
    conn = get_conn()
    row = conn.execute("SELECT front1,front2,front3,front4,front5,back1,back2 FROM draws WHERE period = ?", (target_period,)).fetchone()
    
    if not row: 
        conn.close()
        return None, "未找到该期号数据"
    
    target_front = set(row[0:5])
    target_back = set(row[5:7])
    fw, bw = weights["front_prob"], weights["back_prob"]
    
    count = 0
    max_simulations = 5000000 
    
    while count < max_simulations:
        count += 1
        available = list(range(1, 36))
        front = []
        for _ in range(5):
            w = [fw[n] + 0.01 for n in available]
            pick = random.choices(available, weights=w, k=1)[0]
            front.append(pick)
            available.remove(pick)
        
        bavail = list(range(1, 13))
        back = []
        for _ in range(2):
            w = [bw[n] + 0.01 for n in bavail]
            pick = random.choices(bavail, weights=w, k=1)[0]
            back.append(pick)
            bavail.remove(pick)
        
        if set(front) == target_front and set(back) == target_back:
            f_list = sorted(list(target_front))
            b_list = sorted(list(target_back))
            sum_val = sum(f_list)
            odd_count = sum(1 for n in f_list if n%2==1)
            
            hot_hits = len(set(f_list) & set(weights["hot_nums"]))
            cold_hits = len(set(f_list) & set(weights["cold_nums"]))
            
            analysis = f"该期号码和值为 {sum_val}，奇偶比为 {odd_count}:{5-odd_count}。"
            analysis += f"前区命中了 {hot_hits} 个热号，{5-hot_hits-cold_hits} 个温号，{cold_hits} 个冷号。"
            
            if sum_val >= 75 and sum_val <= 110:
                analysis += " 整体形态属于历史高概率区间。"
            else:
                analysis += " 形态属于极端偏态，能开出纯属极小概率的随机爆发。"
                
            conn.execute("INSERT INTO backtest_logs (user_id, period, simulations, deep_analysis, created_at) VALUES (?,?,?,?,?)",
                (user_id, target_period, count, analysis, datetime.now().strftime("%Y-%m-%d %H:%M")))
            conn.commit()
            conn.close()
            return count, analysis
            
    conn.close()
    return max_simulations, "超过 500 万次仍未中，符合极低的中奖率"

def get_backtest_logs(user_id):
    init_db()
    conn = get_conn()
    rows = conn.execute("SELECT period, simulations, deep_analysis, created_at FROM backtest_logs WHERE user_id = ? ORDER BY id DESC", (user_id,)).fetchall()
    conn.close()
    return rows

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
        pred_front = set(json.loads(fj))
        hit_f = len(pred_front & actual_front)
        hit_b = len(set(json.loads(bj)) & set(actual_back_list))

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
            conn.execute("INSERT INTO lessons (user_id, period, pred_sum, actual_sum, sum_delta, pred_odd, actual_odd, odd_delta, reason, created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
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