"""
智能内容提取器 - 集成失败案例库
================================
基于历史失败案例智能决策是否爬取，自动使用SERP摘要作为fallback
显著提升系统效率和成功率
"""

import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime
import logging

from .content_extractor import ContentExtractor, ExtractionMethod

logger = logging.getLogger(__name__)


class SmartContentExtractor(ContentExtractor):
    """
    智能内容提取器
    集成失败案例库，自动跳过已知失败的URL，使用SERP摘要作为内容
    """
    
    def __init__(self, 
                 firecrawl_api_key: Optional[str] = None,
                 method: ExtractionMethod = ExtractionMethod.AUTO,
                 max_concurrent: int = 10,
                 timeout: int = 60,
                 enable_failure_learning: bool = True,
                 confidence_threshold: float = 0.7):
        """
        初始化智能内容提取器
        
        Args:
            enable_failure_learning: 是否启用失败案例学习
            confidence_threshold: 跳过爬取的置信度阈值
        """
        super().__init__(firecrawl_api_key, method, max_concurrent, timeout)
        # NOTE: failure_learning 功能已移除，简化实现
        self.enable_failure_learning = False  # 强制禁用
        self.confidence_threshold = confidence_threshold
        self.max_concurrent = max_concurrent

        logger.info(f"智能内容提取器初始化完成 (failure_learning已禁用)")
    
    async def __aenter__(self):
        """异步上下文管理器入口"""
        await super().__aenter__()
        # NOTE: failure_db 初始化已移除
        return self
    
    async def smart_extract_content(self,
                                  url: str,
                                  serp_snippet: str = "",
                                  serp_title: str = "",
                                  fallback: bool = True,
                                  include_metadata: bool = True,
                                  force_crawl: bool = False) -> Dict[str, Any]:
        """
        智能内容提取 - 核心方法
        
        Args:
            url: 要提取的URL
            serp_snippet: SERP搜索结果的摘要
            serp_title: SERP搜索结果的标题
            fallback: 是否启用失败回退
            include_metadata: 是否包含元数据
            force_crawl: 强制爬取，忽略失败案例库
        
        Returns:
            提取结果，包含智能决策信息
        """
        start_time = datetime.now()
        
        # 准备SERP fallback内容
        serp_content = self._prepare_serp_content(serp_title, serp_snippet, url)
        
        # 检查是否应该跳过爬取
        should_skip = False
        skip_reason = ""
        confidence = 0.0
        
        if self.enable_failure_learning and self.failure_db and not force_crawl:
            should_skip, skip_reason, confidence = await self.failure_db.should_skip_crawl(url)
        
        if should_skip:
            # 使用SERP摘要作为内容，跳过实际爬取
            logger.info(f"🚀 智能跳过爬取: {skip_reason} (置信度: {confidence:.2f})")
            
            result = {
                'success': True,
                'url': url,
                'content': serp_content,
                'method': 'serp_fallback',
                'is_serp_fallback': True,
                'skip_reason': skip_reason,
                'confidence': confidence,
                'content_length': len(serp_content),
                'extraction_time': (datetime.now() - start_time).total_seconds(),
                'metadata': {
                    'title': serp_title,
                    'snippet': serp_snippet,
                    'intelligent_skip': True
                } if include_metadata else {}
            }
            
            return result
        
        # 正常爬取流程
        logger.debug(f"🔄 执行正常爬取: {url}")
        
        try:
            # 调用父类的提取方法
            result = await super().extract_content(url, fallback, include_metadata)
            
            # 记录成功或失败
            if self.enable_failure_learning and self.failure_db:
                if result['success']:
                    await self.failure_db.record_success(url)
                else:
                    # 提取错误类型和消息
                    error_message = result.get('error', 'Unknown error')
                    failure_type = self._classify_failure_type(error_message, result)
                    await self.failure_db.record_failure(url, failure_type, error_message)
            
            # 如果爬取失败且有SERP内容，使用SERP作为fallback
            if not result['success'] and serp_content and fallback:
                logger.info(f"💡 爬取失败，使用SERP摘要作为fallback: {url}")
                
                result = {
                    'success': True,
                    'url': url,
                    'content': serp_content,
                    'method': 'serp_fallback_after_failure',
                    'is_serp_fallback': True,
                    'original_error': result.get('error', ''),
                    'content_length': len(serp_content),
                    'extraction_time': (datetime.now() - start_time).total_seconds(),
                    'metadata': {
                        'title': serp_title,
                        'snippet': serp_snippet,
                        'fallback_after_failure': True
                    } if include_metadata else {}
                }
            
            # 添加智能提取标记
            result['intelligent_extraction'] = True
            result['failure_learning_enabled'] = self.enable_failure_learning
            
            return result
            
        except Exception as e:
            logger.error(f"智能内容提取异常 {url}: {str(e)}")
            
            # 记录异常
            if self.enable_failure_learning and self.failure_db:
                await self.failure_db.record_failure(url, 'extraction_exception', str(e))
            
            # 如果有SERP内容，使用作为fallback
            if serp_content and fallback:
                logger.info(f"💡 提取异常，使用SERP摘要作为fallback: {url}")
                return {
                    'success': True,
                    'url': url,
                    'content': serp_content,
                    'method': 'serp_fallback_after_exception',
                    'is_serp_fallback': True,
                    'original_exception': str(e),
                    'content_length': len(serp_content),
                    'extraction_time': (datetime.now() - start_time).total_seconds(),
                    'metadata': {
                        'title': serp_title,
                        'snippet': serp_snippet,
                        'fallback_after_exception': True
                    } if include_metadata else {}
                }
            
            # 完全失败
            return {
                'success': False,
                'url': url,
                'error': str(e),
                'content': None,
                'extraction_time': (datetime.now() - start_time).total_seconds()
            }
    
    def _prepare_serp_content(self, title: str, snippet: str, url: str) -> str:
        """准备SERP内容作为fallback"""
        if not title and not snippet:
            return ""
        
        content_parts = []
        
        if title:
            content_parts.append(f"# {title}")
        
        if snippet:
            # 清理和格式化snippet
            cleaned_snippet = snippet.strip()
            if cleaned_snippet:
                content_parts.append(f"\n{cleaned_snippet}")
        
        if url:
            content_parts.append(f"\n\n来源: {url}")
        
        content_parts.append(f"\n\n*注：此内容来源于搜索结果摘要*")
        
        return "\n".join(content_parts)
    
    def _classify_failure_type(self, error_message: str, result: Dict) -> str:
        """分类失败类型"""
        error_lower = error_message.lower()
        
        if '403' in error_message or 'forbidden' in error_lower:
            return 'HTTP_403'
        elif '404' in error_message or 'not found' in error_lower:
            return 'HTTP_404'
        elif '429' in error_message or 'rate limit' in error_lower:
            return 'RATE_LIMITED'
        elif 'timeout' in error_lower:
            return 'TIMEOUT'
        elif 'ssl' in error_lower or 'certificate' in error_lower:
            return 'SSL_ERROR'
        elif 'dns' in error_lower:
            return 'DNS_ERROR'
        elif 'parse' in error_lower or 'extract' in error_lower:
            return 'PARSE_ERROR'
        elif 'connect' in error_lower:
            return 'CONNECTION_ERROR'
        else:
            return 'OTHER'
    
    async def batch_smart_extract(self,
                                 url_data: List[Dict],
                                 fallback: bool = True,
                                 include_metadata: bool = True) -> List[Dict[str, Any]]:
        """
        批量智能内容提取
        
        Args:
            url_data: URL数据列表，每个元素应包含:
                - url: 要提取的URL
                - title: SERP标题 (可选)
                - snippet: SERP摘要 (可选)
        
        Returns:
            提取结果列表
        """
        tasks = []
        
        for item in url_data:
            url = item.get('url', '')
            title = item.get('title', '')
            snippet = item.get('snippet', '')
            
            if url:
                task = self.smart_extract_content(
                    url=url,
                    serp_snippet=snippet,
                    serp_title=title,
                    fallback=fallback,
                    include_metadata=include_metadata
                )
                tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 处理异常
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"批量提取异常 [{i}]: {str(result)}")
                processed_results.append({
                    'success': False,
                    'url': url_data[i].get('url', ''),
                    'error': str(result),
                    'content': None
                })
            else:
                processed_results.append(result)
        
        # 统计信息
        success_count = sum(1 for r in processed_results if r.get('success'))
        serp_fallback_count = sum(1 for r in processed_results if r.get('is_serp_fallback'))
        
        logger.info(f"批量智能提取完成: {success_count}/{len(url_data)} 成功, {serp_fallback_count} 个使用SERP fallback")
        
        return processed_results
    
    async def get_learning_stats(self) -> str:
        """获取学习统计信息"""
        if not self.enable_failure_learning or not self.failure_db:
            return "失败案例学习未启用"
        
        return await self.failure_db.get_stats_report()
    
    async def force_learn_failure(self, url: str, failure_type: str = "MANUAL", 
                                 error_message: str = "手动标记为失败"):
        """手动标记URL为失败案例"""
        if self.enable_failure_learning and self.failure_db:
            await self.failure_db.record_failure(url, failure_type, error_message)
            logger.info(f"手动标记失败案例: {url}")
    
    async def cleanup_old_failures(self, days: int = 30):
        """清理旧的失败记录"""
        if self.enable_failure_learning and self.failure_db:
            await self.failure_db.cleanup_old_records(days)


