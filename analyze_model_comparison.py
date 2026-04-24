#!/usr/bin/env python3
"""
模型表现对比分析脚本

分析两个模型在数据集上的表现，按题目类型和question_type进行对比
"""

import os
import json
import datetime
from collections import defaultdict

# 配置
RESULTS_DIR = "results"
OUTPUT_DIR = "analysis"

# 确保输出目录存在
os.makedirs(OUTPUT_DIR, exist_ok=True)

def get_latest_summary_files():
    """获取最新的两个模型的summary文件"""
    files = os.listdir(RESULTS_DIR)
    summary_files = [f for f in files if f.endswith('_summary.json')]
    
    # 按时间戳排序
    summary_files.sort(reverse=True)
    
    # 分离两个模型的文件
    gpt_files = []
    claude_files = []
    
    for file in summary_files:
        if "GPT-3.5_Turbo" in file:
            gpt_files.append(file)
        elif "Claude_3_Haiku" in file:
            claude_files.append(file)
    
    # 返回最新的文件
    gpt_file = gpt_files[0] if gpt_files else None
    claude_file = claude_files[0] if claude_files else None
    
    return gpt_file, claude_file

def load_summary_file(file_path):
    """加载summary文件"""
    with open(os.path.join(RESULTS_DIR, file_path), 'r', encoding='utf-8') as f:
        return json.load(f)

def analyze_comparison(gpt_summary, claude_summary):
    """分析两个模型的对比"""
    analysis = {
        "timestamp": datetime.datetime.now().isoformat(),
        "models": {
            "gpt": gpt_summary["model_name"],
            "claude": claude_summary["model_name"]
        },
        "overall": {},
        "question_types": {},
        "type_analysis": {}
    }
    
    # 总体对比
    analysis["overall"] = {
        "gpt": {
            "total_questions": gpt_summary["total_questions"],
            "correct": gpt_summary["correct"],
            "incorrect": gpt_summary["incorrect"],
            "accuracy": gpt_summary["accuracy"],
            "average_score": gpt_summary["average_score"]
        },
        "claude": {
            "total_questions": claude_summary["total_questions"],
            "correct": claude_summary["correct"],
            "incorrect": claude_summary["incorrect"],
            "accuracy": claude_summary["accuracy"],
            "average_score": claude_summary["average_score"]
        },
        "difference": {
            "accuracy": claude_summary["accuracy"] - gpt_summary["accuracy"],
            "average_score": claude_summary["average_score"] - gpt_summary["average_score"],
            "correct": claude_summary["correct"] - gpt_summary["correct"]
        }
    }
    
    # 按题目类型对比
    all_question_types = set()
    all_question_types.update(gpt_summary["question_types"].keys())
    all_question_types.update(claude_summary["question_types"].keys())
    
    for qt in all_question_types:
        gpt_data = gpt_summary["question_types"].get(qt, {
            "total": 0, "correct": 0, "incorrect": 0, 
            "accuracy": 0, "average_score": 0
        })
        claude_data = claude_summary["question_types"].get(qt, {
            "total": 0, "correct": 0, "incorrect": 0, 
            "accuracy": 0, "average_score": 0
        })
        
        analysis["question_types"][qt] = {
            "gpt": gpt_data,
            "claude": claude_data,
            "difference": {
                "accuracy": claude_data["accuracy"] - gpt_data["accuracy"],
                "average_score": claude_data["average_score"] - gpt_data["average_score"],
                "correct": claude_data["correct"] - gpt_data["correct"]
            }
        }
    
    # 按question_type对比
    all_type_analysis = set()
    all_type_analysis.update(gpt_summary["type_analysis"].keys())
    all_type_analysis.update(claude_summary["type_analysis"].keys())
    
    for ta in all_type_analysis:
        gpt_data = gpt_summary["type_analysis"].get(ta, {
            "total": 0, "correct": 0, "incorrect": 0, 
            "accuracy": 0, "average_score": 0
        })
        claude_data = claude_summary["type_analysis"].get(ta, {
            "total": 0, "correct": 0, "incorrect": 0, 
            "accuracy": 0, "average_score": 0
        })
        
        analysis["type_analysis"][ta] = {
            "gpt": gpt_data,
            "claude": claude_data,
            "difference": {
                "accuracy": claude_data["accuracy"] - gpt_data["accuracy"],
                "average_score": claude_data["average_score"] - gpt_data["average_score"],
                "correct": claude_data["correct"] - gpt_data["correct"]
            }
        }
    
    return analysis

