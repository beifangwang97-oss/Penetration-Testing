"""
数据集质量评估脚本

功能：
1. 分析数据集覆盖的战术和技术
2. 统计难度分布
3. 计算覆盖程度
4. 给出数据集整体评价
"""

import json
import os
from collections import defaultdict
from datetime import datetime


def load_questions(input_path: str) -> list:
    """加载题目"""
    questions = []
    with open(input_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                questions.append(json.loads(line))
    return questions


def load_attack_data(attack_data_path: str = "data/attack_data.json") -> dict:
    """加载ATT&CK框架数据"""
    if not os.path.exists(attack_data_path):
        print(f"警告: ATT&CK数据文件不存在: {attack_data_path}")
        return {"tactics": {}, "techniques": {}, "sub_techniques": {}}

    with open(attack_data_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    tactics = {}
    techniques = {}
    sub_techniques = {}

    # 遍历tactics数组
    for tactic in data.get("tactics", []):
        tactic_id = tactic.get("id", "")
        tactic_name = tactic.get("name", "")
        if tactic_id:
            tactics[tactic_id] = {"id": tactic_id, "name": tactic_name}

        # 遍历techniques
        for technique in tactic.get("techniques", []):
            technique_id = technique.get("id", "")
            technique_name = technique.get("name", "")
            if technique_id:
                techniques[technique_id] = {"id": technique_id, "name": technique_name}

            # 遍历sub_techniques
            for sub_technique in technique.get("sub_techniques", []):
                sub_technique_id = sub_technique.get("id", "")
                sub_technique_name = sub_technique.get("name", "")
                if sub_technique_id:
                    sub_techniques[sub_technique_id] = {"id": sub_technique_id, "name": sub_technique_name}

    return {
        "tactics": tactics,
        "techniques": techniques,
        "sub_techniques": sub_techniques
    }


def evaluate_dataset(input_path: str, output_dir: str = "evaluation_output"):
    """评估数据集质量"""
    print(f"开始评估数据集质量")
    print(f"输入文件: {input_path}")
    print("=" * 60)

    # 加载题目
    questions = load_questions(input_path)
    total_questions = len(questions)
    print(f"总题目数: {total_questions}\n")

    if total_questions == 0:
        print("错误: 数据集为空")
        return

    # 加载ATT&CK数据
    attack_data = load_attack_data()
    total_tactics = len(attack_data["tactics"])
    total_techniques = len(attack_data["techniques"])
    total_sub_techniques = len(attack_data["sub_techniques"])

    # 统计变量
    difficulty_count = defaultdict(int)
    tactic_count = defaultdict(int)
    technique_count = defaultdict(int)
    sub_technique_count = defaultdict(int)
    question_types = defaultdict(int)

    # 题目质量检查
    quality_issues = []
    valid_questions = 0

    for idx, q in enumerate(questions, 1):
        # 统计题型
        question_id = q.get("question_id", "")
        if question_id:
            q_type = question_id.split("-")[0] if "-" in question_id else "Unknown"
            question_types[q_type] += 1

        # 统计难度
        difficulty = q.get("difficulty", "unknown")
        difficulty_count[difficulty] += 1

        # 解析战术技术
        tactic_technique = q.get("tactic_technique", "")
        if tactic_technique:
            parts = tactic_technique.split("-")
            if len(parts) >= 2:
                tactic_id = parts[0]
                technique_id = parts[1]
                tactic_count[tactic_id] += 1
                technique_count[technique_id] += 1
            if len(parts) >= 3:
                sub_technique_id = f"{parts[1]}.{parts[2]}"
                sub_technique_count[sub_technique_id] += 1

        # 质量检查
        issues = []
        if not q.get("question"):
            issues.append("缺少题目内容")
        if not q.get("options") or len(q.get("options", {})) < 2:
            issues.append("选项不足")
        if not q.get("correct_answer"):
            issues.append("缺少正确答案")
        if not q.get("explanation"):
            issues.append("缺少解析")
        if not q.get("test_prompt"):
            issues.append("缺少测试prompt")
        if q_type == "SSC":
            if not q.get("scenario"):
                issues.append("缺少场景描述")
            elif len(q.get("scenario", "").strip()) < 60:
                issues.append("场景描述过短")
            if len(q.get("options", {})) != 4:
                issues.append("场景单选题选项数应为4")
            if not q.get("related_techniques"):
                issues.append("缺少关联技术")

        if issues:
            quality_issues.append({
                "question_id": question_id,
                "issues": issues
            })
        else:
            valid_questions += 1

    # 计算覆盖率
    covered_tactics = len(tactic_count)
    covered_techniques = len(technique_count)
    covered_sub_techniques = len(sub_technique_count)

    tactic_coverage = (covered_tactics / total_tactics * 100) if total_tactics > 0 else 0
    technique_coverage = (covered_techniques / total_techniques * 100) if total_techniques > 0 else 0
    sub_technique_coverage = (covered_sub_techniques / total_sub_techniques * 100) if total_sub_techniques > 0 else 0

    # 计算难度系数 (加权平均: easy=1, medium=2, hard=3)
    difficulty_weights = {"easy": 1, "medium": 2, "hard": 3}
    total_difficulty_score = 0
    total_weighted_count = 0
    for diff, count in difficulty_count.items():
        weight = difficulty_weights.get(diff, 2)
        total_difficulty_score += weight * count
        total_weighted_count += count

    difficulty_score = (total_difficulty_score / total_weighted_count) if total_weighted_count > 0 else 2.0

    # 计算质量分数
    quality_score = (valid_questions / total_questions * 100) if total_questions > 0 else 0

    # 计算综合评分
    # 覆盖程度权重: 战术30%, 技术50%, 子技术20%
    coverage_score = tactic_coverage * 0.3 + technique_coverage * 0.5 + sub_technique_coverage * 0.2

    # 综合评分: 覆盖程度40%, 质量30%, 难度分布合理性30%
    # 难度分布合理性: 理想分布为 easy:30%, medium:50%, hard:20%
    ideal_distribution = {"easy": 0.3, "medium": 0.5, "hard": 0.2}
    distribution_score = 0
    for diff in ["easy", "medium", "hard"]:
        actual_ratio = difficulty_count.get(diff, 0) / total_questions if total_questions > 0 else 0
        ideal_ratio = ideal_distribution.get(diff, 0)
        diff_score = 1 - abs(actual_ratio - ideal_ratio)
        distribution_score += diff_score * (1/3)
    distribution_score *= 100

    overall_score = coverage_score * 0.4 + quality_score * 0.3 + distribution_score * 0.3

    # 生成评价
    def get_rating(score):
        if score >= 90:
            return "优秀"
        elif score >= 75:
            return "良好"
        elif score >= 60:
            return "合格"
        else:
            return "需改进"

    # 输出报告
    print("=" * 60)
    print("【数据集质量评估报告】")
    print("=" * 60)

    print("\n【基本信息】")
    print(f"  总题目数: {total_questions}")
    print(f"  有效题目数: {valid_questions}")
    print(f"  题型分布: {dict(question_types)}")

    print("\n【难度分布】")
    for diff in ["easy", "medium", "hard", "unknown"]:
        count = difficulty_count.get(diff, 0)
        ratio = (count / total_questions * 100) if total_questions > 0 else 0
        print(f"  {diff}: {count} ({ratio:.1f}%)")
    print(f"  难度系数: {difficulty_score:.2f}/3.0")

    print("\n【覆盖情况】")
    print(f"  战术覆盖: {covered_tactics}/{total_tactics} ({tactic_coverage:.1f}%)")
    print(f"  技术覆盖: {covered_techniques}/{total_techniques} ({technique_coverage:.1f}%)")
    print(f"  子技术覆盖: {covered_sub_techniques}/{total_sub_techniques} ({sub_technique_coverage:.1f}%)")

    print("\n【质量检查】")
    print(f"  质量分数: {quality_score:.1f}%")
    if quality_issues:
        print(f"  存在问题的题目: {len(quality_issues)} 道")
        for issue in quality_issues[:5]:
            print(f"    - {issue['question_id']}: {', '.join(issue['issues'])}")
        if len(quality_issues) > 5:
            print(f"    ... 还有 {len(quality_issues) - 5} 道题目存在问题")
    else:
        print("  所有题目均通过质量检查 ✓")

    print("\n【综合评分】")
    print(f"  覆盖程度: {coverage_score:.1f}%")
    print(f"  质量分数: {quality_score:.1f}%")
    print(f"  难度分布合理性: {distribution_score:.1f}%")
    print(f"  综合评分: {overall_score:.1f}%")
    print(f"  数据集评价: {get_rating(overall_score)}")

    # 保存评估报告
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    report = {
        "evaluation_time": datetime.now().isoformat(),
        "input_file": input_path,
        "basic_info": {
            "total_questions": total_questions,
            "valid_questions": valid_questions,
            "question_types": dict(question_types)
        },
        "difficulty_distribution": {
            "easy": difficulty_count.get("easy", 0),
            "medium": difficulty_count.get("medium", 0),
            "hard": difficulty_count.get("hard", 0),
            "unknown": difficulty_count.get("unknown", 0),
            "difficulty_score": round(difficulty_score, 2)
        },
        "coverage": {
            "tactics": {
                "covered": covered_tactics,
                "total": total_tactics,
                "percentage": round(tactic_coverage, 1)
            },
            "techniques": {
                "covered": covered_techniques,
                "total": total_techniques,
                "percentage": round(technique_coverage, 1)
            },
            "sub_techniques": {
                "covered": covered_sub_techniques,
                "total": total_sub_techniques,
                "percentage": round(sub_technique_coverage, 1)
            },
            "coverage_score": round(coverage_score, 1)
        },
        "quality": {
            "quality_score": round(quality_score, 1),
            "issues_count": len(quality_issues),
            "issues": quality_issues[:10]
        },
        "overall": {
            "coverage_score": round(coverage_score, 1),
            "quality_score": round(quality_score, 1),
            "distribution_score": round(distribution_score, 1),
            "overall_score": round(overall_score, 1),
            "rating": get_rating(overall_score)
        },
        "detailed_coverage": {
            "tactics": dict(tactic_count),
            "techniques": dict(technique_count),
            "sub_techniques": dict(sub_technique_count)
        }
    }

    report_file = os.path.join(output_dir, f"dataset_evaluation_{timestamp}.json")
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"\n评估报告已保存到: {report_file}")

    return report


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="评估数据集质量")
    parser.add_argument(
        "--input",
        type=str,
        required=True,
        help="输入题目文件路径"
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="evaluation_output",
        help="输出目录（默认: evaluation_output）"
    )

    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"错误: 输入文件不存在: {args.input}")
        return

    evaluate_dataset(
        input_path=args.input,
        output_dir=args.output_dir
    )


if __name__ == "__main__":
    main()
