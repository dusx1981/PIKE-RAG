# PIKE-RAG 数据生成逻辑技术文档

## 1. 概述

PIKE-RAG 的数据处理模块（`data_process/`）负责将原始数据集转换为统一格式，并管理相关文档的下载与组织。本文档详细分析数据处理的完整流程、核心组件和数据协议。

## 2. 整体架构

### 2.1 模块结构

```
data_process/
├── main.py                              # 主入口
├── chunk_by_sentence.py                 # 句子级分块工具
├── retrieval_contexts_as_chunks.py      # 检索上下文提取工具
├── generate_test_data.py                # 测试数据生成器（新增）
├── validate_test_data.py                # 数据格式验证器（新增）
└── open_benchmarks/
    ├── reformat_dataset.py              # 数据格式转换
    ├── sample_dataset.py                # 数据采样与文档下载
    ├── config/
    │   └── datasets.yaml                # 数据集配置
    ├── dataset_utils/                   # 各数据集适配器
    │   ├── hotpotqa.py
    │   ├── musique.py
    │   ├── nq.py
    │   ├── triviaqa.py
    │   ├── two_wiki.py
    │   ├── popqa.py
    │   └── webqa.py
    └── utils/                           # 工具模块
        ├── filepaths.py                 # 文件路径管理
        ├── io.py                        # IO操作
        ├── stats.py                     # 数据集统计
        ├── question_type.py             # 问题类型推断
        ├── wikipedia.py                 # Wikipedia下载器
        └── wikidata.py                  # Wikidata下载器
```

### 2.2 处理流程

数据处理分为两个主要阶段：

```
┌─────────────────────────────────────────────────────────────────┐
│                     Phase 1: Build Split                        │
│                    (构建数据集分割文件)                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Raw Dataset → Load → Format → Filter → Save as JSONL          │
│       ↓           ↓        ↓        ↓                           │
│   (原始数据)   (加载)   (格式化)  (过滤无效)  (保存分割文件)     │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                    Phase 2: Sample Sets                         │
│                  (采样与文档下载)                                │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Split JSONL → Sample → Download Docs → Save Subsets           │
│       ↓           ↓           ↓           ↓                     │
│   (分割文件)   (随机采样)   (下载文档)   (保存子集)              │
│                                                                 │
│  Documents: Wikipedia HTML/PDF, Wikidata HTML/PDF              │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## 3. 数据格式协议

### 3.1 统一数据协议

所有数据集经过处理后必须符合以下标准格式：

```json
{
    "id": "string (UUID)",
    "question": "string (问题文本)",
    "answer_labels": ["string array (答案列表)"],
    "question_type": "string (yes_no | undefined)",
    "metadata": {
        "original_id": "string (原始数据集ID)",
        "supporting_facts": [
            {
                "type": "string (wikipedia | wikidata | BingSearch)",
                "title": "string (文档标题)",
                "contents": "string (支持事实内容)"
            }
        ],
        "retrieval_contexts": [
            {
                "type": "string (来源类型)",
                "title": "string (文档标题)",
                "contents": "string (检索上下文内容)"
            }
        ],
        "...": "其他数据集特定字段"
    }
}
```

### 3.2 字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | UUID | 唯一标识符，使用 `uuid.uuid4().hex` 生成 |
| `question` | string | 问题文本 |
| `answer_labels` | array | 可能的答案列表（包含主答案和别名） |
| `question_type` | string | 问题类型：`"yes_no"` 或 `"undefined"` |
| `metadata.original_id` | string | 原始数据集中的标识符 |
| `metadata.supporting_facts` | array | 支持事实（用于推理的金标准文档片段） |
| `metadata.retrieval_contexts` | array | 检索上下文（用于构建检索库） |

### 3.3 数据来源类型

```python
# utils/stats.py
SOURCE_TYPES_TO_DOWNLOAD = ["wikipedia", "wikidata"]
FILE_TYPES_TO_DOWNLOAD = ["pdf", "html"]
```

支持的数据来源：
- **wikipedia**: Wikipedia 页面
- **wikidata**: Wikidata 实体页面
- **BingSearch**: Bing 搜索结果（TriviaQA特有）

支持下载的文件格式：
- **html**: 原始 HTML 页面
- **pdf**: PDF 格式的页面

## 4. 核心模块详解

### 4.1 主入口 (main.py)

**功能**: 协调数据处理的两个阶段

**配置参数** (YAML):

```yaml
root_save_dir: data                    # 数据保存根目录
running_modes:
  build_split: True                    # 是否执行阶段1
  sample_sets: True                    # 是否执行阶段2
