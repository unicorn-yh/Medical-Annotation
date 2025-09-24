import json
import pandas as pd
from collections import defaultdict

# --- Define metric keys ---
# Note: I've updated these to match your new database schema.
METRIC_KEYS = [
    'winner_coherence',
    'winner_adherence',
    'winner_clarity',
    'winner_empathy'
]

def calculate_win_rates_from_df(df):
    """
    Calculates win rates for multiple metrics from a DataFrame.
    The DataFrame must contain 'model_a', 'model_b', and the metric winner columns.
    """
    if df.empty:
        return {}

    rankings = {}
    models = pd.concat([df['model_a'], df['model_b']]).unique()

    for metric_key in METRIC_KEYS:
        if metric_key not in df.columns:
            continue

        stats = defaultdict(lambda: {'wins': 0, 'losses': 0, 'ties': 0, 'comparisons': 0})

        for _, row in df.iterrows():
            model_a = row['model_a']
            model_b = row['model_b']
            winner = row[metric_key]

            # Ensure both models are initialized in stats
            stats[model_a]
            stats[model_b]
            
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
        
        leaderboard = []
        for model, data in stats.items():
            # Avoid division by zero if a model was only ever in 'tie' results for a metric
            valid_comparisons = data['wins'] + data['losses']
            win_rate = data['wins'] / valid_comparisons if valid_comparisons > 0 else 0
            leaderboard.append({
                'model': model, 'win_rate': win_rate, 'wins': data['wins'],
                'losses': data['losses'], 'ties': data['ties'], 'comparisons': data['comparisons']
            })
        
        leaderboard.sort(key=lambda x: x['win_rate'], reverse=True)
        rankings[metric_key.replace('winner_', '')] = leaderboard
        
    return rankings

def display_rankings(rankings):
    """Formats and prints the rankings to the console."""
    for metric_name, leaderboard in rankings.items():
        print(f"\n--- Model Ranking: {metric_name.replace('_', ' ').title()} ---")
        print(f"{'Rank':<5}{'Model':<20}{'Win Rate':<12}{'Wins':<7}{'Losses':<8}{'Ties':<7}{'Compared':<10}")
        print("-" * 80)
        for i, item in enumerate(leaderboard):
            rank = i + 1
            win_rate_str = f"{item['win_rate']:.2%}"
            print(f"{rank:<5}{item['model']:<20}{win_rate_str:<12}{item['wins']:<7}{item['losses']:<8}{item['ties']:<7}{item['comparisons']:<10}")

if __name__ == '__main__':
    # This block allows the script to run locally on a JSON or JSONL file
    FILE_PATH = 'annotation_data/annotation_202509240830.json' # Change to your local file name
    
    try:
        # Load data from the provided JSON structure
        with open(FILE_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        # The data is nested under the "annotation" key
        df = pd.DataFrame(data['annotation'])
        print(f"Successfully loaded {len(df)} records from '{FILE_PATH}'.")

    except (FileNotFoundError, json.JSONDecodeError, KeyError) as e:
        # Fallback for JSONL format
        try:
            print(f"Could not load as standard JSON ({e}), trying JSONL format...")
            df = pd.read_json('results.jsonl', lines=True)
            print(f"Successfully loaded {len(df)} records from 'results.jsonl'.")
        except Exception as e2:
            print(f"Error: Could not read the results file. Please check the format. Error: {e2}")
            df = pd.DataFrame()

    if not df.empty:
        # Calculate rankings from the DataFrame
        calculated_ranks = calculate_win_rates_from_df(df)
        # Display the formatted rankings
        display_rankings(calculated_ranks)