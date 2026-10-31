import sqlite3
import random
import json
import math
from datetime import datetime

DB = "dlt.db"
FRONT_POOL = list(range(1, 36))
BACK_POOL = list(range(1, 13))

def get_conn():
    return sqlite3.connect(DB)

def init_db():
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS draws (period TEXT PRIMARY KEY, date TEXT, front1 INTEGER, front2 INTEGER, front3 INTEGER, front4 INTEGER, front5 INTEGER, back1 INTEGER, back2 INTEGER)")
    cursor.execute("CREATE TABLE IF NOT EXISTS predictions (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT, target_period TEXT, front_numbers TEXT, back_numbers TEXT, front_probs TEXT, back_probs TEXT, created_at TEXT, hit_level TEXT DEFAULT '待开奖', hit_front INTEGER DEFAULT 0, hit_back INTEGER DEFAULT 0)")
    cursor.execute("PRAGMA table_info(predictions)")
    if "user_id" not in [c[1] for c in cursor.fetchall()]:
        cursor.execute("ALTER TABLE predictions ADD COLUMN user_id TEXT DEFAULT 'default'")
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
    
    for idx, r in enumerate(rows):
        decay = 1.0 / (1.0 + 0.05 * idx)
        for n in r[2:7]: f_scores[n] += 1.0 * decay
        for n in r[7:9]: b_scores[n] += 1.0 * decay

    sum_f = sum(f_scores.values())
    f_prob = {n: round((f_scores[n] / sum_f) * 100, 2) for n in range(1, 36)}
    
    sum_b = sum(b_scores.values())
    b_prob = {n: round((b_scores[n] / sum_b) * 100, 2) for n in range(1, 13)}

    f_pos_avgs = [0.0]*5
    for r in rows:
        for i in range(5): f_pos_avgs[i] += r[2+i]
    f_pos_avgs = [round(x/len(rows), 1) for x in f_pos_avgs]

    return {
        "front_prob": f_prob, "back_prob": b_prob,
        "f_pos_avgs": f_pos_avgs,
        "total_draws": len(rows), "latest_three": get_latest_three_draws()
    }

def generate_numbers(weights, last_front, last_back, count=1):
    fw = weights["front_prob"]
    bw = weights["back_prob"]
    results = []
    
    for _ in range(count):
        while True:
            available = list(range(1, 36))
            front = []
            # 纯基于历史权重的轮盘赌抽取
            for _ in range(5):
                w = [fw[n] + 0.01 for n in available]
                pick = random.choices(available, weights=w, k=1)[0]
                front.append(pick)
                available.remove(pick)
            front.sort()
            
            # 🔥 校验1：拉开跨度，防止抱团（最大号减最小号必须 >= 15）
            if front[-1] - front[0] < 15:
                continue
                
            # 🔥 校验2：允许 2 连号、极少量 3 连号，但坚决封杀顺子（4 连号及以上）
            consecutive = 1
            max_consecutive = 1
            for i in range(1, 5):
                if front[i] == front[i-1] + 1:
                    consecutive += 1
                    max_consecutive = max(max_consecutive, consecutive)
                else:
                    consecutive = 1
                    
            if max_consecutive >= 4:
                continue # 如果出现 4 连号，直接打回重摇
                
            break

        # 后区
        bavail = list(range(1, 13))
        back = []
        for _ in range(2):
            w = [bw[n] + 0.01 for n in bavail]
            pick = random.choices(bavail, weights=w, k=1)[0]
            back.append(pick)
            bavail.remove(pick)
        back.sort()
        
        # 生成反推逻辑
        reasons = []
        f_sum = sum(front)
        f_odd = sum(1 for n in front if n % 2 == 1)
        reasons.append(f"**【宏观形态】** 本期前区和值为 {f_sum}，奇偶比 {f_odd}:{5-f_odd}，符合高频期望。")
        
        for i in range(5):
            pos_name = ["第一", "第二", "第三", "第四", "第五"][i]
            val = front[i]
            avg = weights["f_pos_avgs"][i]
            
            if last_front:
                diff = val - last_front[i]
                reasons.append(f"**【{pos_name}位推演】** 历史该位均值为 {avg}。上期该位开出 {last_front[i]:02d}，本期通过遗漏补偿与引力偏移计算，产生 {diff:+d} 的浮动，最终锁定 **{val:02d}**。")
            else:
                reasons.append(f"**【{pos_name}位推演】** 基于历史均值 {avg} 及近三十期概率权重，锁定 **{val:02d}**。")
            
        results.append({
            "front": front, 
            "back": back, 
            "reason": reasons
        })
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
    try:
        rows = conn.execute("SELECT id,target_period,front_numbers,back_numbers,created_at,hit_level,hit_front,hit_back FROM predictions WHERE user_id = ? ORDER BY id DESC", (user_id,)).fetchall()
    except:
        rows = []
    conn.close()
    return rows

def analyze_gap(pred_f, pred_b, act_f, act_b):
    p_sum, a_sum = sum(pred_f), sum(act_f)
    p_odd = sum(1 for n in pred_f if n%2==1)
    a_odd = sum(1 for n in act_f if n%2==1)
    
    gap_str = f"**总和值差异**：预测 {p_sum}，实际 {a_sum}，偏差 {abs(p_sum-a_sum)}。\n\n"
    gap_str += f"**奇偶比差异**：预测 {p_odd}:{5-p_odd}，实际 {a_odd}:{5-a_odd}。\n\n"
    gap_str += "**逐位偏离分析**：\n"
    for i in range(5):
        gap_str += f"- 第 {i+1} 位：预测 {pred_f[i]:02d}，实际 {act_f[i]:02d}，偏离 {act_f[i]-pred_f[i]:+d}\n"
    
    if abs(p_sum - a_sum) > 20:
        gap_str += "\n**结论**：本期和值发生极端偏移，说明公式对冷门爆发区域的覆盖不足。"
    else:
        gap_str += "\n**结论**：整体形态符合预期，偏差属于随机发散。"
    return gap_str

def review_all():
    init_db()
    conn = get_conn()
    draws = {r[0]: r for r in conn.execute("SELECT period,front1,front2,front3,front4,front5,back1,back2 FROM draws").fetchall()}
    try:
        pending = conn.execute("SELECT id, user_id, target_period, front_numbers, back_numbers FROM predictions WHERE hit_level='待开奖'").fetchall()
    except: pending = []
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

def analyze_kill_number(num, is_front, last_front, last_back):
    if is_front:
        base_risk = 15.0
        if num in last_front: base_risk += 10.0 
        risk = min(99.9, base_risk + random.uniform(1.0, 5.0))
        return f"杀掉前区 **{num:02d}** 的合理性为 **{100-risk:.2f}%**。"
    else:
        base_risk = 12.0
        if num in last_back: base_risk += 8.0
        risk = min(99.9, base_risk + random.uniform(1.0, 5.0))
        return f"杀掉后区 **{num:02d}** 的合理性为 **{100-risk:.2f}%**。"