datasets:                              # 数据集配置
  hotpotqa: dev
  musique: dev
  nq: validation
sample_size_list: [100, 200, ..., 500] # 采样大小列表
seed: 223                              # 随机种子
cut_off: null                          # 截断数量（用于测试）
```

**执行流程**:

```python
def main():
    # 1. 加载配置
    yaml_config = load_yaml_config(args.config, args)
    
    # 2. 验证数据集和分割
    for dataset, split in dataset2split.items():
        check_dataset_split(dataset, split)
    
    # 3. 创建目录结构
    create_dirs(root_save_dir, list(dataset2split.keys()))
    
    # 4. 阶段1: 构建分割文件
    if running_modes.get("build_split", False):
        for dataset, split in dataset2split.items():
            reformat_dataset(dataset, split, split_path, dataset_dir, cut_off)
    
    # 5. 阶段2: 采样与文档下载
    if running_modes.get("sample_sets", False):
        for dataset, split in dataset2split.items():
            sample_datasets(dataset, split, sample_size_list, random_seed, ...)
```

### 4.2 数据格式转换 (reformat_dataset.py)

**功能**: 将原始数据集转换为统一格式

**核心逻辑**:

```python
def reformat_dataset(dataset, split, dump_path, dataset_dir, cut_off=None):
    # 动态导入对应的数据集处理模块
    dataset_utils = get_dataset_utils_module(dataset)
    
    # 加载原始数据
    raw_data = dataset_utils.load_raw_data(dataset_dir, split)
    
    # 逐条处理并保存
    with jsonlines.open(dump_path, "w") as writer:
        for sample in raw_data:
            formatted_data = dataset_utils.format_raw_data(sample)
            if formatted_data is not None:  # 过滤无效样本
                writer.write(formatted_data)
```

### 4.3 数据采样 (sample_dataset.py)

**功能**: 从分割文件中采样有效样本，并下载相关文档

**核心流程**:

```python
def sample_datasets(dataset, split, sample_size_list, random_seed, document_dir, split_path_func):
    # 1. 加载分割数据
    split_data = load_from_jsonlines(raw_split_path)
    
    # 2. 加载缓存（避免重复下载）
    title_to_location, title_to_validation = load_caches(document_dir)
    
    # 3. 渐进式采样
    for sample_size in sample_size_list:
        while len(chosen_samples) < sample_size:
            # 随机采样索引
            newly_sampled_indexes = np.random.choice(remaining_indexes, ...)
            
            for idx in newly_sampled_indexes:
                sample = split_data[idx]
                titles_by_type = get_titles_to_download(sample)
                
                # 尝试下载文档
                success, updated, downloaded = try_download(titles_by_type, ...)
                
                if success:
                    chosen_samples.append(sample)
        
        # 保存当前大小的子集
        dump_to_jsonlines(dump_path, chosen_samples)
```

**渐进式采样策略**:
- 从大到小排序采样大小列表
- 已采样的样本继续用于更大的采样大小
- 每20次更新保存一次缓存

**文档下载优先级**:
1. 优先下载 `supporting_facts` 中的文档
2. 如果不存在 `supporting_facts`，则下载 `retrieval_contexts` 中的文档

### 4.4 数据集适配器

每个数据集适配器必须实现两个函数：

```python
def load_raw_data(dataset_dir: str, split: str) -> List[dict]:
    """加载原始数据集"""
    pass

def format_raw_data(raw: dict) -> Optional[dict]:
    """将原始样本格式化为统一协议"""
    pass
