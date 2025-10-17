"""
Content Extraction Module - 支持FireCrawl和Trafilatura
提供灵活的网页内容提取功能，支持多种提取方式和失败回退
"""

import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime
import logging
from enum import Enum
import os
import tempfile
import aiohttp

from ..auto_search_tool.firecrawl_client import FireCrawlAsyncClient
from ..auto_search_tool.trafilatura_client import TrafilaturaAsyncClient
from .logger import get_logger

logger = logging.getLogger(__name__)
ds_logger = get_logger(__name__)


class ExtractionMethod(Enum):
    """内容提取方法枚举"""
    FIRECRAWL = "firecrawl"
    TRAFILATURA = "trafilatura"
    AUTO = "auto"  # 自动选择（优先Trafilatura，失败后回退到FireCrawl）
    SMART = "smart"  # 智能选择（HTML用Trafilatura，PDF用FireCrawl）


class ContentExtractor:
    """
    统一的内容提取器
    支持FireCrawl和Trafilatura两种提取方式
    """
    
    def __init__(self, 
                 firecrawl_api_key: Optional[str] = None,
                 method: ExtractionMethod = ExtractionMethod.AUTO,
                 max_concurrent: int = 10,
                 timeout: int = 60):
        """
        初始化内容提取器
        
        Args:
            firecrawl_api_key: FireCrawl API密钥
            method: 提取方法
            max_concurrent: 最大并发数
            timeout: 超时时间（秒）
        """
        self.firecrawl_api_key = firecrawl_api_key
        self.method = method
        self.timeout = timeout
        self.max_concurrent = max_concurrent
        self.semaphore = asyncio.Semaphore(max_concurrent)
        
        # 初始化FireCrawl客户端
        self.firecrawl_client = None
        if firecrawl_api_key:
            self.firecrawl_client = FireCrawlAsyncClient(
                api_key=firecrawl_api_key,
                max_concurrent=max_concurrent
            )
        
        # 初始化Trafilatura客户端
        self.trafilatura_client = None
        if method in [ExtractionMethod.TRAFILATURA, ExtractionMethod.AUTO, ExtractionMethod.SMART]:
            try:
                self.trafilatura_client = TrafilaturaAsyncClient(
                    max_concurrent=max_concurrent,
                    timeout=timeout
                )
            except ImportError:
                if method == ExtractionMethod.TRAFILATURA:
                    raise
                logger.warning("Trafilatura未安装，将使用其他方法")
        
        # 初始化PDF解析器
        self.pdf_parser = None
        try:
            from .pdf_parser import PDFParser
            self.pdf_parser = PDFParser()
            logger.info("PDF解析器初始化成功")
        except ImportError:
            logger.warning("PDF解析器未找到，PDF文件将使用备选方案处理")
        
        # 初始化简单爬虫客户端
        self.simple_crawler_client = None
        
        method_name = method.value if hasattr(method, 'value') else str(method)
        logger.info(f"内容提取器初始化完成，方法: {method_name}, 最大并发: {max_concurrent}")
    
    async def __aenter__(self):
        """异步上下文管理器入口"""
        if self.firecrawl_client:
            await self.firecrawl_client.__aenter__()
        if self.trafilatura_client:
            await self.trafilatura_client.__aenter__()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        if self.firecrawl_client:
            await self.firecrawl_client.__aexit__(exc_type, exc_val, exc_tb)
        # KISS方案：不再自动关闭trafilatura_client的session
        # 让session在实例级别持久存在，直到实例被销毁
        # if self.trafilatura_client:
        #     await self.trafilatura_client.__aexit__(exc_type, exc_val, exc_tb)
    
    async def extract_content(self, 
                            url: str,
                            fallback: bool = True,
                            include_metadata: bool = True) -> Dict[str, Any]:
        """
        提取网页内容
        
        Args:
            url: 要提取的URL
            fallback: 是否启用失败回退
            include_metadata: 是否包含元数据
        
        Returns:
            提取结果字典
        """
        async with self.semaphore:
            start_time = datetime.now()
            
            # 根据配置的方法选择提取策略
            if self.method == ExtractionMethod.FIRECRAWL:
                result = await self._extract_with_firecrawl(url, include_metadata)
            elif self.method == ExtractionMethod.TRAFILATURA:
                result = await self._extract_with_trafilatura(url, include_metadata)
            elif self.method == ExtractionMethod.SMART:
                # 智能选择：根据内容类型决定提取方法
                result = await self._smart_extract(url, include_metadata, fallback)
            else:  # AUTO模式
                # 先检测是否为PDF文件
                content_type = await self._detect_content_type(url)
                
                if content_type == 'pdf':
                    # PDF文件：优先使用PDF解析器
                    if self.pdf_parser:
                        logger.info(f"AUTO模式检测到PDF，使用PDF解析器: {url}")
                        result = await self._extract_with_pdf_parser(url, include_metadata)
                        if not result['success'] and fallback:
                            # PDF解析失败，尝试其他方法
                            if self.firecrawl_client:
                                logger.info(f"PDF解析器失败，尝试FireCrawl: {url}")
                                result = await self._extract_with_firecrawl(url, include_metadata)
                            elif self.trafilatura_client:
                                logger.info(f"PDF解析器失败，尝试Trafilatura（可能会失败）: {url}")
                                result = await self._extract_with_trafilatura(url, include_metadata)
                    elif self.firecrawl_client:
                        # 没有PDF解析器，使用FireCrawl
                        logger.info(f"AUTO模式检测到PDF，无PDF解析器，使用FireCrawl: {url}")
                        result = await self._extract_with_firecrawl(url, include_metadata)
                    else:
                        # 无法处理PDF
                        result = {
                            'success': False,
                            'url': url,
                            'error': 'No PDF extraction method available',
                            'method': 'none'
                        }
                else:
                    # HTML或其他内容：优先尝试Trafilatura
                    if self.trafilatura_client:
                        result = await self._extract_with_trafilatura(url, include_metadata)
                        if not result['success'] and fallback and self.firecrawl_client:
                            logger.info(f"Trafilatura失败，尝试FireCrawl: {url}")
                            result = await self._extract_with_firecrawl(url, include_metadata)
                    elif self.firecrawl_client:
                        # 没有其他选择，直接使用FireCrawl
                        result = await self._extract_with_firecrawl(url, include_metadata)
                    else:
                        # 所有客户端都不可用
                        result = {
                            'success': False,
                            'url': url,
                            'error': 'No extraction client available',
                            'method': 'none'
                        }
            
            # 添加提取耗时
            result['extraction_time'] = (datetime.now() - start_time).total_seconds()
            
            # 记录日志
            logger.info(f"内容提取完成: url={url}, method={result.get('method', 'unknown')}, success={result['success']}, content_length={len(result.get('content', ''))}, time={result['extraction_time']:.2f}s")
            
            return result
    
    async def _extract_with_firecrawl(self, 
                                    url: str,
                                    include_metadata: bool) -> Dict[str, Any]:
        """
        使用FireCrawl提取内容
        
        Args:
            url: 要提取的URL
            include_metadata: 是否包含元数据
        
        Returns:
            提取结果
        """
        if not self.firecrawl_client:
            return {
                'success': False,
                'url': url,
                'error': 'FireCrawl client not initialized',
                'method': 'firecrawl'
            }
        
        try:
            # 使用FireCrawl爬取
            crawl_result = await self.firecrawl_client.scrape_for_deepsearch(url)
            
            if crawl_result['success'] and crawl_result.get('data'):
                data = crawl_result['data']
                markdown_content = data.get('markdown', '')
                
                # 内容已经被FireCrawl处理过了，直接使用
                content = markdown_content
                
                result = {
                    'success': True,
                    'url': url,
                    'content': content,
                    'markdown': markdown_content,
                    'method': 'firecrawl'
                }
                
                # 添加元数据
                if include_metadata:
                    result['metadata'] = {
                        'title': data.get('title', ''),
                        'crawled_at': data.get('crawl_metadata', {}).get('crawled_at'),
                        'source_url': url
                    }
                
                return result
            else:
                return {
                    'success': False,
                    'url': url,
                    'error': crawl_result.get('error', 'Unknown error'),
                    'method': 'firecrawl'
                }
                
        except Exception as e:
            logger.error(f"FireCrawl提取失败 {url}: {str(e)}")
            return {
                'success': False,
                'url': url,
                'error': str(e),
                'method': 'firecrawl'
            }
    
    async def _extract_with_trafilatura(self,
                                      url: str,
                                      include_metadata: bool) -> Dict[str, Any]:
        """
        使用Trafilatura提取内容
        
        Args:
            url: 要提取的URL
            include_metadata: 是否包含元数据
        
        Returns:
            提取结果
        """
        if not self.trafilatura_client:
            return {
                'success': False,
                'url': url,
                'error': 'Trafilatura client not initialized',
                'method': 'trafilatura'
            }
        
        try:
            # 使用Trafilatura客户端提取内容
            result = await self.trafilatura_client.extract_content(
                url,
                include_metadata=include_metadata,
                include_links=False,
                include_images=False,
                include_tables=True,
                deduplicate=True
            )
            
            # 添加方法标识
            result['method'] = 'trafilatura'
            
            return result
            
        except Exception as e:
            logger.error(f"Trafilatura提取失败 {url}: {str(e)}")
            return {
                'success': False,
                'url': url,
                'error': str(e),
                'method': 'trafilatura'
            }
    
    
    def _write_temp_pdf(self, pdf_content: bytes) -> str:
        """
        同步方法：将PDF内容写入临时文件
        
        Args:
            pdf_content: PDF文件的二进制内容
            
        Returns:
            临时文件路径
        """
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as temp_file:
            temp_file.write(pdf_content)
            return temp_file.name
    
    async def _extract_with_pdf_parser(self,
                                      url: str,
                                      include_metadata: bool) -> Dict[str, Any]:
        """
        使用本地PDF解析器提取内容
        
        Args:
            url: 要提取的URL
            include_metadata: 是否包含元数据
        
        Returns:
            提取结果
        """
        if not self.pdf_parser:
            return {
                'success': False,
                'url': url,
                'error': 'PDF parser not initialized',
                'method': 'pdf_parser'
            }
        
        temp_file = None
        try:
            # 下载PDF文件到临时目录
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=self.timeout) as response:
                    if response.status != 200:
                        return {
                            'success': False,
                            'url': url,
                            'error': f'HTTP {response.status}',
                            'method': 'pdf_parser'
                        }
                    
                    # 创建临时文件 - 使用异步方式避免阻塞
                    pdf_content = await response.read()
                    
                    # 在线程池中执行文件写入操作
                    import asyncio
                    temp_file_path = await asyncio.to_thread(
                        self._write_temp_pdf, pdf_content
                    )
            
            # 使用PDF解析器解析 - 在线程池中执行同步解析
            parse_result = await asyncio.to_thread(
                self.pdf_parser.parse, temp_file_path
            )
            
            if parse_result['success']:
                result = {
                    'success': True,
                    'url': url,
                    'content': parse_result['content'],
                    'markdown': parse_result['content'],  # PDF内容已经是文本格式
                    'method': 'pdf_parser',
                    'token_count': parse_result.get('token_count', 0),
                    'is_truncated': parse_result.get('is_truncated', False)
                }
                
                # 添加元数据
                if include_metadata:
                    result['metadata'] = {
                        'title': parse_result.get('title', ''),
                        'pdf_metadata': parse_result.get('metadata', {}),
                        'source_url': url,
                        'token_info': {
                            'count': parse_result.get('token_count', 0),
                            'truncated': parse_result.get('is_truncated', False),
                            'limit': 8000
                        }
                    }
                
                # 如果内容被截断，记录日志
                if parse_result.get('is_truncated'):
                    logger.info(f"PDF内容被截断: {url} (原始token数: {parse_result.get('token_count', 'unknown')})")
                
                return result
            else:
                return {
                    'success': False,
                    'url': url,
                    'error': parse_result.get('error', 'PDF parsing failed'),
                    'method': 'pdf_parser'
                }
                
        except asyncio.TimeoutError:
            logger.error(f"PDF下载超时 {url}")
            return {
                'success': False,
                'url': url,
                'error': 'Download timeout',
                'method': 'pdf_parser'
            }
        except Exception as e:
            logger.error(f"PDF解析失败 {url}: {str(e)}")
            return {
                'success': False,
                'url': url,
                'error': str(e),
                'method': 'pdf_parser'
            }
        finally:
            # 清理临时文件
            if 'temp_file_path' in locals() and os.path.exists(temp_file_path):
                try:
                    # 在线程池中执行文件删除
                    await asyncio.to_thread(os.unlink, temp_file_path)
                except:
                    pass
    
    async def _smart_extract(self,
                           url: str,
                           include_metadata: bool,
                           fallback: bool) -> Dict[str, Any]:
        """
        智能提取：根据内容类型选择最佳提取方法
        - HTML页面：优先使用Trafilatura（免费、高效）
        - PDF文件：使用FireCrawl（更好的PDF处理能力）
        - 其他文件：根据可用性自动选择
        
        Args:
            url: 要提取的URL
            include_metadata: 是否包含元数据
            fallback: 是否启用失败回退
        
        Returns:
            提取结果
        """
        try:
            # 检测内容类型
            content_type = await self._detect_content_type(url)
            logger.info(f"检测到内容类型: {content_type} for {url}")
            
            if content_type == 'pdf':
                # PDF文件：优先使用本地PDF解析器
                if self.pdf_parser:
                    logger.info(f"PDF文件使用本地PDF解析器: {url}")
                    result = await self._extract_with_pdf_parser(url, include_metadata)
                    if not result['success'] and fallback:
                        # 本地解析失败，尝试FireCrawl
                        if self.firecrawl_client:
                            logger.info(f"PDF解析器失败，回退到FireCrawl: {url}")
                            result = await self._extract_with_firecrawl(url, include_metadata)
                        elif self.trafilatura_client:
                            logger.info(f"PDF解析器失败，回退到Trafilatura: {url}")
                            result = await self._extract_with_trafilatura(url, include_metadata)
                elif self.firecrawl_client:
                    logger.info(f"无PDF解析器，PDF使用FireCrawl: {url}")
                    result = await self._extract_with_firecrawl(url, include_metadata)
                    if not result['success'] and fallback and self.trafilatura_client:
                        logger.info(f"FireCrawl失败，PDF回退到Trafilatura: {url}")
                        result = await self._extract_with_trafilatura(url, include_metadata)
                elif self.trafilatura_client:
                    logger.info(f"无PDF解析器和FireCrawl，PDF使用Trafilatura: {url}")
                    result = await self._extract_with_trafilatura(url, include_metadata)
                else:
                    result = {
                        'success': False,
                        'url': url,
                        'error': 'No client available for PDF extraction',
                        'method': 'none'
                    }
            else:
                # HTML或其他内容：优先使用Trafilatura
                if self.trafilatura_client:
                    logger.info(f"HTML内容使用Trafilatura: {url}")
                    result = await self._extract_with_trafilatura(url, include_metadata)
                    if not result['success'] and fallback and self.firecrawl_client:
                        logger.info(f"Trafilatura失败，HTML回退到FireCrawl: {url}")
                        result = await self._extract_with_firecrawl(url, include_metadata)
                elif self.firecrawl_client:
                    logger.info(f"无Trafilatura，HTML使用FireCrawl: {url}")
                    result = await self._extract_with_firecrawl(url, include_metadata)
                else:
                    result = {
                        'success': False,
                        'url': url,
                        'error': 'No client available for HTML extraction',
                        'method': 'none'
                    }
            
            # 添加智能选择信息
            if result['success']:
                result['smart_choice'] = {
                    'detected_type': content_type,
                    'chosen_method': result['method'],
                    'reason': f"{'PDF' if content_type == 'pdf' else 'HTML'} 内容选择了 {result['method']}"
                }
            
            return result
            
        except Exception as e:
            logger.error(f"智能提取失败 {url}: {str(e)}")
            # 失败时回退到AUTO模式
            return await self._fallback_to_auto(url, include_metadata, fallback)
    
    async def _detect_content_type(self, url: str) -> str:
        """
        检测URL的内容类型
        
        Args:
            url: 要检测的URL
        
        Returns:
            内容类型：'pdf', 'html', 'unknown'
        """
        # 1. 从URL扩展名判断
        if url.lower().endswith('.pdf'):
            return 'pdf'
        
        # 2. 从URL路径判断
        if '/pdf/' in url.lower() or 'filetype:pdf' in url.lower():
            return 'pdf'
        
        # 3. 尝试HEAD请求获取Content-Type
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.head(url, timeout=5) as response:
                    content_type = response.headers.get('content-type', '').lower()
                    
                    if 'application/pdf' in content_type:
                        return 'pdf'
                    elif 'text/html' in content_type:
                        return 'html'
                    elif 'application/json' in content_type:
                        return 'json'
                    elif 'text/plain' in content_type:
                        return 'text'
        except:
            # 网络请求失败，继续其他判断
            pass
        
        # 4. 默认假设为HTML
        return 'html'
    
    async def _fallback_to_auto(self,
                              url: str,
                              include_metadata: bool,
                              fallback: bool) -> Dict[str, Any]:
        """
        回退到AUTO模式的提取逻辑
        """
        if self.firecrawl_client:
            result = await self._extract_with_firecrawl(url, include_metadata)
            if not result['success'] and fallback and self.trafilatura_client:
                result = await self._extract_with_trafilatura(url, include_metadata)
        elif self.trafilatura_client:
            result = await self._extract_with_trafilatura(url, include_metadata)
        else:
            result = {
                'success': False,
                'url': url,
                'error': 'No extraction client available',
                'method': 'none'
            }
        
        return result
    
    
    async def batch_extract(self,
                          urls: List[str],
                          fallback: bool = True,
                          include_metadata: bool = True) -> List[Dict[str, Any]]:
        """
        批量提取多个URL的内容
        
        Args:
            urls: URL列表
            fallback: 是否启用失败回退
            include_metadata: 是否包含元数据
        
        Returns:
            提取结果列表
        """
        tasks = []
        for url in urls:
            task = self.extract_content(url, fallback, include_metadata)
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 处理异常结果
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed_results.append({
                    'success': False,
                    'url': urls[i],
                    'error': str(result),
                    'method': 'unknown'
                })
            else:
                processed_results.append(result)
        
        return processed_results
    
    async def extract_for_search(self,
                               url: str,
                               max_length: int = 5000) -> Dict[str, Any]:
        """
        为搜索优化的内容提取
        
        Args:
            url: 要提取的URL
            max_length: 最大内容长度
        
        Returns:
            优化后的提取结果
        """
        result = await self.extract_content(url, fallback=True, include_metadata=True)
        
        # 限制内容长度
        if result['success'] and result.get('content'):
            content = result['content']
            if len(content) > max_length:
                content = content[:max_length] + '...[内容已截断]'
                result['content'] = content
                result['truncated'] = True
        
        return result


# 使用示例
async def example_usage():
    """内容提取器使用示例"""
    
    # 1. 自动模式（优先FireCrawl，失败回退到Trafilatura）
    async with ContentExtractor(
        firecrawl_api_key="your-api-key",
        method=ExtractionMethod.AUTO
    ) as extractor:
        result = await extractor.extract_content('https://example.com')
        print(f"提取成功: {result['success']}, 方法: {result['method']}")
    
    # 2. 仅使用Trafilatura
    async with ContentExtractor(method=ExtractionMethod.TRAFILATURA) as extractor:
        result = await extractor.extract_content('https://example.com')
        print(f"内容长度: {len(result.get('content', ''))}")
    
    # 3. 批量提取
    urls = ['https://example1.com', 'https://example2.com']
    async with ContentExtractor() as extractor:
        results = await extractor.batch_extract(urls)
        for result in results:
            print(f"{result['url']}: {result['success']}")


if __name__ == "__main__":
    asyncio.run(example_usage())