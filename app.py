# app.py
import os
import json
import random
from datetime import datetime
from flask import Flask, render_template, request, jsonify
from flask_sqlalchemy import SQLAlchemy
import pandas as pd
from calculate_ranking import calculate_win_rates_from_df
from calculate_agreement import calculate_agreements_from_df
from app import app, db

app = Flask(__name__)

# --- 数据库配置 ---
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

ANNOTATOR_LIST = ['yonghui', 'xinhui', 'jingyi', 'luanbo', 'zhenglong', 'yaqing']

# --- 数据库模型定义 ---
class Annotation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    annotator_id = db.Column(db.String(80), nullable=False)
    case_id = db.Column(db.String(80), nullable=False)
    model_a = db.Column(db.String(80), nullable=False)
    model_b = db.Column(db.String(80), nullable=False)
    winner_coherence = db.Column(db.String(80), nullable=False)
    winner_adherence = db.Column(db.String(80), nullable=False)
    winner_clarity = db.Column(db.String(80), nullable=False)
    winner_empathy = db.Column(db.String(80), nullable=False)
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

# 注意：在生产环境中，此命令最好只在初始化时运行一次。
# 在Render上，可以在Blueprint设置中使用 one-off job 来执行。
with app.app_context():
    db.create_all()

# --- 源对话数据加载 ---
DATA_DIR = './data'

