"""独立评估脚本：使用OpenRouter免费模型评估CKT数据集

此脚本完全独立，不依赖项目中的其他代码模块。
"""

import json
import os
import re
import time
from pathlib import Path
from typing import Dict, List, Optional
import requests
from dotenv import load_dotenv


class OpenRouterClient:
    """OpenRouter API客户端"""
    
    def __init__(self, api_key: Optional[str] = None):
        """初始化OpenRouter客户端"""
        load_dotenv()
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY")
        if not self.api_key:
            raise ValueError("OPENROUTER_API_KEY not found. Please set it in environment or .env file")
        
        self.base_url = "https://openrouter.ai/api/v1"
        self.api_url = f"{self.base_url}/chat/completions"
    
    def generate(self, model: str, prompt: str, temperature: float = 0.0) -> str:
        """调用OpenRouter API生成响应"""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/Athena-Software-Group/athenabench",
            "X-Title": "AthenaBench CKT Evaluation",
        }
        
        data = {
            "model": model,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "temperature": temperature,
        }
        
        try:
            response = requests.post(
                self.api_url,
                headers=headers,
                json=data,
                timeout=60
            )
            response.raise_for_status()
            result = response.json()
            
            if "choices" in result and len(result["choices"]) > 0:
                content = result["choices"][0].get("message", {}).get("content", "")
                return content.strip()
            else:
                raise ValueError(f"Unexpected response format: {result}")
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"OpenRouter API request failed: {e}")


def extract_answer(text: str) -> str:
    """从模型响应中提取答案（A-E）"""
    # 移除常见前缀
    prefix_pattern = re.compile(
        r'^\s*(?:final\s+answer|answer|prediction|output|result)\s*[:\-–—]?\s*',
        re.IGNORECASE
    )
    text = prefix_pattern.sub("", text).strip()
    
    # 从底部向上搜索答案
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    
    for i in range(len(lines) - 1, -1, -1):
        line = lines[i]
        # 查找 "Answer: A" 格式
        match = re.search(r'\b([A-E])\b', line, re.IGNORECASE)
        if match:
            return match.group(1).upper()
        
        # 如果这一行包含"Answer"，检查相邻行
        if re.search(r'\banswer\b', line, re.IGNORECASE):
            if i + 1 < len(lines):
                match = re.search(r'\b([A-E])\b', lines[i + 1], re.IGNORECASE)
                if match:
                    return match.group(1).upper()
            if i > 0:
                match = re.search(r'\b([A-E])\b', lines[i - 1], re.IGNORECASE)
                if match:
                    return match.group(1).upper()
    
    # 如果没找到，在整个文本中搜索
    match = re.search(r'\b([A-E])\b', text, re.IGNORECASE)
    if match:
        return match.group(1).upper()
    
    return ""


def load_ckt_dataset(dataset_path: str) -> List[Dict]:
    """加载CKT数据集"""
    records = []
    with open(dataset_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def evaluate_ckt(
    model_name: str,
    dataset_path: str,
    output_dir: str = "openrouter_eval/results",
    delay: float = 20.0
):
    """评估CKT数据集
    
    Args:
        model_name: OpenRouter模型名称（如 'google/gemma-2-9b-it:free'）
        dataset_path: CKT数据集路径
        output_dir: 输出目录
        delay: 每次API调用之间的延迟（秒）
    """
    print(f"开始评估 CKT 数据集")
    print(f"模型: {model_name}")
    print(f"数据集: {dataset_path}")
    print(f"输出目录: {output_dir}")
    print("=" * 60)
    
    # 创建输出目录
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # 初始化客户端
    client = OpenRouterClient()
    
    # 加载数据集
    records = load_ckt_dataset(dataset_path)
    print(f"加载了 {len(records)} 条记录\n")
    
    # 评估结果
    results = []
    correct_count = 0
    total_count = 0
    
    # 处理每条记录
    for idx, record in enumerate(records, 1):
        prompt = record.get("prompt", "")
        correct_answer = record.get("answer", "").upper()
        
        print(f"[{idx}/{len(records)}] 处理中...", end=" ", flush=True)
        
        try:
            # 调用API
            response = client.generate(model_name, prompt)
            
            # 提取答案
            predicted_answer = extract_answer(response)
            
            # 判断是否正确
            is_correct = (predicted_answer == correct_answer)
            if is_correct:
                correct_count += 1
            total_count += 1
            
            # 保存结果
            result = {
                "id": record.get("id", idx - 1),
                "question": record.get("question", ""),
                "prompt": prompt,
                "response": response,
                "predicted_answer": predicted_answer,
                "correct_answer": correct_answer,
                "is_correct": is_correct,
            }
            results.append(result)
            
            status = "✓" if is_correct else "✗"
            print(f"{status} 预测: {predicted_answer}, 正确答案: {correct_answer}")
            
            # 延迟以避免速率限制
            if idx < len(records):
                time.sleep(delay)
                
        except Exception as e:
            print(f"错误: {e}")
            result = {
                "id": record.get("id", idx - 1),
                "question": record.get("question", ""),
                "prompt": prompt,
                "response": "",
                "predicted_answer": "",
                "correct_answer": correct_answer,
                "is_correct": False,
                "error": str(e),
            }
            results.append(result)
            total_count += 1
    
    # 计算准确率
    accuracy = (correct_count / total_count * 100) if total_count > 0 else 0.0
    
    print("\n" + "=" * 60)
    print(f"评估完成!")
    print(f"总题目数: {total_count}")
    print(f"正确数: {correct_count}")
    print(f"准确率: {accuracy:.2f}%")
    print("=" * 60)
    
    # 保存结果
    model_safe_name = model_name.replace("/", "_").replace(":", "_")
    output_file = output_path / f"{model_safe_name}_results.jsonl"
    
    with open(output_file, "w", encoding="utf-8") as f:
        for result in results:
            f.write(json.dumps(result, ensure_ascii=False) + "\n")
    
    # 保存摘要
    summary = {
        "model": model_name,
        "dataset": dataset_path,
        "total_count": total_count,
        "correct_count": correct_count,
        "accuracy": accuracy,
        "results_file": str(output_file),
    }
    
    summary_file = output_path / f"{model_safe_name}_summary.json"
    with open(summary_file, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    
    print(f"\n结果已保存到: {output_file}")
    print(f"摘要已保存到: {summary_file}")
    
    return summary


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="使用OpenRouter模型评估CKT数据集")
    parser.add_argument(
        "--model",
        type=str,
        default="meta-llama/llama-3.3-70b-instruct:free",
        help="OpenRouter模型名称（默认: meta-llama/llama-3.3-70b-instruct:free）"
    )
    parser.add_argument(
        "--dataset",
        type=str,
        default="benchmark-mini/athena-cti-ckt-3k.jsonl",
        help="CKT数据集路径（默认: benchmark-mini/athena-cti-ckt-3k.jsonl）"
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="openrouter_eval/results",
        help="输出目录（默认: openrouter_eval/results）"
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=1.0,
        help="API调用之间的延迟（秒，默认: 1.0）"
    )
    
    args = parser.parse_args()
    
    # 检查数据集文件是否存在
    if not os.path.exists(args.dataset):
        print(f"错误: 数据集文件不存在: {args.dataset}")
        return
    
    # 运行评估
    try:
        evaluate_ckt(
            model_name=args.model,
            dataset_path=args.dataset,
            output_dir=args.output_dir,
            delay=args.delay
        )
    except Exception as e:
        print(f"评估失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()

