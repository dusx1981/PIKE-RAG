# 如何运行MuSiQue示例

这份文档将一步步介绍如何运行MuSiQue示例。要在HotpotQA、2WikiMultiHopQA等公开基准测试上运行实验，步骤与此处列出的类似。请参考本文档并做出相应修改。

## **第一步：测试集准备**

对于MuSiQue这类公开基准测试，我们已经准备了预处理脚本，运行现有脚本即可完成测试集准备。文件 `data_process/open_benchmarks/config/musique.yml` 展示了MuSiQue数据集处理的示例设置。如果你想尝试其他公开基准测试，建议的数据集划分设置可以在文件 `data_process/open_benchmarks/config/datasets.yaml` 中找到。

假设你位于PIKE-RAG的根目录：

```sh
# 安装预处理所需的库
pip install -r data_process/open_benchmarks/requirements.txt

# 运行脚本以下载MuSiQue、采样子集、转换格式
python data_process/main.py data_process/open_benchmarks/config/musique.yml
```

脚本运行完成后，你可以在 `data/musique/` 目录下找到预处理好的数据。具体来说，采样后的数据集是 `data/musique/dev_500.jsonl`。

**如果只想运行MuSiQue，请跳过下面的部分，直接转到第三步。**

需要注意的是，我们仅为有限的特定数据集（列于 `data_process/open_benchmarks/dataset_utils/` 中）提供了预处理工具。要预处理其他数据集，你可以参考这些工具函数添加自己的工具。

此外，要在特定领域进行测试，你需要将测试数据预处理成以下格式，以便重用我们在MuSiQue示例中提供的加载工具函数（或者为你的测试数据编写特定的加载工具函数，并在运行问答脚本时修改设置）。默认的测试套件文件应该是一个 `jsonlines` 文件，每一行表示一个问题的字典。生成式问答的必需字段包含 `"question"`（类型：str）（以及如果需要自动评估，则需 `"answer_labels"`（类型：List[str]））。对于选择题问答，`"answer_mask_labels"`（类型：List[str]）是必需的，而评估则需要 `"answer_masks"`（类型：List[str]）。除此之外，你可以在 `"metadata"`（类型：dict）字段中维护一些其他元数据，就像我们对公开基准测试所做的那样。具体来说，一个通用的生成式问答格式如下：

```python
{
    "question": "必需，str。要回答的问题",
    "id": "可选，str。此问题的ID。例如 'Q001'，便于引用。",
    "answer_labels": [
        "类型：List[str]",
        "自动评估流程所需",
        "长度可以是1个或多个",
        "用于计算指标的答案标签",
    ],
    "question_type": "可选，str。如果适用的问题类型。可设置为 'undefined'",
    "metadata": {
        "meta_key": "可选。任何其他元信息",
    },
}
```

## **第二步：原始文档预处理（可选）**

**如果只想运行MuSiQue，请跳过此步骤，直接转到第三步。**

