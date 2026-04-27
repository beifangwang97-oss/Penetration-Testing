"""
通用题目审查脚本（并发版本）

功能：
1. 支持四种题型的审查：单选(SC)、多选(MC)、判断(JU)、排序(SQ)
2. 根据题型自动选择对应的审查策略
3. 使用高质量模型进行审查
4. 实时写入审查结果
5. 支持并发处理
6. 生成修改记录文件，方便人工审查
"""

import json
import os
import time
import re
import sys
import requests
import threading
from datetime import datetime
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm
from project_paths import DATASETS_REVIEWED_DIR, ensure_standard_directories

# 加载环境变量
load_dotenv()

# 避免 Windows 终端因 Unicode 符号输出失败
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

# 线程锁，用于文件写入同步
file_lock = threading.Lock()


def load_attack_id_name_map() -> dict:
    """加载本地 ATT&CK ID 到名称的映射，用于约束审校结果不要偏离数据源。"""
    attack_path = os.path.join("data", "attack_data.json")
    if not os.path.exists(attack_path):
        return {}

    with open(attack_path, "r", encoding="utf-8") as f:
        attack_data = json.load(f)

    lookup = {}
    for tactic in attack_data.get("tactics", []):
        for technique in tactic.get("techniques", []):
            tech_id = technique.get("id")
            tech_name = technique.get("name", "").strip()
            if tech_id and tech_name:
                lookup[tech_id] = tech_name
            for sub_technique in technique.get("sub_techniques", []):
                sub_id = sub_technique.get("id")
                sub_name = sub_technique.get("name", "").strip()
                if sub_id and sub_name:
                    lookup[sub_id] = sub_name

    return lookup


ATTACK_ID_NAME_MAP = load_attack_id_name_map()


