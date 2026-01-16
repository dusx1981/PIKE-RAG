# QaWorkflow 检索流程详解

## 整体流程图

```python
用户问题 → 检索器 → 相关知识 → 构建Prompt → LLM → 解析答案 → 评估输出
    ↓
  配置管理        日志记录        并行处理        结果存储
```

## 核心检索流程示例

### 场景：医疗问答系统

```yaml
# 配置示例
experiment_name: "医疗知识问答测试"
test_rounds: 3
num_parallel: 4

retriever:
  module_path: "pikerag.knowledge_retrievers"
  class_name: "ChunkAtomRetriever"  # 或 QaChunkRetriever
  args:
    retrieve_k: 5
    atom_retrieve_k: 10

llm_client:
  module_path: "pikerag.llm_client"
  class_name: "OpenAIClient"
  llm_config:
    model: "gpt-4"
    temperature: 0.1
```

### 1. **初始化阶段**

```python
workflow = QaWorkflow(yaml_config)

# 内部执行顺序：
# 1. _init_logger() - 创建日志系统
# 2. _load_testing_suite() - 加载测试数据集
# 3. _init_agent() - 初始化核心组件
#   3.1 _init_protocol() - 加载QA通信协议
#   3.2 _init_retriever() - 初始化检索器
#   3.3 _init_llm_client() - 初始化LLM客户端
# 4. _init_evaluator() - 初始化评估器
# 5. _init_qas_metrics_table() - 初始化结果记录表
```

### 2. **单线程执行流程**

```python
# 对于每个测试轮次
for round_idx in range(3):  # test_rounds=3
    # 更新LLM缓存位置
    workflow._update_llm_cache(round_idx)
    
    # 对于每个测试问题
    for qa in testing_suite:
        # answer() 方法的核心流程
        def answer(qa, question_idx):
            # 步骤1: 检索相关内容
            reference_chunks = retriever.retrieve_contents(
                qa, 
                retrieve_id=f"Q{question_idx:03}"
            )
            
            # 步骤2: 构建Prompt消息
            messages = protocol.process_input(
                content=qa.question,
                references=reference_chunks,
                **qa.as_dict()
            )
            
            # 步骤3: 调用LLM生成回答
            response = client.generate_content_with_messages(messages)
            
            # 步骤4: 解析LLM输出
            output_dict = protocol.parse_output(response, **qa.as_dict())
            
            return output_dict
        
        # 更新评估指标
        evaluator.update_round_metrics(qa)
        
        # 记录结果
        save_to_jsonl(qa)
```

### 3. **多线程并行执行流程**

```python
# 当 num_parallel > 1 时
with ThreadPoolExecutor(max_workers=4) as executor:
    # 步骤1: 并行回答问题
    future_to_index = {
        executor.submit(answer, qa, q_idx): q_idx
        for q_idx, qa in enumerate(testing_suite)
    }
    
    # 步骤2: 收集所有回答
    qas_with_answer = [None] * len(testing_suite)
    for future in as_completed(future_to_index):
        q_idx = future_to_index[future]
        qas_with_answer[q_idx] = process_answer(future.result())
    
    # 步骤3: 并行评估结果
    evaluation_future_to_index = {
        executor.submit(evaluator.update_round_metrics, qa): q_idx
        for q_idx, qa in enumerate(qas_with_answer)
    }
```

## 具体应用示例

### 示例1：医疗诊断问答

```python
# 测试问题
qa = GenerationQaData(
    question="糖尿病患者可以使用阿司匹林吗？",
    answer_labels=["可以使用，但需注意出血风险", ...]
)

# 工作流程执行
workflow.run()

# 具体流程：
# 1. 检索阶段
#   如果是ChunkAtomRetriever：
#     - 从原子存储中检索"糖尿病"、"阿司匹林"、"禁忌症"等原子
#     - 从文档存储中检索糖尿病治疗指南相关章节
#   如果是QaChunkRetriever：
#     - 直接检索包含"糖尿病"和"阿司匹林"的文档块

# 2. Prompt构建（示例）
"""
你是一个医疗专家，请基于以下参考资料回答问题。

参考资料：
1. 阿司匹林使用指南：糖尿病患者使用阿司匹林需评估出血风险...
2. 糖尿病治疗规范：对无禁忌症的糖尿病患者，建议使用小剂量阿司匹林...
3. 药物相互作用：阿司匹林与某些降糖药物可能存在相互作用...

问题：糖尿病患者可以使用阿司匹林吗？

请用中文回答，并解释原因。
"""

# 3. LLM生成回答
response = "糖尿病患者可以使用阿司匹林，但需要医生评估出血风险..."

# 4. 解析和评估
output_dict = {
    "answer": "可以使用，但需注意出血风险",
    "response": response,
    "reference_chunks": [...],
    "confidence": 0.85
}

# 5. 自动评估
# 使用ExactMatch、F1、LLM-Accuracy等指标
```

### 示例2：法律条款检索

```python
# 测试问题
qa = MultipleChoiceQaData(
    question="根据合同法，以下哪种情形属于无效合同？",
    options=["A. 欺诈订立的合同", "B. 重大误解的合同", "C. 显失公平的合同"],
    answer_mask_labels=[1, 0, 0]  # 正确答案是A
)

# 检索器选择建议：
# - 对于精确条款检索：使用ChunkAtomRetriever
# - 对于一般法律概念：使用QaChunkRetriever
```

## 检索器选择策略

