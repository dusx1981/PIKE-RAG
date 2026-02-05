# PIKE-RAG 数据集适配详情

## 数据集对比总览

| 数据集 | 原始格式 | 来源 | 支持分割 | 特殊处理 |
|--------|----------|------|----------|----------|
| HotpotQA | JSON | HTTP | train, dev | supporting_facts 索引解析 |
| MuSiQue | JSONL | GDrive | train, dev | question_decomposition |
| NQ | HuggingFace | HF Datasets | train, validation | HTML字节解析 |
| TriviaQA | HuggingFace | HF Datasets | train, validation | Bing搜索+Wikipedia |
| 2Wiki | JSON | Dropbox | train, dev | Wikidata推理链 |
| PopQA | HuggingFace | HF Datasets | test | Wikidata实体 |
| WebQA | HuggingFace | HF Datasets | train, test | URL解析 |

---

## 1. HotpotQA

### 原始数据结构

```json
{
    "_id": "5a8b57f25542995d1e6f1371",
    "question": "Were Scott Derrickson and Ed Wood of the same nationality?",
    "answer": "yes",
    "type": "comparison",
    "level": "hard",
    "supporting_facts": [
        ["Scott Derrickson", 0],
        ["Ed Wood", 0]
    ],
    "context": [
        ["Scott Derrickson", [
            "Scott Derrickson is an American director, screenwriter and producer."
        ]],
        ["Ed Wood", [
            "Edward Davis Wood Jr. was an American filmmaker."
        ]]
    ]
}
```

### 处理逻辑

```python
def format_raw_data(raw):
    # 1. 从 context 中提取 supporting_facts
    supporting_facts = []
    for title, sent_idx in raw["supporting_facts"]:
        for ctx_title, sentences in raw["context"]:
            if ctx_title == title:
                supporting_facts.append({
                    "type": "wikipedia",
                    "title": title,
                    "contents": sentences[sent_idx]
                })
    
    # 2. 构建 retrieval_contexts
    retrieval_contexts = [
        {
            "type": "wikipedia",
            "title": title,
            "contents": "".join(sentences)
        }
        for title, sentences in raw["context"]
    ]
    
    return {
        "id": uuid.uuid4().hex,
        "question": raw["question"],
        "answer_labels": [raw["answer"]],
        "question_type": infer_question_type([raw["answer"]]),
        "metadata": {
            "original_id": raw["_id"],
            "supporting_facts": supporting_facts,
            "retrieval_contexts": retrieval_contexts,
            "original_type": raw["type"],
            "original_level": raw["level"]
        }
    }
```

### 关键注意点

- **Error Case**: `_id` 为 `5ae61bfd5542992663a4f261` 的样本存在索引错误，会被过滤
- **索引解析**: 需要通过标题和句子索引从 context 中提取支持事实

---

## 2. MuSiQue

### 原始数据结构

```json
{
    "id": "2hop__679_694",
    "question": "Which magazine was started first Arthur's Magazine or First for Women?",
    "answer": "Arthur's Magazine",
    "answer_aliases": ["Arthur's Magazine"],
    "paragraphs": [
        {
            "title": "Arthur's Magazine",
            "paragraph_text": "Arthur's Magazine was an American literary..."
        },
        {
            "title": "First for Women",
            "paragraph_text": "First for Women is a women's magazine..."
        },
        {
            "title": "1844 in literature",
            "paragraph_text": "This article presents lists of..."
        }
    ],
    "question_decomposition": [
        {
            "question": "When was Arthur's Magazine started?",
            "answer": "1844",
            "paragraph_support_idx": 0
        },
        {
            "question": "When was First for Women started?",
            "answer": "1989",
            "paragraph_support_idx": 1
        }
    ]
}
```

### 处理逻辑

