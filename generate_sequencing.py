#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试生成脚本
生成基于MITRE ATT&CK框架的排序题
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

# 加载环境变量
load_dotenv()


class OpenRouterClient:
    """
    OpenRouter客户端
    """
    
    def __init__(self, api_key):
        self.api_key = api_key
        self.base_url = "https://openrouter.ai/api/v1/chat/completions"
    
    def generate(self, model, prompt, max_tokens=2000, temperature=0.7):
        """
        生成内容
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "max_tokens": max_tokens,
            "temperature": temperature
        }
        
        # 最多重试3次
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = requests.post(self.base_url, headers=headers, json=data, timeout=60)
                
                if response.status_code == 200:
                    result = response.json()
                    return {
                        "content": result['choices'][0]['message']['content'],
                        "error": None
                    }
                elif response.status_code == 429:
                    # 速率限制，等待后重试
                    wait_time = 15 * (attempt + 1)
                    print(f"  速率限制，{wait_time}秒后重试...")
                    time.sleep(wait_time)
                else:
                    print(f"  API错误: {response.status_code} - {response.text}")
                    return {"content": "", "error": f"Request error: {response.status_code} {response.text}"}
            except Exception as e:
                print(f"  请求异常: {str(e)}")
                return {"content": "", "error": f"Request error: {str(e)}"}
        
        return {"content": "", "error": "Max retries exceeded"}


def load_attack_data():
    """
    加载ATT&CK数据
    """
    data_file = "data/attack_data.json"
    if not os.path.exists(data_file):
        print("错误: ATT&CK数据文件不存在")
        print("请先运行 attack_data_loader.py 下载数据")
        return None
    
    try:
        with open(data_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"错误: 加载ATT&CK数据失败 - {str(e)}")
        return None


def load_prompt_template():
    """
    加载提示模板
    """
    template_file = "config/prompt_templates.yaml"
    if not os.path.exists(template_file):
        print("错误: 提示模板文件不存在")
        return None
    
    try:
        with open(template_file, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
            return config.get('sequencing', '')
    except Exception as e:
        print(f"错误: 加载提示模板失败 - {str(e)}")
        return None


def generate_sequencing_questions(
    client: OpenRouterClient,
    template: str,
    tactic: dict,
    techniques: list,
    num_questions: int,
    start_index: int,
    model_name: str
) -> list:
    """
    为单个战术生成多道排序题
    """
    # 构建技术列表字符串
    techniques_list = "\n".join([f"  - {tech['name']} ({tech['id']})" for tech in techniques[:10]])  # 最多显示10个技术
    if len(techniques) > 10:
        techniques_list += f"\n  - ... 等共 {len(techniques)} 个技术"
    
    # 生成question_type
    question_types = [
        "technique_execution_order",
        "attack_step_sequence",
        "penetration_test_flow",
        "defense_priority",
        "incident_response_flow"
    ]
    question_type = question_types[start_index % len(question_types)]
    
    prompt = template.format(
        tactic_id=tactic['id'],
        tactic_name=tactic.get('name', ''),
        tactic_description=tactic.get('description', '').replace('\n', ' ').strip()[:300],
        techniques_list=techniques_list,
        num_questions=num_questions,
        question_type=question_type,
        index=f"{start_index:03d}"
    )

    result = client.generate(
        model=model_name,
        prompt=prompt,
        max_tokens=4000,
        temperature=0.7
    )

    if result.get('error') or not result.get('content'):
        print(f"  生成失败: {result.get('error', '未知错误')}")
        return []

    content = result['content'].strip()
    
    # 提取JSON部分
    import re
    json_match = re.search(r'```json\s*(.*?)\s*```', content, re.DOTALL)
    if json_match:
        json_str = json_match.group(1)
    else:
        # 尝试直接提取JSON数组
        start_idx = content.find('[')
        end_idx = content.rfind(']') + 1
        if start_idx != -1 and end_idx != 0:
            json_str = content[start_idx:end_idx]
        else:
            print("  未找到有效的JSON")
            content_preview = content[:500] if len(content) > 500 else content
            print(f"  内容前500字符: {content_preview}...")
            return []

    # 尝试解析JSON，最多重试3次
    max_retries = 3
    parsed_successfully = False
    questions = []
    
    for attempt in range(max_retries):
        try:
            data_list = json.loads(json_str)
            parsed_successfully = True
            
            # 处理每道题目
            for i, data in enumerate(data_list):
                question_id = f"SQ-{start_index + i:03d}"
                # 构建选项字符串
                options_str = ''.join([f"{key}. {value}\n" for key, value in data.get('options', {}).items()])
                
                reorganized_data = {
                    "question_id": question_id,
                    "tactic_technique": f"{tactic.get('id', '')}-multiple",
                    "question_type": "技术关联分析",
                    "difficulty": data.get("difficulty", "medium"),
                    "question": data.get("question", ""),
                    "options": data.get("options", {}),
                    "correct_answer": data.get("correct_answer", []),
                    "explanation": data.get("explanation", ""),
                    "involved_techniques": data.get("involved_techniques", []),
                    "test_prompt": f"""你是一位网络安全专家，请回答以下排序题：

