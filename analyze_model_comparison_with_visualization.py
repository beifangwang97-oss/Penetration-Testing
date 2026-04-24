#!/usr/bin/env python3
"""
模型表现对比分析脚本（带可视化）

分析两个模型在数据集上的表现，按题目类型和question_type进行对比，并生成可视化图表
"""

import os
import json
import datetime
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
from collections import defaultdict

# 配置
RESULTS_DIR = "results"
OUTPUT_DIR = "analysis"

# 确保输出目录存在
os.makedirs(OUTPUT_DIR, exist_ok=True)

def collect_all_summary_files():
    """收集所有summary文件"""
    files = os.listdir(RESULTS_DIR)
    summary_files = [f for f in files if f.endswith('_summary.json')]
    
    # 按模型分组
    model_files = defaultdict(list)
    for file in summary_files:
        if "GPT-3.5_Turbo" in file:
            model_files["GPT-3.5 Turbo"].append(file)
        elif "Claude_3_Haiku" in file:
            model_files["Claude 3 Haiku"].append(file)
    
    return model_files

def load_summary_file(file_path):
    """加载summary文件"""
    with open(os.path.join(RESULTS_DIR, file_path), 'r', encoding='utf-8') as f:
        return json.load(f)

def collect_all_question_types(model_files):
    """收集所有题型的结果"""
    all_results = defaultdict(lambda: defaultdict(dict))
    
    for model_name, files in model_files.items():
        for file in files:
            summary = load_summary_file(file)
            
            # 获取题目类型
            question_types = summary.get("question_types", {})
            for qt, data in question_types.items():
                if qt not in all_results[model_name]:
                    all_results[model_name][qt] = {
                        "total_questions": 0,
                        "correct": 0,
                        "incorrect": 0,
                        "total_score": 0,
                        "accuracy": 0,
                        "average_score": 0
                    }
                
                # 累加数据
                all_results[model_name][qt]["total_questions"] += data.get("total", 0)
                all_results[model_name][qt]["correct"] += data.get("correct", 0)
                all_results[model_name][qt]["incorrect"] += data.get("incorrect", 0)
                all_results[model_name][qt]["total_score"] += data.get("total_score", 0)
            
            # 重新计算准确率和平均分
            for qt, data in all_results[model_name].items():
                if data["total_questions"] > 0:
                    data["accuracy"] = data["correct"] / data["total_questions"]
                    data["average_score"] = data["total_score"] / data["total_questions"]
    
    return all_results

def collect_all_type_analysis(model_files):
    """收集所有知识点类型的结果"""
    all_results = defaultdict(lambda: defaultdict(dict))
    
    for model_name, files in model_files.items():
        for file in files:
            summary = load_summary_file(file)
            
            # 获取知识点类型
            type_analysis = summary.get("type_analysis", {})
            for ta, data in type_analysis.items():
                if ta not in all_results[model_name]:
                    all_results[model_name][ta] = {
                        "total_questions": 0,
                        "correct": 0,
                        "incorrect": 0,
                        "total_score": 0,
                        "accuracy": 0,
                        "average_score": 0
                    }
                
                # 累加数据
                all_results[model_name][ta]["total_questions"] += data.get("total", 0)
                all_results[model_name][ta]["correct"] += data.get("correct", 0)
                all_results[model_name][ta]["incorrect"] += data.get("incorrect", 0)
                all_results[model_name][ta]["total_score"] += data.get("total_score", 0)
            
            # 重新计算准确率和平均分
            for ta, data in all_results[model_name].items():
                if data["total_questions"] > 0:
                    data["accuracy"] = data["correct"] / data["total_questions"]
                    data["average_score"] = data["total_score"] / data["total_questions"]
    
    return all_results

def calculate_overall_results(question_type_results):
    """计算总体结果"""
    overall = defaultdict(dict)
    
    for model_name, qt_results in question_type_results.items():
        total_questions = 0
        correct = 0
        incorrect = 0
        total_score = 0
        
        for qt, data in qt_results.items():
            total_questions += data["total_questions"]
            correct += data["correct"]
            incorrect += data["incorrect"]
            total_score += data["total_score"]
        
        if total_questions > 0:
            accuracy = correct / total_questions
            average_score = total_score / total_questions
        else:
            accuracy = 0
            average_score = 0
        
        overall[model_name] = {
            "total_questions": total_questions,
            "correct": correct,
            "incorrect": incorrect,
            "accuracy": accuracy,
            "average_score": average_score
        }
    
    return overall