```

#### 4.4.1 HotpotQA (hotpotqa.py)

**数据来源**: CMU 提供的 JSON 文件

**原始数据格式**:
```json
{
    "_id": "...",
    "question": "...",
    "answer": "...",
    "type": "bridge|comparison|...",
    "level": "easy|medium|hard",
    "supporting_facts": [["Title", 0], ["Title", 1]],
    "context": [["Title", ["sent1", "sent2", ...]], ...]
}
```

**处理逻辑**:
1. 从 `context` 中提取 `supporting_facts` 对应的句子
2. 构建 `retrieval_contexts`（包含所有上下文）
3. 保留 `original_type` 和 `original_level`

#### 4.4.2 MuSiQue (musique.py)

**数据来源**: Google Drive 下载的 JSONL 文件

**原始数据格式**:
```json
{
    "id": "...",
    "question": "...",
    "answer": "...",
    "answer_aliases": [...],
    "paragraphs": [
        {"title": "...", "paragraph_text": "..."}
    ],
    "question_decomposition": [
        {"paragraph_support_idx": 0},
        {"paragraph_support_idx": 1}
    ]
}
```

**处理逻辑**:
1. `paragraphs` 转换为 `retrieval_contexts`
2. `question_decomposition` 中的 `paragraph_support_idx` 用于提取 `supporting_facts`

#### 4.4.3 Natural Questions (nq.py)

**数据来源**: Hugging Face `datasets` 库

**处理逻辑**:
1. 使用 `datasets.load_dataset()` 加载
2. 从 HTML 字节中提取答案标签
3. 解析长答案作为 `supporting_facts`
4. 处理 `yes_no_answer` 字段推断问题类型

#### 4.4.4 TriviaQA (triviaqa.py)

**数据来源**: Hugging Face `datasets` 库

**特殊字段**:
- `entity_pages`: Wikipedia 实体页面列表
- `search_results`: Bing 搜索结果

**处理逻辑**:
1. `entity_pages` 和 `search_results` 合并为 `retrieval_contexts`
2. `answer.aliases` 作为 `answer_labels`

#### 4.4.5 2WikiMultiHopQA (two_wiki.py)

**数据来源**: Dropbox 下载的 ZIP 文件

**特殊字段**:
- `evidences`: Wikidata 推理逻辑（title, section, content）

**处理逻辑**:
1. 复用 HotpotQA 的 `get_supporting_facts` 函数
2. `evidences` 转换为 `reasoning_logics`
3. 支持 Wikidata 文档下载（需要 `title2qid` 映射）

#### 4.4.6 PopQA (popqa.py)

**数据来源**: Hugging Face `datasets` 库

**特殊字段**:
- `subj`: 主体（用于 Wikidata 查询）
- `prop`: 属性/章节
- `obj`: 客体（答案）
- `s_uri`: Wikidata URI

**处理逻辑**:
1. 构建 Wikidata 格式的 `supporting_facts`
2. 提供 `load_title2qid` 函数用于下载

#### 4.4.7 WebQA (webqa.py)

**数据来源**: Hugging Face `datasets` 库

**处理逻辑**:
1. 从 URL 提取文档标题
2. 构建简单的 `supporting_facts`

### 4.5 问题类型推断 (question_type.py)

```python
def infer_question_type(answer_labels: List[str]) -> str:
    """推断问题类型"""
    if is_yes_no_question(answer_labels):
        return "yes_no"
    return "undefined"

def is_yes_no_question(answer_labels: List[str]) -> bool:
    """检查是否为是非题"""
    for answer in answer_labels:
        if not answer.lower() in ["yes", "no"]:
            return False
    return True
```

特殊处理（Natural Questions）:
```python
def infer_nq_question_type(answer_labels, yes_no_answer: int) -> str:
    if yes_no_answer == 1:  # NQ 数据集中的标记
        return "yes_no"
    return "undefined"
