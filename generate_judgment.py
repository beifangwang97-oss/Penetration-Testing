#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试生成脚本
使用免费的LLama模型快速测试生成判断题
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
            return config.get('true_false', '')
    except Exception as e:
        print(f"错误: 加载提示模板失败 - {str(e)}")
        return None


def generate_judgment_question(
    client: OpenRouterClient,
    template: str,
    tactic: dict,
    technique: dict,
    sub_technique: dict,
    question_index: int,
    model_name: str
) -> dict:
    """
    生成一道判断题（同步版本）
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
        focus_area="技术的核心特点和应用场景",
        index=f"{question_index:03d}"
    )

    result = client.generate(
        model=model_name,
        prompt=prompt,
        max_tokens=1000,
        temperature=0.7
    )

    if result.get('error') or not result.get('content'):
        print(f"  生成失败: {result.get('error', '未知错误')}")
        return None

    content = result['content'].strip()
    
    # 提取JSON部分
    if '```json' in content:
        json_str = content.split('```json')[1].split('```')[0].strip()
    else:
        # 尝试直接提取JSON
        start_idx = content.find('{')
        end_idx = content.rfind('}') + 1
        if start_idx != -1 and end_idx != 0:
            json_str = content[start_idx:end_idx]
        else:
            print("  未找到有效的JSON")
            content_preview = content[:500] if len(content) > 500 else content
            print(f"  内容前500字符: {content_preview}...")
            return None

    # 尝试解析JSON，最多重试3次
    max_retries = 3
    parsed_successfully = False
    for attempt in range(max_retries):
        try:
            data = json.loads(json_str)
            # 重新组织字段顺序，确保question_id在首位
            reorganized_data = {
                "question_id": f"JU-{question_index:03d}",
                "tactic_technique": f"{tactic.get('id', '')}-{technique.get('id', '')}-{sub_technique.get('id', technique.get('id', ''))}",
                "difficulty": data.get("difficulty", "medium"),  # 从模型输出获取难度
                "question": data.get("question", ""),
                "correct_answer": data.get("correct_answer", ""),
                "explanation": data.get("explanation", ""),
                "test_prompt": f"""你是一位网络安全专家，请回答以下判断题：

题目：{data.get('question', '')}

请直接输出正确答案（正确/错误），不要添加任何其他内容。"""
            }
            parsed_successfully = True
            return reorganized_data
        except json.JSONDecodeError as e:
            if attempt < max_retries - 1:
                print(f"  JSON解析失败 (尝试 {attempt + 1}/{max_retries}): {e}")
                # 尝试修复常见的JSON格式问题
                try:
                    import re
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
        content_preview = json_str[:500] if len(json_str) > 500 else json_str
        print(f"  JSON内容前500字符: {content_preview}...")
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

    if not prompt_template:
        print("错误: 判断题提示模板不存在")
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
    print(f"开始生成所有战术技术的判断题...\n")

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

    print(f"预估生成 {total_techniques} 道判断题")

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
                tasks.append({
                    'tactic': tactic,
                    'technique': technique,
                    'sub_technique': technique,
                    'index': question_index
                })
                question_index += 1
            
            # 处理子技术
            sub_techniques = technique.get('sub_techniques', [])
            for sub_technique in sub_techniques:
                sub_tech_id = sub_technique.get('id', '')
                if sub_tech_id and sub_tech_id not in seen_techniques:
                    seen_techniques.add(sub_tech_id)
                    tasks.append({
                        'tactic': tactic,
                        'technique': technique,
                        'sub_technique': sub_technique,
                        'index': question_index
                    })
                    question_index += 1

    print(f"确认生成 {len(tasks)} 道判断题")

    # 准备输出文件
    output_dir = "output"
    os.makedirs(output_dir, exist_ok=True)
    output_file = f"{output_dir}/{test_model_id}_ju_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    
    # 并发生成题目
    total_generated = 0
    max_workers = 3  # 并发数

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # 提交任务
        future_to_task = {}
        for task in tasks:
            future = executor.submit(
                generate_judgment_question,
                client,
                prompt_template,
                task['tactic'],
                task['technique'],
                task['sub_technique'],
                task['index'],
                test_model_name
            )
            future_to_task[future] = task

        # 处理结果
        with tqdm(total=len(tasks), desc="生成判断题", unit="题") as pbar:
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