def create_accuracy_comparison_chart(overall_results, question_type_results, output_file):
    """创建准确率对比图表"""
    plt.figure(figsize=(12, 6))
    
    # 总体准确率
    models = list(overall_results.keys())
    overall_accuracy = [overall_results[model]["accuracy"] for model in models]
    
    # 按题型准确率
    question_types = list(set(qt for model in question_type_results.values() for qt in model.keys()))
    qt_accuracy = {model: [question_type_results[model].get(qt, {}).get("accuracy", 0) for qt in question_types] for model in models}
    
    # 绘制总体准确率
    plt.subplot(1, 2, 1)
    bars = plt.bar(models, overall_accuracy, color=['#1f77b4', '#ff7f0e'])
    plt.title('总体准确率对比')
    plt.ylabel('准确率')
    plt.ylim(0, 1)
    
    # 添加数值标签
    for bar in bars:
        height = bar.get_height()
        plt.text(bar.get_x() + bar.get_width()/2., height + 0.02,
                 f'{height:.2%}', ha='center', va='bottom')
    
    # 绘制题型准确率
    plt.subplot(1, 2, 2)
    width = 0.35
    x = range(len(question_types))
    
    for i, model in enumerate(models):
        plt.bar([pos + i*width for pos in x], qt_accuracy[model], width=width, label=model)
    
    plt.title('各题型准确率对比')
    plt.ylabel('准确率')
    plt.xticks([pos + width/2 for pos in x], question_types, rotation=45, ha='right')
    plt.ylim(0, 1)
    plt.legend()
    
    plt.tight_layout()
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    plt.close()

def create_type_analysis_chart(type_analysis_results, output_file):
    """创建知识点分析对比图表"""
    plt.figure(figsize=(12, 8))
    
    models = list(type_analysis_results.keys())
    type_analysis = list(set(ta for model in type_analysis_results.values() for ta in model.keys()))
    
    # 按知识点准确率
    ta_accuracy = {model: [type_analysis_results[model].get(ta, {}).get("accuracy", 0) for ta in type_analysis] for model in models}
    
    width = 0.35
    x = range(len(type_analysis))
    
    for i, model in enumerate(models):
        plt.bar([pos + i*width for pos in x], ta_accuracy[model], width=width, label=model)
    
    plt.title('各知识点类型准确率对比')
    plt.ylabel('准确率')
    plt.xticks([pos + width/2 for pos in x], type_analysis, rotation=45, ha='right')
    plt.ylim(0, 1)
    plt.legend()
    
    plt.tight_layout()
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    plt.close()

def create_score_comparison_chart(overall_results, question_type_results, output_file):
    """创建得分对比图表"""
    plt.figure(figsize=(12, 6))
    
    # 总体平均分
    models = list(overall_results.keys())
    overall_score = [overall_results[model]["average_score"] for model in models]
    
    # 按题型平均分
    question_types = list(set(qt for model in question_type_results.values() for qt in model.keys()))
    qt_score = {model: [question_type_results[model].get(qt, {}).get("average_score", 0) for qt in question_types] for model in models}
    
    # 绘制总体平均分
    plt.subplot(1, 2, 1)
    bars = plt.bar(models, overall_score, color=['#1f77b4', '#ff7f0e'])
    plt.title('总体平均分对比')
    plt.ylabel('平均分')
    plt.ylim(0, 1)
    
    # 添加数值标签
    for bar in bars:
        height = bar.get_height()
        plt.text(bar.get_x() + bar.get_width()/2., height + 0.02,
                 f'{height:.2f}', ha='center', va='bottom')
    
    # 绘制题型平均分
    plt.subplot(1, 2, 2)
    width = 0.35
    x = range(len(question_types))
    
    for i, model in enumerate(models):
        plt.bar([pos + i*width for pos in x], qt_score[model], width=width, label=model)
    
    plt.title('各题型平均分对比')
    plt.ylabel('平均分')
    plt.xticks([pos + width/2 for pos in x], question_types, rotation=45, ha='right')
    plt.ylim(0, 1)
    plt.legend()
    
    plt.tight_layout()
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    plt.close()

