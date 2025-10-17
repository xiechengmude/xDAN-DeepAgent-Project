"""
Automated Search Tool
====================
Combines web_search → auto fetch → PDF parsing into a single workflow
No LLM intervention needed for tool coordination
"""

import asyncio
from typing import List, Dict, Any, Optional
import logging
from datetime import datetime
import os

from .brightdata_client import BrightDataAsyncClient
from ..utils.content_extractor import ContentExtractor, ExtractionMethod
from ..utils.smart_content_extractor import SmartContentExtractor
from ..utils.pdf_parser import PDFParser

logger = logging.getLogger(__name__)

# 根据环境变量设置日志级别
search_debug_enabled = os.getenv('SEARCH_DEBUG_LOG', 'false').lower() == 'true'
if search_debug_enabled:
    logger.setLevel(logging.DEBUG)
    # 同时设置 BrightData 客户端的日志级别
    brightdata_logger = logging.getLogger('src.tools.brightdata_client')
    brightdata_logger.setLevel(logging.DEBUG)
    # 设置内容提取器的日志级别
    extractor_logger = logging.getLogger('src.utils.content_extractor')
    extractor_logger.setLevel(logging.DEBUG)
    smart_extractor_logger = logging.getLogger('src.utils.smart_content_extractor')
    smart_extractor_logger.setLevel(logging.DEBUG)
    logger.info("🔍 搜索调试日志已开启 (SEARCH_DEBUG_LOG=true)")


