import json
import pandas as pd
import simpledorff
from statsmodels.stats.inter_rater import fleiss_kappa
import numpy as np

# 你要计算的一致性维度
METRIC_KEYS = [
    'winner_coherence',
    'winner_adherence',
    'winner_clarity',
    'winner_empathy'
]

def calculate_agreements_from_df(df):
    if df.empty or 'annotator_id' not in df.columns or len(df['annotator_id'].unique()) < 2:
        return {"error": "Insufficient data or annotators for agreement calculation."}

    agreement_scores = {}
    
    # 构造 task_id（保证同一个case+模型对比是一致的任务）
    df['task_id'] = df.apply(
        lambda row: f"{row['case_id']}_{'_vs_'.join(sorted([row['model_a'], row['model_b']]))}",
        axis=1
    )

    for metric_key in METRIC_KEYS:
        metric_name = metric_key.replace('winner_', '')
        if metric_key not in df.columns:
            agreement_scores[metric_name] = "Metric column not found"
            continue

        kappa_df = df[['task_id', 'annotator_id', metric_key]].dropna()
        kappa_df = kappa_df.rename(columns={metric_key: 'annotation'})

        # 至少要有两个 annotator 标注同一个 task
        task_counts = kappa_df['task_id'].value_counts()
        tasks_with_multiple = task_counts[task_counts > 1].index
        if len(tasks_with_multiple) < 1:
            agreement_scores[metric_name] = "Not enough overlapping annotations"
            continue

        kappa_df_filtered = kappa_df[kappa_df['task_id'].isin(tasks_with_multiple)]

        try:
            # ----- Krippendorff's alpha -----
            alpha = simpledorff.calculate_krippendorffs_alpha_for_df(
                kappa_df_filtered,
                experiment_col='task_id',
                annotator_col='annotator_id',
                class_col='annotation'
            )

            # ----- Fleiss' kappa -----
            # 构造 (n_tasks × n_categories) 的矩阵
            categories = sorted(kappa_df_filtered['annotation'].unique())
            task_ids = kappa_df_filtered['task_id'].unique()
            mat = []
            for tid in task_ids:
                sub = kappa_df_filtered[kappa_df_filtered['task_id'] == tid]
                counts = [sum(sub['annotation'] == c) for c in categories]
                mat.append(counts)
            mat = np.array(mat)

            fleiss = fleiss_kappa(mat)

            agreement_scores[metric_name] = {
                "fleiss": fleiss,
                "krippendorff": alpha
            }

        except Exception as e:
            agreement_scores[metric_name] = f"Calculation error: {e}"

    return agreement_scores


def display_agreement(agreement_scores):
    print("\n--- Annotator Agreement Analysis ---")
    if "error" in agreement_scores:
        print(agreement_scores["error"])
        return

    for metric_name, scores in agreement_scores.items():
        print(f"\nMetric: {metric_name.title()}")
        if isinstance(scores, dict):
            print(f"  Fleiss' kappa       : {scores['fleiss']:.4f}")
            print(f"  Krippendorff's alpha: {scores['krippendorff']:.4f}")
        else:
            print(f"  {scores}")

    print("\nInterpretation (Landis & Koch):")
    print("  0.61 - 0.80: Substantial agreement")
    print("  0.81 - 1.00: Almost perfect agreement")


if __name__ == '__main__':
    FILE_PATH = 'annotation_data/annotation_202509240830.json'

    try:
        with open(FILE_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        df = pd.DataFrame(data['annotation'])
        print(f"Successfully loaded {len(df)} records from '{FILE_PATH}'.")

    except (FileNotFoundError, json.JSONDecodeError, KeyError) as e:
        try:
            print(f"Could not load as standard JSON ({e}), trying JSONL format...")
            df = pd.read_json('results.jsonl', lines=True)
            print(f"Successfully loaded {len(df)} records from 'results.jsonl'.")
        except Exception as e2:
            print(f"Error: Could not read the results file. Error: {e2}")
            df = pd.DataFrame()

    if not df.empty:
        calculated_agreement = calculate_agreements_from_df(df)
        display_agreement(calculated_agreement)