```python
def format_raw_data(raw):
    # 1. paragraphs → retrieval_contexts
    retrieval_contexts = [
        {
            "type": "wikipedia",
            "title": para["title"],
            "contents": para["paragraph_text"]
        }
        for para in raw["paragraphs"]
    ]
    
    # 2. question_decomposition → supporting_facts
    supporting_facts = [
        retrieval_contexts[item["paragraph_support_idx"]]
        for item in raw["question_decomposition"]
    ]
    
    return {
        "id": uuid.uuid4().hex,
        "question": raw["question"],
        "answer_labels": [raw["answer"]] + raw["answer_aliases"],
        "question_type": infer_question_type([raw["answer"]]),
        "metadata": {
            "original_id": raw["id"],
            "supporting_facts": supporting_facts,
            "retrieval_contexts": retrieval_contexts
        }
    }
```

### 关键注意点

- **答案别名**: 包含 `answer_aliases` 作为备选答案
- **段落索引**: `paragraph_support_idx` 直接指向 `paragraphs` 数组

---

## 3. Natural Questions (NQ)

### 原始数据结构

```python
{
    "id": "-1000253785448025465",
    "question": {
        "text": "when is the next olympics"
    },
    "document": {
        "title": "Olympic Games",
        "html": "<html>...</html>"
    },
    "annotations": {
        "short_answers": [
            {"start_byte": 10405, "end_byte": 10417}
        ],
        "long_answer": {
            "start_byte": 10360,
            "end_byte": 10450
        },
        "yes_no_answer": -1  # -1: not yes/no, 1: yes, 0: no
    }
}
```

### 处理逻辑

```python
def format_raw_data(raw):
    html_bytes = raw["document"]["html"].encode()
    
    # 1. 从字节偏移提取短答案
    answer_labels = []
    for answer in raw["annotations"]["short_answers"]:
        start, end = answer["start_byte"][0], answer["end_byte"][0]
        evidence = html_bytes[start:end].decode()
        # 使用 BeautifulSoup 清理 HTML
        soup = BeautifulSoup(evidence, "html.parser")
        answer_labels.append(clean_text(soup.get_text()))
    
    if not answer_labels:
        return None  # 过滤无答案样本
    
    # 2. 提取长答案作为 supporting_fact
    long_answer = raw["annotations"]["long_answer"]
    evidence_contents = html_bytes[
        long_answer[0]["start_byte"]:long_answer[0]["end_byte"]
    ].decode()
    
    return {
        "id": uuid.uuid4().hex,
        "question": raw["question"]["text"],
        "answer_labels": answer_labels,
        "question_type": infer_nq_question_type(
            answer_labels, 
            raw["annotations"]["yes_no_answer"]
        ),
        "metadata": {
            "original_id": raw["id"],
            "supporting_facts": [{
                "type": "wikipedia",
                "title": raw["document"]["title"],
                "contents": clean_text(evidence_contents)
            }],
            "original_type": qtype
        }
    }
```

### 关键注意点

- **字节偏移**: 答案位置通过字节偏移量指定
- **HTML清理**: 使用 BeautifulSoup 去除 HTML 标签
- **是非题判断**: `yes_no_answer` 字段：-1=非是非题, 1=yes, 0=no
- **过滤条件**: 无短答案或无法提取长答案的样本被过滤

---

## 4. TriviaQA

### 原始数据结构

```python
{
    "question_id": "tc_19",
    "question": "Who was the man behind The Chipmunks?",
    "answer": {
        "aliases": ["Ross Bagdasarian, Sr.", "David Seville", ...],
        "matched_wiki_entity_name": "Ross Bagdasarian, Sr.",
        "normalized_aliases": [...],
        "normalized_value": "ross bagdasarian, sr.",
        "type": "WikipediaEntity",
        "value": "Ross Bagdasarian, Sr."
    },
    "entity_pages": [
        {
            "doc_source": "http://en.wikipedia.org/wiki/Ross_Bagdasarian,_Sr.",
            "title": "Ross Bagdasarian, Sr.",
            "wiki_context": "Rostom Sipan Bagdasarian , known professionally..."
        }
    ],
    "search_results": [
        {
            "description": "Ross Bagdasarian was an American singer...",
            "filename": "98/98880.txt",
            "link": "http://www.nndb.com/people/974/000164479/",
            "rank": 0,
            "search_context": "NNDB has added thousands of bibliographies...",
            "title": "Ross Bagdasarian",
            "url": "http://www.nndb.com/people/974/000164479/"
        }
    ]
}
```

