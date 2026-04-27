"""
多选题生成脚本
使用GPT-4o-mini生成多项选择题
"""

import json
import yaml
import os
import time
import requests
import re
from datetime import datetime
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm
from project_paths import DATASETS_GENERATED_DIR, attack_data_path, ensure_standard_directories

# 加载环境变量
load_dotenv()


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
    return config.get('multiple_choice', '')


def fix_json_string(json_str):
    """
    自动修复常见的JSON格式错误
    """
    # 修复1: 移除BOM字符
    json_str = json_str.replace('\ufeff', '')
    
    # 修复2: 修复未转义的反斜杠（但保留已转义的）
    json_str = re.sub(r'(?<!\\)\\(?!["\\/bfnrt])', r'\\\\', json_str)
    
    # 修复3: 修复缺少引号的键
    json_str = re.sub(r'(\w+)\s*:', r'"\1":', json_str)
    
    # 修复4: 修复单引号
    json_str = json_str.replace("'", '"')
    
    # 修复5: 修复尾随逗号
    json_str = re.sub(r',\s*}', '}', json_str)
    json_str = re.sub(r',\s*\]', ']', json_str)
    
    # 修复6: 修复缺少引号的字符串值
    json_str = re.sub(r':\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*([,}])', r': "\1"\2', json_str)
    
    # 修复7: 移除注释
    json_str = re.sub(r'//.*?\n', '\n', json_str)
    json_str = re.sub(r'/\*.*?\*/', '', json_str, flags=re.DOTALL)
    
    # 修复8: 修复换行符问题
    json_str = json_str.replace('\n', ' ')
    json_str = json_str.replace('\r', ' ')
    
    # 修复9: 移除多余空格
    json_str = re.sub(r'\s+', ' ', json_str)
    
    return json_str.strip()


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


