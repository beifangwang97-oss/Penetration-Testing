"""
场景化单项选择题生成脚本

功能：
1. 基于 ATT&CK 技术/子技术生成 SSC 题目
2. 为每道题显式生成 scenario 字段
3. 输出与现有评测链路兼容的 JSONL 文件
"""

import json
import os
import random
import re
import time
import argparse
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

import requests
import yaml
from dotenv import load_dotenv
from tqdm import tqdm
from project_paths import DATASETS_GENERATED_DIR, attack_data_path, ensure_standard_directories

load_dotenv()

# 避免 Windows 终端因 Unicode 符号输出失败
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass


def load_attack_data():
    cache_path = str(attack_data_path())
    if os.path.exists(cache_path):
        from attack_data_loader import load_parsed_data

        return load_parsed_data(cache_path)

    print("错误: 请先运行 attack_data_loader.py 下载数据")
    return None


def load_prompt_template():
    with open("config/prompt_templates.yaml", "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    return config.get("scenario_single_choice", "")


class OpenRouterClient:
    """使用同步 requests 的 OpenRouter 客户端"""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.api_url = "https://openrouter.ai/api/v1/chat/completions"

    def generate(self, model: str, prompt: str, temperature: float = 0.7, max_retries: int = 3) -> dict:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/Athena-Software-Group/athenabench",
            "X-Title": "ATT&CK Scenario Dataset Generator",
        }

        messages = [
            {
                "role": "system",
                "content": "你是一位网络安全渗透测试专家，熟悉 MITRE ATT&CK 框架。请严格按照要求生成场景化单项选择题。",
            },
            {
                "role": "user",
                "content": prompt,
            },
        ]

        data = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
        }

        for attempt in range(max_retries):
            try:
                response = requests.post(self.api_url, headers=headers, json=data, timeout=90)
                if response.status_code == 401:
                    return {
                        "content": "",
                        "error": "Unauthorized: OpenRouter API key 无效、已过期，或当前模型无访问权限",
                    }
                if response.status_code == 429:
                    wait_time = (attempt + 1) * 15
                    print(f"    速率限制，等待 {wait_time} 秒后重试...")
                    time.sleep(wait_time)
                    continue

                response.raise_for_status()
                result = response.json()
                if "choices" in result and result["choices"]:
                    content = result["choices"][0].get("message", {}).get("content", "")
                    return {"content": content, "error": None}
                return {"content": "", "error": "No choices in response"}
            except requests.exceptions.Timeout:
                if attempt < max_retries - 1:
                    time.sleep(5)
                    continue
                return {"content": "", "error": "Request timeout"}
            except requests.exceptions.RequestException as exc:
                if attempt < max_retries - 1:
                    time.sleep(5)
                    continue
                return {"content": "", "error": f"Request error: {exc}"}
            except Exception as exc:
                return {"content": "", "error": f"Error: {exc}"}

        return {"content": "", "error": "Max retries exceeded"}


def extract_json_payload(content: str) -> str:
    json_match = re.search(r"```json\s*(.*?)\s*```", content, re.DOTALL)
    if json_match:
        return json_match.group(1).strip()

    json_match = re.search(r"\{.*\}", content, re.DOTALL)
    if json_match:
        return json_match.group(0).strip()

    return content.strip()


def build_test_prompt(question_data: dict) -> str:
    options = question_data.get("options", {})
    return f"""你是一位网络安全专家，请阅读以下攻击场景并回答单项选择题：

场景：
{question_data.get('scenario', '')}

问题：
{question_data.get('question', '')}

选项：
A. {options.get('A', '')}
B. {options.get('B', '')}
C. {options.get('C', '')}
D. {options.get('D', '')}

请直接输出正确答案的字母选项（如：B），不要添加任何其他内容。"""