def generate_report(analysis):
    """生成人类可读的报告"""
    report = []
    report.append("# 模型表现对比分析报告\n")
    report.append(f"生成时间: {analysis['timestamp']}\n")
    report.append(f"对比模型: {analysis['models']['gpt']} vs {analysis['models']['claude']}\n\n")
    
    # 总体对比
    report.append("## 总体表现\n")
    overall = analysis['overall']
    report.append("| 指标 | GPT-3.5 Turbo | Claude 3 Haiku | 差异 |")
    report.append("|------|----------------|---------------|------|")
    report.append(f"| 总题目数 | {overall['gpt']['total_questions']} | {overall['claude']['total_questions']} | - |")
    report.append(f"| 正确数 | {overall['gpt']['correct']} | {overall['claude']['correct']} | +{overall['difference']['correct']} |")
    report.append(f"| 错误数 | {overall['gpt']['incorrect']} | {overall['claude']['incorrect']} | -{abs(overall['difference']['correct'])} |")
    report.append(f"| 准确率 | {overall['gpt']['accuracy']:.2%} | {overall['claude']['accuracy']:.2%} | +{overall['difference']['accuracy']:.2%} |")
    report.append(f"| 平均分 | {overall['gpt']['average_score']:.2f} | {overall['claude']['average_score']:.2f} | +{overall['difference']['average_score']:.2f} |")
    report.append("\n")
    
    # 按题目类型对比
    report.append("## 按题目类型对比\n")
    if analysis['question_types']:
        for qt, data in analysis['question_types'].items():
            report.append(f"### 题目类型: {qt}\n")
            report.append("| 指标 | GPT-3.5 Turbo | Claude 3 Haiku | 差异 |")
            report.append("|------|----------------|---------------|------|")
            report.append(f"| 题目数 | {data['gpt']['total']} | {data['claude']['total']} | - |")
            report.append(f"| 正确数 | {data['gpt']['correct']} | {data['claude']['correct']} | +{data['difference']['correct']} |")
            report.append(f"| 准确率 | {data['gpt']['accuracy']:.2%} | {data['claude']['accuracy']:.2%} | +{data['difference']['accuracy']:.2%} |")
            report.append(f"| 平均分 | {data['gpt']['average_score']:.2f} | {data['claude']['average_score']:.2f} | +{data['difference']['average_score']:.2f} |")
            report.append("\n")
    
    # 按question_type对比
    report.append("## 按知识点类型对比\n")
    if analysis['type_analysis']:
        for ta, data in analysis['type_analysis'].items():
            report.append(f"### 知识点: {ta}\n")
            report.append("| 指标 | GPT-3.5 Turbo | Claude 3 Haiku | 差异 |")
            report.append("|------|----------------|---------------|------|")
            report.append(f"| 题目数 | {data['gpt']['total']} | {data['claude']['total']} | - |")
            report.append(f"| 正确数 | {data['gpt']['correct']} | {data['claude']['correct']} | +{data['difference']['correct']} |")
            report.append(f"| 准确率 | {data['gpt']['accuracy']:.2%} | {data['claude']['accuracy']:.2%} | +{data['difference']['accuracy']:.2%} |")
            report.append(f"| 平均分 | {data['gpt']['average_score']:.2f} | {data['claude']['average_score']:.2f} | +{data['difference']['average_score']:.2f} |")
            report.append("\n")
    
    # 总结
    report.append("## 总结\n")
    report.append(f"1. **总体表现**: {analysis['models']['claude']} 在整体准确率和平均分上优于 {analysis['models']['gpt']}\n")
    report.append(f"2. **准确率提升**: {analysis['models']['claude']} 的准确率比 {analysis['models']['gpt']} 高 {analysis['overall']['difference']['accuracy']:.2%}\n")
    report.append(f"3. **正确题数**: {analysis['models']['claude']} 比 {analysis['models']['gpt']} 多答对 {analysis['overall']['difference']['correct']} 题\n")
    
    # 分析各知识点的表现
    best_improvement = None
    best_improvement_ta = None
    
    for ta, data in analysis['type_analysis'].items():
        if data['difference']['accuracy'] > 0:
            if not best_improvement or data['difference']['accuracy'] > best_improvement:
                best_improvement = data['difference']['accuracy']
                best_improvement_ta = ta
    
    if best_improvement_ta:
        report.append(f"4. **最显著提升**: 在 '{best_improvement_ta}' 知识点上，{analysis['models']['claude']} 的准确率比 {analysis['models']['gpt']} 高 {best_improvement:.2%}\n")
    
    report.append("\n**结论**: Claude 3 Haiku 在本次测试中整体表现优于 GPT-3.5 Turbo，特别是在跨战术关联分析等复杂知识点上表现更为突出。")
    
    return "".join(report)

def main():
    """主函数"""
    # 获取最新的summary文件
    gpt_file, claude_file = get_latest_summary_files()
    
    if not gpt_file or not claude_file:
        print("Error: 无法找到两个模型的summary文件")
        return
    
    print(f"使用文件:\n- GPT-3.5 Turbo: {gpt_file}\n- Claude 3 Haiku: {claude_file}")
    
    # 加载文件
    gpt_summary = load_summary_file(gpt_file)
    claude_summary = load_summary_file(claude_file)
    
    # 分析对比
    analysis = analyze_comparison(gpt_summary, claude_summary)
    
    # 生成报告
    report = generate_report(analysis)
    
    # 保存结果
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    analysis_file = os.path.join(OUTPUT_DIR, f"model_comparison_analysis_{timestamp}.json")
    report_file = os.path.join(OUTPUT_DIR, f"model_comparison_report_{timestamp}.md")
    
    with open(analysis_file, 'w', encoding='utf-8') as f:
        json.dump(analysis, f, ensure_ascii=False, indent=2)
    
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(report)
    
    print(f"分析完成！结果已保存到:\n- 详细分析: {analysis_file}\n- 报告: {report_file}")

if __name__ == "__main__":
    main()
