# 实战推理题型扩展设计

## 1. 背景与目标

当前 `demo/` 已具备以下题型：

- `judgment`
- `single_choice`
- `multiple_choice`
- `sequencing`
- `scenario_single_choice`

其中，`scenario_single_choice` 已经把题目从“单技术记忆”推进到了“场景化判断”，但整体仍以单步判断为主。下一轮扩展应进一步提升题目的实战推理强度，减少对术语记忆的依赖，增强对以下能力的覆盖：

- 从多条线索中提取关键信息
- 基于场景进行技术归因
- 理解攻击链的前后关系
- 判断攻击者的下一步动作
- 给出合理的调查或响应决策
- 用简洁自然语言说明判断依据

本轮新增两个题型：

1. `scenario_multi_step_reasoning`
2. `short_answer_reasoning`

设计原则：

- 一道题尽量覆盖一个场景、一个技术族或一段小攻击链
- 优先考察推理能力，而不是 ATT&CK 名词背诵
- 尽量复用现有生成、审查、评测框架
- 保持题目结构清晰，避免开放到无法稳定评审

## 2. 方案比较

### 方案 A：仅扩展多阶段推理题

优点：

- 最容易沿用当前选择题框架
- 自动评测稳定
- 贴近实战且工程风险最低

缺点：

- 仍然以选项约束为主
- 无法充分考察模型的解释能力与表达能力

### 方案 B：仅扩展简答题

优点：

- 最贴近真实分析工作
- 能更好考察证据提取、解释与归因能力

缺点：

- 参考答案设计难度高
- 评分更复杂，稳定性风险更高
- 若直接作为主力题型，工程成本偏大

### 方案 C：双轨扩展

内容：

- 以 `scenario_multi_step_reasoning` 作为主力题型
- 以 `short_answer_reasoning` 作为高价值补充题型

优点：

- 同时覆盖结构化推理和自然语言解释
- 能复用现有系统并逐步扩展评分能力
- 风险和收益更加平衡

缺点：

- 实现范围大于单题型扩展
- 需要维护两种不同评分逻辑

推荐采用方案 C。

理由：

- `scenario_multi_step_reasoning` 可以成为下一轮主数据集的主体，保证产能和可评测性
- `short_answer_reasoning` 可以作为增强层，补上真实分析表达能力的考察
- 两者组合最符合“贴近实战推理”的目标

## 3. 题型一：多阶段推理题

### 3.1 题型定义

题型名：

- `scenario_multi_step_reasoning`

定位：

- 共享一个主场景
- 围绕同一场景设置 `2-4` 个连续小问
- 每个小问为单选
- 整题考察的是连续推理，而非孤立判断

### 3.2 能力目标

该题型重点覆盖：

- 技术识别
- 阶段判断
- 下一步动作预测
- 调查优先级判断
- 响应决策判断

### 3.3 题目结构

一题应包含以下部分：

- `title`
- `scenario`
- `background`（可选）
- `target_family`
- `target_techniques`
- `steps`
- `overall_explanation`
- `per_step_explanations`

结构要求：

- 主场景应包含真实感较强的证据元素，例如命令行、日志、进程行为、注册表、网络访问、脚本片段、主机告警摘要等
- 小问应围绕同一主场景展开，不得变成多个独立小题拼接
- 小问之间应形成逻辑链，但不允许强依赖前一问的答案才能理解下一问

### 3.4 小问类型

推荐小问从以下类型中组合：

- `technique_identification`
  根据线索识别最符合的 ATT&CK 技术或子技术
- `stage_inference`
  判断当前行为更接近哪一阶段
- `next_step_prediction`
  判断攻击者下一步最可能采取的行动
- `investigation_priority`
  判断防守方优先调查哪项证据
- `response_decision`
  判断最优先或最合理的响应动作

首版不建议加入过多开放类型，避免生成和评审复杂度失控。

### 3.5 数据 Schema

建议新增题型字段：

- `question_type: "scenario_multi_step_reasoning"`

推荐 JSON 结构如下：