题目：{data.get('question', '')}

选项：
{options_str}

请直接输出正确的顺序，使用字母选项，按顺序用逗号分隔（如：A,C,B,D），不要添加任何其他内容。"""
                }
                questions.append(reorganized_data)
            break
        except json.JSONDecodeError as e:
            if attempt < max_retries - 1:
                print(f"  JSON解析失败 (尝试 {attempt + 1}/{max_retries}): {e}")
                # 尝试修复常见的JSON格式问题
                try:
                    # 修复缺少引号的问题
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
        content_preview = content[:500] if len(content) > 500 else content
        print(f"  内容前500字符: {content_preview}...")
        return []

    return questions


def generate_cross_tactic_questions(
    client: OpenRouterClient,
    template: str,
    tactics: list,
    num_questions: int,
    start_index: int,
    model_name: str
) -> list:
    """
    生成跨战术的排序题
    """
    # 构建战术列表字符串
    tactics_list = "\n".join([f"  - {tactic['name']} ({tactic['id']}): {tactic.get('description', '').replace(chr(10), ' ')[:100]}..." for tactic in tactics])
    
    # 生成question_type
    question_types = [
        "complete_attack_chain",
        "penetration_test_overall",
        "incident_response_process",
        "threat_hunting_flow",
        "security_assessment_flow"
    ]
    question_type = question_types[start_index % len(question_types)]
    
    # 构建跨战术专用prompt
    prompt = f"""你是一位网络安全渗透测试专家，熟悉MITRE ATT&CK框架。请根据以下要求生成跨战术排序题：

【涉及的战术】
{tactics_list}

【题目要求】
- 题型: 排序题
- 问题类型: {question_type}
- 请一次性生成 {num_questions} 道排序题
- **重要**: 每道题目必须从上述多个战术中选择**有关联的战术**进行组合
- 考察这些战术之间的执行顺序、逻辑关系或依赖关系（如攻击链的先后顺序）
- 每道题目提供4-6个步骤选项（对应选择的战术或战术下的技术）
- 不同题目应选择不同的战术组合，避免重复
- 题目应清晰说明排序的依据

【输出格式】
请严格按照以下JSON格式输出，不要添加任何其他内容：
```json
[
  {{
    "question": "题目内容（要求按照正确顺序排列）",
    "options": {{
      "A": "步骤A（战术/技术名称）",
      "B": "步骤B（战术/技术名称）",
      "C": "步骤C（战术/技术名称）",
      "D": "步骤D（战术/技术名称）"
    }},
    "correct_answer": ["正确顺序数组", "如：[\"C\", \"A\", \"D\", \"B\"]"],
    "explanation": "详细解析，说明为什么是这个顺序，涉及哪些战术",
    "difficulty": "难度等级（easy/medium/hard）",
    "involved_tactics": ["涉及的战术ID列表"]
  }},
  // 更多题目...
]
```