class AutoSearchTool:
    """
    自动化搜索工具
    自动执行：搜索 → 抓取所有结果 → PDF自动解析
    """
    
    def __init__(self,
                 brightdata_api_key: str,
                 firecrawl_api_key: Optional[str] = None,
                 max_concurrent_fetch: int = 3,
                 auto_fetch_limit: int = 3,
                 max_content_length: int = 10000,
                 max_content_tokens: int = 3000,
                 enable_smart_extraction: bool = True,
                 confidence_threshold: float = 0.7,
                 parallel_timeout: float = 30.0,
                 single_url_timeout: float = 15.0):
        """
        初始化自动搜索工具
        
        Args:
            brightdata_api_key: BrightData API密钥
            firecrawl_api_key: FireCrawl API密钥（可选）
            max_concurrent_fetch: 最大并发抓取数
            auto_fetch_limit: 自动抓取的最大结果数
            max_content_length: 每个内容的最大长度
            max_content_tokens: 每个内容的最大token数（使用字符数/3.5估算）
            enable_smart_extraction: 是否启用智能提取（失败学习机制）
            confidence_threshold: 跳过爬取的置信度阈值
            parallel_timeout: 并行URL抓取的总超时时间（秒）
            single_url_timeout: 单个URL的超时时间（秒）
        """
        self.brightdata_client = BrightDataAsyncClient(
            api_key=brightdata_api_key,
            max_concurrent=3
        )
        
        # 根据配置选择使用智能提取器或普通提取器
        if enable_smart_extraction:
            self.content_extractor = SmartContentExtractor(
                firecrawl_api_key=firecrawl_api_key,
                method=ExtractionMethod.AUTO,
                max_concurrent=max_concurrent_fetch,
                enable_failure_learning=True,
                confidence_threshold=confidence_threshold
            )
            logger.info(f"启用智能内容提取器，置信度阈值: {confidence_threshold}")
        else:
            self.content_extractor = ContentExtractor(
                firecrawl_api_key=firecrawl_api_key,
                method=ExtractionMethod.AUTO,
                max_concurrent=max_concurrent_fetch
            )
            logger.info("使用普通内容提取器")
        
        self.enable_smart_extraction = enable_smart_extraction
        
        self.auto_fetch_limit = auto_fetch_limit
        self.max_content_length = max_content_length
        self.max_content_tokens = max_content_tokens
        # 字符到token的换算比例（1 token ≈ 4 字符，保守估计）
        self.char_to_token_ratio = 4.0
        self.parallel_timeout = parallel_timeout
        self.single_url_timeout = single_url_timeout
        
        logger.info(f"自动搜索工具初始化完成，自动抓取限制: {auto_fetch_limit}")
    
    async def __aenter__(self):
        """异步上下文管理器入口"""
        await self.brightdata_client.__aenter__()
        await self.content_extractor.__aenter__()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        await self.brightdata_client.__aexit__(exc_type, exc_val, exc_tb)
        # KISS方案：content_extractor现在管理自己的session生命周期
        await self.content_extractor.__aexit__(exc_type, exc_val, exc_tb)
    
    async def search_and_fetch(self,
                             query: str,
                             num_results: int = 10,
                             mode: str = "full",
                             search_options: Optional[Dict] = None) -> Dict[str, Any]:
        """
        执行搜索并根据模式决定是否抓取内容
        
        Args:
            query: 搜索查询
            num_results: 搜索结果数量
            mode: 搜索模式
                - "light": 只返回搜索结果和snippets（快速模式）
                - "full": 自动抓取完整内容并解析PDF（深度模式）
            search_options: 搜索选项（传递给BrightData）
        
        Returns:
            包含搜索结果和抓取内容的字典
        """
        start_time = datetime.now()
        search_options = search_options or {}
        
        # 创建请求ID用于追踪
        request_id = f"search_{datetime.now().strftime('%H%M%S')}_{query[:20]}"
        if search_debug_enabled:
            logger.info(f"🔍 [REQ-{request_id}] 开始搜索: {query} | mode: {mode} | num_results: {num_results}")
        else:
            logger.info(f"🔍 开始搜索: {query}")
        
        # Step 1: 执行搜索
        search_start = datetime.now()
        search_result = await self.brightdata_client.search(
            query=query,
            num_results=num_results,
            **search_options
        )
        search_elapsed = (datetime.now() - search_start).total_seconds()
        if search_debug_enabled:
            logger.info(f"⏱️ [REQ-{request_id}] BrightData搜索耗时: {search_elapsed:.2f}秒")
        
        if not search_result['success']:
            logger.error(f"❌ [REQ-{request_id}] 搜索失败: {search_result.get('error', 'Unknown error')}")
            return {
                'success': False,
                'query': query,
                'error': search_result.get('error', 'Search failed'),
                'stage': 'search',
                'request_id': request_id,
                'elapsed': search_elapsed
            }
        
        search_results = search_result.get('results', [])
        logger.info(f"✅ [REQ-{request_id}] 搜索完成，找到 {len(search_results)} 个结果")
        
        # Light mode: 直接返回搜索结果，不抓取内容
        if mode == "light":
            logger.info("💡 Light模式：仅返回搜索结果和snippets")
            enhanced_results = []
            for i, result in enumerate(search_results):
                enhanced_results.append({
                    'url': result.get('url', ''),
                    'title': result.get('title', ''),
                    'snippet': result.get('snippet', ''),
                    'position': result.get('position', i + 1),
                    'fetch_success': False,
                    'fetch_reason': 'light_mode',
                    'content': None
                })
            
            elapsed = (datetime.now() - start_time).total_seconds()
            
            return {
                'success': True,
                'query': query,
                'mode': 'light',
                'results': enhanced_results,
                'statistics': {
                    'total_results': len(search_results),
                    'auto_fetched': 0,
                    'fetch_success': 0,
                    'pdf_count': 0,
                    'elapsed': elapsed
                }
            }
        
        # Full mode: 自动抓取前N个结果
        logger.info("🔍 Full模式：自动抓取完整内容")
        urls_to_fetch = []
        for i, result in enumerate(search_results[:self.auto_fetch_limit]):
            if result.get('url'):
                urls_to_fetch.append({
                    'url': result['url'],
                    'title': result.get('title', ''),
                    'snippet': result.get('snippet', ''),
                    'position': result.get('position', i + 1)
                })
        
        if search_debug_enabled:
            logger.info(f"📥 [REQ-{request_id}] 开始并行抓取 {len(urls_to_fetch)} 个URL")
            for idx, item in enumerate(urls_to_fetch):
                logger.debug(f"  [{idx+1}] {item['url']}")
        else:
            logger.info(f"📥 开始自动抓取 {len(urls_to_fetch)} 个URL")
        
        # Normal/Deep模式：使用配置的并发数
        extractor_max_concurrent = getattr(self.content_extractor, "max_concurrent", 3)
        effective_concurrent = min(extractor_max_concurrent, len(urls_to_fetch))
        
        if search_debug_enabled:
            logger.debug(f"🔧 [REQ-{request_id}] 并发策略: mode={mode}, concurrent={effective_concurrent}")
        
        # 使用信号量控制并发数
        semaphore = asyncio.Semaphore(effective_concurrent)
        
        async def fetch_with_semaphore(item):
            async with semaphore:
                return await self._fetch_and_process(item)
        
        # 并发抓取所有URL（带总体超时控制）
        fetch_tasks = []
        for idx, item in enumerate(urls_to_fetch):
            # 为每个任务添加索引和请求ID
            item['_index'] = idx
            item['_request_id'] = request_id
            task = fetch_with_semaphore(item)
            fetch_tasks.append(task)
        
        # 添加总体超时控制，防止并行抓取耗时过长
        fetch_start = datetime.now()
        try:
            effective_timeout = self.parallel_timeout

            if search_debug_enabled:
                logger.debug(f"🕒 [REQ-{request_id}] 并行抓取超时设置: {effective_timeout}秒")
            
            fetch_results = await asyncio.wait_for(
                asyncio.gather(*fetch_tasks, return_exceptions=True),
                timeout=effective_timeout
            )
            fetch_elapsed = (datetime.now() - fetch_start).total_seconds()
            logger.info(f"⏱️ [REQ-{request_id}] 并行抓取总耗时: {fetch_elapsed:.2f}秒")
        except asyncio.TimeoutError:
            fetch_elapsed = (datetime.now() - fetch_start).total_seconds()
            logger.warning(f"⚠️ [REQ-{request_id}] URL批量抓取超时（{fetch_elapsed:.2f}秒），取消未完成的任务")
            logger.debug(f"⚠️ [REQ-{request_id}] 超时类型: URL并行抓取级别 | 限制: {effective_timeout}秒 | 模式: {mode}")
            # 取消所有未完成的任务
            for task in fetch_tasks:
                if not task.done():
                    task.cancel()
            # 收集已完成的结果
            fetch_results = []
            for task in fetch_tasks:
                try:
                    if task.done() and not task.cancelled():
                        fetch_results.append(task.result())
                    else:
                        fetch_results.append(Exception("Task cancelled due to timeout"))
                except Exception as e:
                    fetch_results.append(e)
        
        # 整合结果
        enhanced_results = []
        fetch_success_count = 0
        pdf_count = 0
        
        for i, (item, fetch_result) in enumerate(zip(urls_to_fetch, fetch_results)):
            if isinstance(fetch_result, Exception):
                logger.error(f"抓取异常 {item['url']}: {str(fetch_result)}")
                enhanced_result = {
                    **item,
                    'fetch_success': False,
                    'fetch_error': str(fetch_result),
                    'content': None
                }
            else:
                enhanced_result = {
                    **item,
                    **fetch_result
                }
                if fetch_result.get('fetch_success'):
                    fetch_success_count += 1
                if fetch_result.get('is_pdf'):
                    pdf_count += 1
            
            # KISS: 如果没有 content 但有 snippet，用 snippet 作为 content
            if enhanced_result.get('content') is None and enhanced_result.get('snippet'):
                enhanced_result['content'] = enhanced_result['snippet']
                enhanced_result['extraction_method'] = enhanced_result.get('extraction_method', 'snippet_fallback')
            
            enhanced_results.append(enhanced_result)
        
        # 添加未抓取的搜索结果（保留snippet）
        for result in search_results[self.auto_fetch_limit:]:
            snippet = result.get('snippet', '')
            enhanced_results.append({
                'url': result.get('url', ''),
                'title': result.get('title', ''),
                'snippet': snippet,
                'position': result.get('position', 0),
                'fetch_success': False,
                'fetch_reason': 'exceeded_auto_fetch_limit',
                'content': snippet,  # KISS: 直接使用 snippet 作为 content
                'extraction_method': 'snippet_only'
            })
        
        elapsed = (datetime.now() - start_time).total_seconds()
        
        # 记录详细统计
        total_elapsed = (datetime.now() - start_time).total_seconds()
        
        if search_debug_enabled:
            logger.info(f"✅ [REQ-{request_id}] 自动搜索完成:")
            logger.info(f"   - 总耗时: {total_elapsed:.2f}秒 (搜索: {search_elapsed:.2f}秒)")
            logger.info(f"   - 成功抓取: {fetch_success_count}/{len(urls_to_fetch)}")
            logger.info(f"   - PDF文档: {pdf_count}")
            
            # 记录失败的URL
            failed_urls = [r for r in enhanced_results[:len(urls_to_fetch)] if not r.get('fetch_success', False)]
            if failed_urls:
                logger.warning(f"❌ [REQ-{request_id}] 失败的URL ({len(failed_urls)}个):")
                for failed in failed_urls:
                    logger.warning(f"   - {failed.get('url', 'Unknown')}: {failed.get('fetch_error', 'Unknown error')}")
        else:
            logger.info(f"✅ 自动搜索完成: {fetch_success_count}/{len(urls_to_fetch)} 成功抓取, {pdf_count} 个PDF")
        
        # 性能分析日志
        if logger.isEnabledFor(logging.DEBUG):
            # 计算每个URL的平均耗时
            url_timings = [r.get('elapsed', 0) for r in enhanced_results[:len(urls_to_fetch)] if 'elapsed' in r]
            if url_timings:
                avg_time = sum(url_timings) / len(url_timings)
                max_time = max(url_timings)
                min_time = min(url_timings)
                logger.debug(f"📊 [REQ-{request_id}] URL抓取性能分析:")
                logger.debug(f"   - 平均耗时: {avg_time:.2f}秒")
                logger.debug(f"   - 最快: {min_time:.2f}秒")
                logger.debug(f"   - 最慢: {max_time:.2f}秒")
        
        return {
            'success': True,
            'query': query,
            'request_id': request_id,
            'results': enhanced_results,
            'statistics': {
                'total_results': len(search_results),
                'auto_fetched': len(urls_to_fetch),
                'fetch_success': fetch_success_count,
                'pdf_count': pdf_count,
                'elapsed': total_elapsed,
                'search_elapsed': search_elapsed,
                'fetch_elapsed': fetch_elapsed if 'fetch_elapsed' in locals() else 0
            }
        }
    
    async def _fetch_and_process(self, item: Dict) -> Dict[str, Any]:
        """
        抓取并处理单个URL
        
        Args:
            item: 包含url, title, snippet等信息的字典
        
        Returns:
            处理结果
        """
        url = item['url']
        title = item.get('title', '')
        snippet = item.get('snippet', '')
        idx = item.get('_index', -1)
        request_id = item.get('_request_id', 'unknown')
        
        fetch_start = datetime.now()
        if search_debug_enabled:
            logger.debug(f"🔗 [REQ-{request_id}][URL-{idx+1}] 开始抓取: {url[:80]}...")
        
        try:
            # 为单个内容提取添加超时控制
            single_fetch_timeout = self.single_url_timeout  # 使用配置的超时时间
            
            # 使用智能内容提取器（如果启用）或普通提取器
            if self.enable_smart_extraction and hasattr(self.content_extractor, 'smart_extract_content'):
                # 使用智能提取，传递SERP数据作为fallback
                extract_result = await asyncio.wait_for(
                    self.content_extractor.smart_extract_content(
                        url=url,
                        serp_snippet=snippet,
                        serp_title=title,
                        fallback=True,
                        include_metadata=True
                    ),
                    timeout=single_fetch_timeout
                )
            else:
                # 使用普通提取器
                extract_result = await asyncio.wait_for(
                    self.content_extractor.extract_content(
                        url=url,
                        fallback=True,
                        include_metadata=True
                    ),
                    timeout=single_fetch_timeout
                )
            
            if extract_result['success']:
                content = extract_result.get('content', '')
                fetch_elapsed = (datetime.now() - fetch_start).total_seconds()
                
                # 简单token估算：字符数 / 3.5
                estimated_tokens = len(content) / self.char_to_token_ratio
                
                # 先检查token限制，再检查字符限制
                if estimated_tokens > self.max_content_tokens:
                    # 根据token限制计算允许的最大字符数
                    max_chars = int(self.max_content_tokens * self.char_to_token_ratio)
                    content = content[:max_chars] + '\n\n[内容已截断]'
                    is_truncated = True
                    estimated_tokens = self.max_content_tokens
                elif len(content) > self.max_content_length:
                    content = content[:self.max_content_length] + '\n\n[内容已截断]'
                    is_truncated = True
                    estimated_tokens = len(content) / self.char_to_token_ratio
                else:
                    is_truncated = extract_result.get('is_truncated', False)
                
                if search_debug_enabled:
                    logger.info(f"✅ [REQ-{request_id}][URL-{idx+1}] 成功抓取 | 耗时: {fetch_elapsed:.2f}秒 | 内容: {len(content)}字符 | Tokens: {int(estimated_tokens)}")
                
                result_dict = {
                    'fetch_success': True,
                    'content': content,
                    'content_length': len(content),
                    'estimated_tokens': int(estimated_tokens),
                    'is_truncated': is_truncated,
                    'extraction_method': extract_result.get('method', 'unknown'),
                    'is_pdf': extract_result.get('method') == 'pdf_parser',
                    'metadata': extract_result.get('metadata', {})
                }
                
                # 添加智能提取相关信息
                if extract_result.get('is_serp_fallback'):
                    result_dict['is_serp_fallback'] = True
                    result_dict['skip_reason'] = extract_result.get('skip_reason', '')
                    result_dict['confidence'] = extract_result.get('confidence', 0.0)
                    logger.info(f"🚀 使用SERP fallback: {url} - {result_dict['skip_reason']}")
                
                if extract_result.get('intelligent_extraction'):
                    result_dict['intelligent_extraction'] = True
                    result_dict['failure_learning_enabled'] = extract_result.get('failure_learning_enabled', False)
                
                return result_dict
            else:
                fetch_elapsed = (datetime.now() - fetch_start).total_seconds()
                error_msg = extract_result.get('error', 'Unknown error')
                if search_debug_enabled:
                    logger.warning(f"❌ [REQ-{request_id}][URL-{idx+1}] 抓取失败 | 耗时: {fetch_elapsed:.2f}秒 | 错误: {error_msg}")
                return {
                    'fetch_success': False,
                    'fetch_error': error_msg,
                    'content': None,
                    'elapsed': fetch_elapsed
                }
                
        except asyncio.TimeoutError:
            fetch_elapsed = (datetime.now() - fetch_start).total_seconds()
            if search_debug_enabled:
                logger.warning(f"⏱️ [REQ-{request_id}][URL-{idx+1}] 单URL内容提取超时 | 耗时: {fetch_elapsed:.2f}秒 (限制: {single_fetch_timeout}秒) | URL: {url[:80]}")
                logger.debug(f"⏱️ [REQ-{request_id}][URL-{idx+1}] 超时类型: 单个URL内容提取级别")
            else:
                logger.warning(f"⏱️ 内容提取超时: {url[:80]}")
            return {
                'fetch_success': False,
                'fetch_error': f'Content extraction timeout ({single_fetch_timeout}s)',
                'content': snippet,  # 使用snippet作为fallback
                'is_timeout': True,
                'elapsed': fetch_elapsed
            }
        except Exception as e:
            fetch_elapsed = (datetime.now() - fetch_start).total_seconds()
            if search_debug_enabled:
                logger.error(f"❌ [REQ-{request_id}][URL-{idx+1}] 处理失败 | 耗时: {fetch_elapsed:.2f}秒 | 错误: {str(e)} | URL: {url[:80]}")
            else:
                logger.error(f"❌ 处理URL失败: {url[:80]} - {str(e)}")
            return {
                'fetch_success': False,
                'fetch_error': str(e),
                'content': None,
                'elapsed': fetch_elapsed
            }
    
    async def get_smart_extraction_stats(self) -> str:
        """获取智能提取统计信息"""
        if self.enable_smart_extraction and hasattr(self.content_extractor, 'get_learning_stats'):
            return await self.content_extractor.get_learning_stats()
        else:
            return "智能提取未启用"
    
    async def force_learn_failure(self, url: str, failure_type: str = "MANUAL", 
                                 error_message: str = "手动标记为失败"):
        """手动标记URL为失败案例"""
        if self.enable_smart_extraction and hasattr(self.content_extractor, 'force_learn_failure'):
            await self.content_extractor.force_learn_failure(url, failure_type, error_message)
        else:
            logger.warning("智能提取未启用，无法标记失败案例")


