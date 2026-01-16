# Generation QA Protocols 输入输出分析

## 1. **基础概念理解**

这两个协议是用于问答系统的通信模板：
- `generation_qa_protocol`: 无参考上下文的生成式问答
- `generation_qa_with_reference_protocol`: 基于参考上下文的生成式问答

## 2. **输入输出结构分析**

### 2.1 共同结构
```python
# 输出格式（两个协议相同）
{
    "answer": "答案字符串",        # 必需：最终答案
    "rationale": "推理过程字符串"   # 必需：推理理由
}

# 输入结构
content: str              # 问题文本
references: List[str]     # 参考文本列表（仅带参考的协议使用）
kwargs: Dict              # 其他参数（如answer_labels）
```

## 3. **具体示例分析**

### 3.1 `generation_qa_protocol` 示例

#### 示例1：简单事实问答
```python
# 输入
content = "中国的首都是哪里？"
references = []  # 空列表，不使用参考

# Protocol处理过程
# 1. 模板填充
messages = [
    ("system", "You are a helpful AI assistant on question answering."),
    ("user", """
# Task
Your task is to give your answer to the given question.

# Output format
Your output should strictly follow the format below. Make sure your output parsable by json in Python.
{
    "answer": <a string. Your answer.>,
    "rationale": <a string. Rationale behind your answer.>
}

# Question
中国的首都是哪里？

Let's think step by step.
""".strip())
]

# 2. LLM响应（模拟）
llm_response = '''
{
    "answer": "北京",
    "rationale": "北京是中华人民共和国的首都，位于华北平原北部。"
}
'''

# 3. Parser解析
output = GenerationQaParser().decode(llm_response)
# 输出: {"answer": "北京", "rationale": "北京是中华人民共和国的首都，位于华北平原北部。"}
```

#### 示例2：需要推理的问题
```python
# 输入
content = "如果一只鸡和半只鸡一天半生1.5个蛋，一只鸡一天生几个蛋？"

# LLM响应
response = '''
{
    "answer": "2/3个蛋",
    "rationale": "设一只鸡每天生x个蛋。一只鸡和半只鸡一共1.5只鸡。1.5只鸡1.5天生1.5个蛋，所以1.5只鸡每天生1个蛋。因此1只鸡每天生1/1.5=2/3个蛋。"
}
'''
```

### 3.2 `generation_qa_with_reference_protocol` 示例

#### 示例1：医学问答
```python
# 输入
content = "糖尿病患者可以服用阿司匹林吗？"
references = [
    "阿司匹林是一种非甾体抗炎药，具有抗血小板聚集作用。",
    "糖尿病患者心血管疾病风险较高，阿司匹林可用于一级预防。",
    "但糖尿病患者服用阿司匹林需注意出血风险，特别是胃肠道出血。",
    "对于年龄≥50岁且伴有至少一项主要心血管危险因素的2型糖尿病患者，建议使用小剂量阿司匹林。"
]
answer_labels = ["yes", "no"]  # 这是个yes/no问题

# Protocol处理过程
# 1. Parser编码
content_str, extra_args = GenerationQaParser().encode(
    content=content,
    references=references,
    answer_labels=answer_labels
)

# extra_args包含：
# yes_or_no_limit = ' Your answer shall be "Yes" or "No".'
# context_if_any = references合并后的字符串

# 2. 模板填充后的消息
messages = [
    ("system", "You are a helpful AI assistant on question answering."),
    ("user", """
# Task
Your task is to answer a question referring to a given context, if any.
For answering the Question at the end, you need to first read the context provided, then give your final answer.

# Output format
Your output should strictly follow the format below. Make sure your output parsable by json in Python.
{
    "answer": <A string. Your Answer.>,
    "rationale": <A string. Rationale behind your choice>
}

# Context, if any
阿司匹林是一种非甾体抗炎药，具有抗血小板聚集作用。
糖尿病患者心血管疾病风险较高，阿司匹林可用于一级预防。
但糖尿病患者服用阿司匹林需注意出血风险，特别是胃肠道出血。
对于年龄≥50岁且伴有至少一项主要心血管危险因素的2型糖尿病患者，建议使用小剂量阿司匹林。

# Question
糖尿病患者可以服用阿司匹林吗？ Your answer shall be "Yes" or "No".

Let's think step by step.
""".strip())
]

# 3. LLM响应
response = '''
{
    "answer": "Yes",
    "rationale": "根据提供的资料，糖尿病患者可以服用阿司匹林，特别是对于年龄≥50岁且伴有心血管危险因素的患者。但需要医生评估出血风险。"
}
'''
```