### 处理逻辑

```python
def format_raw_data(raw):
    # 1. 构建 Bing 搜索结果
    bing_search_results = [
        {
            "type": "BingSearch",
            "title": title,
            "url": url,
            "description": description,
            "contents": contents,
            "rank": rank
        }
        for title, url, description, contents, rank in zip(
            raw["search_results"]["title"],
            raw["search_results"]["url"],
            raw["search_results"]["description"],
            raw["search_results"]["search_context"],
            raw["search_results"]["rank"]
        )
    ]
    
    return {
        "id": uuid.uuid4().hex,
        "question": raw["question"],
        "answer_labels": raw["answer"]["aliases"],
        "question_type": infer_question_type(raw["answer"]["aliases"]),
        "metadata": {
            "original_id": raw["question_id"],
            "retrieval_contexts": [
                {"type": "wikipedia", "title": title}
                for title in raw["entity_pages"]["title"]
            ] + bing_search_results
        }
    }
```

### 关键注意点

- **混合来源**: 结合 Wikipedia 实体页面和 Bing 搜索结果
- **答案别名**: `answer.aliases` 提供多个可能的正确答案
- **无 supporting_facts**: TriviaQA 原始数据不包含显式支持事实

---

## 5. 2WikiMultiHopQA

### 原始数据结构

```json
{
    "_id": "...",
    "question": "Which team does the player who was a runner-up in the 1982 FIFA World Cup play for?",
    "answer": "West Germany national football team",
    "type": "bridge",
    "supporting_facts": [
        ["1982 FIFA World Cup", 1],
        ["West Germany national football team", 0]
    ],
    "context": [
        ["1982 FIFA World Cup", [
            "The 1982 FIFA World Cup was the 12th FIFA World Cup...",
            "The tournament was won by Italy, who defeated West Germany 3–1 in the final..."
        ]],
        ["West Germany national football team", [
            "The Germany national football team is the men's football team..."
        ]]
    ],
    "evidences": [
        ["1982 FIFA World Cup", "final", "West Germany"],
        ["West Germany national football team", " FIFA World Cup", "runners-up"]
    ]
}
```

### 处理逻辑

```python
def format_raw_data(raw):
    # 1. 复用 HotpotQA 的 get_supporting_facts
    supporting_facts = get_supporting_facts(
        raw["supporting_facts"], 
        raw["context"]
    )
    
    if supporting_facts is None:
        return None
    
    return {
        "id": uuid.uuid4().hex,
        "question": raw["question"],
        "answer_labels": [raw["answer"]],
        "question_type": infer_question_type([raw["answer"]]),
        "metadata": {
            "original_id": raw["_id"],
            "original_type": raw["type"],
            "supporting_facts": supporting_facts,
            "retrieval_contexts": [
                {
                    "type": "wikipedia",
                    "title": title,
                    "contents": "".join(sentences)
                }
                for title, sentences in raw["context"]
            ],
            "reasoning_logics": [
                {
                    "type": "wikidata",
                    "title": title,
                    "section": section,
                    "contents": content
                }
                for title, section, content in raw["evidences"]
            ]
        }
    }
```

### 关键注意点

- **复用 HotpotQA**: 使用相同的 `get_supporting_facts` 函数
- **Wikidata 链**: `evidences` 包含 Wikidata 推理逻辑
- **需要 title2qid**: 下载 Wikidata 文档时需要 `title2qid` 映射