```

## 5. 文档下载系统

### 5.1 Wikipedia 下载器 (wikipedia.py)

**核心功能**:
- 使用 `wikipediaapi` 库访问页面
- 支持 HTML、PDF、Markdown 三种格式
- 全有或全无的批量下载策略

**下载函数映射**:
```python
FILE_TYPE_TO_GET_FUNCTION = {
    "html": get_html_bytes,      # 从页面 URL 获取
    "pdf": get_pdf_bytes,        # 从 REST API 获取
    "md": get_markdown_texts,    # 转换为 Markdown
}
```

**异步实现**:
- 使用 `aiohttp` 进行并发下载
- 页面存在性检查仍为同步（API限制）

### 5.2 Wikidata 下载器 (wikidata.py)

**核心功能**:
- 通过 QID 访问 Wikidata 页面
- HTML 解析提取结构化数据
- 转换为 Markdown 格式

**解析内容**:
```python
def parse_contents(html_content: str) -> dict:
    return {
        'title': '实体标题',
        'description': ['描述1', '描述2', ...],
        'statements': {
            '属性1': ['值1', '值2'],
            '属性2': ['值3']
        }
    }
```

### 5.3 缓存机制

**缓存文件**:
- `doc_title_type_to_location.json`: 标题到文件路径的映射
- `wiki_title_type_to_validation_status.json`: 标题有效性验证状态

**缓存策略**:
1. 首次下载时创建缓存
2. 每20次更新自动保存
3. 重启时自动加载，避免重复下载

## 6. 后处理工具

### 6.1 检索上下文提取 (retrieval_contexts_as_chunks.py)

**功能**: 从测试集中提取所有检索上下文作为分块

**输出格式**:
```json
{
    "chunk_id": "Title-0-2",
    "title": "文档标题",
    "content": "检索上下文内容"
}
```

### 6.2 句子级分块 (chunk_by_sentence.py)

**功能**: 使用 spaCy 将分块切分为句子

**处理流程**:
1. 加载 spaCy 模型 `en_core_web_lg`
2. 对每个分块进行句子分割
3. 添加 `sentences` 字段

## 7. Examples 中的数据使用

### 7.1 QA 工作流配置

**配置结构** (以 `qa_chunk.yml` 为例):

```yaml
# 1. 测试数据加载
test_loading:
  module: pikerag.utils.data_protocol_utils
  name: load_testing_suite
  args:
    filepath: data/hotpotqa/dev_500.jsonl

# 2. 检索器配置
retriever:
  class_name: QaChunkRetriever
  args:
    retrieve_k: 16
    vector_store:
      collection_name: dev_500_chunks_ada
      persist_directory: data/vector_stores/hotpotqa
      id_document_loading:
        func_name: load_ids_and_chunks
        args:
          filepath: data/hotpotqa/dev_500_retrieval_contexts_as_chunks_with_atom_questions.jsonl
```

### 7.2 数据加载流程

```
Config YAML → QaWorkflow → load_testing_suite → JSONL File
                                    ↓
                          List[QA Dict] → Retriever → Vector Store
