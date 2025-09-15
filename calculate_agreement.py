# calculate_agreement.py (Updated for multi-metric)
import json
import pandas as pd
from simpledorff import calculate_kappas

RESULTS_FILE = 'results.jsonl'
# --- NEW: Define all metric keys we want to analyze ---
METRIC_KEYS = [
    'winner_overall', 
    'winner_efficiency', 
    'winner_safety', 
    'winner_empathy'
]

def calculate_inter_annotator_agreement():
    try:
        df = pd.read_json(RESULTS_FILE, lines=True)
    except (FileNotFoundError, ValueError):
        print(f"错误: 结果文件 '{RESULTS_FILE}' 未找到或为空。")
        return

    if df.empty:
        print("没有可供分析的标注数据。")
        return

    # --- MODIFIED: Loop through each metric and calculate Kappa ---
    print("--- 标注者一致性分析 (Fleiss' Kappa) ---")
    
    # Create a unique task ID
    df['task_id'] = df.apply(
        lambda row: f"{row['case_id']}_{'_vs_'.join(sorted([row['model_a'], row['model_b']]))}",
        axis=1
    )

    for metric_key in METRIC_KEYS:
        if metric_key not in df.columns:
            print(f"\n跳过 '{metric_key}': 在结果文件中未找到该列。")
            continue

        # Prepare DataFrame for this metric
        kappa_df = df[['task_id', 'annotator_id', metric_key]].dropna()
        kappa_df = kappa_df.rename(columns={metric_key: 'annotation'})

        task_counts = kappa_df['task_id'].value_counts()
        tasks_with_multiple = task_counts[task_counts > 1].index
        
        if len(tasks_with_multiple) == 0:
            print(f"\n指标 '{metric_key.replace('winner_', '')}': 没有找到被多个标注者同时标注过的任务，无法计算。")
            continue
            
        kappa_df_filtered = kappa_df[kappa_df['task_id'].isin(tasks_with_multiple)]

        # Calculate Fleiss' Kappa
        kappa_results = calculate_kappas(kappa_df_filtered,
                                         document_col='task_id',
                                         annotator_col='annotator_id')
        
        fleiss_kappa = kappa_results['fleiss']['overall']
        metric_name = metric_key.replace('winner_', '').replace('_', ' ').title()

        print(f"\n指标: {metric_name}")
        print(f"  Fleiss' Kappa: {fleiss_kappa:.4f}")

    print("\nKappa 值解释:")
    print("  0.61-0.80: 良好 (Substantial agreement)")
    print("  0.81-1.00: 几乎完美 (Almost perfect agreement)")

if __name__ == '__main__':
    calculate_inter_annotator_agreement()