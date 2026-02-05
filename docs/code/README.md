# PIKE-RAG 数据处理技术文档索引

本目录包含 PIKE-RAG 数据生成逻辑的完整技术文档。

## 文档清单

### 核心文档

1. **[data_process_analysis.md](./data_process_analysis.md)** (656行)
   - 数据处理的完整技术文档
   - 涵盖整体架构、数据协议、核心模块详解
   - 包含数据流示意图和扩展指南

2. **[data_protocol_cheatsheet.md](./data_protocol_cheatsheet.md)** (144行)
   - 数据协议速查表
   - 快速参考统一数据格式、字段说明
   - 常用命令和配置参数

3. **[dataset_adapters_detail.md](./dataset_adapters_detail.md)** (547行)
   - 7个数据集适配器的详细说明
   - 每个数据集的原始格式、处理逻辑、关键注意点
   - 包含完整的代码示例

## 快速开始

### 1. 了解整体架构
阅读 [data_process_analysis.md](./data_process_analysis.md) 的第1-5章

### 2. 查看数据格式
阅读 [data_protocol_cheatsheet.md](./data_protocol_cheatsheet.md)

### 3. 了解特定数据集
阅读 [dataset_adapters_detail.md](./dataset_adapters_detail.md) 的对应章节

### 4. 扩展新数据集
阅读 [data_process_analysis.md](./data_process_analysis.md) 的第9章"扩展指南"

## 文档结构图

```
docs/code/
├── data_process_analysis.md          # 完整技术文档 (主文档)
│   ├── 1. 概述
│   ├── 2. 整体架构
│   ├── 3. 数据格式协议
│   ├── 4. 核心模块详解
│   ├── 5. 文档下载系统
│   ├── 6. 后处理工具
│   ├── 7. Examples中的数据使用
│   ├── 8. 数据流完整示意图
│   ├── 9. 扩展指南
│   └── 10. 测试数据生成
│
├── data_protocol_cheatsheet.md       # 速查表 (快速参考)
│   ├── 统一数据格式
│   ├── 关键函数
│   ├── 配置参数
│   └── 输出文件结构
│
└── dataset_adapters_detail.md        # 适配器详情
    ├── HotpotQA 详解
    ├── MuSiQue 详解
    ├── Natural Questions 详解
    ├── TriviaQA 详解
    ├── 2WikiMultiHopQA 详解
    ├── PopQA 详解
    └── WebQA 详解
```

## 相关代码文件

- `data_process/main.py` - 主入口
- `data_process/open_benchmarks/reformat_dataset.py` - 数据格式转换
- `data_process/open_benchmarks/sample_dataset.py` - 数据采样与下载
- `data_process/open_benchmarks/dataset_utils/` - 数据集适配器
- `data_process/open_benchmarks/utils/` - 工具模块

## 测试工具

- `data_process/generate_test_data.py` - 生成合成测试数据
- `data_process/validate_test_data.py` - 验证数据格式

## 其他相关文档

本目录还包含其他技术文档：

- `QaWorkflow.md` - QA工作流分析
- `QaSelfAskWorkflow.md` - SelfAsk工作流分析
- `评估流程分析.md` - 评估流程详解
- `分块流程整理.md` - 分块流程说明
- `tag_protocal.md` - 标注协议说明

---

**最后更新**: 2025-02-05