def load_data():
    """将所有源对话模型数据从文件加载并按 case_id 组织"""
    all_data = {}
    if not os.path.exists(DATA_DIR):
        print(f"Warning: Data directory '{DATA_DIR}' not found.")
        return {}
        
    model_files = [f for f in os.listdir(DATA_DIR) if f.endswith('.jsonl')]
    for file_name in model_files:
        model_name = os.path.splitext(file_name)[0]
        with open(os.path.join(DATA_DIR, file_name), 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    record = json.loads(line)
                    case_id = record.get('case_id')
                    if not case_id: continue
                    
                    interactions = record.get('interactions', [])
                    dialogue_parts = []
                    for turn in interactions:
                        if isinstance(turn, list) and len(turn) == 2:
                            dialogue_parts.append(f'<div class="doctor-turn">医生: {turn[0]}</div>')
                            dialogue_parts.append(f'<div class="patient-turn">患者: {turn[1]}</div>')
                    
                    formatted_dialogue = "".join(dialogue_parts).replace('*','')
                    
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

# --- 【新版本】从数据库获取已完成任务 ---
def get_completed_annotations(annotator_id):
    """从数据库获取指定标注员已完成的任务"""
    completed = set()
    try:
        annotations = db.session.query(Annotation).filter_by(
            annotator_id=annotator_id
        ).with_entities(
            Annotation.case_id, Annotation.model_a, Annotation.model_b
        ).all()

        for ann in annotations:
            models = tuple(sorted((ann.model_a, ann.model_b)))
            completed.add((ann.case_id, models))
    except Exception as e:
        print(f"Database error in get_completed_annotations: {e}")
    return completed

# --- 应用启动时加载和计算 ---
organized_data = load_data()
all_cases = list(organized_data.keys())

def calculate_total_pairs(data):
    """计算数据集中所有可能的对比组合总数"""
    total = 0
    for case_id in data:
        models_in_case = list(data[case_id].keys())
        if len(models_in_case) >= 2:
            total += len(models_in_case) * (len(models_in_case) - 1) // 2
    return total

TOTAL_PAIRS = calculate_total_pairs(organized_data)

# --- 网页路由 ---
@app.route('/')
def index():
    return render_template('index.html')

# app.py

# ... (您的其他代码，包括 ANNOTATOR_LIST 和数据库模型定义保持不变) ...

# 这是一个一次性生成的全量任务列表，为了保证分配的稳定性
# 我们在生成它时对 case_id 和 models 都进行了排序
ALL_THEORETICAL_PAIRS = []
for case_id in sorted(all_cases):
    models_in_case = sorted(list(organized_data.get(case_id, {}).keys()))
    if len(models_in_case) < 2: continue
    for i in range(len(models_in_case)):
        for j in range(i + 1, len(models_in_case)):
            model1, model2 = models_in_case[i], models_in_case[j]
            task = (case_id, tuple(sorted((model1, model2))))
            ALL_THEORETICAL_PAIRS.append(task)

@app.route('/get_comparison_pair')
def get_comparison_pair():
    annotator_id = request.args.get('annotator_id')
    if not annotator_id:
        return jsonify({"error": "Annotator ID is required"}), 400

    if annotator_id not in ANNOTATOR_LIST:
        return jsonify({"error": f"Annotator ID '{annotator_id}' is not in the recognized list."}), 400

    # --- 步骤 1: 根据固定规则，计算出分配给当前标注员的全部任务 ---
    annotator_index = ANNOTATOR_LIST.index(annotator_id)
    num_annotators = len(ANNOTATOR_LIST)
    
    my_assigned_tasks = [
        task for i, task in enumerate(ALL_THEORETICAL_PAIRS)
        if i % num_annotators == annotator_index
    ]
    # 这是当前用户的个人任务总数
    my_total_tasks = len(my_assigned_tasks)

    # --- 步骤 2: 从数据库获取当前标注员已完成的任务 ---
    completed_by_me = get_completed_annotations(annotator_id)

    # --- 步骤 3: 从“分配给我的任务”中，筛选出“待办”的任务 ---
    # 使用集合(set)运算提高效率
    my_assigned_tasks_set = set(my_assigned_tasks)
    my_pending_tasks = list(my_assigned_tasks_set - completed_by_me)
    
    # --- 步骤 4: 计算正确的个人进度 ---
    my_completed_count = my_total_tasks - len(my_pending_tasks)

    # --- 步骤 5: 判断个人任务是否已全部完成 ---
    if not my_pending_tasks:
        return jsonify({
            "message": "Congratulations! You have completed all your assigned tasks.",
            "progress_completed": my_completed_count,
            "progress_total": my_total_tasks
        })
    
    # --- 步骤 6: 从个人待办任务中随机选择一个并返回 ---
    case_id, models = random.choice(my_pending_tasks)
    model_a, model_b = models[0], models[1]
    
    # 随机交换A/B的显示位置
    if random.random() < 0.5:
        model_a, model_b = model_b, model_a

    data_for_case = organized_data.get(case_id, {}).get(model_a, {})
    pair = {
        "case_id": case_id,
        "category": data_for_case.get('category', 'N/A'),
        "choices": data_for_case.get('choices', 'N/A'),
        "model_a_info": {"name": model_a, "dialogue": organized_data.get(case_id, {}).get(model_a, {}).get('dialogue', '')},
        "model_b_info": {"name": model_b, "dialogue": organized_data.get(case_id, {}).get(model_b, {}).get('dialogue', '')}
    }
    # 在返回的json中使用正确的个人进度值
    pair["progress_completed"] = my_completed_count
    pair["progress_total"] = my_total_tasks
    return jsonify(pair)



@app.route('/submit_annotation', methods=['POST'])
def submit_annotation():
    data = request.json
    required_fields = ['annotator_id', 'case_id', 'model_a', 'model_b', 'winners']
    if not all(field in data for field in required_fields) or not all(key in data['winners'] for key in ['coherence', 'adherence', 'clarity', 'empathy']):
        return jsonify({"error": "Missing data"}), 400
        
    new_annotation = Annotation(
        annotator_id=data['annotator_id'],
        case_id=data['case_id'],
        model_a=data['model_a'],
        model_b=data['model_b'],
        winner_coherence=data['winners']['coherence'],
        winner_adherence=data['winners']['adherence'],
        winner_clarity=data['winners']['clarity'],
        winner_empathy=data['winners']['empathy'],
        timestamp=datetime.now()
    )

    try:
        db.session.add(new_annotation)
        db.session.commit()
        return jsonify({"success": True})
    except Exception as e:
        db.session.rollback()
        print(f"Database error: {e}")
        return jsonify({"error": "Failed to save to database"}), 500

ADMIN_PASSWORD = "123"
# 数据看板链接：https://medical-dialogue-annotation.onrender.com/results?password=123
@app.route('/results')
def view_results():
    password = request.args.get('password')
    if password != ADMIN_PASSWORD:
        return "<h1>访问被拒绝</h1><p>请提供正确的访问密码。</p>", 403

    try:
        all_annotations = Annotation.query.order_by(Annotation.timestamp.desc()).all()
        return render_template('results.html', annotations=all_annotations, count=len(all_annotations))
    except Exception as e:
        print(f"Error fetching results: {e}")
        return "<h1>查询数据时出错</h1><p>请检查服务器日志。</p>", 500



def get_data_as_dataframe(db_session):
    """Queries all annotations and returns them as a Pandas DataFrame."""
    query = db_session.query(Annotation).statement
    df = pd.read_sql(query, db_session.bind)
    return df


# https://medical-dialogue-annotation.onrender.com/analytics?password=123
@app.route('/analytics')
def view_analytics():
    """Renders the analytics dashboard with rankings and agreement scores."""
    password = request.args.get('password')
    if password != ADMIN_PASSWORD:
        return "<h1>Access Denied</h1><p>Please provide the correct access password.</p>", 403

    try:
        df = get_data_as_dataframe(db.session)
        
        if df.empty:
            return "<h1>No Data</h1><p>There is no annotation data in the database to analyze.</p>"

        # Calculate rankings and agreement scores
        rankings = calculate_win_rates_from_df(df)
        agreement = calculate_kappas_from_df(df)
        
        return render_template(
            'analytics.html',
            rankings=rankings,
            agreement=agreement
        )
    except Exception as e:
        print(f"Error generating analytics page: {e}")
        return "<h1>Error</h1><p>An error occurred while generating analytics.</p>", 500


@app.route('/export/csv')
def export_csv():
    password = request.args.get('password')
    if not ADMIN_PASSWORD or password != ADMIN_PASSWORD:
        return "<h1>Access Denied</h1>", 403
    
    try:
        annotations = Annotation.query.order_by(Annotation.timestamp.asc()).all()
        if not annotations:
            return "No data to export."
        data_to_export = [
            {
                "id": ann.id,
                "timestamp": ann.timestamp.isoformat(),
                "annotator_id": ann.annotator_id,
                "case_id": ann.case_id,
                "model_a": ann.model_a,
                "model_b": ann.model_b,
                "winner_coherence": ann.winner_coherence,
                "winner_adherence": ann.winner_adherence,
                "winner_clarity": ann.winner_clarity,
                "winner_empathy": ann.winner_empathy,
            } for ann in annotations
        ]
        df = pd.DataFrame(data_to_export)
        csv_output = df.to_csv(index=False, encoding='utf-8-sig') # utf-8-sig for Excel compatibility
        return Response(
            csv_output,
            mimetype="text/csv",
            headers={"Content-disposition":
                     f"attachment; filename=annotations_{datetime.now().strftime('%Y%m%d')}.csv"}
        )
    except Exception as e:
        print(f"Error exporting CSV: {e}")
        return "<h1>Error exporting data</h1>", 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5002, debug=False)