"""
自动化大模型渗透测试能力评估平台

B/S架构，支持：
1. 数据集上传/选择
2. 模型配置
3. API调用
4. 自动评分
5. 结果可视化
6. 报告生成
"""

import os
import json
import asyncio
import time
import random
from datetime import datetime
from aiohttp import web
from dotenv import load_dotenv

# 导入ModelEvaluator
from evaluate_models import ModelEvaluator

# 加载环境变量
load_dotenv()

# 全局变量
UPLOAD_DIR = "uploads"
RESULTS_DIR = "results"
DATASETS_DIR = "datasets"

# 确保目录存在
for directory in [UPLOAD_DIR, RESULTS_DIR, DATASETS_DIR]:
    os.makedirs(directory, exist_ok=True)

# 示例模型配置
DEFAULT_MODELS = [
    {
        "name": "GPT-4o",
        "model_id": "openai/gpt-4o",
        "api_key": "",
        "endpoint": "https://openrouter.ai/api/v1/chat/completions"
    },
    {
        "name": "Claude 3.5 Sonnet",
        "model_id": "anthropic/claude-3.5-sonnet",
        "api_key": "",
        "endpoint": "https://openrouter.ai/api/v1/chat/completions"
    },
    {
        "name": "Gemini 3.1 Flash",
        "model_id": "google/gemini-3.1-flash-lite-preview",
        "api_key": "",
        "endpoint": "https://openrouter.ai/api/v1/chat/completions"
    },
    {
        "name": "Qwen 3.5 Flash",
        "model_id": "qwen/qwen3.5-flash-02-23",
        "api_key": "",
        "endpoint": "https://openrouter.ai/api/v1/chat/completions"
    }
]

# 示例数据集列表
DEFAULT_DATASETS = [
    "datasets/gpt-4o-mini_ju_833.json",
    "datasets/gpt-4o-mini_mc_test_20260309_191142.json"
]




async def handle_index(request):
    """首页"""
    with open("templates/index.html", "r", encoding="utf-8") as f:
        content = f.read()
    return web.Response(text=content, content_type="text/html")


async def handle_get_datasets(request):
    """获取可用数据集"""
    datasets = []
    # 检查上传目录
    for filename in os.listdir(UPLOAD_DIR):
        if filename.endswith(".json"):
            datasets.append(f"uploads/{filename}")
    # 检查默认数据集目录
    for filename in os.listdir(DATASETS_DIR):
        if filename.endswith(".json"):
            datasets.append(f"datasets/{filename}")
    return web.json_response({"datasets": datasets})


async def handle_get_models(request):
    """获取默认模型配置"""
    return web.json_response({"status": "success", "models": DEFAULT_MODELS})


async def handle_upload_dataset(request):
    """上传数据集"""
    reader = await request.multipart()
    filepaths = []
    
    while True:
        field = await reader.next()
        if not field:
            break
        
        if field.name == "datasets":
            filename = field.filename
            filepath = os.path.join(UPLOAD_DIR, filename)
            
            with open(filepath, 'wb') as f:
                while True:
                    chunk = await field.read_chunk()
                    if not chunk:
                        break
                    f.write(chunk)
            
            filepaths.append(f"uploads/{filename}")
    
    if not filepaths:
        return web.json_response({"status": "error", "message": "未上传文件"})
    
    return web.json_response({"status": "success", "filepaths": filepaths})


async def handle_delete_dataset(request):
    """删除数据集"""
    data = await request.json()
    dataset_path = data.get("path")
    
    if not dataset_path:
        return web.json_response({"status": "error", "message": "缺少路径参数"})
    
    # 安全检查：确保路径在允许的目录内
    allowed_dirs = [UPLOAD_DIR, DATASETS_DIR]
    full_path = os.path.abspath(dataset_path)
    
    is_allowed = False
    for allowed_dir in allowed_dirs:
        if full_path.startswith(os.path.abspath(allowed_dir)):
            is_allowed = True
            break
    
    if not is_allowed:
        return web.json_response({"status": "error", "message": "不允许删除此路径的文件"})
    
    # 检查文件是否存在
    if not os.path.exists(full_path):
        return web.json_response({"status": "error", "message": "文件不存在"})
    
    try:
        os.remove(full_path)
        return web.json_response({"status": "success", "message": "数据集删除成功"})
    except Exception as e:
        return web.json_response({"status": "error", "message": f"删除失败: {str(e)}"})


async def handle_start_evaluation(request):
    """开始评估"""
    data = await request.json()
    dataset = data.get("dataset")
    models = data.get("models", [])
    
    if not dataset or not models:
        return web.json_response({"status": "error", "message": "缺少必要参数"})
    
    # 生成评估任务ID
    task_id = f"eval_{int(time.time())}_{random.randint(1000, 9999)}"
    
    # 启动评估任务（异步）
    asyncio.create_task(run_evaluation(task_id, dataset, models))
    
    return web.json_response({"status": "success", "task_id": task_id})