```json
{
  "question_id": "MSR-0001",
  "question_type": "scenario_multi_step_reasoning",
  "title": "Encoded PowerShell Activity on Finance Endpoint",
  "scenario": "A finance workstation launches powershell.exe with an encoded command, downloads content from an external domain, and spawns a child process shortly after the user opens an email attachment.",
  "background": {
    "platform": "Windows",
    "role": "Finance workstation",
    "evidence_sources": ["EDR", "Process Creation Log", "Proxy Log"]
  },
  "target_family": ["T1059", "T1204"],
  "target_techniques": ["T1059.001", "T1204.002"],
  "difficulty": "medium",
  "steps": [
    {
      "step_id": 1,
      "reasoning_focus": "technique_identification",
      "prompt": "根据当前线索，最符合的攻击技术是什么？",
      "options": [
        {"label": "A", "attack_id": "T1059.001", "text": "PowerShell"},
        {"label": "B", "attack_id": "T1218", "text": "System Binary Proxy Execution"},
        {"label": "C", "attack_id": "T1562.001", "text": "Impair Defenses"},
        {"label": "D", "attack_id": "T1041", "text": "Exfiltration Over C2 Channel"}
      ],
      "correct_answer": "A",
      "step_explanation": "编码 PowerShell 命令、远程下载和脚本执行痕迹共同指向 T1059.001。"
    },
    {
      "step_id": 2,
      "reasoning_focus": "next_step_prediction",
      "prompt": "在该场景下，攻击者下一步最可能执行哪类动作？",
      "options": [
        {"label": "A", "text": "建立持久化机制"},
        {"label": "B", "text": "立即进行大规模数据泄露"},
        {"label": "C", "text": "直接破坏备份系统"},
        {"label": "D", "text": "修改企业边界路由策略"}
      ],
      "correct_answer": "A",
      "step_explanation": "脚本执行后的常见后续动作是建立持久化或拉取后续载荷，而非立即进入后期目标。"
    },
    {
      "step_id": 3,
      "reasoning_focus": "investigation_priority",
      "prompt": "防守方此时最优先核查什么？",
      "options": [
        {"label": "A", "text": "该主机的启动项、计划任务和 Run 键变更"},
        {"label": "B", "text": "过去一年的物理门禁记录"},
        {"label": "C", "text": "打印队列历史"},
        {"label": "D", "text": "办公 Wi-Fi 覆盖热力图"}
      ],
      "correct_answer": "A",
      "step_explanation": "若攻击者可能建立持久化，优先核查启动项、计划任务与注册表自启动痕迹。"
    }
  ],
  "overall_explanation": "本题围绕用户执行后触发的脚本执行场景，要求答题者完成技术识别、攻击链下一步预测和调查优先级判断。",
  "references": {
    "attack_ids": ["T1059.001", "T1204.002"]
  }
}
```

### 3.6 生成策略

#### 生成单位

不采用“一技一题”，而采用以下单位：

- 技术族
- 小攻击链
- 场景模板

优先选择更容易构成链路的主题：

- 用户执行 -> 脚本执行 -> 下载执行
- 凭证访问 -> 横向移动
- 持久化 -> 隐蔽/防御规避
- 发现 -> 收集 -> 外传

#### 题量建议

首版建议总量：

- `120-180` 题

说明：

- 每题 `2-4` 个小问
- 总判断点可覆盖 `300-500` 个推理点
- 比 SSC 数量更少，但单题价值更高

#### 生成约束

- 每题必须有唯一主线，不得同时硬塞过多技术
- 每题最多聚焦 `1-2` 个主技术族
- 干扰项优先来自相邻阶段、同类执行方式或相似行为，不得明显离题
- 小问顺序要符合合理攻击链或分析流程

## 4. 题型二：简答题

### 4.1 题型定义

题型名：

- `short_answer_reasoning`

定位：

- 提供一个主场景
- 提出一个简答要求
- 要求答题者使用 `1-4` 句作答
- 重点考察技术归因、证据使用和表达清晰度

### 4.2 能力目标

该题型重点覆盖：

- 关键线索提取
- 技术归因
- 证据解释
- 调查或响应思路表达
- 自然语言分析能力

### 4.3 问法模板

首版建议只开放以下几类，保证可控：

- `technique_judgment`
  该行为最可能对应什么 ATT&CK 技术？请说明依据。
- `evidence_reasoning`
  场景中哪条线索最支持你的判断？为什么？
- `investigation_next_step`
  你接下来最优先验证什么？为什么？
- `response_priority`
  如果你是防守方，此时最优先的处置动作是什么？为什么？
- `risk_summary`
  请简要概括该场景反映的攻击目的或风险。

### 4.4 数据 Schema

建议新增题型字段：

- `question_type: "short_answer_reasoning"`

推荐 JSON 结构如下：

```json
{
  "question_id": "SAR-0001",
  "question_type": "short_answer_reasoning",
  "title": "Suspicious Scheduled Task Creation",
  "scenario": "An endpoint creates a new scheduled task shortly after an unsigned binary is written to a public user directory and executed by cmd.exe.",
  "prompt": "根据以上场景，判断最可能的 ATT&CK 技术，并说明你的依据。",
  "prompt_type": "technique_judgment",
  "target_family": ["T1053"],
  "target_techniques": ["T1053.005"],
  "difficulty": "medium",
  "reference_answer": "该行为最可能对应 Scheduled Task/Job: Scheduled Task。依据是可疑程序执行后立即创建计划任务，这是一种常见的持久化方式。",
  "key_points": [
    "识别出 Scheduled Task 或 T1053.005",
    "指出计划任务创建这一关键证据",
    "说明其与持久化或后续自动执行有关"
  ],
  "scoring_rubric": {
    "technique_correct": 0.5,
    "evidence_used": 0.3,
    "reasoning_clear": 0.2
  },
  "answer_constraints": {
    "max_sentences": 4,
    "preferred_length": "1-3 sentences"
  },
  "references": {
    "attack_ids": ["T1053.005"]
  }
}
```

