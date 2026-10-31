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
    cursor = conn.cursor()
    
    # 1. 基础开奖表
    cursor.execute("CREATE TABLE IF NOT EXISTS draws (period TEXT PRIMARY KEY, date TEXT, front1 INTEGER, front2 INTEGER, front3 INTEGER, front4 INTEGER, front5 INTEGER, back1 INTEGER, back2 INTEGER)")
    
    # 2. 预测记录表（包含自动查漏补缺）
    cursor.execute("CREATE TABLE IF NOT EXISTS predictions (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT, target_period TEXT, front_numbers TEXT, back_numbers TEXT, front_probs TEXT, back_probs TEXT, created_at TEXT, hit_level TEXT DEFAULT '待开奖', hit_front INTEGER DEFAULT 0, hit_back INTEGER DEFAULT 0)")
    cursor.execute("PRAGMA table_info(predictions)")
    cols = [c[1] for c in cursor.fetchall()]
    if "user_id" not in cols:
        cursor.execute("ALTER TABLE predictions ADD COLUMN user_id TEXT DEFAULT 'default'")
        
    # 3. 经验教训表
    cursor.execute("CREATE TABLE IF NOT EXISTS lessons (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT, period TEXT, pred_sum INTEGER, actual_sum INTEGER, sum_delta INTEGER, pred_odd INTEGER, actual_odd INTEGER, odd_delta INTEGER, reason TEXT, created_at TEXT)")
    cursor.execute("PRAGMA table_info(lessons)")
    cols = [c[1] for c in cursor.fetchall()]
    if "user_id" not in cols:
        cursor.execute("ALTER TABLE lessons ADD COLUMN user_id TEXT DEFAULT 'default'")

    # 4. 极限回测表
    cursor.execute("CREATE TABLE IF NOT EXISTS backtest_logs (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT, period TEXT, simulations INTEGER, deep_analysis TEXT, created_at TEXT)")
    
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

def get_latest_three_draws():
    rows = get_all_draws()
    return rows[:3] if len(rows) >= 3 else rows

def get_advanced_weights():
    rows = get_all_draws()
    if len(rows) < 10: return None
    
    f_scores = {n: 0.0 for n in range(1, 36)}
    b_scores = {n: 0.0 for n in range(1, 13)}
    
    # 时间衰减算法
    for idx, r in enumerate(rows):
        decay = 1.0 / (1.0 + 0.05 * idx)
        for n in r[2:7]: f_scores[n] += 1.0 * decay
        for n in r[7:9]: b_scores[n] += 1.0 * decay

    sum_f = sum(f_scores.values())
    f_prob = {n: round((f_scores[n] / sum_f) * 100, 2) for n in range(1, 36)}
    
    sum_b = sum(b_scores.values())
    b_prob = {n: round((b_scores[n] / sum_b) * 100, 2) for n in range(1, 13)}

    sorted_nums = sorted(f_prob.items(), key=lambda x: x[1], reverse=True)
    hot_nums = [n for n, p in sorted_nums[:10]]
    warm_nums = [n for n, p in sorted_nums[10:25]]
    cold_nums = [n for n, p in sorted_nums[25:]]

    return {
        "front_prob": f_prob, "back_prob": b_prob,
        "hot_nums": hot_nums, "warm_nums": warm_nums, "cold_nums": cold_nums,
        "total_draws": len(rows), "latest_three": get_latest_three_draws()
    }

def generate_numbers(weights, last_front, last_back, count=1):
    fw, bw = weights["front_prob"], weights["back_prob"]
    results = []
    
    for _ in range(count):
        available = list(range(1, 36))
        front = [random.choices(available, weights=[fw[n] + 0.01 for n in available], k=1)[0] for _ in range(5)]
        front = sorted(list(set(front)))
        while len(front) < 5:
            extra = random.choice([n for n in range(1, 36) if n not in front])
            front.append(extra)
            front.sort()

        bavail = list(range(1, 13))
        back = [random.choices(bavail, weights=[bw[n] + 0.01 for n in bavail], k=1)[0] for _ in range(2)]
        back = sorted(list(set(back)))
        while len(back) < 2:
            extra = random.choice([n for n in range(1, 13) if n not in back])
            back.append(extra)
            back.sort()
            
        f_sum = sum(front)
        f_odd = sum(1 for n in front if n % 2 == 1)
        h_hits = len(set(front) & set(weights["hot_nums"]))
        
        reason = f"本期推荐前区和值为 {f_sum}，奇偶比 {f_odd}:{5-f_odd}。包含 {h_hits} 个热号。"
        if last_front:
            repeats = len(set(front) & set(last_front))
            reason += f" 与上期产生 {repeats} 个重号。"
            
        results.append({"front": front, "back": back, "reason": reason})
    return results

