# app.py (Updated Version)
import os
import json
import random
from datetime import datetime
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

DATA_DIR = './data'
RESULTS_FILE = 'results.jsonl'

# app.py

# 1. MODIFIED: This function is updated to handle the new JSON structure and wrap dialogue in HTML.
def load_data():
    """将所有模型数据加载并按 case_id 组织"""
    all_data = {}
    model_files = [f for f in os.listdir(DATA_DIR) if f.endswith('.jsonl')]
    for file_name in model_files:
        model_name = os.path.splitext(file_name)[0]
        with open(os.path.join(DATA_DIR, file_name), 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    record = json.loads(line)
                    case_id = record.get('case_id')
                    if not case_id:
                        continue
                    
                    # --- NEW: Format the 'interactions' array into an HTML dialogue string ---
                    interactions = record.get('interactions', [])
                    dialogue_parts = []
                    for turn in interactions:
                        if isinstance(turn, list) and len(turn) == 2:
                            # Wrap doctor's turn in a div with class "doctor-turn"
                            dialogue_parts.append(f'<div class="doctor-turn">医生: {turn[0]}</div>')
                            # Wrap patient's turn in a div with class "patient-turn"
                            dialogue_parts.append(f'<div class="patient-turn">患者: {turn[1]}</div>')
                    
                    # Join the HTML parts together
                    formatted_dialogue = "".join(dialogue_parts)
                    formatted_dialogue = formatted_dialogue.replace('*','')
                    # --- END NEW ---

                    if case_id not in all_data:
                        all_data[case_id] = {}
                    
                    all_data[case_id][model_name] = {
                        "dialogue": formatted_dialogue,
                        "choices": record.get("choices", "N/A"),
                        "category": record.get("category", "N/A")
                    }

                except json.JSONDecodeError:
                    print(f"Warning: Skipping invalid JSON line in {file_name}")
    return all_data


def get_completed_annotations(annotator_id):
    """获取指定标注员已完成的任务"""
    completed = set()
    if not os.path.exists(RESULTS_FILE):
        return completed
    with open(RESULTS_FILE, 'r', encoding='utf-8') as f:
        for line in f:
            record = json.loads(line)
            if record.get('annotator_id') == annotator_id:
                models = tuple(sorted((record['model_a'], record['model_b'])))
                completed.add((record['case_id'], models))
    return completed

# (This section does not need changes)
organized_data = load_data()
all_models = list(set(model for case in organized_data.values() for model in case.keys()))
all_cases = list(organized_data.keys())

def calculate_total_pairs(data):
    """计算数据集中所有可能的对比组合总数"""
    total = 0
    for case_id in data:
        models_in_case = list(data[case_id].keys())
        if len(models_in_case) >= 2:
            # This calculates combinations of 2 from the number of models
            total += len(models_in_case) * (len(models_in_case) - 1) // 2
    return total

TOTAL_PAIRS = calculate_total_pairs(organized_data)

@app.route('/')
def index():
    """渲染主页面"""
    return render_template('index.html')


# MODIFIED: This function is updated to send the new contextual info.
@app.route('/get_comparison_pair')
def get_comparison_pair():
    """为前端提供一个随机的、未被标注过的对话对"""
    annotator_id = request.args.get('annotator_id')
    if not annotator_id:
        return jsonify({"error": "Annotator ID is required"}), 400

    completed = get_completed_annotations(annotator_id)
    completed_count = len(completed)
    
    possible_pairs = []
    for case_id in all_cases:
        models_in_case = list(organized_data[case_id].keys())
        if len(models_in_case) < 2:
            continue
        for i in range(len(models_in_case)):
            for j in range(i + 1, len(models_in_case)):
                model1, model2 = models_in_case[i], models_in_case[j]
                task = (case_id, tuple(sorted((model1, model2))))
                if task not in completed:
                    possible_pairs.append((case_id, model1, model2))
    
    if not possible_pairs:
        return jsonify({
            "message": "All tasks completed! Thank you!",
            "progress_completed": completed_count,
            "progress_total": TOTAL_PAIRS
        })
    
    case_id, model_a, model_b = random.choice(possible_pairs)
    
    if random.random() < 0.5:
        model_a, model_b = model_b, model_a

    # --- NEW: Add 'category' and 'task' to the response ---
    data_for_case = organized_data[case_id][model_a] # Get context from one of the models
    pair = {
        "case_id": case_id,
        "category": data_for_case.get('category'),
        "choices": data_for_case.get('choices'),
        "model_a_info": {"name": model_a, "dialogue": organized_data[case_id][model_a]['dialogue']},
        "model_b_info": {"name": model_b, "dialogue": organized_data[case_id][model_b]['dialogue']}
    }
    pair["progress_completed"] = completed_count
    pair["progress_total"] = TOTAL_PAIRS
    # --- END NEW ---
    return jsonify(pair)


# (This function does not need changes)
@app.route('/submit_annotation', methods=['POST'])
def submit_annotation():
    """接收并保存前端提交的标注结果"""
    data = request.json
    required_fields = ['annotator_id', 'case_id', 'model_a', 'model_b', 'winners']
    if not all(field in data for field in required_fields):
        return jsonify({"error": "Missing data"}), 400
    
    # 校验 'winners' 字典内部的key
    required_winners = ['coherence', 'adherence', 'clarity', 'empathy']
    # required_winners = ['overall', 'efficiency', 'safety', 'empathy']
    if not all(winner in data['winners'] for winner in required_winners):
        return jsonify({"error": "Missing winner data for some metrics"}), 400

    # 将 winners 字典扁平化存入结果，方便后续 pandas 处理
    result = {
        "annotator_id": data['annotator_id'],
        "case_id": data['case_id'],
        "model_a": data['model_a'],
        "model_b": data['model_b'],
        "winner_coherence": data['winners']['coherence'],
        "winner_adherence": data['winners']['adherence'],
        "winner_clarity": data['winners']['clarity'],
        "winner_empathy": data['winners']['empathy'],
        "timestamp": datetime.now().isoformat()
    }

    with open(RESULTS_FILE, 'a', encoding='utf-8') as f:
        f.write(json.dumps(result) + '\n')
        
    return jsonify({"success": True})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5002, debug=False)