# 使用示例
async def example_usage():
    """智能内容提取器使用示例"""
    
    async with SmartContentExtractor(enable_failure_learning=True) as extractor:
        
        # 单个URL智能提取
        result = await extractor.smart_extract_content(
            url="https://finance.yahoo.com/quote/TSLA/history/",
            serp_snippet="Tesla stock price history and chart data",
            serp_title="Tesla, Inc. (TSLA) Stock Price History"
        )
        
        if result['success']:
            print(f"提取成功: 方法={result['method']}, 长度={result['content_length']}")
            if result.get('is_serp_fallback'):
                print("使用了SERP摘要作为内容")
        
        # 批量智能提取
        url_data = [
            {
                'url': 'https://www.nasdaq.com/market-activity/stocks/tsla',
                'title': 'TSLA Stock Price',
                'snippet': 'Tesla stock price and market data'
            },
            {
                'url': 'https://finance.yahoo.com/quote/TSLA/',
                'title': 'Tesla Stock',
                'snippet': 'Real-time Tesla stock price and analysis'
            }
        ]
        
        batch_results = await extractor.batch_smart_extract(url_data)
        
        print(f"批量提取完成: {len(batch_results)} 个结果")
        for i, result in enumerate(batch_results):
            print(f"  {i+1}. {result['url'][:50]}... -> {'成功' if result['success'] else '失败'}")
        
        # 获取学习统计
        stats = await extractor.get_learning_stats()
        print(f"\n学习统计:\n{stats}")


if __name__ == "__main__":
    asyncio.run(example_usage())