def validate_question_data(data: dict) -> bool:
    if not data.get("scenario") or len(data.get("scenario", "").strip()) < 60:
        return False
    if not data.get("question"):
        return False
    options = data.get("options", {})
    if set(options.keys()) != {"A", "B", "C", "D"}:
        return False
    if data.get("correct_answer") not in {"A", "B", "C", "D"}:
        return False
    if not data.get("explanation"):
        return False
    related = data.get("related_techniques", [])
    if not isinstance(related, list) or not related:
        return False
    tags = data.get("scenario_tags", [])
    if not isinstance(tags, list):
        return False
    return True


def extract_attack_ids(text: str) -> list[str]:
    return re.findall(r"T\d{4}(?:\.\d{3})?", text or "")


def get_expected_answer_id(technique: dict, sub_technique: dict) -> str:
    return (sub_technique or {}).get("id") or (technique or {}).get("id", "")


def normalize_related_techniques(related_techniques, technique: dict, sub_technique: dict):
    """规范 related_techniques，并确保当前技术在列表中"""
    normalized = []
    for item in related_techniques or []:
        if not isinstance(item, str):
            continue
        item = item.strip()
        if item and item not in normalized:
            normalized.append(item)

    preferred = sub_technique.get("id") or technique.get("id")
    if preferred and preferred not in normalized:
        normalized.insert(0, preferred)

    return normalized


def contains_attack_id(text: str) -> bool:
    return bool(re.search(r"T\d{4}(?:\.\d{3})?", text or ""))


def has_relevant_answer_mapping(
    correct_answer: str,
    options: dict,
    related_techniques: list[str],
    expected_answer_id: str,
) -> bool:
    """检查正确选项文本是否显式映射到目标 ATT&CK 技术"""
    correct_text = options.get(correct_answer, "")
    if not contains_attack_id(correct_text):
        return False

    correct_ids = extract_attack_ids(correct_text)
    if len(set(correct_ids)) != 1:
        return False

    if expected_answer_id and correct_ids[0] != expected_answer_id:
        return False

    return expected_answer_id in related_techniques


def has_clean_option_ids(options: dict, correct_answer: str, expected_answer_id: str) -> bool:
    """检查选项中的 ATT&CK ID 是否清晰、唯一且不混淆目标答案"""
    seen_ids = set()

    for key in ("A", "B", "C", "D"):
        option_text = options.get(key, "")
        attack_ids = extract_attack_ids(option_text)

        if not attack_ids:
            return False
        if len(set(attack_ids)) != 1:
            return False

        option_id = attack_ids[0]
        if option_id in seen_ids:
            return False
        seen_ids.add(option_id)

        if key == correct_answer and option_id != expected_answer_id:
            return False
        if key != correct_answer and option_id == expected_answer_id:
            return False

    return True


def related_techniques_are_consistent(related_techniques: list[str], expected_answer_id: str) -> bool:
    """检查 related_techniques 与当前目标技术的一致性"""
    if not related_techniques or not expected_answer_id:
        return False

    if expected_answer_id not in related_techniques:
        return False

    parent_id = expected_answer_id.split(".")[0]
    for tech_id in related_techniques:
        if not re.fullmatch(r"T\d{4}(?:\.\d{3})?", tech_id):
            return False
        if tech_id == expected_answer_id:
            continue
        if "." in expected_answer_id and tech_id == parent_id:
            continue

    return True