---

## 6. PopQA

### 原始数据结构

```python
{
    "id": 1000,
    "question": "What is the capital of France?",
    "possible_answers": '["Paris", "Paris, France"]',
    "subj": "France",
    "prop": "capital",
    "obj": "Paris",
    "s_uri": "http://www.wikidata.org/entity/Q142",
    "o_uri": "http://www.wikidata.org/entity/Q90",
    "subj_pop": 100.0,
    "obj_pop": 100.0
}
```

### 处理逻辑

```python
def format_raw_data(raw):
    if raw["subj"] is None:
        return None  # 过滤无主体样本
    
    answer_labels = json.loads(raw["possible_answers"])
    
    return {
        "id": uuid.uuid4().hex,
        "question": raw["question"],
        "answer_labels": answer_labels,
        "question_type": infer_question_type(answer_labels),
        "metadata": {
            "original_id": raw["id"],
            "supporting_facts": [{
                "type": "wikidata",
                "title": raw["subj"],
                "section": raw["prop"],
                "contents": raw["obj"]
            }]
        }
    }

def load_title2qid(dataset_dir, split):
    """为 Wikidata 下载提供 QID 映射"""
    dataset = load_raw_data("", split)
    title2qid = {}
    for raw in dataset:
        if raw["subj"] is not None:
            qid = raw["s_uri"].split("/")[-1]
            title2qid[raw["subj"]] = qid
    return title2qid
```

### 关键注意点

- **Wikidata 格式**: 使用 `subj/prop/obj` 三元组
- **需要 QID**: `s_uri` 提取 QID 用于文档下载
- ** popularity 分数**: `subj_pop` 和 `obj_pop` 未在协议中使用

---

## 7. WebQA

### 原始数据结构

```python
{
    "url": "https://en.wikipedia.org/wiki/Stanford_University",
    "question": "What university was founded in 1885?",
    "answers": ["Stanford University", "Stanford"]
}
```

### 处理逻辑

```python
def format_raw_data(raw):
    qtype = infer_question_type(raw["answers"])
    
    return {
        "id": uuid.uuid4().hex,
        "question": raw["question"],
        "answer_labels": raw["answers"],
        "question_type": qtype,
        "metadata": {
            "supporting_facts": [{
                "type": "wikipedia",
                "title": raw["url"].split("/")[-1].replace("_", " ")
            }]
        }
    }
```

### 关键注意点

- **URL解析**: 从 URL 提取文档标题
- **简单结构**: 无复杂的 metadata
- **无 contents**: supporting_facts 不含 contents 字段

---

## 数据集特定字段汇总

| 数据集 | 特有 metadata 字段 | 说明 |
|--------|-------------------|------|
| HotpotQA | `original_type`, `original_level` | bridge/comparison, easy/medium/hard |
| MuSiQue | - | 标准格式 |
| NQ | `original_type` | yes_no/undefined |
| TriviaQA | - | 标准格式 |
| 2Wiki | `original_type`, `reasoning_logics` | bridge/comparison, Wikidata推理链 |
| PopQA | - | 标准格式 |
| WebQA | - | 标准格式 |

## 常见问题

### Q: 为什么有些样本会被过滤？

A: 以下情况会导致样本被过滤：
- NQ: 无法提取短答案或长答案
- HotpotQA/2Wiki: supporting_facts 索引无效
- PopQA: `subj` 为 None

### Q: 如何为自定义数据集实现适配器？

A: 参考结构最简单的 WebQA，实现两个函数：
1. `load_raw_data()`: 返回原始数据列表
2. `format_raw_data()`: 返回符合协议的字典

### Q: supporting_facts 和 retrieval_contexts 的区别？

A: 
- **supporting_facts**: 用于推理的金标准文档片段（通常2-4条）
- **retrieval_contexts**: 用于构建检索库的完整文档（通常10-20条）
