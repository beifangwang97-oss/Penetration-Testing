"""
测试生成脚本
使用免费的LLama模型快速测试生成单项选择题
"""

import json
import yaml
import os
import time
import requests
from datetime import datetime
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm
from project_paths import DATASETS_GENERATED_DIR, attack_data_path, ensure_standard_directories

# 加载环境变量
load_dotenv()


def load_config(config_path: str) -> dict:
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def load_attack_data():
    cache_path = str(attack_data_path())
    if os.path.exists(cache_path):
        from attack_data_loader import load_parsed_data
        return load_parsed_data(cache_path)
    else:
        print("错误: 请先运行 attack_data_loader.py 下载数据")
        return None


def load_prompt_template():
    with open('config/prompt_templates.yaml', 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    return config.get('single_choice', '')


class OpenRouterClient:
    """使用同步requests的OpenRouter客户端"""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.api_url = "https://openrouter.ai/api/v1/chat/completions"

    def generate(self, model: str, prompt: str, temperature: float = 0.7, max_retries: int = 3) -> dict:
        """调用OpenRouter API生成内容，带重试机制"""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/Athena-Software-Group/athenabench",
            "X-Title": "ATT&CK Dataset Generator",
        }

        messages = [
            {
                "role": "system",
                "content": "你是一位网络安全渗透测试专家，熟悉MITRE ATT&CK框架。请严格按照要求生成题目。"
            },
            {
                "role": "user",
                "content": prompt
            }
        ]

        data = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
        }

        for attempt in range(max_retries):
            try:
                response = requests.post(
                    self.api_url,
                    headers=headers,
                    json=data,
                    timeout=60
                )

                if response.status_code == 429:
                    # 速率限制，等待更长时间后重试
                    wait_time = (attempt + 1) * 15
                    print(f"    速率限制，等待 {wait_time} 秒后重试...")
                    time.sleep(wait_time)
                    continue

                response.raise_for_status()
                result = response.json()

                if "choices" in result and len(result["choices"]) > 0:
                    content = result["choices"][0].get("message", {}).get("content", "")
                    return {"content": content, "error": None}
                else:
                    return {"content": "", "error": "No choices in response"}
            except requests.exceptions.Timeout:
                if attempt < max_retries - 1:
                    time.sleep(5)
                    continue
                return {"content": "", "error": "Request timeout"}
            except requests.exceptions.RequestException as e:
                if attempt < max_retries - 1:
                    time.sleep(5)
                    continue
                return {"content": "", "error": f"Request error: {str(e)}"}
            except Exception as e:
                return {"content": "", "error": f"Error: {str(e)}"}

        return {"content": "", "error": "Max retries exceeded"}


# 题目类型定义
QUESTION_TYPES = [
    "technique_purpose",
    "tactic_classification",
    "tool_mapping",
    "defense_detection",
    "attack_scenario"
]

def generate_single_question(
    client: OpenRouterClient,
    template: str,
    tactic: dict,
    technique: dict,
    sub_technique: dict,
    question_index: int,
    question_type: str,
    model_name: str
) -> dict:
    """
    生成一道单项选择题（同步版本）
    """
    prompt = template.format(
        tactic_id=tactic['id'],
        tactic_name=tactic.get('name', ''),
        tactic_description=tactic.get('description', '').replace('\n', ' ').strip()[:300],
        technique_id=technique['id'],
        technique_name=technique.get('name', ''),
        technique_description=technique.get('description', '').replace('\n', ' ').strip()[:500],
        sub_technique_id=sub_technique.get('id', technique['id']),
        sub_technique_name=sub_technique.get('name', sub_technique.get('name', '')),
        question_type=question_type,
        index=f"{question_index:03d}"
    )

    result = client.generate(
        model=model_name,
        prompt=prompt,
        temperature=0.7
    )

    if result.get("error"):
        print(f"  生成失败: {result['error']}")
        return None

    content = result["content"]
    # 尝试提取JSON部分
    import re

    # 尝试提取 ```json ... ``` 块
    json_match = re.search(r'```json\s*(.*?)\s*```', content, re.DOTALL)
    if json_match:
        json_str = json_match.group(1)
    else:
        # 如果没有json块，尝试找 {...} 块
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        else:
            json_str = content

    # 清理JSON字符串
    json_str = json_str.strip()

    # 尝试解析JSON，最多重试3次
    max_retries = 3
    parsed_successfully = False
    for attempt in range(max_retries):
        try:
            data = json.loads(json_str)
            # 重新组织字段顺序，确保question_id在首位
            reorganized_data = {
                "question_id": f"SC-{question_index:03d}",
                "tactic_technique": f"{tactic.get('id', '')}-{technique.get('id', '')}-{sub_technique.get('id', technique.get('id', ''))}",
                "question_type": question_type,
                "question_form": "single_choice",
                "capability_dimension": question_type,
                "difficulty": data.get("difficulty", "medium"),
                "question": data.get("question", ""),
                "options": data.get("options", {}),
                "correct_answer": data.get("correct_answer", ""),
                "explanation": data.get("explanation", ""),
                "test_prompt": f"""你是一位网络安全专家，请回答以下单项选择题：

题目：{data.get('question', '')}

选项：
A. {data.get('options', {}).get('A', '')}
B. {data.get('options', {}).get('B', '')}
C. {data.get('options', {}).get('C', '')}
D. {data.get('options', {}).get('D', '')}

请直接输出正确答案的字母选项（如：B），不要添加任何其他内容。"""
            }
            parsed_successfully = True
            return reorganized_data
        except json.JSONDecodeError as e:
            if attempt < max_retries - 1:
                print(f"  JSON解析失败 (尝试 {attempt + 1}/{max_retries}): {e}")
                # 尝试修复常见的JSON格式问题
                try:
                    # 修复缺少引号的问题，如 "C": .dll文件
                    fixed_json_str = re.sub(r'(["\w+"]):\s*([a-zA-Z0-9_\-\.]+)(?=\s*,|\s*})', r'\1: "\2"', json_str)
                    # 修复未转义的反斜杠
                    fixed_json_str = fixed_json_str.replace('\\', '\\\\')
                    # 修复可能的其他问题
                    fixed_json_str = fixed_json_str.replace('\n', ' ')
                    json_str = fixed_json_str
                    print(f"  尝试修复JSON格式...")
                except Exception as fix_error:
                    print(f"  修复失败: {fix_error}")
                    break
    
    if not parsed_successfully:
        print(f"  JSON解析失败")
        # 打印更多内容帮助调试
        content_preview = result["content"][:500] if result["content"] else "Empty"
        print(f"  内容前500字符: {content_preview}...")
        return None