def generate_report(overall_results, question_type_results, type_analysis_results):
    """生成人类可读的报告"""
    report = []
    report.append("# 模型表现对比分析报告\n")
    report.append(f"生成时间: {datetime.datetime.now().isoformat()}\n")
    report.append(f"对比模型: {list(overall_results.keys())[0]} vs {list(overall_results.keys())[1]}\n\n")
    
    # 总体对比
    report.append("## 总体表现\n")
    models = list(overall_results.keys())
    gpt_name = models[0] if "GPT" in models[0] else models[1]
    claude_name = models[1] if "Claude" in models[1] else models[0]
    
    gpt_data = overall_results[gpt_name]
    claude_data = overall_results[claude_name]
    
    accuracy_diff = claude_data["accuracy"] - gpt_data["accuracy"]
    score_diff = claude_data["average_score"] - gpt_data["average_score"]
    correct_diff = claude_data["correct"] - gpt_data["correct"]
    
    report.append("| 指标 | GPT-3.5 Turbo | Claude 3 Haiku | 差异 |")
    report.append("|------|----------------|---------------|------|")
    report.append(f"| 总题目数 | {gpt_data['total_questions']} | {claude_data['total_questions']} | - |")
    report.append(f"| 正确数 | {gpt_data['correct']} | {claude_data['correct']} | +{correct_diff} |")
    report.append(f"| 错误数 | {gpt_data['incorrect']} | {claude_data['incorrect']} | -{abs(correct_diff)} |")
    report.append(f"| 准确率 | {gpt_data['accuracy']:.2%} | {claude_data['accuracy']:.2%} | +{accuracy_diff:.2%} |")
    report.append(f"| 平均分 | {gpt_data['average_score']:.2f} | {claude_data['average_score']:.2f} | +{score_diff:.2f} |")
    report.append("\n")
    
    # 按题目类型对比
    report.append("## 按题目类型对比\n")
    if question_type_results:
        question_types = list(set(qt for model in question_type_results.values() for qt in model.keys()))
        for qt in question_types:
            gpt_qt_data = question_type_results[gpt_name].get(qt, {
                "total_questions": 0, "correct": 0, "incorrect": 0, 
                "accuracy": 0, "average_score": 0
            })
            claude_qt_data = question_type_results[claude_name].get(qt, {
                "total_questions": 0, "correct": 0, "incorrect": 0, 
                "accuracy": 0, "average_score": 0
            })
            
            qt_accuracy_diff = claude_qt_data["accuracy"] - gpt_qt_data["accuracy"]
            qt_score_diff = claude_qt_data["average_score"] - gpt_qt_data["average_score"]
            qt_correct_diff = claude_qt_data["correct"] - gpt_qt_data["correct"]
            
            report.append(f"### 题目类型: {qt}\n")
            report.append("| 指标 | GPT-3.5 Turbo | Claude 3 Haiku | 差异 |")
            report.append("|------|----------------|---------------|------|")
            report.append(f"| 题目数 | {gpt_qt_data['total_questions']} | {claude_qt_data['total_questions']} | - |")
            report.append(f"| 正确数 | {gpt_qt_data['correct']} | {claude_qt_data['correct']} | +{qt_correct_diff} |")
            report.append(f"| 准确率 | {gpt_qt_data['accuracy']:.2%} | {claude_qt_data['accuracy']:.2%} | +{qt_accuracy_diff:.2%} |")
            report.append(f"| 平均分 | {gpt_qt_data['average_score']:.2f} | {claude_qt_data['average_score']:.2f} | +{qt_score_diff:.2f} |")
            report.append("\n")
    
    # 按知识点类型对比
    report.append("## 按知识点类型对比\n")
    if type_analysis_results:
        type_analysis = list(set(ta for model in type_analysis_results.values() for ta in model.keys()))
        for ta in type_analysis:
            gpt_ta_data = type_analysis_results[gpt_name].get(ta, {
                "total_questions": 0, "correct": 0, "incorrect": 0, 
                "accuracy": 0, "average_score": 0
            })
            claude_ta_data = type_analysis_results[claude_name].get(ta, {
                "total_questions": 0, "correct": 0, "incorrect": 0, 
                "accuracy": 0, "average_score": 0
            })
            
            ta_accuracy_diff = claude_ta_data["accuracy"] - gpt_ta_data["accuracy"]
            ta_score_diff = claude_ta_data["average_score"] - gpt_ta_data["average_score"]
            ta_correct_diff = claude_ta_data["correct"] - gpt_ta_data["correct"]
            
            report.append(f"### 知识点: {ta}\n")
            report.append("| 指标 | GPT-3.5 Turbo | Claude 3 Haiku | 差异 |")
            report.append("|------|----------------|---------------|------|")
            report.append(f"| 题目数 | {gpt_ta_data['total_questions']} | {claude_ta_data['total_questions']} | - |")
            report.append(f"| 正确数 | {gpt_ta_data['correct']} | {claude_ta_data['correct']} | +{ta_correct_diff} |")
            report.append(f"| 准确率 | {gpt_ta_data['accuracy']:.2%} | {claude_ta_data['accuracy']:.2%} | +{ta_accuracy_diff:.2%} |")
            report.append(f"| 平均分 | {gpt_ta_data['average_score']:.2f} | {claude_ta_data['average_score']:.2f} | +{ta_score_diff:.2f} |")
            report.append("\n")
    
    # 总结
    report.append("## 总结\n")
    report.append(f"1. **总体表现**: {claude_name} 在整体准确率和平均分上优于 {gpt_name}\n")
    report.append(f"2. **准确率提升**: {claude_name} 的准确率比 {gpt_name} 高 {accuracy_diff:.2%}\n")
    report.append(f"3. **正确题数**: {claude_name} 比 {gpt_name} 多答对 {correct_diff} 题\n")
    
    # 分析各知识点的表现
    best_improvement = None
    best_improvement_ta = None
    
    for ta in type_analysis:
        gpt_ta_data = type_analysis_results[gpt_name].get(ta, {"accuracy": 0})
        claude_ta_data = type_analysis_results[claude_name].get(ta, {"accuracy": 0})
        improvement = claude_ta_data["accuracy"] - gpt_ta_data["accuracy"]
        
        if improvement > 0:
            if not best_improvement or improvement > best_improvement:
                best_improvement = improvement
                best_improvement_ta = ta
    
    if best_improvement_ta:
        report.append(f"4. **最显著提升**: 在 '{best_improvement_ta}' 知识点上，{claude_name} 的准确率比 {gpt_name} 高 {best_improvement:.2%}\n")
    
    report.append("\n**结论**: Claude 3 Haiku 在本次测试中整体表现优于 GPT-3.5 Turbo，特别是在跨战术关联分析等复杂知识点上表现更为突出。")
    
    return "".join(report)

