"""
简单数据集评估脚本

功能：
1. 评估文件夹内的所有文件
2. 根据question_Id标签收集题型
3. 收集设计的战术技术
4. 收集question_type
5. 简单的结果呈现
"""

import json
import os
from collections import defaultdict
from question_metadata import resolve_capability_dimension, resolve_question_form


def process_file(file_path):
    """处理单个文件"""
    questions = []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            # 读取所有内容
            content = f.read()
            
            # 尝试按JSON对象处理
            try:
                data = json.loads(content)
                if isinstance(data, list):
                    # 如果是数组，直接添加所有元素
                    questions.extend(data)
                elif isinstance(data, dict):
                    # 如果是对象，检查是否包含questions或items字段
                    if 'questions' in data:
                        questions.extend(data['questions'])
                    elif 'items' in data:
                        questions.extend(data['items'])
                    else:
                        # 否则将整个对象作为一个题目
                        questions.append(data)
            except json.JSONDecodeError:
                # 如果不是有效的JSON对象，尝试按JSONL格式处理
                f.seek(0)  # 重置文件指针
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            questions.append(json.loads(line))
                        except json.JSONDecodeError:
                            # 跳过无法解析的行
                            pass
    except Exception as e:
        print(f"处理文件 {file_path} 时出错: {e}")
    return questions


def evaluate_dataset_folder(folder_path):
    """评估文件夹内的所有文件"""
    print(f"开始评估文件夹: {folder_path}")
    print("=" * 60)
    
    # 收集所有文件
    dataset_files = []
    for root, _, files in os.walk(folder_path):
        for file in files:
            if file.endswith('.jsonl') or file.endswith('.json'):
                dataset_files.append(os.path.join(root, file))
    
    if not dataset_files:
        print("错误: 文件夹中没有找到 .jsonl 或 .json 文件")
        return
    
    print(f"找到 {len(dataset_files)} 个数据集文件")
    
    # 统计变量
    total_questions = 0
    question_types = defaultdict(int)  # 按题目ID前缀统计的题型
    question_type_tags = defaultdict(int)  # 按question_type标签统计的题型
    tactics = defaultdict(int)  # 战术
    techniques = defaultdict(int)  # 技术
    sub_techniques = defaultdict(int)  # 子技术
    
    # 处理每个文件
    for file_path in dataset_files:
        print(f"\n处理文件: {os.path.basename(file_path)}")
        questions = process_file(file_path)
        
        file_questions = len(questions)
        total_questions += file_questions
        print(f"  包含题目数: {file_questions}")
        
        # 统计每个文件的内容
        for q in questions:
            # 统计题型（根据question_id）
            q_type = resolve_question_form(q)
            question_types[q_type] += 1
            
            # 统计question_type标签
            q_type_tag = resolve_capability_dimension(q)
            question_type_tags[q_type_tag] += 1
            
            # 统计战术技术
            tactic_technique = q.get("tactic_technique", "")
            if tactic_technique:
                parts = tactic_technique.split("-")
                if len(parts) >= 2:
                    tactic_id = parts[0]
                    technique_id = parts[1]
                    tactics[tactic_id] += 1
                    techniques[technique_id] += 1
                if len(parts) >= 3:
                    sub_technique_id = f"{parts[1]}.{parts[2]}"
                    sub_techniques[sub_technique_id] += 1
    
    # 生成结果报告
    print("\n" + "=" * 60)
    print("【评估结果】")
    print("=" * 60)
    
    print(f"\n基本信息:")
    print(f"  总文件数: {len(dataset_files)}")
    print(f"  总题目数: {total_questions}")
    
    print(f"\n题型分布（按question_id前缀）:")
    for q_type, count in sorted(question_types.items()):
        percentage = (count / total_questions * 100) if total_questions > 0 else 0
        print(f"  {q_type}: {count} ({percentage:.1f}%)")
    
    print(f"\n题型分布（按question_type标签）:")
    for q_type, count in sorted(question_type_tags.items()):
        percentage = (count / total_questions * 100) if total_questions > 0 else 0
        print(f"  {q_type}: {count} ({percentage:.1f}%)")
    
    print(f"\n战术覆盖:")
    print(f"  覆盖战术数: {len(tactics)}")
    if tactics:
        print("  战术详情:")
        for tactic, count in sorted(tactics.items())[:10]:  # 只显示前10个
            print(f"    {tactic}: {count}")
        if len(tactics) > 10:
            print(f"    ... 还有 {len(tactics) - 10} 个战术")
    
    print(f"\n技术覆盖:")
    print(f"  覆盖技术数: {len(techniques)}")
    if techniques:
        print("  技术详情:")
        for technique, count in sorted(techniques.items())[:10]:  # 只显示前10个
            print(f"    {technique}: {count}")
        if len(techniques) > 10:
            print(f"    ... 还有 {len(techniques) - 10} 个技术")
    
    print(f"\n子技术覆盖:")
    print(f"  覆盖子技术数: {len(sub_techniques)}")
    if sub_techniques:
        print("  子技术详情:")
        for sub_technique, count in sorted(sub_techniques.items())[:10]:  # 只显示前10个
            print(f"    {sub_technique}: {count}")
        if len(sub_techniques) > 10:
            print(f"    ... 还有 {len(sub_techniques) - 10} 个子技术")
    
    # 保存结果
    result = {
        "evaluation_time": os.path.getmtime(__file__),
        "folder_path": folder_path,
        "file_count": len(dataset_files),
        "total_questions": total_questions,
        "question_types": dict(question_types),
        "question_type_tags": dict(question_type_tags),
        "tactics": dict(tactics),
        "techniques": dict(techniques),
        "sub_techniques": dict(sub_techniques)
    }
    
    output_file = os.path.join(folder_path, "evaluation_summary.json")
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    print(f"\n评估结果已保存到: {output_file}")
    
    return result


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="简单数据集评估")
    parser.add_argument(
        "--folder",
        type=str,
        required=True,
        help="数据集文件夹路径"
    )

    args = parser.parse_args()

    if not os.path.exists(args.folder):
        print(f"错误: 文件夹不存在: {args.folder}")
        return

    if not os.path.isdir(args.folder):
        print(f"错误: 不是文件夹: {args.folder}")
        return

    evaluate_dataset_folder(args.folder)


if __name__ == "__main__":
    main()