【质量要求】
1. 必须从提供的战术列表中选择多个战术进行组合
2. 选择的战术应有明确的逻辑顺序或依赖关系（如侦察→初始访问→执行）
3. 排序项应有明确的逻辑顺序
4. 题目应清晰说明排序的依据
5. 解析应说明每一步骤之间的逻辑关系
6. 每道题目应选择不同的战术组合，避免重复
7. 难度应根据题目复杂度合理设置"""

    result = client.generate(
        model=model_name,
        prompt=prompt,
        max_tokens=4000,
        temperature=0.7
    )

    if result.get('error') or not result.get('content'):
        print(f"  生成失败: {result.get('error', '未知错误')}")
        return []

    content = result['content'].strip()
    
    # 提取JSON部分
    import re
    json_match = re.search(r'```json\s*(.*?)\s*```', content, re.DOTALL)
    if json_match:
        json_str = json_match.group(1)
    else:
        # 尝试直接提取JSON数组
        start_idx = content.find('[')
        end_idx = content.rfind(']') + 1
        if start_idx != -1 and end_idx != 0:
            json_str = content[start_idx:end_idx]
        else:
            print("  未找到有效的JSON")
            content_preview = content[:500] if len(content) > 500 else content
            print(f"  内容前500字符: {content_preview}...")
            return []

    # 尝试解析JSON，最多重试3次
    max_retries = 3
    parsed_successfully = False
    questions = []
    
    for attempt in range(max_retries):
        try:
            data_list = json.loads(json_str)
            parsed_successfully = True
            
            # 处理每道题目
            for i, data in enumerate(data_list):
                question_id = f"SQ-{start_index + i:03d}"
                # 构建选项字符串
                options_str = ''.join([f"{key}. {value}\n" for key, value in data.get('options', {}).items()])
                
                reorganized_data = {
                    "question_id": question_id,
                    "tactic_technique": f"CROSS-multiple",
                    "question_type": "跨战术关联分析",
                    "difficulty": data.get("difficulty", "medium"),
                    "question": data.get("question", ""),
                    "options": data.get("options", {}),
                    "correct_answer": data.get("correct_answer", []),
                    "explanation": data.get("explanation", ""),
                    "involved_tactics": data.get("involved_tactics", []),
                    "test_prompt": f"""你是一位网络安全专家，请回答以下排序题：

题目：{data.get('question', '')}

选项：
{options_str}