def create_auto_search_tool(brightdata_api_key: str,
                          firecrawl_api_key: Optional[str] = None,
                          auto_fetch_limit: int = 5,
                          enable_smart_extraction: bool = True,
                          confidence_threshold: float = 0.7) -> Dict:
    """
    创建自动搜索工具（LangChain格式）
    
    Args:
        brightdata_api_key: BrightData API密钥
        firecrawl_api_key: FireCrawl API密钥（可选）
        auto_fetch_limit: 自动抓取的最大URL数量，默认5个
        enable_smart_extraction: 是否启用智能提取（失败学习机制）
        confidence_threshold: 跳过爬取的置信度阈值
    
    Returns:
        LangChain工具定义
    """
    from langchain_core.tools import StructuredTool
    
    # 创建工具实例
    tool_instance = AutoSearchTool(
        brightdata_api_key=brightdata_api_key,
        firecrawl_api_key=firecrawl_api_key,
        auto_fetch_limit=auto_fetch_limit,
        enable_smart_extraction=enable_smart_extraction,
        confidence_threshold=confidence_threshold
    )
    
    async def auto_search(query: str, num_results: int = 10, mode: str = "full", **kwargs) -> Dict[str, Any]:
        """
        智能搜索工具，支持单一搜索和并行搜索
        
        Args:
            query: 搜索查询，支持两种格式:
                - 单一搜索: "<search>OpenAI GPT-4</search>"
                - 并行搜索: "<search>OpenAI GPT-4|Google Gemini|Claude 3</search>"
            num_results: 搜索结果数量（并行搜索时会平分给各查询）
            mode: 搜索模式
                - "light": 只返回搜索结果和snippets，不抓取内容
                - "full": 自动抓取内容并解析PDF
        
        Returns:
            搜索和抓取结果，包含并行搜索的统计信息
        """
        # KISS: 只处理<search>标签
        import re
        search_match = re.search(r'<search>(.*?)</search>', query, re.IGNORECASE | re.DOTALL)
        
        if search_match:
            # 提取标签内容
            search_content = search_match.group(1).strip()
            
            # 检查是否有管道符号
            if '|' in search_content:
                # 并行搜索：分割查询
                search_tags = [q.strip() for q in search_content.split('|') if q.strip()]
            else:
                # 单一搜索
                search_tags = [search_content]
        else:
            # 没有<search>标签，作为单一查询处理
            search_tags = [query]
        
        if len(search_tags) > 1:
            # 并行搜索模式
            logger.info(f"🔍 检测到并行搜索: {len(search_tags)} 个查询")
            
            # KISS方案：直接使用工具实例，session自动管理
            # 为每个查询分配结果数量
            results_per_query = max(1, num_results // len(search_tags))
            
            # 根据模式设置并发限制，避免同时发起太多请求
            extractor_max_concurrent = getattr(tool_instance.content_extractor, "max_concurrent", 4)
            if mode == "light":
                # Light模式：优先速度，支持更高并发
                max_concurrent = min(max(1, extractor_max_concurrent), len(search_tags))
                search_timeout = 60.0  # 单查询60秒超时
            else:
                # Normal/Deep模式：更保守的并发策略
                max_concurrent = min(max(1, extractor_max_concurrent), len(search_tags))
                search_timeout = 120.0  # 单查询120秒超时
            
            # 使用信号量控制并发
            semaphore = asyncio.Semaphore(max_concurrent)
            
            async def search_with_limit(idx: int, query: str):
                async with semaphore:
                    logger.debug(f"[{idx}] 开始搜索: {query}")
                    try:
                        result = await asyncio.wait_for(
                            tool_instance.search_and_fetch(query, results_per_query, mode, search_options=kwargs),
                            timeout=search_timeout
                        )
                        logger.debug(f"[{idx}] 搜索完成: {query}")
                        return result
                    except asyncio.TimeoutError:
                        logger.warning(f"[{idx}] 搜索查询超时({search_timeout}秒): {query}")
                        logger.debug(f"[{idx}] 超时类型: 并行搜索查询级别 | 模式: {mode}")
                        raise
                    except Exception as e:
                        # 检查是否是下层超时传递上来的
                        if "轮询超时" in str(e):
                            logger.error(f"[{idx}] BrightData轮询超时: {query} - {str(e)}")
                            logger.debug(f"[{idx}] 超时类型: BrightData轮询级别")
                        elif "SERP搜索超时" in str(e):
                            logger.error(f"[{idx}] BrightData搜索超时: {query} - {str(e)}")
                            logger.debug(f"[{idx}] 超时类型: BrightData API级别")
                        else:
                            logger.error(f"[{idx}] 搜索失败: {query} - {str(e)}")
                        raise
            
            # 创建受控的搜索任务
            search_tasks = []
            for i, search_query in enumerate(search_tags):
                clean_query = search_query.strip()
                if clean_query:
                    task = asyncio.create_task(search_with_limit(i, clean_query))
                    search_tasks.append((i, clean_query, task))
            
            # 等待所有搜索完成（捕获所有异常包括超时）
            search_results = await asyncio.gather(
                *[task for _, _, task in search_tasks],
                return_exceptions=True
            )
            
            # 整合并行搜索结果
            all_results = []
            parallel_stats = {
                'total_queries': len(search_tags),
                'successful_queries': 0,
                'total_results': 0,
                'total_fetched': 0,
                'total_fetch_success': 0,
                'total_pdf_count': 0,
                'query_details': []
            }
            
            for (i, search_query, _), result in zip(search_tasks, search_results):
                if isinstance(result, Exception):
                    logger.error(f"并行搜索失败 [{i}] {search_query}: {str(result)}")
                    parallel_stats['query_details'].append({
                        'query': search_query,
                        'query_index': i,
                        'success': False,
                        'error': str(result)
                    })
                elif result.get('success'):
                    parallel_stats['successful_queries'] += 1
                    query_results = result.get('results', [])
                    
                    # 为结果添加查询索引
                    for item in query_results:
                        item['search_query'] = search_query
                        item['search_index'] = i
                    
                    all_results.extend(query_results)
                    
                    # 累计统计
                    stats = result.get('statistics', {})
                    parallel_stats['total_results'] += stats.get('total_results', 0)
                    parallel_stats['total_fetched'] += stats.get('auto_fetched', 0)
                    parallel_stats['total_fetch_success'] += stats.get('fetch_success', 0)
                    parallel_stats['total_pdf_count'] += stats.get('pdf_count', 0)
                    
                    parallel_stats['query_details'].append({
                        'query': search_query,
                        'query_index': i,
                        'success': True,
                        'results_count': len(query_results),
                        'statistics': stats
                    })
                else:
                    logger.warning(f"并行搜索失败 [{i}] {search_query}: {result.get('error', 'Unknown error')}")
                    parallel_stats['query_details'].append({
                        'query': search_query,
                        'query_index': i,
                        'success': False,
                        'error': result.get('error', 'Search failed')
                    })
            
            logger.info(f"✅ 并行搜索完成: {parallel_stats['successful_queries']}/{parallel_stats['total_queries']} 成功")
            
            return {
                    'success': True,
                    'query': query,
                    'mode': mode,
                    'search_type': 'parallel',
                    'parallel_queries': search_tags,
                    'results': all_results,
                    'statistics': parallel_stats
                }
        else:
            # 单一搜索模式 - KISS方案：使用提取的查询内容
            actual_query = search_tags[0] if search_tags else query
            result = await tool_instance.search_and_fetch(actual_query, num_results, mode, search_options=kwargs)
            # 添加搜索类型标识
            result['search_type'] = 'single'
            return result
    
    return StructuredTool.from_function(
        func=auto_search,
        coroutine=auto_search,
        name="auto_search",
        description=(
            "Advanced automated search tool with intelligent failure learning and single/parallel search capabilities: "
            "SINGLE SEARCH: Use <search>query</search> format, e.g., '<search>OpenAI GPT-4</search>' "
            "PARALLEL SEARCH: Use pipe symbol within search tags, e.g., '<search>Tesla stock|Apple stock|Microsoft stock</search>' "
            "MODES: 1) mode='light' - Returns search results with snippets only (fast) "
            "2) mode='full' - Automatically fetches full content and parses PDFs (comprehensive). "
            "SMART FEATURES: Learns from crawl failures, automatically skips known failing URLs, uses SERP snippets as fallback content for better efficiency. "
            "Parallel searches distribute num_results across all queries and aggregate results with query tracking."
        )
    )


# 使用示例
async def example_usage():
    """自动搜索工具使用示例"""
    
    # 创建工具实例
    async with AutoSearchTool(
        brightdata_api_key="your-brightdata-key",
        firecrawl_api_key="your-firecrawl-key"
    ) as tool:
        
        # 执行搜索 - 自动抓取和处理所有内容
        result = await tool.search_and_fetch(
            query="RAG optimization techniques 2024",
            num_results=10
        )
        
        if result['success']:
            print(f"搜索成功！统计信息: {result['statistics']}")
            
            for item in result['results'][:3]:
                print(f"\n标题: {item['title']}")
                print(f"URL: {item['url']}")
                
                if item.get('fetch_success'):
                    print(f"内容长度: {item.get('content_length', 0)}")
                    print(f"是否PDF: {item.get('is_pdf', False)}")
                    print(f"提取方法: {item.get('extraction_method', 'unknown')}")
                    
                    # 显示内容预览
                    content = item.get('content', '')
                    if content:
                        preview = content[:200] + '...' if len(content) > 200 else content
                        print(f"内容预览: {preview}")
                else:
                    print(f"抓取失败: {item.get('fetch_error', 'Unknown')}")


if __name__ == "__main__":
    asyncio.run(example_usage())