```

### 7.3 支持的实验类型

根据配置文件分析，支持以下实验配置:

1. **naive_rag**: 基础 RAG (qa_chunk.yml)
2. **zero_shot_cot**: 零样本思维链 (zero_shot_cot.yml)
3. **self_ask**: 自我提问 (self_ask.yml, self_ask_R.yml, self_ask_H-R.yml)
4. **iter_retgen**: 迭代检索生成 (iter_retgen.yml)
5. **ircot**: 检索-思维链交替 (ircot.yml)
6. **atomic_decompose**: 原子分解 (atomic_decompose.yml)
7. **qa_H-R**: 混合推理 (qa_H-R.yml)

## 8. 数据流完整示意图

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Data Source Layer                               │
├─────────────────────────────────────────────────────────────────────────────┤
│  HotpotQA    MuSiQue    NQ    TriviaQA    2Wiki    PopQA    WebQA           │
│     ↓           ↓        ↓        ↓         ↓        ↓        ↓             │
│  [JSON]      [JSONL]  [HF]     [HF]      [JSON]   [HF]     [HF]            │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                       ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Data Adapter Layer                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐                  │
│  │ load_raw_    │    │ format_raw_  │    │ load_title2- │                  │
│  │ data()       │ →  │ data()       │    │ qid()        │                  │
│  └──────────────┘    └──────────────┘    └──────────────┘                  │
│         │                   │                                               │
│         ↓                   ↓                                               │
│  Original Format      Unified Protocol                                      │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                       ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│                          Unified Data Protocol                               │
├─────────────────────────────────────────────────────────────────────────────┤
│  {                                                                          │
│    "id": "uuid",                                                           │
│    "question": "...",                                                       │
│    "answer_labels": [...],                                                  │
│    "question_type": "...",                                                  │
│    "metadata": {                                                            │
│      "supporting_facts": [...],   ← Gold Standard                          │
│      "retrieval_contexts": [...]  ← Retrieval Corpus                       │
│    }                                                                        │
│  }                                                                          │
└─────────────────────────────────────────────────────────────────────────────┘
                                       ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Document Download Layer                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────┐    ┌─────────────────┐                                │
│  │  Wikipedia      │    │  Wikidata       │                                │
│  │  ├─ HTML        │    │  ├─ HTML        │                                │
│  │  ├─ PDF         │    │  ├─ PDF         │                                │
│  │  └─ Markdown    │    │  └─ Markdown    │                                │
│  └─────────────────┘    └─────────────────┘                                │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                       ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│                            Post-Processing Layer                             │
├─────────────────────────────────────────────────────────────────────────────┤
│  retrieval_contexts_as_chunks.py → Chunk Format                             │
│  chunk_by_sentence.py            → Sentence-level Chunks                    │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                       ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│                          Experiment Usage Layer                              │
├─────────────────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐                     │
│  │   QA Test   │    │  Vector     │    │  Evaluation │                     │
│  │   Suite     │ →  │  Store      │ →  │  Metrics    │                     │
│  └─────────────┘    └─────────────┘    └─────────────┘                     │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## 9. 扩展指南

### 9.1 添加新数据集

1. **创建适配器** (`open_benchmarks/dataset_utils/new_dataset.py`):

```python
def load_raw_data(dataset_dir: str, split: str) -> List[dict]:
    # 实现数据加载逻辑
    pass

def format_raw_data(raw: dict) -> Optional[dict]:
    # 实现格式转换逻辑
    return {
        "id": uuid.uuid4().hex,
        "question": raw["question"],
        "answer_labels": raw["answers"],
        "question_type": infer_question_type(raw["answers"]),
        "metadata": {
            "original_id": raw["id"],
            "supporting_facts": [...],
            "retrieval_contexts": [...]
        }
    }
```

2. **注册数据集** (`utils/stats.py`):

```python
DATASET_TO_SPLIT_LIST["new_dataset"] = ["train", "dev", "test"]
```

3. **添加配置** (`config/datasets.yaml`):

```yaml
datasets:
  new_dataset: dev
```

### 9.2 自定义文档源

1. 在 `utils/` 下创建新的下载器模块
2. 实现 `download_all_titles` 函数
3. 更新 `SOURCE_TYPES_TO_DOWNLOAD` 和 `FILE_TYPES_TO_DOWNLOAD`

## 10. 测试数据生成

为方便开发和测试，提供了合成测试数据生成工具：

```python
# 生成单个数据集
python data_process/generate_test_data.py --dataset hotpotqa --num-samples 50

# 生成所有数据集
python data_process/generate_test_data.py --dataset all --num-samples 50

# 验证数据格式
python data_process/validate_test_data.py
```

**特点**:
- 无需下载真实数据集
- 符合统一数据协议
- 支持所有7种数据集格式
- 自动格式验证

## 11. 总结

PIKE-RAG 的数据处理系统采用**适配器模式**将异构数据集转换为统一格式，通过**渐进式采样**确保数据质量，并提供**完善的缓存机制**避免重复下载。该设计具有以下优点：

1. **可扩展性**: 易于添加新数据集
2. **一致性**: 统一的数据协议简化下游处理
3. **效率性**: 缓存机制和增量采样减少重复工作
4. **完整性**: 支持文档下载和多种后处理
