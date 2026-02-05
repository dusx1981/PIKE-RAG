# PIKE-RAG QA 工作流技术文档

## 目录

1. [概述](#1-概述)
2. [基础 RAG (QaWorkflow)](#2-基础-rag-qaworkflow)
3. [Self-Ask (QaSelfAskWorkflow)](#3-self-ask-qaselfaskworkflow)
4. [Iter-RetGen (QaIterRetgenWorkflow)](#4-iter-retgen-qaiterretgenworkflow)
5. [IRCoT (QaIRCoTWorkflow)](#5-ircot-qaircotworkflow)
6. [Atomic Decomposition (QaDecompositionWorkflow)](#6-atomic-decomposition-qadecompositionworkflow)
7. [工作流对比与选择指南](#7-工作流对比与选择指南)
8. [配置示例汇总](#8-配置示例汇总)

---

## 1. 概述

PIKE-RAG 提供了5种 QA 工作流，针对不同的 RAG 场景和痛点进行了优化。这些工作流遵循统一的设计模式：

```
┌─────────────────────────────────────────────────────────────────┐
│                     统一工作流架构                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐      │
│  │   数据加载    │ →  │   工作流处理  │ →  │   结果评估    │      │
│  └──────────────┘    └──────────────┘    └──────────────┘      │
│                             ↓                                   │
│                    ┌──────────────┐                            │
│                    │   answer()   │  ← 各工作流核心实现        │
│                    └──────────────┘                            │
│                             ↓                                   │
│         ┌──────────────────┼──────────────────┐                │
│         ↓                  ↓                  ↓                │
│    ┌─────────┐      ┌─────────┐      ┌─────────┐              │
│    │ Retriever│      │  LLM    │      │ Evaluator│              │
│    └─────────┘      └─────────┘      └─────────┘              │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 工作流分类

| 工作流 | 核心思想 | 迭代次数 | 主要解决的问题 |
|--------|----------|----------|----------------|
| **QaWorkflow** | 单次检索+生成 | 1 | 基础问答 |
| **QaSelfAskWorkflow** | 自我提问+子问题解答 | 动态 | 多跳推理 |
| **QaIterRetgenWorkflow** | 迭代式检索生成 | 固定(默认5) | 信息补全 |
| **QaIRCoTWorkflow** | 交错检索+思维链 | 动态(最大5) | 复杂推理 |
| **QaDecompositionWorkflow** | 原子化分解+选择 | 动态(最大5) | 精细信息筛选 |

---

## 2. 基础 RAG (QaWorkflow)

### 2.1 核心逻辑

基础 RAG 工作流实现最经典的检索-生成范式：

```python
def answer(self, qa: BaseQaData, question_idx: int) -> dict:
    # Step 1: 检索相关文档片段
    reference_chunks = self._retriever.retrieve_contents(qa, retrieve_id=f"Q{question_idx:03}")
    
    # Step 2: 构建提示词
    messages = self._qa_protocol.process_input(content=qa.question, references=reference_chunks, **qa.as_dict())
    
    # Step 3: LLM生成答案
    response = self._client.generate_content_with_messages(messages, **self.llm_config)
    output_dict = self._qa_protocol.parse_output(response, **qa.as_dict())
    
    # Step 4: 返回结果
    output_dict["reference_chunks"] = reference_chunks
    return output_dict
```

### 2.2 执行流程

```
Question → Retrieve(k=16) → LLM(prompt+references) → Answer
```

### 2.3 特点

- **简单直接**: 单次检索，单次生成
- **效率高**: 最少的 LLM 调用次数
- **易于理解**: 符合直觉的问答流程
- **可并行**: 支持多线程并行处理

### 2.4 解决的 RAG 痛点

| 痛点 | 解决方案 |
|------|----------|
| 基础事实性问题 | 直接检索相关文档生成答案 |
| 简单单跳问题 | 单次检索即可获得足够信息 |
| 快速原型验证 | 最简实现，快速验证数据质量 |

### 2.5 适用场景

- ✅ **简单问答**: 事实性、单跳问题
- ✅ **快速验证**: 数据集质量验证、基线测试
- ✅ **资源受限**: LLM API 调用次数受限的场景
- ❌ **多跳推理**: 需要连接多个信息点的问题
- ❌ **复杂推理**: 需要逐步推导的问题

### 2.6 配置示例

```yaml
workflow:
  module_path: pikerag.workflows.qa
  class_name: QaWorkflow

retriever:
  module_path: pikerag.knowledge_retrievers
  class_name: QaChunkRetriever
  args:
    retrieve_k: 16
    retrieve_score_threshold: 0.2
```

---

## 3. Self-Ask (QaSelfAskWorkflow)

### 3.1 核心逻辑

Self-Ask 工作流模拟人类解决问题的思维方式：将复杂问题分解为一系列子问题，逐一解答后再得出最终答案。

```python
def answer(self, qa: BaseQaData, question_idx: int) -> Dict:
    followup_pairs = []  # (子问题, 子答案) 列表
    
    # 循环：不断提问直到得到最终答案
    while final_answer is None and followup is not None:
        # 1. LLM 决定是否需要继续提问
        final_answer, followup, messages, response = self._move_forward(
            qa.question, followup_pairs, ask_followup=True, ask_final=False
        )
        
        if followup is not None:
            # 2. 检索并解答子问题
            intermediate_answer, references = self._answer_followup_question(followup, ...)
            followup_pairs.append((followup, intermediate_answer))
    
    # 3. 基于所有子问题答案生成最终答案
    if final_answer is None:
        final_answer, _, messages, response = self._move_forward(
            qa.question, followup_pairs, ask_followup=False, ask_final=True
        )
    
    return {"answer": final_answer, "follow_ups": followup_infos}
```

### 3.2 执行流程

```
Question 
    ↓
┌─────────────────────────────────────────────┐
│ 循环：                                       │
│   1. LLM: "需要问子问题吗？如果要，是什么？"  │
│   ↓                                          │
│   2. 如果需要：                              │
│      - 检索子问题相关文档                    │
│      - LLM 回答子问题                        │
│      - 记录 (子问题, 子答案)                 │
│   ↓                                          │
│   3. 直到 LLM 认为可以给出最终答案           │
└─────────────────────────────────────────────┘
    ↓
Final Answer
```

### 3.3 特点

- **动态分解**: LLM 自主决定需要哪些子问题
- **增量推理**: 逐步积累中间结果
- **透明可追溯**: 所有子问题及答案都保留
- **自适应**: 根据问题复杂度自动调整迭代次数

### 3.4 解决的 RAG 痛点

| 痛点 | 解决方案 |
|------|----------|
| 多跳问题 | 将多跳分解为多个单跳子问题 |
| 隐含关系 | 通过子问题显式建立实体关系 |
| 复杂条件 | 逐步筛选满足所有条件的信息 |
| 推理链缺失 | 自动生成并保留完整推理链 |

### 3.5 适用场景

- ✅ **多跳问答**: "A的妻子是谁的姐妹？"
- ✅ **隐含关系推理**: "X和Y的共同属性是什么？"
- ✅ **条件筛选**: "满足条件A且条件B的人物是谁？"
- ✅ **解释性要求高**: 需要展示推理过程的场景
- ❌ **简单事实**: 单跳问题会增加不必要的开销
- ❌ **实时性要求高**: 多次 LLM 调用增加延迟

### 3.6 配置示例

```yaml
workflow:
  module_path: pikerag.workflows.qa_self_ask
  class_name: QaSelfAskWorkflow

self_ask_protocol:
  module_path: pikerag.prompts.self_ask
  protocol_name: self_ask_protocol

followup_qa_protocol:
  module_path: pikerag.prompts.qa
  protocol_name: generation_qa_with_reference_protocol
```

### 3.7 提示词策略

Self-Ask 需要两个提示词协议：
1. **self_ask_protocol**: 引导 LLM 决定是否需要继续提问或给出最终答案
2. **followup_qa_protocol**: 指导 LLM 基于检索文档回答子问题

---

## 4. Iter-RetGen (QaIterRetgenWorkflow)

### 4.1 核心逻辑

Iter-RetGen 工作流通过交替执行检索和生成，利用上一轮生成的答案和推理来指导下一次检索。

```python
def answer(self, qa: BaseQaData, question_idx: int) -> dict:
    # 第一轮：基础检索生成
    output_dict = self.answer(qa, question_idx)  # 调用父类方法
    answers.append(output_dict["answer"])
    rationales.append(output_dict["rationale"])
    
    # 后续轮次：基于前一轮结果迭代
    for iter in range(1, num_iterations):
        # 构建查询：前一轮的推理 + 答案
        query = f"{rationales[-1]} So the final answer is {answers[-1]}"
        
        # 基于新查询检索
        chunks = self._retriever.retrieve_contents_by_query(query, ...)
        
        # 重新生成答案
        output_dict = self._iter_answer(qa, question_idx, answers, rationales)
        
        answers.append(output_dict["answer"])
        rationales.append(output_dict["rationale"])
```

### 4.2 执行流程

```
Iteration 1:
  Question → Retrieve(Question) → LLM → Answer1 + Rationale1

Iteration 2:
  Query = "Rationale1 So the final answer is Answer1"
  Query → Retrieve(Query) → LLM → Answer2 + Rationale2

Iteration 3:
  Query = "Rationale2 So the final answer is Answer2"
  Query → Retrieve(Query) → LLM → Answer3 + Rationale3

... (默认5轮)

Final: Answer5
```

### 4.3 特点

- **迭代优化**: 每轮基于前一轮结果改进
- **信息累积**: 逐步获取更全面的信息
- **自我纠错**: 后一轮可能修正前一轮的错误
- **多版本输出**: 保留每轮结果供分析

### 4.4 解决的 RAG 痛点

| 痛点 | 解决方案 |
|------|----------|
| 初始检索不完整 | 利用生成内容发现遗漏信息 |
| 信息分散 | 多轮检索聚合分散在不同文档中的信息 |
| 答案不一致 | 通过迭代逐步收敛到正确答案 |
| 首次检索偏差 | 用生成内容扩展查询，减少偏差 |

### 4.5 适用场景

- ✅ **信息分散**: 答案需要整合多个来源
- ✅ **开放性问题**: "描述X的主要成就"
- ✅ **总结性问题**: "总结Y的优缺点"
- ✅ **渐进式探索**: 需要从粗到细的信息获取
- ❌ **明确定义的问题**: 简单查找问题浪费计算资源
- ❌ **成本敏感**: 多次迭代增加 API 调用成本

### 4.6 配置示例

```yaml
workflow:
  module_path: pikerag.workflows.qa_iter_retgen
  class_name: QaIterRetgenWorkflow
  args:
    num_iters: 5  # 迭代轮数

retriever:
  class_name: QaChunkRetriever
  args:
    retrieve_k: 16
```

### 4.7 评估特性

Iter-RetGen 的特殊之处在于它为每轮迭代都创建独立的 evaluator：

```python
self._evaluator_list = [
    Evaluator(name=f"Iter-{i + 1}", ...)
    for i in range(self._num_iteration)
]
```

这允许分析答案随迭代的变化趋势。

---

## 5. IRCoT (QaIRCoTWorkflow)

### 5.1 核心逻辑

IRCoT (Interleaved Retrieval-CoT) 将检索与思维链(CoT)推理交错执行，每一步推理后根据新产生的信息决定是否继续检索。

```python
def answer(self, qa: BaseQaData, question_idx: int) -> Dict:
    rationales = []
    references = []
    
    for round in range(max_num_rounds):
        # 1. 基于最新推理进行检索
        query = rationales[-1] if rationales else qa.question
        chunks = self._retriever.retrieve_contents_by_query(query, ...)
        references.extend(chunks)
        
        # 2. LLM 生成下一步推理或答案
        messages = self._ircot_protocol.process_input(
            qa.question, rationales=rationales, references=references
        )
        response = self._client.generate_content_with_messages(messages, ...)
        output_dict = self._ircot_protocol.parse_output(response)
        
        # 3. 判断是否可以给出答案
        if output_dict["answer"] is not None:
            return output_dict["answer"]
        elif output_dict["next_rationale"] is not None:
            rationales.append(output_dict["next_rationale"])
        else:
            break
    
    # 4. 强制生成最终答案
    messages = self._ircot_protocol.process_input(
        qa.question, rationales=rationales, references=references, is_limit=True
    )
    ...
```

### 5.2 执行流程

```
Round 1:
  Question → Retrieve(Question) → LLM(生成Rationale1或Answer)

Round 2:
  Rationale1 → Retrieve(Rationale1) → LLM(生成Rationale2或Answer)

Round 3:
  Rationale2 → Retrieve(Rationale2) → LLM(生成Rationale3或Answer)

... 直到 LLM 给出答案或达到最大轮数

Final: 强制生成答案
```

### 5.3 特点

- **交错执行**: 检索和推理紧密耦合
- **动态控制**: LLM 自主决定何时停止推理
- **增量检索**: 每轮基于最新推理检索新信息
- **推理链完整**: 保留完整推理过程

### 5.4 解决的 RAG 痛点

| 痛点 | 解决方案 |
|------|----------|
| 复杂多步推理 | 逐步推导，每步基于最新信息 |
| 中间信息缺失 | 动态检索当前推理所需信息 |
| 静态检索局限 | 根据推理进展动态调整检索方向 |
| 推理不透明 | 生成完整推理链 |

### 5.5 与 Self-Ask 的区别

| 特性 | Self-Ask | IRCoT |
|------|----------|-------|
| 问题分解 | 显式生成子问题 | 隐式包含在推理中 |
| 检索触发 | 每个子问题检索 | 每步推理后检索 |
| 答案生成 | 所有子问题后统一生成 | 每步都可能生成 |
| 可控性 | 子问题边界清晰 | 更灵活的推理过程 |
| 适用问题 | 结构化的多跳 | 开放式复杂推理 |

### 5.6 适用场景

- ✅ **复杂数学/逻辑推理**: 需要多步推导
- ✅ **开放域推理**: 无法预定义子问题类型
- ✅ **探索性问题**: "为什么X会导致Y？"
- ✅ **因果推理**: 需要追踪因果关系链
- ❌ **结构化多跳**: Self-Ask 更可控
- ❌ **事实查找**: 基础 RAG 更高效

### 5.7 配置示例

```yaml
workflow:
  module_path: pikerag.workflows.qa_ircot
  class_name: QaIRCoTWorkflow
  args:
    max_num_rounds: 5

retriever:
  class_name: QaChunkRetriever
  args:
    retrieve_k: 4  # 每轮检索较少文档
```

### 5.8 提示词策略

IRCoT 协议需要特殊设计，使 LLM 能够：
1. 基于已有推理和参考生成下一步推理
2. 判断是否有足够信息给出答案
3. 在达到限制时强制给出答案

---

## 6. Atomic Decomposition (QaDecompositionWorkflow)

### 6.1 核心逻辑

原子分解工作流将问题分解为原子级别的子问题，并通过精细的选择机制筛选最有用的信息。

```python
def answer(self, qa: BaseQaData, question_idx: int) -> Dict:
    chosen_atom_infos = []  # 已选中的原子信息
    
    while len(chosen_atom_infos) < max_num_question:
        # Step 1: 提出分解建议
        decompose, thinking, proposals = self._propose_question_decomposition(
            qa.question, chosen_atom_infos
        )
        
        if not decompose:
            break
        
        # Step 2: 检索原子信息候选
        atom_info_candidates = self._retrieve_atom_info_candidates(
            proposals, qa.question, chosen_atom_infos
        )
        
        if not atom_info_candidates:
            break
        
        # Step 3: 选择最有用的原子信息
        selected, thinking, chosen_info = self._select_atom_question(
            qa.question, atom_info_candidates, chosen_atom_infos
        )
        
        if selected:
            chosen_atom_infos.append(chosen_info)
        else:
            break
    
    # 基于选中的原子信息回答问题
    output = self._answer_original_question(qa.question, chosen_atom_infos)
    return output
```

### 6.2 执行流程

```
Loop (max 5 iterations):
  ┌─────────────────────────────────────────────────────────┐
  │ Step 1: Proposal                                        │
  │   LLM: 基于已有信息，提出可能帮助回答的子问题列表         │
  └─────────────────────────────────────────────────────────┘
                             ↓
  ┌─────────────────────────────────────────────────────────┐
  │ Step 2: Retrieval                                       │
  │   - 使用子问题检索原子信息                               │
  │   - 备用：使用原问题检索                                 │
  │   - 备用：直接检索文档块                                 │
  │   - 过滤：排除已选同文档块的候选                         │
  └─────────────────────────────────────────────────────────┘
                             ↓
  ┌─────────────────────────────────────────────────────────┐
  │ Step 3: Selection                                       │
  │   LLM: 从候选中选择最有用的原子信息                      │
  │   (有备用选择协议)                                       │
  └─────────────────────────────────────────────────────────┘
                             ↓
                    选中则加入 chosen_atom_infos
                             ↓
                    未选中或达到上限则退出循环
                             ↓
Final: 基于所有选中信息生成答案
```

### 6.3 特点

- **三级备用检索**: 子问题 → 原问题 → 直接检索块
- **精细过滤**: 避免重复选择同文档块
- **双选择协议**: 主选择协议 + 备用选择协议
- **信息原子化**: 基于预生成的原子问题检索

### 6.4 解决的 RAG 痛点

| 痛点 | 解决方案 |
|------|----------|
| 信息过载 | 通过选择机制筛选最有用信息 |
| 噪声干扰 | 多轮精选减少无关信息 |
| 粒度不匹配 | 原子级检索更精确 |
| 重复信息 | 同块过滤避免重复 |
| 检索失败 | 三级备用策略提高召回 |

### 6.5 依赖要求

原子分解工作流需要特殊的检索器和数据：

```yaml
retriever:
  class_name: ChunkAtomRetriever  # 必须使用此检索器
  args:
    retrieve_k: 8
    atom_retrieve_k: 4

# 需要预生成的原子问题数据
id_document_loading:
  func_name: load_ids_and_chunks
  args:
    filepath: data/..._with_atom_questions.jsonl
    atom_tag: atom_questions

id_atom_loading:
  func_name: load_ids_and_atoms
  args:
    filepath: data/..._with_atom_questions.jsonl
    atom_tag: atom_questions
```

### 6.6 适用场景

- ✅ **信息密集型问题**: 需要从大量文档中精选
- ✅ **高质量要求**: 对答案准确性要求极高
- ✅ **噪声数据**: 检索结果包含大量无关信息
- ✅ **长文档处理**: 需要细粒度检索
- ❌ **快速响应**: 多轮交互增加延迟
- ❌ **简单问题**: 过度工程化

### 6.7 配置示例

```yaml
workflow:
  module_path: pikerag.workflows.qa_decompose
  class_name: QaDecompositionWorkflow
  args:
    max_num_question: 5
    question_similarity_threshold: 0.999

decompose_proposal_protocol:
  module_path: pikerag.prompts.decomposition
  protocol_name: question_decompose_protocol

selection_protocol:
  module_path: pikerag.prompts.decomposition
  protocol_name: atom_question_selection_protocol

backup_selection_protocol:
  module_path: pikerag.prompts.decomposition
  protocol_name: chunk_selection_protocol

original_question_answering_protocol:
  module_path: pikerag.prompts.decomposition
  protocol_name: final_qa_protocol
```

### 6.8 四个提示词协议

1. **decompose_proposal_protocol**: 引导 LLM 提出子问题分解建议
2. **selection_protocol**: 从候选中选择最有用的原子信息
3. **backup_selection_protocol**: 备用选择策略
4. **original_question_answering_protocol**: 基于选中信息生成最终答案

---

## 7. 工作流对比与选择指南

### 7.1 能力对比矩阵

| 能力 | QaWorkflow | Self-Ask | Iter-RetGen | IRCoT | Decomposition |
|------|:----------:|:--------:|:-----------:|:-----:|:-------------:|
| **单跳问答** | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐ |
| **多跳推理** | ⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐⭐ |
| **复杂推理** | ⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐⭐ |
| **信息聚合** | ⭐⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ |
| **噪声过滤** | ⭐⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐⭐ |
| **实时性** | ⭐⭐⭐ | ⭐⭐ | ⭐ | ⭐⭐ | ⭐ |
| **成本控制** | ⭐⭐⭐ | ⭐⭐ | ⭐ | ⭐⭐ | ⭐ |
| **可解释性** | ⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ |

*⭐越多表示该能力越强*

### 7.2 问题类型匹配

```
问题特征分析:
├─ 单跳/简单事实
│  └─→ QaWorkflow (基础RAG)
│
├─ 多跳/结构化推理
│  ├─ 子问题边界清晰
│  │  └─→ QaSelfAskWorkflow (Self-Ask)
│  └─ 子问题边界模糊
│     └─→ QaIRCoTWorkflow (IRCoT)
│
├─ 开放域/探索性
│  ├─ 需要逐步探索
│  │  └─→ QaIRCoTWorkflow (IRCoT)
│  └─ 需要信息聚合
│     └─→ QaIterRetgenWorkflow (Iter-RetGen)
│
└─ 信息密集型/高精度
   └─→ QaDecompositionWorkflow (Atomic)
```

### 7.3 选择决策树

```
开始
│
├─ 问题是否简单明确？(单跳)
│  ├─ 是 → 使用 QaWorkflow
│  └─ 否 → 继续
│
├─ 是否需要极高精度/噪声过滤？
│  ├─ 是 → 使用 QaDecompositionWorkflow
│  └─ 否 → 继续
│
├─ 问题是否可以分解为明确子问题？
│  ├─ 是 → 使用 QaSelfAskWorkflow
│  └─ 否 → 继续
│
├─ 是否需要逐步探索/推理？
│  ├─ 是 → 使用 QaIRCoTWorkflow
│  └─ 否 → 使用 QaIterRetgenWorkflow
```

### 7.4 性能与成本权衡

| 工作流 | 平均 LLM 调用/问题 | 平均检索次数/问题 | 适用规模 |
|--------|:------------------:|:-----------------:|:--------:|
| QaWorkflow | 1 | 1 | 大规模 |
| Self-Ask | 2n+1 (n=子问题数) | n | 中等规模 |
| Iter-RetGen | 5 | 5 | 小规模 |
| IRCoT | n+1 (n=推理步数) | n | 中等规模 |
| Decomposition | 3n+1 (n=选中数) | 3n | 小规模 |

---

## 8. 配置示例汇总

### 8.1 基础 RAG

```yaml
workflow:
  module_path: pikerag.workflows.qa
  class_name: QaWorkflow

qa_protocol:
  module_path: pikerag.prompts.qa
  attr_name: generation_qa_with_reference_protocol

retriever:
  class_name: QaChunkRetriever
  args:
    retrieve_k: 16
    retrieve_score_threshold: 0.2
```

### 8.2 Self-Ask

```yaml
workflow:
  module_path: pikerag.workflows.qa_self_ask
  class_name: QaSelfAskWorkflow

self_ask_protocol:
  module_path: pikerag.prompts.self_ask
  protocol_name: self_ask_protocol

followup_qa_protocol:
  module_path: pikerag.prompts.qa
  protocol_name: generation_qa_with_reference_protocol
```

### 8.3 Iter-RetGen

```yaml
workflow:
  module_path: pikerag.workflows.qa_iter_retgen
  class_name: QaIterRetgenWorkflow
  args:
    num_iters: 5

qa_protocol:
  module_path: pikerag.prompts.qa
  attr_name: generation_qa_with_reference_protocol
```

### 8.4 IRCoT

```yaml
workflow:
  module_path: pikerag.workflows.qa_ircot
  class_name: QaIRCoTWorkflow
  args:
    max_num_rounds: 5

ircot_protocol:
  module_path: pikerag.prompts.ircot
  protocol_name: ircot_qa_protocol
```

### 8.5 Atomic Decomposition

```yaml
workflow:
  module_path: pikerag.workflows.qa_decompose
  class_name: QaDecompositionWorkflow
  args:
    max_num_question: 5
    question_similarity_threshold: 0.999

decompose_proposal_protocol:
  module_path: pikerag.prompts.decomposition
  protocol_name: question_decompose_protocol

selection_protocol:
  module_path: pikerag.prompts.decomposition
  protocol_name: atom_question_selection_protocol

backup_selection_protocol:
  module_path: pikerag.prompts.decomposition
  protocol_name: chunk_selection_protocol

original_question_answering_protocol:
  module_path: pikerag.prompts.decomposition
  protocol_name: final_qa_protocol

retriever:
  class_name: ChunkAtomRetriever
  args:
    retrieve_k: 8
    atom_retrieve_k: 4
```

---

## 9. 高级主题

### 9.1 自定义工作流

要创建自定义 QA 工作流，继承 `QaWorkflow` 并重写 `answer` 方法：

```python
from pikerag.workflows.qa import QaWorkflow
from pikerag.workflows.common import BaseQaData

class CustomQaWorkflow(QaWorkflow):
    def _init_protocol(self) -> None:
        super()._init_protocol()
        # 初始化自定义协议
        self._custom_protocol = load_protocol(...)
    
    def answer(self, qa: BaseQaData, question_idx: int) -> dict:
        # 自定义问答逻辑
        # 1. 检索
        # 2. 处理
        # 3. 生成
        return {"answer": answer, "metadata": {...}}
```

### 9.2 并行执行

所有工作流都支持并行执行，通过配置控制：

```yaml
workflow:
  args:
    num_parallel: 4  # 并行线程数
```

### 9.3 多轮测试

支持多轮测试以评估稳定性：

```yaml
test_rounds: 3  # 测试3轮，报告平均/最小/最大指标
```

---

## 10. 总结

PIKE-RAG 的 QA 工作流体系覆盖了从简单到复杂的各种 RAG 场景：

- **QaWorkflow**: 简单直接，适合快速验证和基础问答
- **QaSelfAskWorkflow**: 结构化分解，适合清晰的多跳问题
- **QaIterRetgenWorkflow**: 迭代优化，适合信息聚合
- **QaIRCoTWorkflow**: 交错推理，适合复杂开放域推理
- **QaDecompositionWorkflow**: 精细筛选，适合高精度要求

选择合适的工作流需综合考虑：问题复杂度、精度要求、延迟容忍度和成本预算。