class OpenRouterClient:
    """OpenRouter API客户端（线程安全）"""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.api_url = "https://openrouter.ai/api/v1/chat/completions"
        # 用于速率限制的锁
        self.rate_limit_lock = threading.Lock()
        self.last_request_time = 0
        self.min_interval = 1.0  # 最小请求间隔（秒）

    def generate(self, model: str, prompt: str, temperature: float = 0.3, max_retries: int = 3) -> str:
        """调用OpenRouter API生成响应（线程安全）"""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/Athena-Software-Group/athenabench",
            "X-Title": "ATT&CK Question Review",
        }

        messages = [
            {
                "role": "system",
                "content": "你是一位网络安全专家审核员，请严格按照要求审查题目。"
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
                # 速率限制控制
                with self.rate_limit_lock:
                    current_time = time.time()
                    elapsed = current_time - self.last_request_time
                    if elapsed < self.min_interval:
                        time.sleep(self.min_interval - elapsed)
                    self.last_request_time = time.time()

                response = requests.post(
                    self.api_url,
                    headers=headers,
                    json=data,
                    timeout=60
                )

                if response.status_code == 429:
                    wait_time = (attempt + 1) * 10
                    print(f"    速率限制，等待 {wait_time} 秒后重试...")
                    time.sleep(wait_time)
                    continue

                response.raise_for_status()
                result = response.json()

                if "choices" in result and len(result["choices"]) > 0:
                    content = result["choices"][0].get("message", {}).get("content", "")
                    return content.strip()
                else:
                    return ""
            except requests.exceptions.RequestException as e:
                print(f"    API错误: {e}")
                if attempt < max_retries - 1:
                    time.sleep(5)
                    continue
                return ""
        return ""


def build_review_prompt(question_data: dict, question_type: str) -> str:
    """根据题型构建审查prompt"""
    
    question_id = question_data.get('question_id', '')
    difficulty = question_data.get('difficulty', 'medium')
    question_text = question_data.get('question', '')
    explanation = question_data.get('explanation', '')
    
    # 基础信息
    base_info = f"""【题目信息】
题目ID：{question_id}
题型：{get_question_form_name(question_type)}
难度：{difficulty}
题目：{question_text}
解析：{explanation}"""

    # 根据题型构建不同的审查内容
    if question_type == 'SC':  # 单选题
        options = question_data.get('options', {})
        correct_answer = question_data.get('correct_answer', '')
        
        content = f"""{base_info}

选项：
A. {options.get('A', '')}
B. {options.get('B', '')}
C. {options.get('C', '')}
D. {options.get('D', '')}

正确答案：{correct_answer}

【审查要点】
1. 技术准确性：答案是否正确？技术描述是否准确？
2. 题目清晰度：表述是否明确无歧义？
3. 选项合理性：干扰项是否合理？是否有明显错误选项？
4. 解析完整性：解析是否充分？是否解释了正确答案的原因？
5. 难度合理性：难度等级是否与题目实际复杂度匹配？
6. 答案唯一性：是否只有一个正确答案？

【输出要求】
如果题目没有问题，请直接输出：无需修改

如果题目有问题需要修改，请输出修正后的题目：
```json
{{"question": "修正后的题目", "options": {{"A": "...", "B": "...", "C": "...", "D": "..."}}, "correct_answer": "修正后的答案", "explanation": "修正后的解析", "difficulty": "修正后的难度"}}
```

请严格按照以上要求输出，不要添加任何其他内容。"""

    elif question_type == 'SSC':  # 场景化单选题
        options = question_data.get('options', {})
        correct_answer = question_data.get('correct_answer', '')
        scenario = question_data.get('scenario', '')
        related_techniques = question_data.get('related_techniques', [])
        scenario_tags = question_data.get('scenario_tags', [])
        target_technique = get_primary_target_id(question_data)

        content = f"""{base_info}

场景：
{scenario}

选项：
A. {options.get('A', '')}
B. {options.get('B', '')}
C. {options.get('C', '')}
D. {options.get('D', '')}

正确答案：{correct_answer}
目标技术：{target_technique}
涉及技术：{', '.join(related_techniques)}
场景标签：{', '.join(scenario_tags)}

【审查要点】
1. 场景真实性：场景是否真实可信，是否包含明确上下文和关键线索？
2. 场景依赖性：问题是否依赖场景信息作答，而不是脱离场景即可直接回答？
3. 技术准确性：正确答案是否最符合场景？涉及技术描述是否准确？
4. 题目清晰度：表述是否明确无歧义？
5. 选项合理性：干扰项是否与场景相关且具有迷惑性，而非明显错误？
6. 答案唯一性：是否存在唯一最优答案？
7. 解析完整性：解析是否指出了场景中的关键证据，并解释其他选项为什么不最优？
8. 难度合理性：难度等级是否与题目实际复杂度匹配？
9. 目标一致性：优先保持题目围绕当前目标技术 `{target_technique}` 展开，不要把题目改写成另一种 ATT&CK 技术

【输出要求】
如果题目没有问题，请直接输出：无需修改

如果题目有问题需要修改，请输出修正后的题目：
```json
{{"scenario": "修正后的场景", "question": "修正后的题目", "options": {{"A": "...", "B": "...", "C": "...", "D": "..."}}, "correct_answer": "修正后的答案", "explanation": "修正后的解析", "difficulty": "修正后的难度", "related_techniques": ["修正后的技术ID数组"], "scenario_tags": ["修正后的场景标签数组"]}}
```

请严格按照以上要求输出，不要添加任何其他内容。"""

    elif question_type == 'MC':  # 多选题
        options = question_data.get('options', {})
        correct_answer = question_data.get('correct_answer', [])
        involved_techniques = question_data.get('involved_techniques', [])
        involved_tactics = question_data.get('involved_tactics', [])
        question_category = question_data.get('question_type', '')
        
        # 根据题目类型决定显示内容
        if question_category == "跨战术关联分析" and involved_tactics:
            involved_info = f"涉及战术：{', '.join(involved_tactics)}"
        else:
            involved_info = f"涉及技术：{', '.join(involved_techniques)}"
        
        content = f"""{base_info}

选项：
A. {options.get('A', '')}
B. {options.get('B', '')}
C. {options.get('C', '')}
D. {options.get('D', '')}
E. {options.get('E', '')}

正确答案：{', '.join(correct_answer)}
{involved_info}

【审查要点】
1. 技术准确性：答案是否正确？技术描述是否准确？
2. 题目清晰度：表述是否明确无歧义？
3. 选项合理性：干扰项是否合理？是否有明显错误选项？
4. 解析完整性：解析是否充分？是否解释了正确答案的原因？
5. 难度合理性：难度等级是否与题目实际复杂度匹配？
6. 答案数量：正确答案数量是否在2-4个之间？
7. 技术关联性：涉及的技术是否有明确的关联关系？
8. 战术关联性：涉及的战术是否有明确的关联关系？

【输出要求】
如果题目没有问题，请直接输出：无需修改

如果题目有问题需要修改，请输出修正后的题目：
```json
{{"question": "修正后的题目", "options": {{"A": "...", "B": "...", "C": "...", "D": "...", "E": "..."}}, "correct_answer": ["修正后的答案数组"], "explanation": "修正后的解析", "difficulty": "修正后的难度", "involved_techniques": ["修正后的技术ID数组"], "involved_tactics": ["修正后的战术ID数组"]}}
```

请严格按照以上要求输出，不要添加任何其他内容。"""

    elif question_type == 'JU':  # 判断题
        correct_answer = question_data.get('correct_answer', '')
        
        content = f"""{base_info}

正确答案：{correct_answer}

【审查要点】
1. 技术准确性：判断是否正确？技术描述是否准确？
2. 题目清晰度：表述是否明确无歧义？
3. 解析完整性：解析是否充分？是否说明了判断的依据？
4. 难度合理性：难度等级是否与题目实际复杂度匹配？
5. 答案明确性：答案是否明确为"正确"或"错误"？

【输出要求】
如果题目没有问题，请直接输出：无需修改

如果题目有问题需要修改，请输出修正后的题目：
```json
{{"question": "修正后的题目", "correct_answer": "修正后的答案", "explanation": "修正后的解析", "difficulty": "修正后的难度"}}
```

请严格按照以上要求输出，不要添加任何其他内容。"""

    elif question_type == 'SQ':  # 排序题
        options = question_data.get('options', {})
        correct_answer = question_data.get('correct_answer', [])
        involved_techniques = question_data.get('involved_techniques', [])
        involved_tactics = question_data.get('involved_tactics', [])
        question_category = question_data.get('question_type', '')
        
        # 根据题目类型决定显示内容
        if question_category == "跨战术关联分析" and involved_tactics:
            involved_info = f"涉及战术：{', '.join(involved_tactics)}"
        else:
            involved_info = f"涉及技术：{', '.join(involved_techniques)}"
        
        content = f"""{base_info}

选项：
A. {options.get('A', '')}
B. {options.get('B', '')}
C. {options.get('C', '')}
D. {options.get('D', '')}

正确顺序：{', '.join(correct_answer)}
{involved_info}

【审查要点】
1. 技术准确性：顺序是否正确？技术描述是否准确？
2. 题目清晰度：表述是否明确无歧义？
3. 选项合理性：排序步骤是否合理？是否有逻辑顺序？
4. 解析完整性：解析是否充分？是否说明了每一步骤的逻辑关系？
5. 难度合理性：难度等级是否与题目实际复杂度匹配？
6. 顺序逻辑性：排序步骤之间是否有明确的逻辑关系或依赖关系？
7. 技术关联性：涉及的技术是否有明确的关联关系？
8. 战术关联性：涉及的战术是否有明确的关联关系？

【输出要求】
如果题目没有问题，请直接输出：无需修改

如果题目有问题需要修改，请输出修正后的题目：
```json
{{"question": "修正后的题目", "options": {{"A": "...", "B": "...", "C": "...", "D": "..."}}, "correct_answer": ["修正后的顺序数组"], "explanation": "修正后的解析", "difficulty": "修正后的难度", "involved_techniques": ["修正后的技术ID数组"], "involved_tactics": ["修正后的战术ID数组"]}}
```

请严格按照以上要求输出，不要添加任何其他内容。"""

    else:
        content = f"""{base_info}

【审查要点】
1. 技术准确性：内容是否准确？
2. 题目清晰度：表述是否明确无歧义？
3. 解析完整性：解析是否充分？
4. 难度合理性：难度等级是否与题目实际复杂度匹配？

【输出要求】
如果题目没有问题，请直接输出：无需修改

如果题目有问题需要修改，请输出修正后的题目。"""

    return content


def get_question_form_name(question_form: str) -> str:
    """获取题型名称（单选/多选/判断/排序）"""
    form_names = {
        'SC': '单项选择题',
        'SSC': '场景化单项选择题',
        'MC': '多项选择题',
        'JU': '判断题',
        'SQ': '排序题'
    }
    return form_names.get(question_form, '未知题型')


def extract_json(text: str) -> dict:
    """从文本中提取JSON"""
    json_match = re.search(r'```json\s*(.*?)\s*```', text, re.DOTALL)
    if json_match:
        json_str = json_match.group(1)
    else:
        # 如果没有json块，尝试找 {...} 块
        json_match = re.search(r'\{.*\}', text, re.DOTALL)
        if json_match:
            json_str = json_match.group(0)
        else:
            return None

    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        return None


def extract_attack_ids(text: str) -> list[str]:
    return re.findall(r"T\d{4}(?:\.\d{3})?", text or "")


def parse_option_attack_mapping(option_text: str):
    match = re.match(r"^\s*(.*?)\s*\((T\d{4}(?:\.\d{3})?)\)\s*$", option_text or "")
    if not match:
        return None, None
    return match.group(1).strip(), match.group(2)


def get_primary_target_id(question: dict) -> str:
    tactic_technique = question.get("tactic_technique", "")
    parts = [part for part in tactic_technique.split("-") if part]
    return parts[-1] if parts else ""


def get_correct_option_attack_id(question: dict) -> str:
    options = question.get("options", {})
    correct_answer = question.get("correct_answer", "")
    correct_text = options.get(correct_answer, "")
    ids = extract_attack_ids(correct_text)
    return ids[0] if ids else ""


def validate_reviewed_ssc_question(original_question: dict, reviewed_question: dict):
    """校验 SSC 审校结果，防止模型把题目改成与本地 ATT&CK 数据不一致的新题。"""
    options = reviewed_question.get("options", {})
    if set(options.keys()) != {"A", "B", "C", "D"}:
        return False, "选项结构无效"

    correct_answer = reviewed_question.get("correct_answer", "")
    if correct_answer not in {"A", "B", "C", "D"}:
        return False, "correct_answer 非法"

    seen_ids = set()
    for key in ("A", "B", "C", "D"):
        option_name, attack_id = parse_option_attack_mapping(options.get(key, ""))
        if not option_name or not attack_id:
            return False, f"选项 {key} 不是标准 ATT&CK 格式"
        canonical_name = ATTACK_ID_NAME_MAP.get(attack_id)
        if not canonical_name:
            return False, f"选项 {key} 使用了本地 ATT&CK 中不存在的技术 ID {attack_id}"
        if option_name != canonical_name:
            return False, f"选项 {key} 的技术名与本地 ATT&CK 映射不一致"
        if attack_id in seen_ids:
            return False, f"多个选项复用了同一个 ATT&CK ID {attack_id}"
        seen_ids.add(attack_id)

    original_correct_id = get_correct_option_attack_id(original_question)
    reviewed_correct_id = get_correct_option_attack_id(reviewed_question)
    target_id = get_primary_target_id(original_question)

    if not reviewed_correct_id:
        return False, "无法解析审校后正确答案对应的 ATT&CK ID"
    if original_correct_id and reviewed_correct_id != original_correct_id:
        return False, f"审校将正确答案从 {original_correct_id} 改成了 {reviewed_correct_id}"
    if target_id and reviewed_correct_id != target_id:
        return False, f"审校结果偏离了当前题目的目标技术 {target_id}"

    related_techniques = reviewed_question.get("related_techniques", [])
    if not isinstance(related_techniques, list) or not related_techniques:
        return False, "related_techniques 非法"
    for tech_id in related_techniques:
        if tech_id not in ATTACK_ID_NAME_MAP:
            return False, f"related_techniques 中存在未知技术 ID {tech_id}"
    if target_id and target_id not in related_techniques:
        return False, f"related_techniques 未包含目标技术 {target_id}"

    return True, ""

    try:
        return json.loads(json_str.strip())
    except json.JSONDecodeError:
        return None


def load_questions(input_path: str) -> list:
    """加载题目"""
    questions = []
    with open(input_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                questions.append(json.loads(line))
    return questions


def update_test_prompt(question: dict, question_type: str) -> str:
    """更新test_prompt"""
    
    if question_type == 'SC':  # 单选题
        return f"""你是一位网络安全专家，请回答以下单项选择题：

题目：{question['question']}

选项：
A. {question['options']['A']}
B. {question['options']['B']}
C. {question['options']['C']}
D. {question['options']['D']}

请直接输出正确答案的字母选项（如：B），不要添加任何其他内容。"""

    elif question_type == 'SSC':  # 场景化单选题
        return f"""你是一位网络安全专家，请阅读以下攻击场景并回答单项选择题：

场景：
{question.get('scenario', '')}

问题：
{question['question']}

选项：
A. {question['options']['A']}
B. {question['options']['B']}
C. {question['options']['C']}
D. {question['options']['D']}

请直接输出正确答案的字母选项（如：B），不要添加任何其他内容。"""

    elif question_type == 'MC':  # 多选题
        options = question['options']
        return f"""你是一位网络安全专家，请回答以下多项选择题：

题目：{question['question']}

选项：
A. {options.get('A', '')}
B. {options.get('B', '')}
C. {options.get('C', '')}
D. {options.get('D', '')}
E. {options.get('E', '')}

请直接输出所有正确答案的字母选项，按字母顺序排列，用逗号分隔（如：A,C,D），不要添加任何其他内容。"""

    elif question_type == 'JU':  # 判断题
        return f"""你是一位网络安全专家，请回答以下判断题：

题目：{question['question']}

请直接输出正确答案（正确/错误），不要添加任何其他内容。"""

    elif question_type == 'SQ':  # 排序题
        options = question['options']
        return f"""你是一位网络安全专家，请回答以下排序题：

题目：{question['question']}

选项：
A. {options.get('A', '')}
B. {options.get('B', '')}
C. {options.get('C', '')}
D. {options.get('D', '')}

请直接输出正确的顺序，使用字母选项，按顺序用逗号分隔（如：A,C,B,D），不要添加任何其他内容。"""

    else:
        return question.get('test_prompt', '')


def detect_question_type(question_id: str) -> str:
    """根据question_id检测题型"""
    if question_id.startswith('SSC-'):
        return 'SSC'
    elif question_id.startswith('SC-'):
        return 'SC'
    elif question_id.startswith('MC-'):
        return 'MC'
    elif question_id.startswith('JU-'):
        return 'JU'
    elif question_id.startswith('SQ-'):
        return 'SQ'
    else:
        return 'UNKNOWN'


def get_question_type_abbr(question_type: str) -> str:
    """获取题型缩写"""
    type_abbr = {
        'SC': 'SC',
        'SSC': 'SSC',
        'MC': 'MC',
        'JU': 'JU',
        'SQ': 'SQ'
    }
    return type_abbr.get(question_type, 'UNKNOWN')


def process_single_question(args):
    """处理单个题目（用于并发）"""
    idx, question, client, model_name = args
    question_id = question.get("question_id", f"Q{idx}")
    question_type = detect_question_type(question_id)
    
    # 构建审查prompt
    review_prompt = build_review_prompt(question, question_type)
    
    # 调用模型
    response = client.generate(model_name, review_prompt)
    
    # 检查结果
    if "无需修改" in response or "无需修改" in response:
        # 无需修改，保留原题目
        reviewed_question = question
        status = "unchanged"
        message = f"OK {question_id} ({get_question_form_name(question_type)}): 无需修改"
    else:
        # 尝试提取修改后的JSON
        review_result = extract_json(response)

        if review_result:
            # 保留原有字段，更新修改后的内容
            reviewed_question = {
                "question_id": question.get("question_id", ""),
                "tactic_technique": question.get("tactic_technique", ""),
                "difficulty": review_result.get("difficulty", question.get("difficulty", "medium")),
                "question": review_result.get("question", question.get("question", "")),
                "explanation": review_result.get("explanation", question.get("explanation", "")),
                "test_prompt": ""
            }
            
            # 根据题型保留特定字段
            if question_type in ['SC', 'SSC', 'MC', 'SQ']:
                reviewed_question["options"] = review_result.get("options", question.get("options", {}))
            
            if question_type in ['SC', 'SSC', 'MC', 'JU', 'SQ']:
                reviewed_question["correct_answer"] = review_result.get("correct_answer", question.get("correct_answer", ""))

            if question_type == 'SSC':
                reviewed_question["scenario"] = review_result.get("scenario", question.get("scenario", ""))
                reviewed_question["related_techniques"] = review_result.get("related_techniques", question.get("related_techniques", []))
                reviewed_question["scenario_tags"] = review_result.get("scenario_tags", question.get("scenario_tags", []))
            
            if question_type in ['MC', 'SQ']:
                reviewed_question["involved_techniques"] = review_result.get("involved_techniques", question.get("involved_techniques", []))
                reviewed_question["involved_tactics"] = review_result.get("involved_tactics", question.get("involved_tactics", []))
            
            if question_type in ['SC', 'SSC', 'MC', 'SQ']:
                reviewed_question["question_type"] = question.get("question_type", "")
            
            # 更新test_prompt
            reviewed_question["test_prompt"] = update_test_prompt(reviewed_question, question_type)

            if question_type == 'SSC':
                is_valid_review, validation_reason = validate_reviewed_ssc_question(question, reviewed_question)
                if not is_valid_review:
                    reviewed_question = question
                    status = "unchanged"
                    message = (
                        f"OK {question_id} ({get_question_form_name(question_type)}): "
                        f"审校修改未采纳，保留原题 ({validation_reason})"
                    )
                else:
                    status = "modified"
                    message = f"OK {question_id} ({get_question_form_name(question_type)}): 已修改"
            else:
                status = "modified"
                message = f"OK {question_id} ({get_question_form_name(question_type)}): 已修改"
        else:
            # 解析失败，保留原题目
            reviewed_question = question
            status = "error"
            message = f"ERROR {question_id} ({get_question_form_name(question_type)}): 解析失败，保留原题目"

    return question, reviewed_question, status, message


def review_questions(model_name: str, input_path: str, output_dir: str = str(DATASETS_REVIEWED_DIR), max_workers: int = 3):
    """审查题目（支持并发）"""
    print(f"开始审查题目")
    print(f"使用模型: {model_name}")
    print(f"输入文件: {input_path}")
    print(f"输出目录: {output_dir}")
    print(f"并发数: {max_workers}")
    print("=" * 60)

    # 加载API密钥
    api_key = os.getenv('OPENROUTER_API_KEY')
    if not api_key:
        print("错误: 请设置 OPENROUTER_API_KEY 环境变量")
        return

    # 初始化客户端
    client = OpenRouterClient(api_key)

    # 加载题目
    questions = load_questions(input_path)
    print(f"加载了 {len(questions)} 道题目\n")

    # 检测题型
    if questions:
        first_question_id = questions[0].get("question_id", "")
        question_type = detect_question_type(first_question_id)
        question_type_abbr = get_question_type_abbr(question_type)
    else:
        question_type_abbr = "UNKNOWN"

    # 准备输出文件 - 新命名格式：review_审查模型_题目类型_题目数量.jsonl
    ensure_standard_directories()
    os.makedirs(output_dir, exist_ok=True)
    
    # 提取模型名称（去掉路径前缀）
    model_short_name = model_name.split('/')[-1] if '/' in model_name else model_name
    
    # 构建文件名：review_审查模型_题目类型_题目数量.jsonl
    output_file = os.path.join(
        output_dir, 
        f"review_{model_short_name}_{question_type_abbr}_{len(questions)}.jsonl"
    )
    
    # 构建修改记录文件：review_修改记录_审查模型_题目类型_题目数量.jsonl
    modified_record_file = os.path.join(
        output_dir, 
        f"review_修改记录_{model_short_name}_{question_type_abbr}_{len(questions)}.jsonl"
    )
    
    # 统计变量
    modified_count = 0
    unchanged_count = 0
    error_count = 0

    # 准备任务参数
    task_args = [(idx, question, client, model_name) for idx, question in enumerate(questions, 1)]

    # 并发处理
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        with tqdm(total=len(questions), desc="审查进度", unit="题") as pbar:
            # 提交所有任务
            future_to_idx = {executor.submit(process_single_question, args): args[0] for args in task_args}
            
            # 处理完成的任务
            for future in as_completed(future_to_idx):
                try:
                    original_question, reviewed_question, status, message = future.result()
                    
                    # 实时写入主输出文件
                    with file_lock:
                        with open(output_file, 'a', encoding='utf-8') as f:
                            f.write(json.dumps(reviewed_question, ensure_ascii=False) + '\n')
                    
                    # 如果题目被修改，写入修改记录文件
                    if status == "modified":
                        with file_lock:
                            with open(modified_record_file, 'a', encoding='utf-8') as f:
                                # 写入修改前的题目（添加标识）
                                f.write('修改前: ' + json.dumps(original_question, ensure_ascii=False) + '\n')
                                # 写入修改后的题目（添加标识）
                                f.write('修改后: ' + json.dumps(reviewed_question, ensure_ascii=False) + '\n')
                    
                    # 更新统计
                    if status == "modified":
                        modified_count += 1
                    elif status == "unchanged":
                        unchanged_count += 1
                    else:
                        error_count += 1
                    
                    # 打印状态
                    print(message)
                    
                except Exception as e:
                    print(f"ERROR 处理失败: {e}")
                    error_count += 1
                
                pbar.update(1)

    # 写入修改记录文件的统计信息
    if modified_count > 0:
        total_questions = len(questions)
        modification_ratio = (modified_count / total_questions) * 100 if total_questions > 0 else 0
        
        stats = {
            "total_questions": total_questions,
            "modified_count": modified_count,
            "unchanged_count": unchanged_count,
            "error_count": error_count,
            "modification_ratio": f"{modification_ratio:.2f}%",
            "model": model_name,
            "input_file": input_path,
            "review_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        with open(modified_record_file, 'a', encoding='utf-8') as f:
            f.write('\n' + json.dumps(stats, ensure_ascii=False) + '\n')

    print("\n" + "=" * 60)
    print(f"审查完成！共处理 {len(questions)} 道题目")
    print(f"  无需修改: {unchanged_count} 道")
    print(f"  已修改: {modified_count} 道")
    print(f"  解析错误: {error_count} 道")
    print(f"输出文件: {output_file}")
    if modified_count > 0:
        print(f"修改记录文件: {modified_record_file}")

    return output_file


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="通用题目审查脚本（并发版本）")
    parser.add_argument(
        "--model",
        type=str,
        default="openai/gpt-4o",
        help="审查模型名称（默认: openai/gpt-4o）"
    )
    parser.add_argument(
        "--input",
        type=str,
        required=True,
        help="输入题目文件路径"
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="review_output",
        help="输出目录（默认: review_output）"
    )
    parser.add_argument(
        "--max-workers",
        type=int,
        default=3,
        help="并发数（默认: 3，建议根据API速率限制调整）"
    )

    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"错误: 输入文件不存在: {args.input}")
        return

    review_questions(
        model_name=args.model,
        input_path=args.input,
        output_dir=args.output_dir,
        max_workers=args.max_workers
    )


if __name__ == "__main__":
    main()
