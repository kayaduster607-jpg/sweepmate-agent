"""Exercise actual Chroma indexing and RAG prompt assembly with fake embeddings."""

from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
from langchain_core.documents import Document
from langchain_core.embeddings import DeterministicFakeEmbedding
from langchain_core.runnables import RunnableLambda
from model.factory import embed_model
from rag import vector_store as vector_module
from rag import rag_service
from utils.file_handler import listdir_with_allowed_type


class RagTests(unittest.TestCase):
    def test_compatible_embedding_provider_receives_text(self):
        self.assertFalse(embed_model.check_embedding_ctx_length)

    def test_faq_chunk_keeps_source_metadata(self):
        service = object.__new__(vector_module.VectorStoreService)
        text = "\n".join(f"{i}. question {i}\nanswer {i}" for i in range(1, 7))
        result = service.smart_split_documents(
            [Document(page_content=text, metadata={"source": "synthetic.txt", "page": 2})], Mock())
        self.assertEqual(len(result), 6)
        self.assertTrue(all(doc.metadata == {"source": "synthetic.txt", "page": 2} for doc in result))

    def test_plain_text_uses_the_recursive_splitter(self):
        service = object.__new__(vector_module.VectorStoreService)
        splitter = Mock()
        splitter.split_documents.return_value = [Document(page_content="part")]
        result = service.smart_split_documents([Document(page_content="ordinary prose")], splitter)
        self.assertEqual(result[0].page_content, "part")
        splitter.split_documents.assert_called_once()

    def test_missing_directory_does_not_return_fake_file_names(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(listdir_with_allowed_type(str(Path(directory) / "missing"), ("txt", "pdf")), ())

    def test_actual_chroma_ingest_deduplicates_and_retrieves(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as directory:
            root = Path(directory)
            knowledge = root / "knowledge"
            knowledge.mkdir()
            (knowledge / "faq.txt").write_text("\n".join(
                f"{i}. Synthetic question {i}\nSynthetic answer {i}" for i in range(1, 7)), encoding="utf-8")
            config = dict(vector_module.chroma_conf, data_path=str(knowledge),
                          persist_directory=str(root / "chroma"), md5_hex_store=str(root / "hashes.txt"),
                          collection_name="synthetic_tests")
            with patch.object(vector_module, "chroma_conf", config), patch.object(
                vector_module, "embed_model", DeterministicFakeEmbedding(size=16)):
                service = vector_module.VectorStoreService()
                first = service.load_document()
                second = service.load_document()
                hits = service.get_retriever().invoke("Synthetic question 1")
                self.assertEqual(first["chunks"], 6)
                self.assertEqual(first["failed_files"], 0)
                self.assertEqual(second["skipped_files"], 1)
                self.assertEqual(service.vector_store._collection.count(), 6)
                self.assertEqual(len(hits), 3)
                self.assertTrue(all(hit.metadata["source"].endswith("faq.txt") for hit in hits))

    def test_rag_chain_receives_question_and_retrieved_evidence(self):
        seen = []
        def summarize(prompt):
            seen.append(prompt.to_string())
            return "synthetic summary"

        retriever = Mock()
        retriever.invoke.return_value = [Document(page_content="SYNTHETIC_EVIDENCE", metadata={"source": "demo.txt"})]
        store = Mock()
        store.get_retriever.return_value = retriever
        with patch.object(rag_service, "VectorStoreService", return_value=store), patch.object(
            rag_service, "chat_model", RunnableLambda(summarize)):
            service = rag_service.RagSummarizeService()
            result = service.rag_summarize("SYNTHETIC_QUESTION")
        self.assertEqual(result, "synthetic summary")
        self.assertIn("SYNTHETIC_QUESTION", seen[0])
        self.assertIn("SYNTHETIC_EVIDENCE", seen[0])
        self.assertIn("demo.txt", seen[0])