有时候，性能与原始文档的预处理方式高度相关。在原始文档格式为多模态（如PDF文档）且你的应用追求极致性能的场景下，我们建议你利用文档智能（DI）工具（例如 [Azure AI Document Intelligence](https://azure.microsoft.com/en-us/products/ai-services/ai-document-intelligence)）来预处理原始文档。

目前，我们尚未在PIKE-RAG中提供集成DI工具的脚本或组件。请根据你的需求构建DI预处理流程。

## **第三步：将原始文档分割成文本块**

为了重现[技术报告](https://arxiv.org/abs/2501.11551)中的实验，**不需要**运行分块脚本。相反，我们从这些公开基准测试中提取上下文段落，并将它们聚合在一起作为参考块池。文件 `data_process/retrieval_contexts_as_chunks.py` 展示了如何提取上下文段落的示例。

假设你位于PIKE-RAG的根目录：

```sh
# 运行脚本从QA数据中提取上下文段落。
python data_process/retrieval_contexts_as_chunks.py
```

脚本运行完成后，你可以在 `data/musique/` 目录下找到文件 `dev_500_retrieval_contexts_as_chunks.jsonl`。

**如果只想运行MuSiQue，请跳过下面的部分，直接转到第四步。**

文件 `examples/biology/configs/chunking.yml` 是一个示例YAML配置，用于利用上下文感知的文档分块将markdown文件分割成块。要运行此类分块任务，你可以根据需要修改配置并运行命令：

```sh
# 读入文档并将其分割成块。
python examples/chunking.py 你的YAML配置文件路径
```

如果你想使用不调用LLM模型的轻量级分割器，我们也提供了 `RecursiveSentenceSplitter`。你可以在YAML配置文件中修改 `splitter` 设置部分来使用它：

```yaml
splitter:
    module_path: pikerag.document_transformers
    class_name: RecursiveSentenceSplitter
    args:
        ...  # 根据你的需要进行配置
```

我们还支持现有的第三方分割器，例如 `langchain.text_splitter.TextSplitter`。要使用它，请修改YAML配置文件：

```yaml
splitter:
    module_path: langchain.text_splitter
    class_name: TextSplitter
    args:
        ...  # 根据你的需要进行配置
```

## **第四步：原子问题标注（可选）**

在当前的发布版本和这个MuSiQue示例中，我们展示了一种蒸馏方法——原子问题标注。要为MuSiQue样本集标注原子问题，假设你位于PIKE-RAG的根目录：

```sh
python examples/tagging.py examples/musique/configs/tagging.yml
```

运行完成后，你可以在 `data/musique/` 目录下找到文件 `dev_500_retrieval_contexts_as_chunks_with_atom_questions.jsonl`。

## **第五步：问答**

对于包含 `answer_labels` 的测试集，评估可以与问答同时进行。要在MuSiQue上运行基于已标注原子问题的检索，假设你位于PIKE-RAG的根目录：

```sh
python examples/qa.py examples/musique/configs/atomic_decompose.yml
```

运行完成后，你可以在文件 `logs/musique/atomic_decompose/atomic_decompose.jsonl` 中找到答案数据，其中每一行对应一个QA `dict` 数据，包含一个新的 `answer`（类型：str）字段和一个 `answer_metadata`（类型：dict）字段。

如果你想测试不同的算法，可以在工作流中调整答案流并在YAML文件中进行配置。如果你的测试套件中还没有准备好 `answer_labels`，你可以简单地移除YAML配置文件中的 `evaluator` 部分，以运行不进行评估的问答。

## **第六步：仅进行评估（可选）**

**如果只想运行MuSiQue，请跳过下面的部分。**

要为符合PIKE-RAG生成格式的答案日志 `jsonlines` 文件运行评估工作流，请修改 `examples/evaluate.yml` 文件或参考它创建一个新文件，假设你位于PIKE-RAG的根目录：

```sh
python examples/evaluate.py examples/evaluate.yml
```

---

## **详细解释与流程梳理**

这份文档是**运行PIKE-RAG项目MuSiQue实验的官方、权威指南**，直接回答了之前你关于`dev_500.jsonl`等数据集文件如何获取的问题。以下是文档核心内容的梳理和解释：

### **📁 第一步：解决你的核心疑问——数据从何而来？**

这是最关键的一步。你之前寻找的 `data/musique/dev_500.jsonl` 文件，**并非需要手动下载，而是通过运行项目提供的预处理脚本自动生成的**。

**具体操作与输出**：
```bash
python data_process/main.py data_process/open_benchmarks/config/musique.yml
```
- **作用**：该脚本会自动从官方源头**下载原始MuSiQue数据集**，然后进行**采样**（例如，抽取500条作为开发集 `dev_500`），并**转换**为项目内部使用的标准`jsonlines`格式。
- **结果**：在 `data/musique/` 目录下生成 `dev_500.jsonl` 文件。

### **🔄 完整实验工作流总览**

整个流程是一个典型的RAG系统构建与评估流水线，下图清晰地展示了各步骤的输入、输出与依赖关系：

```mermaid
flowchart TD
    A[“第一步: 测试集准备<br>运行预处理脚本”] -->|生成| B[“核心测试文件<br>data/musique/dev_500.jsonl”]
    
    B --> C[“第三步: 构建知识库<br>提取上下文为文本块”]
    C -->|生成| D[“知识库源文件<br>dev_500_retrieval_contexts_as_chunks.jsonl”]
    
    D --> E[“第四步: 知识增强<br>原子问题标注 (可选)”]
    E -->|生成| F[“增强知识库文件<br>..._with_atom_questions.jsonl”]
    
    F --> G[“第五步: 问答与评估<br>运行主实验脚本”]
    G -->|使用配置| H[“实验配置文件<br>atomic_decompose.yml”]
    G -->|生成结果与日志| I[“答案文件<br>logs/musique/.../atomic_decompose.jsonl”]
```

下面，我们对图中的关键步骤进行详细拆解：

### **第三步与第四步：构建与增强“知识库”**
这两个步骤的目标是**为RAG系统准备检索所用的“知识库”**。

1.  **第三步：提取上下文作为文本块**
    - **命令**：`python data_process/retrieval_contexts_as_chunks.py`
    - **原理**：直接从MuSiQue数据集的每个问题所附带的“支持段落”中，提取出所有唯一的上下文文本。这些文本块（chunks）就是后续检索的直接对象。
    - **输出**：`dev_500_retrieval_contexts_as_chunks.jsonl`。这个文件正是你在 `atomic_decompose.yml` 配置的 `retriever` 部分看到的源文件。

2.  **第四步：原子问题标注（PIKE-RAG的核心技术之一）**
    - **命令**：`python examples/tagging.py examples/musique/configs/tagging.yml`
    - **原理**：利用LLM，为第三步生成的每个文本块**自动生成多个细粒度的“原子问题”**。这些原子问题就像给知识块贴上了多种“提问方式”的标签，极大地提升了检索系统对用户复杂问题的理解能力和命中率。
    - **输出**：`dev_500_retrieval_contexts_as_chunks_with_atom_questions.jsonl`。这个文件在原有文本块基础上，增加了 `atom_questions` 字段。你的配置文件正是使用了这个增强版的知识库。

### **第五步：运行核心实验**
这是最终环节，启动你之前深入研究的那个复杂问答流水线。

- **命令**：`python examples/qa.py examples/musique/configs/atomic_decompose.yml`
- **过程**：
    1.  加载你配置的 `QaDecompositionWorkflow`。
    2.  读取测试集 (`dev_500.jsonl`)。
    3.  对于每个复杂问题，使用LLM（如GPT-4）将其**分解为原子问题**。
    4.  利用 `ChunkAtomRetriever`，既在文本块中检索，也在原子问题中检索，**双重检索**相关信息。
    5.  组织检索结果，合成最终答案。
    6.  根据 `evaluator` 配置，将答案与标准答案 (`answer_labels`) 对比，自动计算各项评分。
- **输出**：完整的答案、模型推理过程以及评估指标，保存在 `logs/` 目录下。

### **💡 关键提示与关联**
- **跳过可选步骤**：文档明确指出，如果只想重现论文中的MuSiQue基准测试结果，可以**跳过第二步（原始文档预处理）和第六步（单独评估）**。
- **与你之前工作的关联**：你之前分析的 `atomic_decompose.yml` 配置文件，正是**第五步**要使用的核心文件。你现在已经彻底明白了该配置中每个数据路径（如 `dev_500.jsonl`, `...with_atom_questions.jsonl`）的来源和生成方式。
- **通用性**：这个流程是模块化的。如果你想在其他数据集（如HotpotQA）或自己的数据上运行，只需修改相应的配置文件和数据路径即可。

总结来说，这份指南为你提供了从零开始运行PIKE-RAG实验的完整路线图。你现在可以按照 **第一步 -> 第三步 -> 第四步 -> 第五步** 的顺序，依次执行命令，来完整重现MuSiQue上的“原子问题分解”实验。如果在执行任何一步时遇到具体问题（例如环境依赖、脚本报错），可以随时提问。