MANUAL_FAMILY_TARGET_OVERRIDES = {
    "T1027": ["T1027.002", "T1027.006", "T1027.010", "T1027.007", "T1027.013"],
    "T1036": ["T1036.002", "T1036.003", "T1036.004", "T1036.007"],
    "T1053": ["T1053.005", "T1053.003", "T1053.004"],
    "T1055": ["T1055.001", "T1055.003", "T1055.012", "T1055.013"],
    "T1059": ["T1059.001", "T1059.003", "T1059.004", "T1059.009"],
    "T1070": ["T1070.001", "T1070.003", "T1070.004", "T1070.006"],
    "T1098": ["T1098.001", "T1098.002", "T1098.004"],
    "T1137": ["T1137.001", "T1137.003", "T1137.005"],
    "T1213": ["T1213.003", "T1213.005", "T1213.006"],
    "T1218": ["T1218.004", "T1218.005", "T1218.010", "T1218.011"],
    "T1505": ["T1505.001", "T1505.003", "T1505.004"],
    "T1546": ["T1546.003", "T1546.004", "T1546.012", "T1546.013", "T1546.015"],
    "T1547": ["T1547.001", "T1547.004", "T1547.011", "T1547.013", "T1547.015"],
    "T1552": ["T1552.001", "T1552.003", "T1552.004"],
    "T1555": ["T1555.001", "T1555.003", "T1555.004"],
    "T1556": ["T1556.002", "T1556.003", "T1556.006"],
    "T1558": ["T1558.001", "T1558.003"],
    "T1562": ["T1562.001", "T1562.002", "T1562.004", "T1562.008"],
    "T1564": ["T1564.001", "T1564.003", "T1564.004", "T1564.010"],
    "T1574": ["T1574.002", "T1574.008", "T1574.010", "T1574.013"],
    "T1583": ["T1583.001", "T1583.004", "T1583.005"],
    "T1584": ["T1584.001", "T1584.004", "T1584.005"],
    "T1588": ["T1588.001", "T1588.002", "T1588.005"],
    "T1590": ["T1590.001", "T1590.002", "T1590.005"],
    "T1608": ["T1608.001", "T1608.002", "T1608.005"],
}


def get_family_quota(sub_technique_count: int) -> int:
    if sub_technique_count <= 2:
        return 1
    if sub_technique_count <= 5:
        return 2
    if sub_technique_count <= 9:
        return 3
    if sub_technique_count <= 14:
        return 4
    return 5


def spread_pick_sub_techniques(sub_techniques: list[dict], quota: int) -> list[dict]:
    """在没有人工覆盖时，按均匀分布选出代表性子技术。"""
    if quota >= len(sub_techniques):
        return list(sub_techniques)
    if quota == 1:
        return [sub_techniques[0]]

    picked_indices = []
    for index in range(quota):
        candidate = round(index * (len(sub_techniques) - 1) / (quota - 1))
        if candidate not in picked_indices:
            picked_indices.append(candidate)

    while len(picked_indices) < quota:
        for candidate in range(len(sub_techniques)):
            if candidate not in picked_indices:
                picked_indices.append(candidate)
                if len(picked_indices) == quota:
                    break

    return [sub_techniques[index] for index in sorted(picked_indices)]


def select_family_targets(technique: dict) -> list[dict]:
    """根据技术族配额选择代表性子技术。"""
    sub_techniques = list(technique.get("sub_techniques", []) or [])
    if not sub_techniques:
        return []

    quota = get_family_quota(len(sub_techniques))
    tech_id = technique.get("id", "")
    manual_ids = MANUAL_FAMILY_TARGET_OVERRIDES.get(tech_id, [])
    sub_map = {item.get("id"): item for item in sub_techniques if item.get("id")}

    if manual_ids:
        selected = [sub_map[sub_id] for sub_id in manual_ids if sub_id in sub_map][:quota]
        if len(selected) == quota:
            return selected

    return spread_pick_sub_techniques(sub_techniques, quota)


def build_canonical_attack_entries(attack_data: dict) -> list[tuple[dict, dict]]:
    """按父技术去重，保留首次出现的 tactic-technique 组合作为规范入口。"""
    canonical_entries = []
    seen_techniques = set()

    for tactic in attack_data.get("tactics", []):
        for technique in tactic.get("techniques", []):
            tech_id = technique.get("id", "")
            if tech_id and tech_id not in seen_techniques:
                seen_techniques.add(tech_id)
                canonical_entries.append((tactic, technique))

    return canonical_entries


