# PIKE-RAG QA 工作流速查表

## 快速选择指南

```
问题类型 → 推荐工作流
─────────────────────────────────────────
单跳/简单事实 → QaWorkflow (基础RAG)
多跳/结构化  → QaSelfAskWorkflow (Self-Ask)
开放推理     → QaIRCoTWorkflow (IRCoT)
信息聚合     → QaIterRetgenWorkflow (Iter-RetGen)
高精度筛选   → QaDecompositionWorkflow (Atomic)
```

---

## 工作流概览

| 工作流 | 类名 | 核心思想 | 平均LLM调用 |
|--------|------|----------|-------------|
| 基础RAG | `QaWorkflow` | 单次检索+生成 | 1 |
| Self-Ask | `QaSelfAskWorkflow` | 自我提问+子问题解答 | 2n+1 |
| Iter-RetGen | `QaIterRetgenWorkflow` | 迭代检索生成 | 5 (固定) |
| IRCoT | `QaIRCoTWorkflow` | 交错检索+CoT | n+1 |
| Atomic | `QaDecompositionWorkflow` | 原子分解+选择 | 3n+1 |

---

## 配置模板

### 1. 基础 RAG

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
```

### 2. Self-Ask

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

### 3. Iter-RetGen

```yaml
workflow:
  module_path: pikerag.workflows.qa_iter_retgen
  class_name: QaIterRetgenWorkflow
  args:
    num_iters: 5
```

### 4. IRCoT

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

### 5. Atomic Decomposition

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
  class_name: ChunkAtomRetriever  # 必须使用
  args:
    retrieve_k: 8
    atom_retrieve_k: 4
```

---

## 核心算法伪代码

### 基础 RAG
```python
def answer(qa):
    chunks = retrieve(qa.question)
    answer = llm(qa.question, chunks)
    return answer
```

### Self-Ask
```python
def answer(qa):
    followups = []
    while True:
        final, followup = llm.ask_or_answer(qa.question, followups)
        if final:
            return final
        answer = answer_followup(followup)
        followups.append((followup, answer))
```

### Iter-RetGen
```python
def answer(qa):
    answers, rationales = [], []
    for i in range(5):
        query = f"{rationales[-1]} Answer: {answers[-1]}" if i > 0 else qa.question
        chunks = retrieve(query)
        answer, rationale = llm(qa.question, chunks)
        answers.append(answer)
        rationales.append(rationale)
    return answers[-1]
```

### IRCoT
```python
def answer(qa):
    rationales, references = [], []
    for round in range(5):
        query = rationales[-1] if rationales else qa.question
        chunks = retrieve(query)
        references.extend(chunks)
        result = llm(qa.question, references, rationales)
        if result.has_answer:
            return result.answer
        rationales.append(result.next_rationale)
    return llm.force_answer(qa.question, references, rationales)
```

### Atomic Decomposition
```python
def answer(qa):
    chosen_infos = []
    while len(chosen_infos) < 5:
        proposals = llm.propose(qa.question, chosen_infos)
        candidates = retrieve_atoms(proposals, qa.question)
        if not candidates:
            break
        selected, info = llm.select(qa.question, candidates, chosen_infos)
        if not selected:
            break
        chosen_infos.append(info)
    return llm.answer_with_infos(qa.question, chosen_infos)
```

---

## 适用场景矩阵

| 场景 | 基础RAG | Self-Ask | Iter-RetGen | IRCoT | Atomic |
|------|:-------:|:--------:|:-----------:|:-----:|:------:|
| 单跳问答 | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐ |
| 多跳推理 | ⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐⭐ |
| 复杂推理 | ⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐⭐ |
| 信息聚合 | ⭐⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ |
| 噪声过滤 | ⭐⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐⭐ |
| 实时响应 | ⭐⭐⭐ | ⭐⭐ | ⭐ | ⭐⭐ | ⭐ |
| 成本控制 | ⭐⭐⭐ | ⭐⭐ | ⭐ | ⭐⭐ | ⭐ |

