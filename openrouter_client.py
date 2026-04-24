"""
OpenRouter API客户端实现
支持通过OpenRouter调用多个模型
"""

import json
import time
from typing import Dict, Any, List, Optional
import aiohttp
from dataclasses import dataclass


@dataclass
class OpenRouterConfig:
    api_key: str
    base_url: str = "https://openrouter.ai/api/v1/chat/completions"
    timeout: int = 60


class OpenRouterClient:
    def __init__(self, config: OpenRouterConfig):
        self.config = config
        self.session = None
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=self.config.timeout)
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def generate(
        self,
        model: str,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 4096
    ) -> Dict[str, Any]:
        """
        调用OpenRouter API生成内容
        """
        if not self.session:
            self.session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.config.timeout)
            )
        
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "top_p": 1.0,
            "frequency_penalty": 0.0,
            "presence_penalty": 0.0
        }
        
        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://your-application.com",  # 替换为你的应用URL
            "X-Title": "ATT&CK Dataset Generator"  # 替换为你的应用名称
        }
        
        for attempt in range(3):
            try:
                async with self.session.post(
                    self.config.base_url,
                    headers=headers,
                    json=payload
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        return result
                    elif response.status == 429:
                        # 速率限制
                        wait_time = 2 ** attempt
                        print(f"Rate limited, waiting {wait_time} seconds...")
                        await asyncio.sleep(wait_time)
                        continue
                    else:
                        error_text = await response.text()
                        print(f"Error: {response.status} - {error_text}")
                        return {"error": f"API error: {response.status}", "detail": error_text}
            except asyncio.TimeoutError:
                print(f"Timeout error (attempt {attempt + 1}/3)")
                if attempt < 2:
                    await asyncio.sleep(2)
                    continue
                return {"error": "Request timeout"}
            except aiohttp.ClientError as e:
                print(f"Client error (attempt {attempt + 1}/3): {e}")
                if attempt < 2:
                    await asyncio.sleep(2)
                    continue
                return {"error": f"Client error: {str(e)}"}
            except Exception as e:
                print(f"Exception: {type(e).__name__}: {e}")
                if attempt < 2:
                    await asyncio.sleep(2)
                    continue
                return {"error": f"{type(e).__name__}: {str(e)}"}
        
        return {"error": "Max retries exceeded"}
    
    async def get_available_models(self) -> List[Dict[str, Any]]:
        """
        获取OpenRouter可用的模型列表
        """
        if not self.session:
            self.session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.config.timeout)
            )
        
        url = "https://openrouter.ai/api/v1/models"
        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "HTTP-Referer": "https://your-application.com",
            "X-Title": "ATT&CK Dataset Generator"
        }
        
        try:
            async with self.session.get(url, headers=headers) as response:
                if response.status == 200:
                    result = await response.json()
                    return result.get("data", [])
                else:
                    error_text = await response.text()
                    print(f"Error: {response.status} - {error_text}")
                    return []
        except Exception as e:
            print(f"Exception: {e}")
            return []


class OpenRouterModelAdapter:
    """
    适配OpenRouter API到通用模型客户端接口
    """
    def __init__(self, config: OpenRouterConfig, model_id: str, model_name: str):
        self.config = config
        self.model_id = model_id
        self.model_name = model_name
        self.client = OpenRouterClient(config)
    
    async def generate(self, prompt: str) -> Dict[str, Any]:
        """
        生成内容
        """
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
        
        result = await self.client.generate(
            model=self.model_name,
            messages=messages,
            temperature=0.7,
            max_tokens=4096
        )
        
        if "error" in result:
            return {
                "error": result["error"],
                "content": "",
                "confidence": 0.0
            }
        
        if "choices" in result and len(result["choices"]) > 0:
            content = result["choices"][0]["message"]["content"]
            # 提取JSON内容（如果有的话）
            try:
                # 尝试提取JSON部分
                import re
                json_match = re.search(r'```json\n(.*?)\n```', content, re.DOTALL)
                if json_match:
                    content = json_match.group(1)
            except:
                pass
            
            return {
                "content": content,
                "confidence": 0.8,  # OpenRouter不返回置信度，使用默认值
                "usage": result.get("usage", {})
            }
        
        return {
            "content": "",
            "confidence": 0.0
        }
    
    async def review(self, question: Dict[str, Any]) -> Dict[str, Any]:
        """
        审核题目
        """
        question_str = json.dumps(question, ensure_ascii=False, indent=2)
        
        prompt = f"你是一位网络安全专家审核员，请审核以下渗透测试能力评估题目的质量：\n\n【题目内容】\n{question_str}\n\n【审核要点】\n1. 技术准确性：答案是否正确？技术描述是否准确？\n2. 题目清晰度：表述是否明确无歧义？\n3. 选项合理性：干扰项是否合理？是否有明显错误选项？\n4. 解析完整性：解析是否充分？是否解释了正确答案的原因？\n5. 知识点相关性：题目是否有效考察了目标知识点？\n\n请按照以下JSON格式输出审核结果：\n{{\n  \"is_valid\": true或false,\n  \"score\": 0-100的评分,\n  \"issues\": [\"发现的问题1\", \"发现的问题2\"],\n  \"suggestions\": [\"改进建议1\", \"改进建议2\"],\n  \"correctness_check\": {{\n    \"answer_correct\": true或false,\n    \"explanation_accurate\": true或false\n  }},\n  \"quality_check\": {{\n    \"clarity_score\": 0-100,\n    \"option_quality_score\": 0-100,\n    \"explanation_score\": 0-100\n  }}\n}}"
        
        result = await self.generate(prompt)
        
        try:
            review_result = json.loads(result["content"])
            return review_result
        except json.JSONDecodeError:
            return {
                "is_valid": False,
                "score": 0,
                "issues": ["审核结果解析失败"],
                "suggestions": ["请检查生成的审核结果格式"],
                "correctness_check": {
                    "answer_correct": False,
                    "explanation_accurate": False
                },
                "quality_check": {
                    "clarity_score": 0,
                    "option_quality_score": 0,
                    "explanation_score": 0
                }
            }


import asyncio


async def test_openrouter_client():
    """
    测试OpenRouter客户端
    """
    import os
    from dotenv import load_dotenv
    
    # 加载环境变量
    load_dotenv()
    api_key = os.getenv("OPENROUTER_API_KEY")
    
    if not api_key:
        print("请设置OPENROUTER_API_KEY环境变量")
        return
    
    config = OpenRouterConfig(api_key=api_key)
    
    async with OpenRouterClient(config) as client:
        # 测试获取模型列表
        models = await client.get_available_models()
        print(f"可用模型数量: {len(models)}")
        for model in models[:10]:  # 只显示前10个
            print(f"- {model['id']}: {model['name']}")
        
        # 测试生成功能
        adapter = OpenRouterModelAdapter(config, "gpt-4", "gpt-4")
        result = await adapter.generate("请生成一道关于SQL注入的单项选择题")
        print("\n生成结果:")
        print(result["content"])


if __name__ == "__main__":
    asyncio.run(test_openrouter_client())
