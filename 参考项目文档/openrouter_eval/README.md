# OpenRouter CKT 数据集评估

这是一个完全独立的评估脚本，使用 OpenRouter 免费模型对 CKT（Cyber Knowledge Test）数据集进行评估。

## 特点

- ✅ **完全独立**：不依赖项目中的其他代码模块
- ✅ **简单易用**：只需设置 API 密钥即可运行
- ✅ **自动评估**：自动提取答案并计算准确率
- ✅ **结果保存**：保存详细的评估结果和摘要

## 设置

### 1. 安装依赖

```bash
pip install requests python-dotenv
```

### 2. 获取 OpenRouter API 密钥

1. 访问 [OpenRouter 官网](https://openrouter.ai/) 注册账户
2. 在账户设置中生成 API 密钥
3. 在项目根目录创建 `.env` 文件：

```
OPENROUTER_API_KEY=your-api-key-here
```

### 3. 测试连接

```bash
python openrouter_eval/test_connection.py
```

## 使用方法

### 基本用法

使用默认模型和迷你数据集：

```bash
python openrouter_eval/evaluate_ckt.py
```

### 指定模型

```bash
python openrouter_eval/evaluate_ckt.py --model meta-llama/llama-3.1-8b-instruct:free
```

### 使用完整数据集

```bash
python openrouter_eval/evaluate_ckt.py --dataset benchmark/athena-cti-ckt-3k.jsonl
```

### 调整API调用延迟

```bash
python openrouter_eval/evaluate_ckt.py --delay 2.0
```

### 完整参数示例

```bash
python openrouter_eval/evaluate_ckt.py \
    --model qwen/qwen-2.5-7b-instruct:free \
    --dataset benchmark-mini/athena-cti-ckt-3k.jsonl \
    --output-dir openrouter_eval/results \
    --delay 1.5
```

## 可用的免费模型

经过测试，以下模型可用：

- `meta-llama/llama-3.3-70b-instruct:free` - Meta Llama 3.3 70B（推荐）
- `mistralai/mistral-small-3.1-24b-instruct:free` - Mistral Small 3.1 24B
- `google/gemma-3-4b-it:free` - Google Gemma 3 4B（可能受地理位置限制）
- `qwen/qwen3-4b:free` - Qwen3 4B（可能受参数限制）

更多免费模型请访问 [OpenRouter 模型列表](https://openrouter.ai/models)

**注意**：某些模型可能因地理位置或参数限制而不可用，建议先运行 `test_connection.py` 测试。

## 输出文件

评估结果保存在 `openrouter_eval/results/` 目录：

1. **`{model_name}_results.jsonl`** - 详细结果
   - 每条记录包含：问题、提示、模型响应、预测答案、正确答案、是否正确

2. **`{model_name}_summary.json`** - 评估摘要
   - 包含：模型名称、数据集路径、总题目数、正确数、准确率

## 结果格式

### results.jsonl 示例

```json
{
  "id": 1,
  "question": "Which ATT&CK technique...",
  "prompt": "You are given a multiple-choice question...",
  "response": "The answer is C because...\nAnswer: C",
  "predicted_answer": "C",
  "correct_answer": "C",
  "is_correct": true
}
```

### summary.json 示例

```json
{
  "model": "google/gemma-2-9b-it:free",
  "dataset": "benchmark-mini/athena-cti-ckt-3k.jsonl",
  "total_count": 301,
  "correct_count": 240,
  "accuracy": 79.73,
  "results_file": "openrouter_eval/results/google_gemma-2-9b-it_free_results.jsonl"
}
```

## 注意事项

1. **API 限制**：免费模型有调用频率限制，建议设置适当的延迟（`--delay` 参数）
2. **网络问题**：如果遇到超时，可以增加延迟时间
3. **模型可用性**：某些免费模型可能在某些时段不可用

## 故障排除

### API 密钥错误

```
错误: 未找到 OPENROUTER_API_KEY
```

**解决**：确保 `.env` 文件在项目根目录，且包含正确的 API 密钥。

### 模型不可用

```
请求失败: 404 Not Found
```

**解决**：检查模型名称是否正确，访问 OpenRouter 网站确认模型可用。

### 请求超时

```
请求失败: Read timeout
```

**解决**：增加延迟时间或检查网络连接。

## 代码结构

```
openrouter_eval/
├── evaluate_ckt.py      # 主评估脚本
├── test_connection.py    # API连接测试
└── README.md            # 本文件
```

## 独立实现说明

此实现完全独立，不依赖项目中的 `athena_eval` 模块：
- 自己实现 OpenRouter API 调用
- 自己实现答案提取逻辑
- 自己实现评估和结果保存
- 只使用 CKT 数据集文件
