"""
为排序题添加 question_type 标签

根据 tactic_technique 字段判断题目类型：
- "TAxxxx-multiple" 格式 → 技术关联分析（单个战术下的多技术组合）
- "CROSS-multiple" 格式 → 跨战术关联分析（跨多个战术）

question_type 字段插入到 JSON 的第三个位置
"""

import json
import os
import argparse
from datetime import datetime
from collections import OrderedDict


def detect_question_category(tactic_technique: str) -> str:
    """
    根据 tactic_technique 判断题目分类
    
    规则：
    1. "TAxxxx-multiple" 格式 → 技术关联分析
    2. "CROSS-multiple" 格式 → 跨战术关联分析
    """
    if not tactic_technique:
        return "技术关联分析"
    
    # 检查是否为跨战术格式
    if tactic_technique.startswith("CROSS"):
        return "跨战术关联分析"
    
    # 其他情况（TAxxxx-multiple）→ 技术关联分析
    return "技术关联分析"


def insert_question_type_ordered(question: dict, category: str) -> OrderedDict:
    """
    将 question_type 插入到第三个位置
    
    字段顺序：
    1. question_id
    2. tactic_technique
    3. question_type (新插入)
    4. difficulty
    5. question
    6. options
    7. correct_answer
    8. explanation
    9. involved_techniques
    10. test_prompt
    """
    ordered = OrderedDict()
    
    # 第1个：question_id
    if "question_id" in question:
        ordered["question_id"] = question["question_id"]
    
    # 第2个：tactic_technique
    if "tactic_technique" in question:
        ordered["tactic_technique"] = question["tactic_technique"]
    
    # 第3个：question_type (新插入)
    ordered["question_type"] = category
    
    # 第4个：difficulty
    if "difficulty" in question:
        ordered["difficulty"] = question["difficulty"]
    
    # 第5个：question
    if "question" in question:
        ordered["question"] = question["question"]
    
    # 第6个：options
    if "options" in question:
        ordered["options"] = question["options"]
    
    # 第7个：correct_answer
    if "correct_answer" in question:
        ordered["correct_answer"] = question["correct_answer"]
    
    # 第8个：explanation
    if "explanation" in question:
        ordered["explanation"] = question["explanation"]
    
    # 第9个：involved_techniques
    if "involved_techniques" in question:
        ordered["involved_techniques"] = question["involved_techniques"]
    
    # 第10个：test_prompt
    if "test_prompt" in question:
        ordered["test_prompt"] = question["test_prompt"]
    
    # 添加可能存在的其他字段（保持原有顺序）
    for key, value in question.items():
        if key not in ordered:
            ordered[key] = value
    
    return ordered


def process_sequencing_file(input_path: str, output_path: str = None):
    """处理排序题文件，添加 question_type 字段到第三个位置"""
    
    print(f"处理文件: {input_path}")
    
    # 读取题目
    questions = []
    with open(input_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                questions.append(json.loads(line))
    
    print(f"共读取 {len(questions)} 道题目")
    
    # 统计分类
    category_stats = {
        "技术关联分析": 0,
        "跨战术关联分析": 0
    }
    
    # 处理每道题目
    processed_questions = []
    for question in questions:
        tactic_technique = question.get("tactic_technique", "")
        category = detect_question_category(tactic_technique)
        category_stats[category] += 1
        
        # 创建有序字典，将 question_type 插入到第三个位置
        ordered_question = insert_question_type_ordered(question, category)
        processed_questions.append(ordered_question)
    
    # 确定输出路径
    if not output_path:
        # 生成带时间戳的输出文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_name = os.path.basename(input_path)
        name, ext = os.path.splitext(base_name)
        # 移除之前可能添加的 _with_type_ 后缀
        if "_with_type_" in name:
            name = name.split("_with_type_")[0]
        output_path = os.path.join(
            os.path.dirname(input_path),
            f"{name}_with_type_{timestamp}{ext}"
        )
    
    # 保存处理后的题目
    with open(output_path, 'w', encoding='utf-8') as f:
        for question in processed_questions:
            f.write(json.dumps(question, ensure_ascii=False) + '\n')
    
    print(f"\n处理完成！")
    print(f"  技术关联分析: {category_stats['技术关联分析']} 道")
    print(f"  跨战术关联分析: {category_stats['跨战术关联分析']} 道")
    print(f"输出文件: {output_path}")
    
    return output_path


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="为排序题添加 question_type 标签")
    parser.add_argument(
        "--input",
        type=str,
        required=True,
        help="输入排序题文件路径"
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="输出文件路径（可选，默认自动生成）"
    )
    
    args = parser.parse_args()
    
    if not os.path.exists(args.input):
        print(f"错误: 输入文件不存在: {args.input}")
        return
    
    process_sequencing_file(args.input, args.output)


if __name__ == "__main__":
    main()
