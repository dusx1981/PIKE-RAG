# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.
import json
import pickle
from typing import List, Literal, Tuple

from datasets import load_dataset, Dataset
from tqdm import tqdm

from langchain_core.documents import Document

from pikerag.utils.walker import list_files_recursively
from pikerag.workflows.common import MultipleChoiceQaData

def read_jsonl_file(file_path):
    """
    从本地 JSONL 文件中读取数据
    
    参数:
        file_path (str): JSONL 文件路径
        
    返回:
        list: 包含所有解析后的 JSON 对象的列表
    """
    data = []
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            for line in file:
                line = line.strip()  # 去除空白字符
                if line:  # 跳过空行
                    try:
                        item = json.loads(line)
                        data.append(item)
                    except json.JSONDecodeError as e:
                        print(f"JSON 解析错误 (行内容: {line[:50]}...): {e}")
                        continue
        return data
    except FileNotFoundError:
        print(f"错误: 文件 '{file_path}' 不存在")
        return []
    except Exception as e:
        print(f"读取文件时发生错误: {e}")
        return []


def load_testing_suite(path: str="cais/mmlu", name: str="college_biology") -> List[MultipleChoiceQaData]:
    # dataset: Dataset = load_dataset(path, name)["test"]
    dataset = read_jsonl_file(path + name)
    testing_suite: List[dict] = []
    for qa in dataset:
        testing_suite.append(
            MultipleChoiceQaData(
                question=qa["question"],
                metadata={
                    "subject": qa["subject"],
                },
                options={
                    chr(ord('A') + i): choice
                    for i, choice in enumerate(qa["choices"])
                },
                answer_mask_labels=[chr(ord('A') + qa["answer"])],
            )
        )
    return testing_suite


def load_ids_and_chunks(chunk_file_dir: str) -> Tuple[Literal[None], List[Document]]:
    chunks: List[Document] = []
    chunk_idx: int = 0
    for doc_name, doc_path in tqdm(
        list_files_recursively(directory=chunk_file_dir, extensions=["pkl"]),
        desc="Loading Files",
    ):
        with open(doc_path, "rb") as fin:
            chunks_in_file: List[Document] = pickle.load(fin)

        for doc in chunks_in_file:
            doc.metadata.update(
                {
                    "filename": doc_name,
                    "chunk_idx": chunk_idx,
                }
            )
            chunk_idx += 1

        chunks.extend(chunks_in_file)

    return None, chunks
