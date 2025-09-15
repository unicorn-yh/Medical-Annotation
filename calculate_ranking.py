# calculate_ranking.py (Updated for multi-metric)
import json
from collections import defaultdict

RESULTS_FILE = 'results.jsonl'
# --- NEW: Define all metric keys we want to analyze ---
METRIC_KEYS = [
    'winner_overall', 
    'winner_efficiency', 
    'winner_safety', 
    'winner_empathy'
]

def calculate_model_ranking():
    try:
        with open(RESULTS_FILE, 'r', encoding='utf-8') as f:
            results = [json.loads(line) for line in f]
    except FileNotFoundError:
        print(f"错误: 结果文件 '{RESULTS_FILE}' 未找到。")
        return

    if not results:
        print("没有可供分析的标注数据。")
        return

    # --- MODIFIED: Loop through each metric and calculate ranks ---
    for metric_key in METRIC_KEYS:
        stats = defaultdict(lambda: {'wins': 0, 'losses': 0, 'ties': 0, 'comparisons': 0})

        for res in results:
            # Skip if a result line somehow doesn't have this metric
            if metric_key not in res:
                continue

            model_a = res['model_a']
            model_b = res['model_b']
            winner = res[metric_key]

            stats[model_a]['comparisons'] += 1
            stats[model_b]['comparisons'] += 1

            if winner == model_a:
                stats[model_a]['wins'] += 1
                stats[model_b]['losses'] += 1
            elif winner == model_b:
                stats[model_b]['wins'] += 1
                stats[model_a]['losses'] += 1
            elif winner == 'tie':
                stats[model_a]['ties'] += 1
                stats[model_b]['ties'] += 1

        if not stats:
            continue

        leaderboard = []
        for model, data in stats.items():
            win_rate = data['wins'] / data['comparisons'] if data['comparisons'] > 0 else 0
            leaderboard.append({
                'model': model, 'win_rate': win_rate, 'wins': data['wins'],
                'losses': data['losses'], 'ties': data['ties'], 'comparisons': data['comparisons']
            })

        leaderboard.sort(key=lambda x: x['win_rate'], reverse=True)
        
        # --- MODIFIED: Print a header for each metric's ranking ---
        metric_name = metric_key.replace('winner_', '').replace('_', ' ').title()
        print(f"\n--- 模型排名: {metric_name} ---")
        print(f"{'排名':<5}{'模型':<20}{'胜率':<10}{'胜场':<7}{'负场':<7}{'平局':<7}{'总比较次数':<10}")
        print("-" * 75)
        for i, item in enumerate(leaderboard):
            rank = i + 1
            win_rate_str = f"{item['win_rate']:.2%}"
            print(f"{rank:<5}{item['model']:<20}{win_rate_str:<10}{item['wins']:<7}{item['losses']:<7}{item['ties']:<7}{item['comparisons']:<10}")

if __name__ == '__main__':
    calculate_model_ranking()