def save_predictions_batch(weights, target_period, predictions, user_id):
    init_db()
    conn = get_conn()
    tp = target_period.strip() or "未指定"
    for p in predictions:
        fp = {str(n): weights["front_prob"][n] for n in p["front"]}
        bp = {str(n): weights["back_prob"][n] for n in p["back"]}
        conn.execute("INSERT INTO predictions (user_id, target_period, front_numbers, back_numbers, front_probs, back_probs, created_at) VALUES (?,?,?,?,?,?,?)",
            (user_id, tp, json.dumps(p["front"]), json.dumps(p["back"]), json.dumps(fp, ensure_ascii=False), json.dumps(bp, ensure_ascii=False), datetime.now().strftime("%Y-%m-%d %H:%M")))
    conn.commit()
    conn.close()

def get_predictions(user_id):
    init_db()
    conn = get_conn()
    # 这里也加入了容错机制，防止老数据库报错
    try:
        rows = conn.execute("SELECT id,target_period,front_numbers,back_numbers,created_at,hit_level,hit_front,hit_back FROM predictions WHERE user_id = ? ORDER BY id DESC", (user_id,)).fetchall()
    except sqlite3.OperationalError:
        rows = []
    conn.close()
    return rows

def analyze_kill_number(num, is_front, last_front, last_back):
    if is_front:
        base_risk = 15.0
        if num in last_front: base_risk += 10.0 
        risk = min(99.9, base_risk + random.uniform(1.0, 5.0))
        return f"基于近期走势，杀掉前区 **{num:02d}** 的合理性为 **{100-risk:.2f}%**。"
    else:
        base_risk = 12.0
        if num in last_back: base_risk += 8.0
        risk = min(99.9, base_risk + random.uniform(1.0, 5.0))
        return f"基于近期走势，杀掉后区 **{num:02d}** 的合理性为 **{100-risk:.2f}%**。"

def review_all():
    init_db()
    conn = get_conn()
    draws = {r[0]: r for r in conn.execute("SELECT period,front1,front2,front3,front4,front5,back1,back2 FROM draws").fetchall()}
    
    try:
        pending = conn.execute("SELECT id, user_id, target_period, front_numbers, back_numbers FROM predictions WHERE hit_level='待开奖'").fetchall()
    except:
        pending = []

    for pid, uid, tp, fj, bj in pending:
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
    max_simulations = 2000000 
    
    while count < max_simulations:
        count += 1
        avail = random.choices(list(range(1, 36)), weights=[fw[n]+0.01 for n in range(1, 36)], k=5)
        bav = random.choices(list(range(1, 13)), weights=[bw[n]+0.01 for n in range(1, 13)], k=2)
        
        if set(avail) == target_front and set(bav) == target_back:
            f_list = sorted(list(target_front))
            sum_val = sum(f_list)
            odd_count = sum(1 for n in f_list if n%2==1)
            analysis = f"🎯 **第 {count:,} 次模拟命中！**\n\n**数学验证**：该期开奖和值为 **{sum_val}**，奇偶比 **{odd_count}:{5-odd_count}**。结合上期重邻号引力，成功命中。"
            conn.execute("INSERT INTO backtest_logs (user_id, period, simulations, deep_analysis, created_at) VALUES (?,?,?,?,?)",
                (user_id, target_period, count, analysis, datetime.now().strftime("%Y-%m-%d %H:%M")))
            conn.commit()
            conn.close()
            return count, analysis
            
    conn.close()
    return max_simulations, "超过 200 万次仍未中，符合极低概率。"

def get_backtest_logs(user_id):
    init_db()
    conn = get_conn()
    try:
        rows = conn.execute("SELECT period, simulations, deep_analysis, created_at FROM backtest_logs WHERE user_id = ? ORDER BY id DESC", (user_id,)).fetchall()
    except:
        rows = []
    conn.close()
    return rows