### 4.5 生成策略

简答题不追求海量，而追求高质量与稳定评分。

生成要求：

- 一个场景只问一个核心问题
- 问题必须有明确指向，不能变成开放作文
- 每题都必须生成：
  - `reference_answer`
  - `key_points`
  - `scoring_rubric`
- 参考答案要短、准、可比对，不写成长篇报告

题量建议：

- `60-100` 题

### 4.6 评分策略

简答题评分采用双层结构：

#### 规则评分

用于保证底线客观性，检查：

- 是否命中正确 ATT&CK ID 或技术名
- 是否提到关键证据点
- 是否命中关键调查或响应词

#### LLM 评分

按照 rubric 评估：

- 技术判断是否正确
- 理由是否使用了场景证据
- 表达是否简洁清晰

最终建议使用加权总分：

- 规则分：`60%`
- LLM 分：`40%`

首版可先输出细分项分数，后续再决定是否压缩成总分。

## 5. 现有系统改造方案

### 5.1 生成层

新增脚本：

- `generate_multi_step_reasoning.py`
- `generate_short_answer_reasoning.py`

复用能力：

- `attack_data_loader.py`
- `openrouter_client.py`
- 现有并发与重试逻辑
- 现有输出 JSONL 流程

配置扩展：

- 在 `config/prompt_templates.yaml` 中新增两个题型模板
- 为多阶段推理题加入 `step blueprints`
- 为简答题加入 `prompt_type` 与 `rubric template`

### 5.2 审查层

在 `review_all_questions.py` 中新增两类规则。

#### 多阶段推理题审查规则

- 主场景与所有小问必须一致
- 每一步正确答案必须与题目目标一致
- `reasoning_focus` 与小问文本必须匹配
- 小问顺序合理，不能出现明显链路反转
- 干扰项必须相近但错误
- `overall_explanation` 与各步解释不能冲突
- ATT&CK ID 必须来自本地 `attack_data.json`

#### 简答题审查规则

- 问题必须存在明确指向
- `reference_answer` 不能过长或过空
- `key_points` 必须可操作、可判定
- `scoring_rubric` 权重总和必须为 `1.0`
- 目标技术与参考答案必须一致
- 不允许出现多个同等合理但 rubric 无法区分的答案

### 5.3 评测层

需要扩展：

- `evaluate_models.py`
- `evaluate_dataset.py`

#### 多阶段推理题评分

- step 级准确率
- 整题全对率
- 不同 `reasoning_focus` 的分类统计

建议新增指标：

- `step_accuracy`
- `question_full_match_rate`
- `focus_accuracy_breakdown`

#### 简答题评分

建议新增字段：

- `rule_score`
- `llm_score`
- `final_score`
- `rubric_breakdown`

## 6. 数据集规划

### 6.1 第一阶段目标

建议第一阶段总目标：

- `scenario_multi_step_reasoning`: `120-180` 题
- `short_answer_reasoning`: `60-100` 题

### 6.2 生产顺序

推荐顺序：

1. 先完成 `scenario_multi_step_reasoning`
2. 用小批次验证生成与 review 稳定性
3. 再落地 `short_answer_reasoning`
4. 最后扩展评测与对比分析

原因：

- 多阶段推理题与现有 SSC 最接近，迁移成本更低
- 简答题依赖评分设计，应在结构化题型稳定后推进

## 7. 风险与控制

### 7.1 多阶段推理题风险

- 风险：多步之间逻辑不连贯
- 控制：生成时固定 `step blueprint`，review 时校验步间关系

- 风险：题目覆盖技术过多导致主线不清
- 控制：限制为 `1-2` 个主技术族

- 风险：后续小问严重依赖前一问正确
- 控制：要求每一步可直接由场景作答

### 7.2 简答题风险

- 风险：问题过于开放，无法稳定评分
- 控制：首版只使用固定问法模板

- 风险：参考答案写成主观分析报告
- 控制：限制答案长度并强制输出关键点

- 风险：LLM 评分漂移
- 控制：先保留规则分为主、LLM 分为辅

## 8. 最终建议

本轮题型扩展建议正式采用以下双轨方案：

1. 主力题型：`scenario_multi_step_reasoning`
2. 补充题型：`short_answer_reasoning`

推荐落地顺序：

1. 先定稿两个题型的 schema
2. 优先实现多阶段推理题的生成、审查和评测
3. 再实现简答题的生成、rubric 和评分
4. 最后统一加入数据集分析与模型对比

该方案能在不破坏当前工程结构的前提下，把题库从“场景化选择题”推进到“连续推理 + 简短分析表达”的阶段。