请直接输出正确的顺序，使用字母选项，按顺序用逗号分隔（如：A,C,B,D），不要添加任何其他内容。"""
                }
                questions.append(reorganized_data)
            break
        except json.JSONDecodeError as e:
            if attempt < max_retries - 1:
                print(f"  JSON解析失败 (尝试 {attempt + 1}/{max_retries}): {e}")
                # 尝试修复常见的JSON格式问题
                try:
                    # 修复缺少引号的问题
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
        content_preview = content[:500] if len(content) > 500 else content
        print(f"  内容前500字符: {content_preview}...")
        return []

    return questions

def main():
    """
    主函数
    """
    # 加载配置
    attack_data = load_attack_data()
    prompt_template = load_prompt_template()

    if not attack_data:
        return

    if not prompt_template:
        print("错误: 排序题提示模板不存在")
        return

    # 获取OpenRouter API密钥
    #openrouter_api_key = os.getenv('OPENROUTER_API_KEY')
    # 使用新的API密钥
    openrouter_api_key = "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"
    if not openrouter_api_key:
        print("错误: 请设置 OPENROUTER_API_KEY 环境变量")
        print("设置命令: set OPENROUTER_API_KEY=your_api_key")
        return

    # 使用GPT-4o-mini
    test_model_id = "gpt-4o-mini"
    test_model_name = "openai/gpt-4o-mini"

    print(f"使用模型: {test_model_name}")
    print(f"开始生成排序题...\n")

    client = OpenRouterClient(openrouter_api_key)

    # 构建任务
    tasks = []
    question_index = 1
    
    # 配置：每个战术调用API的次数和每次生成的题目数
    SINGLE_TACTIC_BATCHES = 5  # 每个战术调用5次API
    SINGLE_TACTIC_QUESTIONS_PER_BATCH = 5  # 每次生成5道题
    
    CROSS_TACTIC_BATCHES = 3  # 每组跨战术调用3次API
    CROSS_TACTIC_QUESTIONS_PER_BATCH = 8  # 每次生成8道题

    # 为每个战术生成排序题 - 多次调用API
    for tactic in attack_data.get('tactics', []):
        techniques = tactic.get('techniques', [])
        if techniques:
            # 为每个战术创建多个批次任务
            for batch in range(SINGLE_TACTIC_BATCHES):
                tasks.append({
                    'type': 'single_tactic',
                    'tactic': tactic,
                    'techniques': techniques,
                    'num_questions': SINGLE_TACTIC_QUESTIONS_PER_BATCH,
                    'batch_index': batch,
                    'start_index': question_index
                })
                question_index += SINGLE_TACTIC_QUESTIONS_PER_BATCH

    # 生成跨战术的排序题 - 多次调用API
    all_tactics = attack_data.get('tactics', [])
    if len(all_tactics) > 1:
        # 每5个战术一组
        for i in range(0, len(all_tactics), 5):
            tactic_group = all_tactics[i:i+5]
            if len(tactic_group) >= 2:
                # 为每组跨战术创建多个批次任务
                for batch in range(CROSS_TACTIC_BATCHES):
                    tasks.append({
                        'type': 'cross_tactic',
                        'tactics': tactic_group,
                        'num_questions': CROSS_TACTIC_QUESTIONS_PER_BATCH,
                        'batch_index': batch,
                        'start_index': question_index
                    })
                    question_index += CROSS_TACTIC_QUESTIONS_PER_BATCH

    print(f"共生成 {len(tasks)} 个任务，预计生成 {question_index - 1} 道排序题")

    # 准备输出文件
    output_dir = "output"
    os.makedirs(output_dir, exist_ok=True)
    output_file = f"{output_dir}/{test_model_id}_sq_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    
    # 并发生成题目
    total_generated = 0
    max_workers = 3  # 并发数

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # 提交任务
        future_to_task = {}
        for task in tasks:
            if task['type'] == 'single_tactic':
                future = executor.submit(
                    generate_sequencing_questions,
                    client,
                    prompt_template,
                    task['tactic'],
                    task['techniques'],
                    task['num_questions'],
                    task['start_index'],
                    test_model_name
                )
            else:  # cross_tactic
                future = executor.submit(
                    generate_cross_tactic_questions,
                    client,
                    prompt_template,
                    task['tactics'],
                    task['num_questions'],
                    task['start_index'],
                    test_model_name
                )
            future_to_task[future] = task

        # 处理结果
        with tqdm(total=len(tasks), desc="生成排序题", unit="任务") as pbar:
            for future in as_completed(future_to_task):
                task = future_to_task[future]
                try:
                    questions = future.result()
                    if questions:
                        # 实时写入文件
                        with open(output_file, 'a', encoding='utf-8') as f:
                            for q in questions:
                                f.write(json.dumps(q, ensure_ascii=False) + '\n')
                        total_generated += len(questions)
                        if task['type'] == 'single_tactic':
                            print(f"✓ {task['tactic']['name']} ({task['tactic']['id']}) 批次{task['batch_index']+1}: 成功生成 {len(questions)} 道题")
                        else:
                            tactic_names = [t['name'] for t in task['tactics'][:3]]
                            if len(task['tactics']) > 3:
                                tactic_names.append('...')
                            print(f"✓ 跨战术 [{', '.join(tactic_names)}] 批次{task['batch_index']+1}: 成功生成 {len(questions)} 道题")
                    else:
                        if task['type'] == 'single_tactic':
                            print(f"✗ {task['tactic']['name']} ({task['tactic']['id']}) 批次{task['batch_index']+1}: 生成失败")
                        else:
                            print(f"✗ 跨战术任务 批次{task['batch_index']+1}: 生成失败")
                except Exception as e:
                    print(f"✗ 错误 - {str(e)}")
                pbar.update(1)

    print(f"\n生成完成！")
    print(f"成功生成: {total_generated} 道排序题")
    print(f"输出文件: {output_file}")


if __name__ == "__main__":
    main()