#### 示例2：法律条款解释
```python
# 输入
content = "根据以下合同条款，甲方违约需要承担什么责任？"
references = [
    "第8条违约责任：如甲方未按约定时间支付款项，每逾期一日，应按应付未付款项的千分之三向乙方支付违约金。",
    "第9条赔偿范围：违约方应赔偿守约方因此遭受的全部损失，包括但不限于直接损失、间接损失和律师费。",
    "第10条合同解除：乙方有权在甲方逾期超过30日后单方解除合同。"
]

# 上下文长度限制示例
context_len_limit = 200  # 假设限制200字符

# 处理过程
# 1. Parser编码会截断references
context_if_any = ""
for context in list(set(references)):
    context_if_any += f"\n{context}\n"
    if len(context_if_any) >= context_len_limit:  # 达到限制
        break

# 2. LLM响应
response = '''
{
    "answer": "甲方违约需要承担：1)每日千分之三的违约金；2)赔偿乙方全部损失；3)乙方有权在逾期30日后解除合同。",
    "rationale": "根据合同第8、9、10条，甲方违约的具体责任包括支付违约金、赔偿损失以及可能面临合同解除。"
}
'''
```

## 4. **Parser工作流程详解**

### 4.1 `GenerationQaParser.encode()` 逻辑
```python
def encode(self, content: str, references: List[str]=[], context_len_limit: int=80000, **kwargs):
    # 步骤1: 判断是否为yes/no问题
    answer_labels = kwargs.get("answer_labels", [])
    if len(answer_labels) == 1 and answer_labels[0] in ["yes", "no"]:
        yes_or_no_limit = """ Your answer shall be "Yes" or "No"."""
    else:
        yes_or_no_limit = ""

    # 步骤2: 构建参考上下文（去重并截断）
    context_if_any = ""
    for context in list(set(references)):  # 去重
        context_if_any += f"\n{context}\n"
        if len(context_if_any) >= context_len_limit:
            break  # 达到长度限制

    return content, {
        "yes_or_no_limit": yes_or_no_limit,
        "context_if_any": context_if_any,
    }
```

### 4.2 `GenerationQaParser.decode()` 逻辑
```python
def decode(self, content: str, **kwargs) -> Dict[str, str]:
    try:
        output = parse_json(content)  # 解析JSON
    except Exception as e:
        # 解析失败处理
        print(f"[GenerationQaParser] Content: {content}\nException: {e}")
        return {
            "answer": "parsing error",
            "rationale": "parsing error",
        }

    # 确保所有值都是字符串
    for key, value in output.items():
        output[key] = str(value)
    return output
```

## 5. **不同应用场景对比**

### 场景1：开放域问答 vs 检索增强问答
```python
# 开放域问答（使用generation_qa_protocol）
# 适合：通用知识、常识推理
content = "为什么天空是蓝色的？"
# 依赖LLM的内部知识

# 检索增强问答（使用generation_qa_with_reference_protocol）
# 适合：专业领域、具体文档、实时信息
content = "根据2024年财报，某公司净利润增长率是多少？"
references = ["2024年财报显示：某公司净利润为..."]
# 结合外部信息源
```

### 场景2：考试系统
```python
# 无参考模式 - 测试学生记忆
questions = [
    "牛顿第二定律公式是什么？",
    "光合作用的化学方程式是什么？"
]
# 使用generation_qa_protocol

# 开卷考试模式 - 测试学生信息处理能力
questions = [
    "根据提供的实验数据，分析反应速率与温度的关系。"
]
references = [实验数据文档]
# 使用generation_qa_with_reference_protocol
```

### 场景3：客服系统
```python
# 一级回答：标准FAQ（无参考）
content = "你们的退货政策是什么？"
# 使用generation_qa_protocol，训练好的通用回答

# 二级回答：具体案例处理（有参考）
content = "订单号202412345的商品可以退货吗？"
references = [
    "订单202412345状态：已发货7天，商品未使用。",
    "退货政策：未使用商品在签收后15天内可退货。",
    "用户历史：该用户有过3次成功退货记录。"
]
# 使用generation_qa_with_reference_protocol，结合具体信息
```

