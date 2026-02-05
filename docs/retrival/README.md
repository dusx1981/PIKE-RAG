# PIKE-RAG QA 工作流文档

本目录包含 PIKE-RAG 中所有 QA 工作流的详细技术文档。

## 文档列表

### 1. [qa_workflows_guide.md](./qa_workflows_guide.md) - 完整技术文档

详细分析5种 QA 工作流的：
- 核心逻辑与算法
- 执行流程
- 特点与优势
- 解决的 RAG 痛点
- 适用场景
- 配置示例

### 2. [qa_workflows_cheatsheet.md](./qa_workflows_cheatsheet.md) - 速查表

快速参考指南，包含：
- 快速选择指南
- 配置模板
- 核心算法伪代码
- 适用场景矩阵
- 常见问题解答

## 工作流总览

| 工作流 | 核心思想 | 适用场景 |
|--------|----------|----------|
| **QaWorkflow** | 单次检索+生成 | 简单事实问答 |
| **QaSelfAskWorkflow** | 自我提问+子问题解答 | 结构化多跳推理 |
| **QaIterRetgenWorkflow** | 迭代检索生成 | 信息聚合、开放性问题 |
| **QaIRCoTWorkflow** | 交错检索+思维链 | 复杂开放域推理 |
| **QaDecompositionWorkflow** | 原子分解+选择 | 高精度要求、噪声过滤 |

## 快速选择

```
问题类型 → 推荐工作流
─────────────────────────
单跳/简单事实 → QaWorkflow
多跳/结构化  → QaSelfAskWorkflow
开放推理     → QaIRCoTWorkflow
信息聚合     → QaIterRetgenWorkflow
高精度筛选   → QaDecompositionWorkflow
```

## 代码位置

- 工作流实现: `pikerag/workflows/`
- 配置示例: `examples/hotpotqa/configs/`
- 基础类: `pikerag/workflows/common.py`

## 使用示例

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

## 阅读建议

1. **初学者**: 先看速查表了解概览，再阅读完整文档深入理解
2. **选择工作流**: 使用速查表的选择指南快速定位
3. **配置部署**: 参考完整文档中的配置示例章节
4. **自定义开发**: 参考完整文档的高级主题章节

---

**最后更新**: 2025-02-05