---

## RAG 痛点与解决方案

| 痛点 | 最佳工作流 | 解决方案 |
|------|-----------|----------|
| 多跳推理 | Self-Ask | 分解为子问题逐一解答 |
| 信息分散 | Iter-RetGen | 迭代检索聚合信息 |
| 复杂推理 | IRCoT | 交错检索与推理 |
| 信息过载 | Atomic | 精细筛选原子信息 |
| 初始检索偏差 | Iter-RetGen | 用生成内容扩展查询 |
| 噪声干扰 | Atomic | 多轮选择过滤噪声 |
| 中间信息缺失 | IRCoT | 动态检索当前所需 |

---

## 执行流程对比

### 基础 RAG
```
Q → R(Q) → LLM → A
1步完成
```

### Self-Ask
```
Q → LLM?(子问题?) → R(子问题) → LLM → 子答案
                    ↓ (循环n次)
Q → LLM → 最终答案
2n+1步
```

### Iter-RetGen
```
R1: Q → R(Q) → LLM → A1 + R1
R2: A1,R1 → R(A1,R1) → LLM → A2 + R2
...
R5: A4,R4 → R(...) → LLM → A5 + R5
5步固定
```

### IRCoT
```
R1: Q → R(Q) → LLM → 推理1/答案
R2: 推理1 → R(推理1) → LLM → 推理2/答案
...
n+1步(动态)
```

### Atomic
```
Loop:
  LLM → 子问题建议
  R(子问题) → 候选原子
  LLM → 选择最佳原子
3n+1步
```

---

## 常见问题

### Q: 如何选择 retrieve_k？

A:
- 基础RAG: 16 (平衡召回与噪声)
- IRCoT: 4-8 (多轮累积，每轮较少)
- Atomic: 8+atom 4 (双检索器)
- 文档长/噪声大: 适当降低
- 文档短/信息密: 适当提高

### Q: Self-Ask 和 IRCoT 的区别？

A:
- Self-Ask: 显式子问题，边界清晰
- IRCoT: 隐式推理，更灵活
- 结构化多跳 → Self-Ask
- 开放复杂推理 → IRCoT

### Q: Atomic 需要特殊数据？

A:
- 是，需要预生成原子问题
- 使用 `ChunkAtomRetriever`
- 需要 `_with_atom_questions.jsonl` 数据文件

### Q: 如何降低 LLM 调用成本？

A:
1. 简单问题用基础RAG
2. 限制 Self-Ask/Atomic 的最大轮数
3. 减少 Iter-RetGen 迭代次数
4. 启用 LLM 缓存

### Q: 多轮测试如何配置？

A:
```yaml
test_rounds: 3  # 报告平均/最小/最大指标
```

---

## 代码片段

### 运行工作流

```bash
# 基础RAG
python examples/qa.py examples/hotpotqa/configs/qa_chunk.yml

# Self-Ask
python examples/qa.py examples/hotpotqa/configs/self_ask.yml

# Iter-RetGen
python examples/qa.py examples/hotpotqa/configs/iter_retgen.yml

# IRCoT
python examples/qa.py examples/hotpotqa/configs/ircot.yml

# Atomic Decomposition
python examples/qa.py examples/hotpotqa/configs/atomic_decompose.yml
```

### 自定义工作流

```python
from pikerag.workflows.qa import QaWorkflow

class MyWorkflow(QaWorkflow):
    def answer(self, qa, question_idx):
        # 自定义逻辑
        chunks = self._retriever.retrieve_contents(qa)
        # ...处理...
        return {"answer": answer}
```

---

## 参考文档

- [完整技术文档](./qa_workflows_guide.md)
- [examples/hotpotqa/configs/](../../examples/hotpotqa/configs/)
- [pikerag/workflows/](../../pikerag/workflows/)