async def handle_get_progress(request):
    """获取评估进度"""
    task_id = request.query.get("task_id")
    if not task_id:
        return web.json_response({"status": "error", "message": "缺少task_id"})
    
    progress_file = os.path.join(RESULTS_DIR, f"{task_id}_progress.json")
    if os.path.exists(progress_file):
        with open(progress_file, "r", encoding="utf-8") as f:
            progress = json.load(f)
        return web.json_response({"status": "success", "progress": progress})
    else:
        return web.json_response({"status": "error", "message": "任务不存在"})


async def handle_get_results(request):
    """获取评估结果"""
    task_id = request.query.get("task_id")
    if not task_id:
        return web.json_response({"status": "error", "message": "缺少task_id"})
    
    results_file = os.path.join(RESULTS_DIR, f"{task_id}_results.json")
    if os.path.exists(results_file):
        with open(results_file, "r", encoding="utf-8") as f:
            results = json.load(f)
        return web.json_response({"status": "success", "results": results})
    else:
        return web.json_response({"status": "error", "message": "结果不存在"})


async def run_evaluation(task_id, dataset_paths, models):
    """运行评估任务"""
    try:
        # 初始化进度
        progress = {
            "task_id": task_id,
            "status": "running",
            "start_time": datetime.now().isoformat()
        }
        
        # 保存进度
        progress_file = os.path.join(RESULTS_DIR, f"{task_id}_progress.json")
        with open(progress_file, "w", encoding="utf-8") as f:
            json.dump(progress, f, ensure_ascii=False, indent=2)
        
        # 动态配置评估器
        from evaluate_models import MODEL_CONFIGS
        
        # 清空并添加新的模型配置
        MODEL_CONFIGS.clear()
        model_ids = []
        
        for model in models:
            model_name = model.get("name")
            model_id = model.get("model_id")
            api_key = model.get("api_key")
            endpoint = model.get("endpoint", "https://openrouter.ai/api/v1/chat/completions")
            
            if not api_key:
                continue
            
            # 添加模型配置
            MODEL_CONFIGS[model_id] = {
                "name": model_name,
                "endpoint": endpoint,
                "api_key": api_key
            }
            model_ids.append(model_id)
        
        if not model_ids:
            progress["status"] = "error"
            progress["error"] = "没有可用的模型配置"
            with open(progress_file, "w", encoding="utf-8") as f:
                json.dump(progress, f, ensure_ascii=False, indent=2)
            return
        
        # 确保dataset_paths是列表
        if isinstance(dataset_paths, str):
            dataset_paths = [dataset_paths]
        
        # 合并所有评估结果
        all_results = {}
        all_result_files = []
        total_questions = 0
        
        # 对每个数据集文件进行评估
        for dataset_idx, dataset_path in enumerate(dataset_paths):
            # 更新进度信息
            progress["status"] = "running"
            progress["current_dataset"] = dataset_idx + 1
            progress["total_datasets"] = len(dataset_paths)
            progress["current_dataset_path"] = dataset_path
            
            with open(progress_file, "w", encoding="utf-8") as f:
                json.dump(progress, f, ensure_ascii=False, indent=2)
            
            # 定义进度回调函数
            async def progress_callback(progress_data):
                # 更新进度信息
                progress["status"] = progress_data["status"]
                progress["current_question"] = progress_data["current_question"]
                progress["total_questions"] = progress_data["total_questions"]
                progress["current_question_id"] = progress_data["current_question_id"]
                progress["model_name"] = progress_data["model_name"]
                
                # 计算进度百分比
                if progress_data["total_questions"] > 0:
                    progress["percentage"] = int((progress_data["current_question"] / progress_data["total_questions"]) * 100)
                
                # 保存进度
                with open(progress_file, "w", encoding="utf-8") as f:
                    json.dump(progress, f, ensure_ascii=False, indent=2)
            
            # 创建评估器
            evaluator = ModelEvaluator(dataset_path, model_ids, max_workers=3, progress_callback=progress_callback, model_configs=MODEL_CONFIGS)
            # 运行评估
            await evaluator.run()
            
            # 收集ModelEvaluator生成的文件路径
            for model_name in evaluator.results.keys():
                # 获取模型名称的文件安全版本
                safe_model_name = model_name.replace(' ', '_')
                detailed_file = os.path.join(RESULTS_DIR, f"eval_{evaluator.task_id}_{safe_model_name}_detailed.jsonl")
                summary_file = os.path.join(RESULTS_DIR, f"eval_{evaluator.task_id}_{safe_model_name}_summary.json")
                
                if os.path.exists(detailed_file):
                    all_result_files.append({
                        "model_name": model_name,
                        "type": "detailed",
                        "filename": os.path.basename(detailed_file),
                        "filepath": detailed_file,
                        "dataset": dataset_path
                    })
                
                if os.path.exists(summary_file):
                    all_result_files.append({
                        "model_name": model_name,
                        "type": "summary",
                        "filename": os.path.basename(summary_file),
                        "filepath": summary_file,
                        "dataset": dataset_path
                    })
            
            # 合并结果
            for model_name, model_results in evaluator.results.items():
                if model_name not in all_results:
                    all_results[model_name] = {
                        "average_score": 0,
                        "total_questions": 0,
                        "correct": 0,
                        "incorrect": 0,
                        "total_score": 0,
                        "question_results": [],
                        "question_types": {},
                        "type_analysis": {}
                    }
                
                # 合并题目结果
                all_results[model_name]["question_results"].extend(model_results.get("question_results", []))
                all_results[model_name]["total_questions"] += model_results.get("total_questions", 0)
                all_results[model_name]["correct"] += model_results.get("correct", 0)
                all_results[model_name]["incorrect"] += model_results.get("incorrect", 0)
                all_results[model_name]["total_score"] += model_results.get("total_score", 0)
                
                # 合并题型分析数据
                if "question_types" in model_results:
                    for q_type, stats in model_results["question_types"].items():
                        if q_type not in all_results[model_name]["question_types"]:
                            all_results[model_name]["question_types"][q_type] = {"total": 0, "correct": 0, "incorrect": 0, "total_score": 0}
                        all_results[model_name]["question_types"][q_type]["total"] += stats.get("total", 0)
                        all_results[model_name]["question_types"][q_type]["correct"] += stats.get("correct", 0)
                        all_results[model_name]["question_types"][q_type]["incorrect"] += stats.get("incorrect", 0)
                        all_results[model_name]["question_types"][q_type]["total_score"] += stats.get("total_score", 0)
                
                # 合并知识点分析数据
                if "type_analysis" in model_results:
                    for q_type, stats in model_results["type_analysis"].items():
                        if q_type not in all_results[model_name]["type_analysis"]:
                            all_results[model_name]["type_analysis"][q_type] = {"total": 0, "correct": 0, "incorrect": 0, "total_score": 0}
                        all_results[model_name]["type_analysis"][q_type]["total"] += stats.get("total", 0)
                        all_results[model_name]["type_analysis"][q_type]["correct"] += stats.get("correct", 0)
                        all_results[model_name]["type_analysis"][q_type]["incorrect"] += stats.get("incorrect", 0)
                        all_results[model_name]["type_analysis"][q_type]["total_score"] += stats.get("total_score", 0)
            
            total_questions += len(evaluator.questions)
        
        # 重新计算平均分数和准确率
        for model_name, model_results in all_results.items():
            if model_results["total_questions"] > 0:
                model_results["average_score"] = model_results["correct"] / model_results["total_questions"]
                model_results["accuracy"] = model_results["correct"] / model_results["total_questions"]
            
            # 重新计算各题型的准确率和平均分
            for q_type, stats in model_results["question_types"].items():
                if stats["total"] > 0:
                    stats["accuracy"] = stats["correct"] / stats["total"]
                    stats["average_score"] = stats["total_score"] / stats["total"]
            
            # 重新计算各知识点的准确率和平均分
            for q_type, stats in model_results["type_analysis"].items():
                if stats["total"] > 0:
                    stats["accuracy"] = stats["correct"] / stats["total"]
                    stats["average_score"] = stats["total_score"] / stats["total"]
        
        # 生成评估报告
        report = {
            "task_id": task_id,
            "datasets": dataset_paths,
            "models": models,
            "results": all_results,
            "total_questions": total_questions,
            "result_files": all_result_files,
            "start_time": progress["start_time"],
            "end_time": datetime.now().isoformat()
        }
        
        # 确保即使没有结果也能生成报告
        if not all_results:
            # 为每个模型创建一个空结果
            for model in models:
                model_name = model.get("name")
                all_results[model_name] = {
                    "average_score": 0,
                    "total_questions": 0,
                    "correct": 0,
                    "incorrect": 0,
                    "total_score": 0,
                    "question_results": [],
                    "question_types": {},
                    "type_analysis": {}
                }
            report["results"] = all_results
        
        # 保存结果
        results_file = os.path.join(RESULTS_DIR, f"{task_id}_results.json")
        with open(results_file, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        # 更新进度为完成
        progress["status"] = "completed"
        progress["end_time"] = datetime.now().isoformat()
        with open(progress_file, "w", encoding="utf-8") as f:
            json.dump(progress, f, ensure_ascii=False, indent=2)
            
    except Exception as e:
        # 保存错误信息
        progress["status"] = "error"
        progress["error"] = str(e)
        with open(progress_file, "w", encoding="utf-8") as f:
            json.dump(progress, f, ensure_ascii=False, indent=2)





# 静态文件路由
app = web.Application()
app.add_routes([
    web.get('/', handle_index),
    web.get('/api/datasets', handle_get_datasets),
    web.get('/api/models', handle_get_models),
    web.post('/api/upload', handle_upload_dataset),
    web.post('/api/delete-dataset', handle_delete_dataset),
    web.post('/api/start', handle_start_evaluation),
    web.get('/api/progress', handle_get_progress),
    web.get('/api/results', handle_get_results),
    web.static('/static', 'static'),
    web.static('/uploads', 'uploads'),
    web.static('/datasets', 'datasets'),
    web.static('/results', 'results')
])


if __name__ == "__main__":
    print("启动测评平台...")
    print("访问地址: http://localhost:8084")
    web.run_app(app, port=8084)