def generate_scenario_question(
    client: OpenRouterClient,
    template: str,
    tactic: dict,
    technique: dict,
    sub_technique: dict,
    question_index: int,
    model_name: str,
):
    prompt = template.format(
        tactic_id=tactic["id"],
        tactic_name=tactic.get("name", ""),
        tactic_description=tactic.get("description", "").replace("\n", " ").strip()[:300],
        technique_id=technique["id"],
        technique_name=technique.get("name", ""),
        technique_description=technique.get("description", "").replace("\n", " ").strip()[:500],
        sub_technique_id=sub_technique.get("id", technique["id"]),
        sub_technique_name=sub_technique.get("name", technique.get("name", "")),
    )

    result = client.generate(model=model_name, prompt=prompt, temperature=0.7)
    if result.get("error"):
        print(f"  生成失败: {result['error']}")
        return None

    json_str = extract_json_payload(result["content"])
    for attempt in range(3):
        try:
            data = json.loads(json_str)
            if not validate_question_data(data):
                print("  题目结构校验失败")
                return None

            primary_sub = sub_technique.get("id", technique.get("id", ""))
            expected_answer_id = get_expected_answer_id(technique, sub_technique)
            related_techniques = normalize_related_techniques(
                data.get("related_techniques"),
                technique,
                sub_technique,
            )
            if not has_relevant_answer_mapping(
                data.get("correct_answer", ""),
                data.get("options", {}),
                related_techniques,
                expected_answer_id,
            ):
                print("  正确答案与技术映射不明确，跳过该题")
                return None
            if not has_clean_option_ids(
                data.get("options", {}),
                data.get("correct_answer", ""),
                expected_answer_id,
            ):
                print("  选项中的 ATT&CK ID 不清晰或存在冲突，跳过该题")
                return None
            if not related_techniques_are_consistent(related_techniques, expected_answer_id):
                print("  related_techniques 与目标技术不一致，跳过该题")
                return None
            reorganized_data = {
                "question_id": f"SSC-{question_index:03d}",
                "tactic_technique": f"{tactic.get('id', '')}-{technique.get('id', '')}-{primary_sub}",
                "question_type": "scenario_single_choice",
                "question_form": "scenario_single_choice",
                "capability_dimension": "scenario_technique_identification",
                "difficulty": data.get("difficulty", "medium"),
                "scenario": data.get("scenario", ""),
                "question": data.get("question", ""),
                "options": data.get("options", {}),
                "correct_answer": data.get("correct_answer", ""),
                "explanation": data.get("explanation", ""),
                "related_techniques": related_techniques,
                "scenario_tags": data.get("scenario_tags", []),
            }
            reorganized_data["test_prompt"] = build_test_prompt(reorganized_data)
            return reorganized_data
        except json.JSONDecodeError as exc:
            if attempt < 2:
                print(f"  JSON 解析失败 (尝试 {attempt + 1}/3): {exc}")
                json_str = json_str.replace("\n", " ").replace("\r", " ")
                json_str = re.sub(r",\s*}", "}", json_str)
                json_str = re.sub(r",\s*\]", "]", json_str)
                continue
            print("  JSON 解析失败，跳过该题")
            return None

    return None


def build_generation_tasks(
    attack_data: dict,
    shuffle: bool = True,
    seed: int = 42,
    task_mode: str = "family",
):
    """构造待生成任务列表。family 模式按技术族配额压缩，full 模式保留旧的一技一题。"""
    tasks = []
    question_index = 1

    if task_mode == "full":
        seen_ids = set()
        for tactic in attack_data.get("tactics", []):
            for technique in tactic.get("techniques", []):
                tech_id = technique.get("id", "")
                if tech_id and tech_id not in seen_ids:
                    seen_ids.add(tech_id)
                    tasks.append((tactic, technique, technique, question_index))
                    question_index += 1

                for sub_technique in technique.get("sub_techniques", []):
                    sub_id = sub_technique.get("id", "")
                    if sub_id and sub_id not in seen_ids:
                        seen_ids.add(sub_id)
                        tasks.append((tactic, technique, sub_technique, question_index))
                        question_index += 1
    else:
        for tactic, technique in build_canonical_attack_entries(attack_data):
            selected_targets = select_family_targets(technique)

            if selected_targets:
                for sub_technique in selected_targets:
                    tasks.append((tactic, technique, sub_technique, question_index))
                    question_index += 1
            else:
                tasks.append((tactic, technique, technique, question_index))
                question_index += 1

    if shuffle:
        rng = random.Random(seed)
        rng.shuffle(tasks)

    return tasks


