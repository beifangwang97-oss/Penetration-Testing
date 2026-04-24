"""
场景化单项选择题生成脚本

功能：
1. 基于 ATT&CK 技术/子技术生成 SSC 题目
2. 为每道题显式生成 scenario 字段
3. 输出与现有评测链路兼容的 JSONL 文件
"""

import json
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

import requests
import yaml
from dotenv import load_dotenv
from tqdm import tqdm

load_dotenv()


def load_attack_data():
    cache_path = "data/attack_data.json"
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
            related_techniques = data.get("related_techniques") or [primary_sub]
            reorganized_data = {
                "question_id": f"SSC-{question_index:03d}",
                "tactic_technique": f"{tactic.get('id', '')}-{technique.get('id', '')}-{primary_sub}",
                "question_type": "scenario_single_choice",
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


def main():
    attack_data = load_attack_data()
    prompt_template = load_prompt_template()
    if not attack_data or not prompt_template:
        return

    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        print("错误: 请设置 OPENROUTER_API_KEY 环境变量")
        return

    model_id = "gpt-4o-mini"
    model_name = "openai/gpt-4o-mini"
    client = OpenRouterClient(api_key)

    tasks = []
    question_index = 1
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

    print(f"使用模型: {model_name}")
    print(f"预计生成 {len(tasks)} 道场景单选题")

    output_dir = "output"
    os.makedirs(output_dir, exist_ok=True)
    output_file = f"{output_dir}/{model_id}_ssc_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jsonl"

    total_generated = 0
    with ThreadPoolExecutor(max_workers=3) as executor:
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
                        print(f"✗ 生成失败: {sub_technique.get('id', technique.get('id', ''))}")
                except Exception as exc:
                    print(f"✗ 生成异常: {exc}")
                pbar.update(1)

    print("\n生成完成！")
    print(f"成功生成: {total_generated} 道题")
    print(f"输出文件: {output_file}")


if __name__ == "__main__":
    main()