def generate_multiple_questions(
    client: OpenRouterClient,
    template: str,
    tactic: dict,
    num_questions: int,
    start_index: int,
    model_name: str
) -> list:
    """
    生成多道多项选择题
    """
    # 收集该战术下的所有技术信息
    techniques_info = []
    for technique in tactic.get('techniques', []):
        tech_info = f"{technique.get('name', '')} ({technique.get('id', '')})"
        techniques_info.append(tech_info)
    
    techniques_list = "\n".join(techniques_info)
    
    prompt = template.format(
        tactic_id=tactic['id'],
        tactic_name=tactic.get('name', ''),
        tactic_description=tactic.get('description', '').replace('\n', ' ').strip()[:300],
        techniques_list=techniques_list,
        question_type='技术关联分析',
        num_questions=num_questions
    )

    result = client.generate(
        model=model_name,
        prompt=prompt,
        temperature=0.7
    )

    if result.get("error"):
        print(f"  生成失败: {result['error']}")
        return []

    try:
        content = result["content"]
        
        # 尝试提取 ```json ... ``` 块
        json_match = re.search(r'```json\s*(.*?)\s*```', content, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        else:
            # 尝试找 [...] 块
            json_match = re.search(r'\[.*\]', content, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
            else:
                json_str = content

        # 清理JSON字符串
        json_str = json_str.strip()

        # 尝试直接解析
        try:
            questions_data = json.loads(json_str)
        except json.JSONDecodeError:
            # 如果直接解析失败，尝试修复常见的JSON格式错误
            print(f"  JSON解析失败，尝试自动修复...")
            
            # 应用自动修复
            json_str = fix_json_string(json_str)
            
            # 再次尝试解析
            try:
                questions_data = json.loads(json_str)
                print(f"  自动修复成功！")
            except json.JSONDecodeError as e:
                print(f"  自动修复失败: {e}")
                # 打印更多内容帮助调试
                content_preview = result["content"][:500] if result["content"] else "Empty"
                print(f"  内容前500字符: {content_preview}...")
                return []

        generated_questions = []
        
        # 处理返回的多个题目
        for i, data in enumerate(questions_data):
            question_index = start_index + i
            # 重新组织字段顺序，确保question_id在首位
            options = data.get('options', {})
            reorganized_data = {
                "question_id": f"MC-{question_index:03d}",
                "tactic_technique": f"{tactic.get('id', '')}-multiple",
                "question_form": "multiple_choice",
                "capability_dimension": "technique_association_analysis",
                "question_type": "技术关联分析",
                "difficulty": data.get("difficulty", "medium"),
                "question": data.get("question", ""),
                "options": options,
                "correct_answer": data.get("correct_answer", []),
                "explanation": data.get("explanation", ""),
                "involved_techniques": data.get("involved_techniques", []),
                "test_prompt": f"""你是一位网络安全专家，请回答以下多项选择题：

题目：{data.get('question', '')}

选项：
A. {options.get('A', '')}
B. {options.get('B', '')}
C. {options.get('C', '')}
D. {options.get('D', '')}
E. {options.get('E', '')}

请直接输出所有正确答案的字母选项，按字母顺序排列，用逗号分隔（如：A,C,D），不要添加任何其他内容。"""
            }
            generated_questions.append(reorganized_data)
        
        return generated_questions
    except Exception as e:
        print(f"  生成失败: {e}")
        # 打印更多内容帮助调试
        content_preview = result["content"][:500] if result["content"] else "Empty"
        print(f"  内容前500字符: {content_preview}...")
        return []


def generate_cross_tactic_questions(
    client: OpenRouterClient,
    tactics: list,
    num_questions: int,
    start_index: int,
    model_name: str
) -> list:
    """
    生成跨战术的多选题
    """
    # 构建战术列表字符串
    tactics_list = "\n".join([f"  - {tactic['name']} ({tactic['id']}): {tactic.get('description', '').replace(chr(10), ' ')[:100]}..." for tactic in tactics])
    
    # 构建跨战术专用prompt
    prompt = f"""你是一位网络安全渗透测试专家，熟悉MITRE ATT&CK框架。请根据以下要求生成跨战术多选题：

【涉及的战术】
{tactics_list}

【题目要求】
- 题型: 多选题
- 请一次性生成 {num_questions} 道多选题
- **重要**: 每道题目必须从上述多个战术中选择**有关联的战术**进行组合
- 考察这些战术之间的关联关系、执行顺序或依赖关系
- 每道题目提供5个选项，正确答案为2-4个
- 不同题目应选择不同的战术组合，避免重复
- 题目应清晰明确，选项要有合理的干扰项

【输出格式】
请严格按照以下JSON格式输出，不要添加任何其他内容：
```json
[
  {{
    "question": "题目内容",
    "options": {{
      "A": "选项A",
      "B": "选项B",
      "C": "选项C",
      "D": "选项D",
      "E": "选项E"
    }},
    "correct_answer": ["正确答案数组", "如：[\"A\", \"C\", \"D\"]"],
    "explanation": "详细解析，说明正确答案的原因",
    "difficulty": "难度等级（easy/medium/hard）",
    "involved_tactics": ["涉及的战术ID列表"]
  }},
  // 更多题目...
]
```

【质量要求】
1. 必须从提供的战术列表中选择多个战术进行组合
2. 选择的战术应有明确的关联关系
3. 题目应清晰明确，无歧义
4. 选项应包含合理的干扰项
5. 解析应详细说明正确答案的原因
6. 每道题目应选择不同的战术组合，避免重复
7. 难度应根据题目复杂度合理设置"""

    result = client.generate(
        model=model_name,
        prompt=prompt,
        temperature=0.7
    )

    if result.get("error"):
        print(f"  生成失败: {result['error']}")
        return []

    try:
        content = result["content"]
        
        # 尝试提取 ```json ... ``` 块
        json_match = re.search(r'```json\s*(.*?)\s*```', content, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        else:
            # 尝试找 [...] 块
            json_match = re.search(r'\[.*\]', content, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
            else:
                json_str = content

        # 清理JSON字符串
        json_str = json_str.strip()

        # 尝试直接解析
        try:
            questions_data = json.loads(json_str)
        except json.JSONDecodeError:
            # 如果直接解析失败，尝试修复常见的JSON格式错误
            print(f"  JSON解析失败，尝试自动修复...")
            
            # 应用自动修复
            json_str = fix_json_string(json_str)
            
            # 再次尝试解析
            try:
                questions_data = json.loads(json_str)
                print(f"  自动修复成功！")
            except json.JSONDecodeError as e:
                print(f"  自动修复失败: {e}")
                # 打印更多内容帮助调试
                content_preview = result["content"][:500] if result["content"] else "Empty"
                print(f"  内容前500字符: {content_preview}...")
                return []

        generated_questions = []
        
        # 处理返回的多个题目
        for i, data in enumerate(questions_data):
            question_index = start_index + i
            # 构建选项字符串
            options = data.get('options', {})
            
            reorganized_data = {
                "question_id": f"MC-{question_index:03d}",
                "tactic_technique": f"CROSS-multiple",
                "question_type": "跨战术关联分析",
                "difficulty": data.get("difficulty", "medium"),
                "question": data.get("question", ""),
                "options": options,
                "correct_answer": data.get("correct_answer", []),
                "explanation": data.get("explanation", ""),
                "involved_tactics": data.get("involved_tactics", []),
                "test_prompt": f"""你是一位网络安全专家，请回答以下多项选择题：

题目：{data.get('question', '')}

选项：
A. {options.get('A', '')}
B. {options.get('B', '')}
C. {options.get('C', '')}
D. {options.get('D', '')}
E. {options.get('E', '')}

请直接输出所有正确答案的字母选项，按字母顺序排列，用逗号分隔（如：A,C,D），不要添加任何其他内容。"""
            }
            generated_questions.append(reorganized_data)
        
        return generated_questions
    except Exception as e:
        print(f"  生成失败: {e}")
        # 打印更多内容帮助调试
        content_preview = result["content"][:500] if result["content"] else "Empty"
        print(f"  内容前500字符: {content_preview}...")
        return []


def main():
    """
    主函数
    """
    # 加载配置
    attack_data = load_attack_data()
    prompt_template = load_prompt_template()

    if not attack_data:
        return

    # 使用新的API密钥
    openrouter_api_key = "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"
    if not openrouter_api_key:
        print("错误: API密钥未设置")
        return

    # 使用GPT-4o-mini
    test_model_id = "gpt-4o-mini"
    test_model_name = "openai/gpt-4o-mini"

    print(f"使用模型: {test_model_name}")
    print(f"开始生成所有战术技术的多选题...\n")

    client = OpenRouterClient(openrouter_api_key)

    # 配置：每个战术调用API的次数和每次生成的题目数
    SINGLE_TACTIC_BATCHES = 5  # 每个战术调用5次API
    SINGLE_TACTIC_QUESTIONS_PER_BATCH = 5  # 每次生成5道题
    
    CROSS_TACTIC_BATCHES = 3  # 每组跨战术调用3次API
    CROSS_TACTIC_QUESTIONS_PER_BATCH = 8  # 每次生成8道题

    # 准备生成任务
    tasks = []
    question_index = 1

    # 为每个战术生成多选题 - 多次调用API
    for tactic in attack_data.get('tactics', []):  # 所有战术
        techniques = tactic.get('techniques', [])
        num_techniques = len(techniques)
        
        if num_techniques == 0:
            continue
        
        # 为每个战术创建多个批次任务
        for batch in range(SINGLE_TACTIC_BATCHES):
            tasks.append({
                'type': 'single_tactic',
                'tactic': tactic,
                'num_questions': SINGLE_TACTIC_QUESTIONS_PER_BATCH,
                'batch_index': batch,
                'start_index': question_index
            })
            question_index += SINGLE_TACTIC_QUESTIONS_PER_BATCH

    # 生成跨战术的多选题 - 多次调用API
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

    print(f"共生成 {len(tasks)} 个任务，预计生成 {question_index - 1} 道多选题")

    # 准备输出文件
    ensure_standard_directories()
    output_dir = str(DATASETS_GENERATED_DIR)
    os.makedirs(output_dir, exist_ok=True)
    output_file = f"{output_dir}/{test_model_id}_mc_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    
    # 并发生成题目
    total_generated = 0
    max_workers = 3  # 并发数

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # 提交任务
        future_to_task = {}
        for task in tasks:
            if task['type'] == 'single_tactic':
                future = executor.submit(
                    generate_multiple_questions,
                    client,
                    prompt_template,
                    task['tactic'],
                    task['num_questions'],
                    task['start_index'],
                    test_model_name
                )
            else:  # cross_tactic
                future = executor.submit(
                    generate_cross_tactic_questions,
                    client,
                    task['tactics'],
                    task['num_questions'],
                    task['start_index'],
                    test_model_name
                )
            future_to_task[future] = task

        # 处理结果
        with tqdm(total=len(tasks), desc="生成多选题", unit="任务") as pbar:
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
    print(f"成功生成: {total_generated} 道题")
    print(f"输出文件: {output_file}")


if __name__ == "__main__":
    main()