def main():
    """
    主函数
    """
    # 加载配置
    attack_data = load_attack_data()
    prompt_template = load_prompt_template()

    if not attack_data:
        return

    # 获取OpenRouter API密钥
    openrouter_api_key = os.getenv('OPENROUTER_API_KEY')
    if not openrouter_api_key:
        print("错误: 请设置 OPENROUTER_API_KEY 环境变量")
        print("设置命令: set OPENROUTER_API_KEY=your_api_key")
        return

    # 使用GPT-4o-mini
    test_model_id = "gpt-4o-mini"
    test_model_name = "openai/gpt-4o-mini"

    print(f"使用模型: {test_model_name}")
    print(f"开始生成所有战术技术的题目...\n")

    client = OpenRouterClient(openrouter_api_key)

    # 先预估题目数量
    seen_techniques = set()
    total_techniques = 0

    # 遍历所有战术技术，计算去重后的数量
    for tactic in attack_data.get('tactics', []):  # 所有战术
        for technique in tactic.get('techniques', []):  # 所有技术
            tech_id = technique.get('id', '')
            
            # 处理技术本身
            if tech_id and tech_id not in seen_techniques:
                seen_techniques.add(tech_id)
                total_techniques += 1
            
            # 处理子技术
            sub_techniques = technique.get('sub_techniques', [])
            for sub_technique in sub_techniques:
                sub_tech_id = sub_technique.get('id', '')
                if sub_tech_id and sub_tech_id not in seen_techniques:
                    seen_techniques.add(sub_tech_id)
                    total_techniques += 1

    # 每个技术/子技术生成5道不同类型的题目
    total_questions = total_techniques * len(QUESTION_TYPES)
    print(f"预估生成 {total_questions} 道题目（每个技术/子技术5道不同类型）")

    # 重新构建任务列表
    seen_techniques = set()  # 重置去重集合
    tasks = []
    question_index = 1

    # 遍历所有战术技术，构建任务
    for tactic in attack_data.get('tactics', []):  # 所有战术
        for technique in tactic.get('techniques', []):  # 所有技术
            tech_id = technique.get('id', '')
            
            # 处理技术本身
            if tech_id and tech_id not in seen_techniques:
                seen_techniques.add(tech_id)
                # 为每个技术生成5道不同类型的题目
                for question_type in QUESTION_TYPES:
                    tasks.append({
                        'tactic': tactic,
                        'technique': technique,
                        'sub_technique': technique,
                        'index': question_index,
                        'question_type': question_type
                    })
                    question_index += 1
            
            # 处理子技术
            sub_techniques = technique.get('sub_techniques', [])
            for sub_technique in sub_techniques:
                sub_tech_id = sub_technique.get('id', '')
                if sub_tech_id and sub_tech_id not in seen_techniques:
                    seen_techniques.add(sub_tech_id)
                    # 为每个子技术生成5道不同类型的题目
                    for question_type in QUESTION_TYPES:
                        tasks.append({
                            'tactic': tactic,
                            'technique': technique,
                            'sub_technique': sub_technique,
                            'index': question_index,
                            'question_type': question_type
                        })
                        question_index += 1

    print(f"确认生成 {len(tasks)} 道题目")

    # 准备输出文件
    ensure_standard_directories()
    output_dir = str(DATASETS_GENERATED_DIR)
    os.makedirs(output_dir, exist_ok=True)
    output_file = f"{output_dir}/{test_model_id}_sc_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    
    # 并发生成题目
    total_generated = 0
    max_workers = 3  # 并发数

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # 提交任务
        future_to_task = {}
        for task in tasks:
            future = executor.submit(
                generate_single_question,
                client,
                prompt_template,
                task['tactic'],
                task['technique'],
                task['sub_technique'],
                task['index'],
                task['question_type'],
                test_model_name
            )
            future_to_task[future] = task

        # 处理结果
        with tqdm(total=len(tasks), desc="生成单选题", unit="题") as pbar:
            for future in as_completed(future_to_task):
                task = future_to_task[future]
                try:
                    question = future.result()
                    if question:
                        # 实时写入文件
                        with open(output_file, 'a', encoding='utf-8') as f:
                            f.write(json.dumps(question, ensure_ascii=False) + '\n')
                        total_generated += 1
                        if total_generated % 10 == 0:
                            print(f"✓ 已生成 {total_generated} 道题")
                    else:
                        print(f"✗ 生成失败: {task['technique']['id']} - {task['technique']['name']}")
                except Exception as e:
                    print(f"✗ 错误 - {str(e)}")
                pbar.update(1)

    print(f"\n生成完成！")
    print(f"成功生成: {total_generated} 道题")
    print(f"输出文件: {output_file}")


if __name__ == "__main__":
    main()
