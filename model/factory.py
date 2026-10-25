from abc import ABC, abstractmethod
from typing import Optional, Union
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_core.embeddings import Embeddings
from langchain_core.language_models import BaseChatModel
from utils.config_handler import rag_conf

# 定义基础工厂类
class BaseModelFactory(ABC):
    @abstractmethod
    def generator(self) -> Optional[Union[Embeddings, BaseChatModel]]:
        """
        生成模型实例。
        使用 Union[A, B] 替代 A | B 以确保 Python 3.9 兼容性。
        """
        pass

# 聊天模型工厂
class ChatModelFactory(BaseModelFactory):
    def generator(self) -> Optional[BaseChatModel]:
        # 从 rag_conf 中读取配置
        return ChatOpenAI(
            model=rag_conf["chat_model_name"],
            base_url=rag_conf["base_url"],
            streaming=True
        )

# 嵌入模型工厂
class EmbeddingsFactory(BaseModelFactory):
    def generator(self) -> Optional[Embeddings]:
        return OpenAIEmbeddings(
            model=rag_conf["embedding_model_name"],
            base_url=rag_conf["base_url"],
            # Compatible providers receive text, not OpenAI-specific token IDs.
            check_embedding_ctx_length=False,
        )

# 实例化对象供项目全局使用
chat_model = ChatModelFactory().generator()
embed_model = EmbeddingsFactory().generator()
