# PIKE-RAG 数据协议速查表

## 1. 统一数据格式

```json
{
    "id": "uuid-string",
    "question": "问题文本",
    "answer_labels": ["答案1", "答案2"],
    "question_type": "yes_no | undefined",
    "metadata": {
        "original_id": "原始ID",
        "supporting_facts": [...],    // 支持事实（金标准）
        "retrieval_contexts": [...]   // 检索上下文
    }
}
```

## 2. Supporting Facts 格式

```json
{
    "type": "wikipedia | wikidata | BingSearch",
    "title": "文档标题",
    "contents": "支持事实内容"
}
```

## 3. Retrieval Contexts 格式

```json
{
    "type": "wikipedia | wikidata | BingSearch",
    "title": "文档标题",
    "contents": "完整文档内容"
}
```

## 4. 支持的数据集

| 数据集 | 来源 | 特点 |
|--------|------|------|
| **HotpotQA** | CMU JSON | 多跳问答，bridge/comparison 类型 |
| **MuSiQue** | Google Drive | 多文档推理，question_decomposition |
| **NQ** | HuggingFace | HTML解析，yes_no_answer 标记 |
| **TriviaQA** | HuggingFace | Bing搜索结果，entity_pages |
| **2Wiki** | Dropbox | Wikidata推理链，evidences字段 |
| **PopQA** | HuggingFace | Wikidata实体，subj/prop/obj |
| **WebQA** | HuggingFace | 简单URL提取 |

## 5. 处理流程

```
原始数据 → load_raw_data() → format_raw_data() → JSONL文件 → sample_datasets() → 子集+文档
```

## 6. 关键函数

| 函数 | 模块 | 功能 |
|------|------|------|
| `load_raw_data()` | dataset_utils/{name}.py | 加载原始数据 |
| `format_raw_data()` | dataset_utils/{name}.py | 格式转换 |
| `reformat_dataset()` | reformat_dataset.py | 批量转换 |
| `sample_datasets()` | sample_dataset.py | 采样+下载 |
| `infer_question_type()` | question_type.py | 问题类型推断 |

## 7. 配置参数

```yaml
root_save_dir: data                    # 数据保存目录
running_modes:
  build_split: True                    # 构建分割文件
  sample_sets: True                    # 采样与下载
datasets:
  hotpotqa: dev
  musique: dev
sample_size_list: [100, 200, 500]     # 采样大小
seed: 223                              # 随机种子
```

## 8. 文档下载

| 类型 | 格式 | 路径 |
|------|------|------|
| Wikipedia | HTML, PDF | `{root}/documents/wikipedia/{html,pdf}/` |
| Wikidata | HTML, PDF | `{root}/documents/wikidata/{html,pdf}/` |

## 9. 输出文件结构

```
data/
├── {dataset}/
│   ├── {split}.jsonl              # 完整分割
│   ├── {split}_{n}.jsonl          # 采样子集
│   └── raw/                       # 原始数据
└── documents/
    ├── wikipedia/
    │   ├── html/
    │   └── pdf/
    └── wikidata/
        ├── html/
        └── pdf/
```

## 10. 缓存文件

- `doc_title_type_to_location.json`: 文档路径映射
- `wiki_title_type_to_validation_status.json`: 验证状态

## 11. 扩展新数据集

```python
# 1. 创建 dataset_utils/new_dataset.py
def load_raw_data(dataset_dir, split):
    return raw_data_list

def format_raw_data(raw):
    return {
        "id": uuid.uuid4().hex,
        "question": raw["question"],
        "answer_labels": raw["answers"],
        "question_type": infer_question_type(raw["answers"]),
        "metadata": {
            "supporting_facts": [...],
            "retrieval_contexts": [...]
        }
    }

# 2. 注册到 utils/stats.py
DATASET_TO_SPLIT_LIST["new_dataset"] = ["train", "dev"]
```

## 12. 测试数据生成

```bash
# 生成单个数据集
python data_process/generate_test_data.py --dataset hotpotqa --num-samples 50

# 生成所有数据集
python data_process/generate_test_data.py --dataset all --num-samples 50

# 验证格式
python data_process/validate_test_data.py
```