def parse_args():
    parser = argparse.ArgumentParser(description="生成场景化单项选择题（SSC）")
    parser.add_argument(
        "--model",
        default="openai/gpt-4o-mini",
        help="用于生成题目的模型名称（默认: openai/gpt-4o-mini）",
    )
    parser.add_argument(
        "--model-id",
        default="gpt-4o-mini",
        help="输出文件名中的模型标识（默认: gpt-4o-mini）",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="限制生成题目数量，0 表示不限制（建议首次先跑 20-30 题）",
    )
    parser.add_argument(
        "--max-workers",
        type=int,
        default=3,
        help="并发生成数量（默认: 3）",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="打乱任务的随机种子（默认: 42）",
    )
    parser.add_argument(
        "--no-shuffle",
        action="store_true",
        help="按 ATT&CK 原顺序生成，不随机打乱",
    )
    parser.add_argument(
        "--output-file",
        default="",
        help="自定义输出文件路径；留空则自动生成",
    )
    parser.add_argument(
        "--task-mode",
        choices=["family", "full"],
        default="family",
        help="任务构建模式：family 为按技术族配额压缩，full 为旧版全量模式",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    attack_data = load_attack_data()
    prompt_template = load_prompt_template()
    if not attack_data or not prompt_template:
        return

    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        print("错误: 请设置 OPENROUTER_API_KEY 环境变量")
        return

    model_id = args.model_id
    model_name = args.model
    client = OpenRouterClient(api_key)

    tasks = build_generation_tasks(
        attack_data,
        shuffle=not args.no_shuffle,
        seed=args.seed,
        task_mode=args.task_mode,
    )
    if args.limit > 0:
        tasks = tasks[: args.limit]

    print(f"使用模型: {model_name}")
    print(f"任务模式: {args.task_mode}")
    print(f"计划生成 {len(tasks)} 道场景单选题")

    ensure_standard_directories()
    output_dir = str(DATASETS_GENERATED_DIR)
    os.makedirs(output_dir, exist_ok=True)
    output_file = args.output_file or f"{output_dir}/{model_id}_ssc_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jsonl"

    total_generated = 0
    with ThreadPoolExecutor(max_workers=args.max_workers) as executor:
        future_to_task = {
            executor.submit(
                generate_scenario_question,
                client,
                prompt_template,
                tactic,
                technique,
                sub_technique,
                index,
                model_name,
            ): (technique, sub_technique)
            for tactic, technique, sub_technique, index in tasks
        }

        with tqdm(total=len(tasks), desc="生成 SSC 题目", unit="题") as pbar:
            for future in as_completed(future_to_task):
                technique, sub_technique = future_to_task[future]
                try:
                    question = future.result()
                    if question:
                        with open(output_file, "a", encoding="utf-8") as f:
                            f.write(json.dumps(question, ensure_ascii=False) + "\n")
                        total_generated += 1
                    else:
                        print(f"FAIL 生成失败: {sub_technique.get('id', technique.get('id', ''))}")
                except Exception as exc:
                    print(f"ERROR 生成异常: {exc}")
                pbar.update(1)

    print("\n生成完成！")
    print(f"成功生成: {total_generated} 道题")
    print(f"输出文件: {output_file}")
    if total_generated == 0:
        print("提示: 本次未生成出题目，请优先检查 OpenRouter API key、模型权限和网络状态。")


if __name__ == "__main__":
    main()
