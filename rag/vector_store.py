from langchain_chroma import Chroma
from chromadb.config import Settings
from langchain_core.documents import Document
from utils.config_handler import chroma_conf
from model.factory import embed_model
from langchain_text_splitters import RecursiveCharacterTextSplitter
from utils.path_tool import get_abs_path
from utils.file_handler import pdf_loader, txt_loader, listdir_with_allowed_type, get_file_md5_hex
from utils.logger_handler import logger
import os
import re


class VectorStoreService:
    def __init__(self):
        self.vector_store = Chroma(
            collection_name=chroma_conf["collection_name"],
            embedding_function=embed_model,
            persist_directory=get_abs_path(chroma_conf["persist_directory"]),
            client_settings=Settings(anonymized_telemetry=False),
        )

        self.spliter = RecursiveCharacterTextSplitter(
            chunk_size=chroma_conf["chunk_size"],
            chunk_overlap=chroma_conf["chunk_overlap"],
            separators=chroma_conf["separators"],
            length_function=len,
        )

    def split_qa(self, text: str, metadata=None):
        parts = re.split(r"(?m)(?=^\s*\d+\.\s)", text)

        docs = []
        for p in parts:
            p = p.strip()
            if p:
                # Keep source/page provenance for FAQ chunks as well as prose.
                docs.append(Document(page_content=p, metadata=dict(metadata or {})))

        return docs

    def looks_like_faq(self, text: str) -> bool:
        matches = re.findall(r"(?m)^\s*\d+\.\s", text)
        return len(matches) >= 5

    def get_retriever(self):
        return self.vector_store.as_retriever(search_kwargs={"k": chroma_conf["k"]})

    def smart_split_documents(self,documents, recursive_splitter):
        """
        根据文档结构自动选择切分策略
        """
        final_docs = []

        for doc in documents:
            text = doc.page_content

            if self.looks_like_faq(text):
                # FAQ 结构：按 QA 切
                faq_docs = self.split_qa(text, doc.metadata)
                final_docs.extend(faq_docs)

            else:
                # 普通文本：用你原来的 splitter
                split_docs = recursive_splitter.split_documents([doc])
                final_docs.extend(split_docs)

        return final_docs

    def load_document(self):
        """
        从数据文件夹内读

          据文件，转为向量存入向量库
        要计算文件的MD5做去重
        :return: None
        """

        stats = {"indexed_files": 0, "skipped_files": 0, "failed_files": 0, "chunks": 0}

        def check_md5_hex(md5_for_check: str):
            if not os.path.exists(get_abs_path(chroma_conf["md5_hex_store"])):
                # 创建文件
                open(get_abs_path(chroma_conf["md5_hex_store"]), "w", encoding="utf-8").close()
                return False            # md5 没处理过

            with open(get_abs_path(chroma_conf["md5_hex_store"]), "r", encoding="utf-8") as f:
                for line in f.readlines():
                    line = line.strip()
                    if line == md5_for_check:
                        return True     # md5 处理过

                return False            # md5 没处理过

        def save_md5_hex(md5_for_check: str):
            with open(get_abs_path(chroma_conf["md5_hex_store"]), "a", encoding="utf-8") as f:
                f.write(md5_for_check + "\n")

        def get_file_documents(read_path: str):
            if read_path.endswith("txt"):
                return txt_loader(read_path)

            if read_path.endswith("pdf"):
                return pdf_loader(read_path)

            return []

        allowed_files_path: list[str] = listdir_with_allowed_type(
            get_abs_path(chroma_conf["data_path"]),
            tuple(chroma_conf["allow_knowledge_file_type"]),
        )

        for path in allowed_files_path:
            # 获取文件的MD5
            md5_hex = get_file_md5_hex(path)

            if check_md5_hex(md5_hex):
                logger.info(f"[加载知识库]{path}内容已经存在知识库内，跳过")
                stats["skipped_files"] += 1
                continue

            try:
                documents: list[Document] = get_file_documents(path)

                if not documents:
                    logger.warning(f"[加载知识库]{path}内没有有效文本内容，跳过")
                    stats["skipped_files"] += 1
                    continue

                split_document = self.smart_split_documents(documents, self.spliter)


                if not split_document:
                    logger.warning(f"[加载知识库]{path}分片后没有有效文本内容，跳过")
                    stats["skipped_files"] += 1
                    continue

                # 将内容存入向量库
                self.vector_store.add_documents(split_document)

                # 记录这个已经处理好的文件的md5，避免下次重复加载
                save_md5_hex(md5_hex)
                stats["indexed_files"] += 1
                stats["chunks"] += len(split_document)

                logger.info(f"[加载知识库]{path} 内容加载成功")
            except Exception as e:
                # exc_info为True会记录详细的报错堆栈，如果为False仅记录报错信息本身
                logger.error(f"[加载知识库]{path}加载失败：{str(e)}", exc_info=True)
                stats["failed_files"] += 1
                continue

        return stats


if __name__ == '__main__':
    vs = VectorStoreService()

    vs.load_document()

    retriever = vs.get_retriever()

    res = retriever.invoke("定时清扫")
    for r in res:
        print(r.page_content)
        print("-"*20)