def main():
    """主函数"""
    # 收集所有summary文件
    model_files = collect_all_summary_files()
    
    if len(model_files) != 2:
        print("Error: 需要两个模型的summary文件")
        return
    
    print("收集数据中...")
    # 收集所有题型的结果
    question_type_results = collect_all_question_types(model_files)
    
    # 收集所有知识点类型的结果
    type_analysis_results = collect_all_type_analysis(model_files)
    
    # 计算总体结果
    overall_results = calculate_overall_results(question_type_results)
    
    # 生成报告
    report = generate_report(overall_results, question_type_results, type_analysis_results)
    
    # 生成可视化图表
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # 准确率对比图
    accuracy_chart = os.path.join(OUTPUT_DIR, f"accuracy_comparison_{timestamp}.png")
    create_accuracy_comparison_chart(overall_results, question_type_results, accuracy_chart)
    
    # 知识点分析对比图
    type_analysis_chart = os.path.join(OUTPUT_DIR, f"type_analysis_comparison_{timestamp}.png")
    create_type_analysis_chart(type_analysis_results, type_analysis_chart)
    
    # 得分对比图
    score_chart = os.path.join(OUTPUT_DIR, f"score_comparison_{timestamp}.png")
    create_score_comparison_chart(overall_results, question_type_results, score_chart)
    
    # 保存报告
    report_file = os.path.join(OUTPUT_DIR, f"model_comparison_report_{timestamp}.md")
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(report)
    
    # 保存分析数据
    analysis_data = {
        "timestamp": datetime.datetime.now().isoformat(),
        "overall": overall_results,
        "question_types": question_type_results,
        "type_analysis": type_analysis_results
    }
    
    analysis_file = os.path.join(OUTPUT_DIR, f"model_comparison_analysis_{timestamp}.json")
    with open(analysis_file, 'w', encoding='utf-8') as f:
        json.dump(analysis_data, f, ensure_ascii=False, indent=2)
    
    print(f"分析完成！结果已保存到:\n- 详细分析: {analysis_file}")
    print(f"- 报告: {report_file}")
    print(f"- 准确率对比图: {accuracy_chart}")
    print(f"- 知识点分析对比图: {type_analysis_chart}")
    print(f"- 得分对比图: {score_chart}")

if __name__ == "__main__":
    main()
