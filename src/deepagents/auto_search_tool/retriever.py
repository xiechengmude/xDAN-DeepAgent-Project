"""
RAGFlow检索器
"""
from typing import List, Optional, Dict
from dataclasses import dataclass
import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
import os
import logging
from contextlib import contextmanager

logger = logging.getLogger(__name__)


@dataclass
class DocumentInfo:
    """文档信息"""
    doc_id: str
    content: str
    source: str = ""
    similarity: float = 0.0
    metadata: Optional[Dict] = None


class RAGFlowRetriever:
    """RAGFlow检索器 - 支持连接池和资源管理"""
    
    def __init__(self, api_url: str, api_key: str, dataset_id: str, 
                 min_similarity: float = 0.5, vector_similarity_weight: float = 0.3):
        # 使用环境变量中的 RAGFlow 配置
        self.api_url = os.getenv("RAGFLOW_API_URL", api_url)
        self.api_key = os.getenv("RAGFLOW_API_KEY", api_key)
        self.dataset_id = os.getenv("DEFAULT_DATASET_ID", dataset_id)
        self.min_similarity = min_similarity  # DRY原则：配置化相似度阈值
        self.vector_similarity_weight = vector_similarity_weight  # 向量相似度权重
        
        # 创建会话和连接池
        self.session = self._create_session()
    
    def _create_session(self) -> requests.Session:
        """创建带有连接池和重试机制的会话"""
        session = requests.Session()
        session.trust_env = False  # 禁用环境代理
        
        # 配置重试策略
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST"]
        )
        
        # 配置适配器和连接池
        adapter = HTTPAdapter(
            max_retries=retry_strategy,
            pool_connections=10,  # 连接池大小
            pool_maxsize=10,      # 最大连接数
            pool_block=False      # 不阻塞等待连接
        )
        
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        # 设置默认超时
        session.timeout = 30
        
        return session
    
    def __enter__(self):
        """上下文管理器入口"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口 - 清理资源"""
        self.close()
    
    def close(self):
        """关闭会话和连接"""
        if hasattr(self, 'session') and self.session:
            self.session.close()
    
    def search(self, query: str, dataset_ids: Optional[List[str]] = None, limit: int = 10, mode: str = "hybrid") -> List[DocumentInfo]:
        """
        使用RAGFlow API搜索文档
        
        Args:
            query: 查询字符串
            dataset_ids: 数据集ID列表，如果为None则使用默认数据集
            limit: 返回结果数量限制
            mode: 搜索模式 - "precision"(精准搜索) | "semantic"(语义搜索) | "hybrid"(混合搜索)
            
        Returns:
            List[DocumentInfo]: 文档信息列表
        """
        try:
            if dataset_ids is None:
                dataset_ids = [self.dataset_id] if self.dataset_id else []
            
            url = f"{self.api_url}/api/v1/retrieval"
            
            # 详细日志记录
            logger.info(f"RAGFlow search called:")
            logger.info(f"  Query: {query}")
            logger.info(f"  Dataset IDs: {dataset_ids}")
            logger.info(f"  Limit: {limit}")
            logger.info(f"  Min similarity: {self.min_similarity}")
            logger.info(f"  API URL: {url}")
            logger.info(f"  Using proxy: {os.environ.get('http_proxy', 'None')}")
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            # 根据搜索模式配置参数
            if mode == "precision":
                # 精准搜索：使用纯向量搜索效果更好
                data = {
                    "question": query,
                    "dataset_ids": dataset_ids,
                    "page": 1,
                    "size": limit,  # 修正：使用正确的参数名 size
                    "similarity_threshold": 0.1,  # 修正：更低的相似度阈值
                    "vector_similarity_weight": 1.0,  # 纯向量搜索
                    "top_k": 1024,
                    "rerank_id": None,
                    "keyword": False  # 关闭关键词搜索（避免干扰）
                }
            elif mode == "semantic":
                # 语义搜索：强调语义理解
                data = {
                    "question": query,
                    "dataset_ids": dataset_ids,
                    "page": 1,
                    "size": limit,  # 修正：使用正确的参数名 size
                    "similarity_threshold": 0.3,  # 修正：中等相似度阈值
                    "vector_similarity_weight": 0.7,  # 更高的向量权重
                    "top_k": 1024,
                    "rerank_id": None,
                    "keyword": True
                }
            else:
                # 默认混合搜索
                data = {
                    "question": query,
                    "dataset_ids": dataset_ids,
                    "page": 1,
                    "size": limit,  # 修正：使用正确的参数名 size
                    "similarity_threshold": self.min_similarity,  # 修正
                    "vector_similarity_weight": self.vector_similarity_weight,
                    "top_k": 1024,
                    "rerank_id": None,
                    "keyword": True
                }
            
            # 使用会话发送请求，自动管理连接，显式禁用代理
            response = self.session.post(url, json=data, headers=headers, timeout=30, proxies={"http": None, "https": None})
            logger.info(f"  Response status: {response.status_code}")
            logger.info(f"  Response headers: {dict(response.headers)}")
            
            if response.status_code != 200:
                logger.error(f"RAGFlow API error: {response.status_code} - {response.text}")
                return []
            
            result = response.json()
            
            # RAGFlow API响应格式：直接在data.chunks中返回结果
            if result.get("code") == 0:
                chunks = result.get("data", {}).get("chunks", [])
            else:
                # 如果没有data结构，检查是否直接返回chunks
                chunks = result.get("chunks", [])
            
            # 转换文档（API已过滤，客户端只需转换）
            documents = [
                DocumentInfo(
                    doc_id=str(chunk.get("chunk_id", chunk.get("id", ""))),
                    content=chunk.get("content", ""),
                    source=chunk.get("document_keyword", chunk.get("doc_name", "")),
                    similarity=float(chunk.get("similarity", 0.0))
                )
                for chunk in chunks
            ]
            
            # 排序并限制数量
            documents.sort(key=lambda x: x.similarity, reverse=True)
            return documents[:limit]
            
        except Exception as e:
            logger.error(f"RAGFlow search error: {e}")
            return []