### 根据问题复杂度选择

```python
def smart_retriever_selection(question, context):
    """智能选择检索器策略"""
    
    # 特征分析
    features = analyze_question_features(question)
    
    if features["complexity"] > 0.7:  # 复杂问题
        # 需要精确检索，使用ChunkAtomRetriever
        retriever = ChunkAtomRetriever(config)
        # 采用多查询策略
        queries = generate_sub_queries(question)
        chunks = []
        for query in queries:
            chunks.extend(retriever.retrieve_atom_info_through_atom(query))
    else:  # 简单问题
        # 使用QaChunkRetriever快速检索
        retriever = QaChunkRetriever(config)
        chunks = retriever.retrieve_contents_by_query(question)
    
    return chunks
```

### 混合检索策略

```python
class HybridRetrieverWorkflow(QaWorkflow):
    def __init__(self, yaml_config):
        super().__init__(yaml_config)
        
        # 初始化两个检索器
        self._init_simple_retriever()
        self._init_advanced_retriever()
    
    def answer(self, qa, question_idx):
        # 步骤1: 先用简单检索器快速筛选
        fast_chunks = self.simple_retriever.retrieve_contents(qa)
        
        if self._needs_precise_retrieval(qa, fast_chunks):
            # 步骤2: 如果需要，用高级检索器精确检索
            precise_chunks = self.advanced_retriever.retrieve_contents(qa)
            reference_chunks = self._merge_chunks(fast_chunks, precise_chunks)
        else:
            reference_chunks = fast_chunks
        
        # 后续流程不变
        messages = self._qa_protocol.process_input(
            content=qa.question,
            references=reference_chunks
        )
        # ...
```

## 性能优化策略

### 1. **缓存优化**
```python
# 每轮测试使用独立缓存
for round_idx in range(test_rounds):
    location = f"cache_round{round_idx}.db"
    client.update_cache_location(location)
    # 避免不同轮次间的缓存污染
```

### 2. **并行处理**
```python
# 根据硬件配置调整并行度
if num_cores >= 8:
    num_parallel = 4  # CPU密集型任务
elif num_gpus >= 1:
    num_parallel = 8  # GPU加速
else:
    num_parallel = 1  # 单线程
```

### 3. **渐进式检索**
```python
def progressive_retrieval(qa, retriever):
    """渐进式检索：先宽后深"""
    # 第一轮：宽泛检索
    broad_chunks = retriever.retrieve_contents_by_query(
        qa.question, 
        retrieve_k=10
    )
    
    # 第二轮：聚焦检索（基于第一轮结果）
    if len(broad_chunks) > 0:
        focused_query = extract_key_phrases(broad_chunks[0])
        focused_chunks = retriever.retrieve_contents_by_query(
            focused_query,
            retrieve_k=5
        )
        return broad_chunks[:3] + focused_chunks
    
    return broad_chunks
```

## 典型应用场景

### 场景1：客服机器人质量评估
```python
# 使用QaChunkRetriever进行快速评估
workflow_config = {
    "experiment_name": "客服FAQ测试",
    "test_rounds": 1,  # 快速测试
    "num_parallel": 8,  # 并行处理提高效率
    "retriever": {
        "class_name": "QaChunkRetriever",  # 简单快速
        "args": {"retrieve_k": 3}  # 只取最相关的3个结果
    }
}
```

### 场景2：法律文档精确检索
```python
# 使用ChunkAtomRetriever进行精确检索
workflow_config = {
    "experiment_name": "法律条款检索测试",
    "test_rounds": 3,  # 多次测试确保稳定性
    "num_parallel": 2,  # 避免并行度过高影响精度
    "retriever": {
        "class_name": "ChunkAtomRetriever",
        "args": {
            "retrieve_k": 5,
            "atom_retrieve_k": 8,  # 原子级细粒度检索
            "similarity_threshold": 0.8  # 高相似度阈值
        }
    }
}
```

### 场景3：教育领域问答系统
```python
# 混合检索策略
workflow_config = {
    "experiment_name": "教育知识库问答",
    "custom_retriever": "HybridRetriever",
    "retrieval_strategy": "adaptive",  # 自适应策略
    "fallback_mechanism": True  # 启用回退机制
}

# 自适应策略逻辑：
# 1. 对于定义性问题（"什么是..."）：使用QaChunkRetriever
# 2. 对于应用性问题（"如何计算..."）：使用ChunkAtomRetriever
# 3. 对于复杂推理问题：使用混合检索
```

## 调试和监控

### 检索过程监控
```python
class DebuggableQaWorkflow(QaWorkflow):
    def answer(self, qa, question_idx):
        # 记录检索开始时间
        retrieval_start = time.time()
        
        # 执行检索
        reference_chunks = self._retriever.retrieve_contents(
            qa, 
            retrieve_id=f"Q{question_idx:03}"
        )
        
        # 记录检索统计
        retrieval_stats = {
            "time": time.time() - retrieval_start,
            "chunks_count": len(reference_chunks),
            "avg_chunk_length": np.mean([len(c) for c in reference_chunks]),
            "question_length": len(qa.question),
            "question_type": classify_question(qa.question)
        }
        
        # 将统计信息添加到metadata
        qa.answer_metadata["retrieval_stats"] = retrieval_stats
        
        # 继续正常流程...
```

这种灵活的工作流程设计使得可以根据具体应用需求选择合适的检索策略和配置，在准确性和效率之间找到最佳平衡点。