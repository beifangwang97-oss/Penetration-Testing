"""测试OpenRouter API连接"""

import os
from dotenv import load_dotenv
import requests


def test_connection():
    """测试OpenRouter API连接"""
    load_dotenv()
    
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        print("错误: 未找到 OPENROUTER_API_KEY")
        print("请在项目根目录创建 .env 文件，并添加:")
        print("OPENROUTER_API_KEY=your-api-key-here")
        return False
    
    print("测试 OpenRouter API 连接...")
    print(f"API Key: {api_key[:10]}...")
    print("-" * 60)
    
    # 测试免费模型（使用实际可用的模型）
    test_models = [
        "google/gemma-3-4b-it:free",
        "meta-llama/llama-3.3-70b-instruct:free",
        "qwen/qwen3-4b:free",
        "mistralai/mistral-small-3.1-24b-instruct:free",
    ]
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/Athena-Software-Group/athenabench",
        "X-Title": "AthenaBench Test",
    }
    
    api_url = "https://openrouter.ai/api/v1/chat/completions"
    
    success_count = 0
    
    for model in test_models:
        print(f"\n测试模型: {model}")
        data = {
            "model": model,
            "messages": [
                {"role": "user", "content": "Say 'Hello' if you can read this."}
            ],
        }
        
        try:
            response = requests.post(api_url, headers=headers, json=data, timeout=30)
            
            # 打印响应状态码
            print(f"  状态码: {response.status_code}")
            
            if response.status_code == 404:
                print(f"  ✗ 模型不存在或端点错误")
                print(f"  尝试检查模型名称是否正确")
                continue
            elif response.status_code == 401:
                print(f"  ✗ 认证失败，请检查API密钥")
                continue
            elif response.status_code == 429:
                print(f"  ✗ 请求过于频繁，请稍后重试")
                continue
            
            response.raise_for_status()
            result = response.json()
            
            if "choices" in result and len(result["choices"]) > 0:
                content = result["choices"][0].get("message", {}).get("content", "")
                print(f"  ✓ 成功! 响应: {content[:50]}...")
                success_count += 1
            else:
                print(f"  ✗ 响应格式异常: {result}")
                
        except requests.exceptions.HTTPError as e:
            print(f"  ✗ HTTP错误: {e}")
            if hasattr(e.response, 'text'):
                print(f"  响应内容: {e.response.text[:200]}")
        except requests.exceptions.RequestException as e:
            print(f"  ✗ 请求失败: {e}")
            continue
    
    print("\n" + "=" * 60)
    if success_count > 0:
        print(f"✓ 连接测试完成! {success_count}/{len(test_models)} 个模型测试成功")
        return True
    else:
        print("✗ 所有模型测试失败，请检查:")
        print("  1. API密钥是否正确")
        print("  2. 网络连接是否正常")
        print("  3. 模型名称是否有效（访问 https://openrouter.ai/models 查看）")
        return False


if __name__ == "__main__":
    test_connection()