## 6. **上下文长度限制的实际影响**

```python
# 示例：大量参考文档的情况
references = [
    "文档1：..." * 1000,  # 1000字符
    "文档2：..." * 1000,  # 1000字符
    "文档3：..." * 1000,  # 1000字符
    "文档4：..." * 1000,  # 1000字符
]

context_len_limit = 2000  # 限制2000字符

# 实际包含的上下文
# 文档1（1000字符） + 文档2（1000字符） = 2000字符
# 文档3、4被截断，不会包含在最终prompt中
```

## 7. **Yes/No问题的特殊处理**

```python
# 场景：医疗诊断辅助
content = "患者症状包括咳嗽、发热、呼吸困难，是否可能感染COVID-19？"
answer_labels = ["yes", "no"]  # 重要：这个标记触发yes/no限制

# 生成的prompt会包含：
# "Your answer shall be \"Yes\" or \"No\"."

# 好处：
# 1. 强制二选一，避免模糊回答
# 2. 便于后续的自动评估（ExactMatch指标）
# 3. 减少LLM的"可能、或许"等不确定表达
```

## 8. **错误处理示例**

```python
# 情况1：LLM返回非JSON格式
response = "答案是北京，因为北京是中国的首都。"
# Parser.decode()会捕获异常，返回：
{
    "answer": "parsing error",
    "rationale": "parsing error"
}

# 情况2：JSON格式正确但字段缺失
response = '{"answer": "北京"}'  # 缺少rationale
# parse_json能解析，但后续可能需要处理字段缺失

# 情况3：JSON解析成功但值不是字符串
response = '{"answer": "北京", "rationale": 123}'
# Parser.decode()会将123转换为"123"
```

## 9. **实际集成到QaWorkflow的完整流程**

```python
class MedicalQaSystem:
    def process_question(self, question, patient_records=None):
        if patient_records:
            # 使用带参考的协议
            protocol = generation_qa_with_reference_protocol
            references = self._retrieve_medical_guidelines(question)
            references.extend(patient_records)
        else:
            # 使用无参考的协议
            protocol = generation_qa_protocol
            references = []
        
        # 构建消息
        messages = protocol.process_input(
            content=question,
            references=references,
            context_len_limit=4000  # 医学上下文可能较长
        )
        
        # 调用LLM
        response = llm_client.generate(messages)
        
        # 解析输出
        result = protocol.parse_output(response)
        
        return {
            "answer": result["answer"],
            "rationale": result["rationale"],
            "confidence": self._calculate_confidence(result)
        }
```

## 10. **性能优化建议**

```python
# 1. 参考文档去重
references = list(set(references))  # Parser内部已做

# 2. 智能截断策略
def smart_context_selection(references, question, limit):
    # 基于相似度排序
    sorted_refs = sorted(references, 
                        key=lambda x: calculate_similarity(x, question),
                        reverse=True)
    
    selected = []
    total_len = 0
    for ref in sorted_refs:
        if total_len + len(ref) <= limit:
            selected.append(ref)
            total_len += len(ref)
        else:
            # 部分截断
            remaining = limit - total_len
            if remaining > 100:  # 至少保留100字符才有意义
                selected.append(ref[:remaining])
            break
    return selected

# 3. 缓存常见问题的答案
# 对于generation_qa_protocol，常见问题可以缓存
# 对于generation_qa_with_reference_protocol，缓存需考虑reference变化
```

## 总结对比表

| 维度 | generation_qa_protocol | generation_qa_with_reference_protocol |
|------|----------------------|--------------------------------------|
| **适用场景** | 开放域问答、常识推理 | 文档问答、专业咨询、事实核查 |
| **输入要求** | 仅问题文本 | 问题文本 + 参考文档列表 |
| **上下文限制** | 无 | 有context_len_limit参数 |
| **Yes/No处理** | 支持 | 支持，且会自动添加限制指令 |
| **输出格式** | 固定的JSON格式 | 同左 |
| **错误处理** | JSON解析异常处理 | 同左 |
| **性能考虑** | 响应快，无检索开销 | 可能慢，受参考文档数量和长度影响 |
| **准确性** | 依赖LLM内部知识 | 可结合最新/特定信息 |

这两个协议构成了问答系统的核心通信机制，通过灵活的配置可以适应从简单问答到复杂文档分析的多种场景。