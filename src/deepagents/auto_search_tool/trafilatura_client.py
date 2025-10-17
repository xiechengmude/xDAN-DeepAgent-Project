"""
Trafilatura客户端 - 高性能异步实现
提供网页内容提取和元数据解析功能
"""

import asyncio
import aiohttp
from typing import List, Dict, Any, Optional, Union
from datetime import datetime
import logging
import re
import time
try:
    from ..utils.logger import get_logger
except ImportError:
    # Fallback to standard logging
    def get_logger(name):
        return logging.getLogger(name)

# 导入trafilatura
try:
    from trafilatura import extract, extract_metadata, fetch_url
    from trafilatura.settings import use_config
    TRAFILATURA_AVAILABLE = True
except ImportError:
    TRAFILATURA_AVAILABLE = False
    extract = None
    extract_metadata = None
    fetch_url = None
    use_config = None

logger = logging.getLogger(__name__)
if 'get_logger' in locals() or 'get_logger' in globals():
    logger = get_logger(__name__)


class TrafilaturaAsyncClient:
    """
    Trafilatura异步客户端
    提供高性能的并发内容提取能力
    """
    
    def __init__(self, max_concurrent: int = 5, timeout: int = 60):
        """
        初始化Trafilatura客户端
        
        Args:
            max_concurrent: 最大并发数
            timeout: 超时时间（秒）
        """
        if not TRAFILATURA_AVAILABLE:
            raise ImportError("Trafilatura not installed. Please run: pip install trafilatura")
        
        self.max_concurrent = max_concurrent
        self.timeout = timeout
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.session = None
        
        # 配置trafilatura
        self.config = use_config()
        self.config.set("DEFAULT", "EXTRACTION_TIMEOUT", str(timeout))
        
        logger.info(f"Trafilatura客户端初始化完成，最大并发数: {max_concurrent}")
    
    def _ensure_session(self):
        """确保session存在且可用（KISS方案核心）"""
        if not self.session or self.session.closed:
            self.session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.timeout)
            )
    
    async def __aenter__(self):
        """异步上下文管理器入口（向后兼容）"""
        self._ensure_session()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口（向后兼容）"""
        # KISS方案：不关闭session，让它持久化
        # 使用 _ensure_session() 机制，session 会在实例销毁时通过 __del__ 清理
        pass
    
    async def close(self):
        """手动关闭session"""
        if self.session and not self.session.closed:
            await self.session.close()
    
    def __del__(self):
        """实例销毁时尝试清理session"""
        if hasattr(self, 'session') and self.session and not self.session.closed:
            try:
                # 尝试在当前事件循环中关闭
                import asyncio
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.create_task(self.session.close())
            except:
                pass  # 忽略清理失败
    
    async def extract_content(self,
                            url: str,
                            include_metadata: bool = True,
                            include_links: bool = False,
                            include_images: bool = False,
                            include_tables: bool = True,
                            deduplicate: bool = True,
                            target_language: Optional[str] = None) -> Dict[str, Any]:
        """
        异步提取单个URL的内容
        
        Args:
            url: 要提取的URL
            include_metadata: 是否包含元数据
            include_links: 是否包含链接
            include_images: 是否包含图片
            include_tables: 是否包含表格
            deduplicate: 是否去重
            target_language: 目标语言
        
        Returns:
            提取结果
        """
        async with self.semaphore:
            try:
                start_time = time.time()
                
                logger.debug(f"Trafilatura提取输入: url={url}, include_metadata={include_metadata}")
                
                # 获取网页内容
                html_content = await self._fetch_url(url)
                
                if not html_content:
                    return {
                        'success': False,
                        'url': url,
                        'error': 'Failed to fetch URL'
                    }
                
                # 在线程池中运行同步提取方法，使用 asyncio.wait_for() 控制超时
                loop = asyncio.get_event_loop()
                try:
                    content = await asyncio.wait_for(
                        loop.run_in_executor(
                            None,
                            self._extract_sync,
                            html_content,
                            url,
                            include_links,
                            include_images,
                            include_tables,
                            deduplicate,
                            target_language
                        ),
                        timeout=self.timeout  # 使用 asyncio 超时而非 signal
                    )
                except asyncio.TimeoutError:
                    return {
                        'success': False,
                        'url': url,
                        'error': f'Content extraction timeout ({self.timeout}s)'
                    }
                
                if not content:
                    return {
                        'success': False,
                        'url': url,
                        'error': 'No content extracted'
                    }
                
                # 清理内容
                content = self._clean_content(content)
                
                result = {
                    'success': True,
                    'url': url,
                    'content': content,
                    'elapsed': time.time() - start_time
                }
                
                # 提取元数据
                if include_metadata:
                    metadata = await loop.run_in_executor(
                        None,
                        extract_metadata,
                        html_content,
                        url
                    )
                    
                    if metadata:
                        result['metadata'] = {
                            'title': metadata.title or '',
                            'author': metadata.author or '',
                            'date': metadata.date or '',
                            'description': metadata.description or '',
                            'sitename': metadata.sitename or '',
                            'categories': metadata.categories or [],
                            'tags': metadata.tags or []
                        }
                
                logger.info(f"Trafilatura提取输出: url={url}, content_length={len(content)}, elapsed={result['elapsed']:.2f}s")
                
                return result
                
            except Exception as e:
                logger.error(f"提取 {url} 失败: {str(e)}")
                logger.error(f"Trafilatura提取错误: {str(e)}")
                return {
                    'success': False,
                    'url': url,
                    'error': str(e)
                }
    
    async def _fetch_url(self, url: str) -> Optional[str]:
        """
        异步获取URL内容
        
        Args:
            url: 要获取的URL
        
        Returns:
            HTML内容或None
        """
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                'Accept-Encoding': 'gzip, deflate, br',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1'
            }
            
            # KISS方案：每次使用前确保session可用
            self._ensure_session()
            
            async with self.session.get(url, headers=headers) as response:
                if response.status == 200:
                    return await response.text()
                else:
                    logger.warning(f"HTTP {response.status} for {url}")
                    return None
                    
        except Exception as e:
            logger.error(f"获取 {url} 失败: {str(e)}")
            return None
    
    def _extract_sync(self,
                     html_content: str,
                     url: str,
                     include_links: bool,
                     include_images: bool,
                     include_tables: bool,
                     deduplicate: bool,
                     target_language: Optional[str]) -> Optional[str]:
        """
        同步提取内容（在线程池中运行）

        NOTE: 显式禁用 signal-based 超时，避免 "signal only works in main thread" 错误
        依赖 asyncio.wait_for() 来控制超时
        """
        # 创建一个副本并禁用 signal-based 超时
        import copy
        config = copy.deepcopy(self.config)
        config.set("DEFAULT", "EXTRACTION_TIMEOUT", "0")  # 0 = 禁用 signal 超时

        return extract(
            html_content,
            url=url,
            include_links=include_links,
            include_images=include_images,
            include_tables=include_tables,
            deduplicate=deduplicate,
            target_language=target_language,
            config=config  # 使用禁用 signal 的配置
        )
    
    def _clean_content(self, content: str) -> str:
        """
        清理提取的内容
        
        Args:
            content: 原始内容
        
        Returns:
            清理后的内容
        """
        if not content:
            return ""
        
        # 移除多余的空白字符
        content = re.sub(r'\s+', ' ', content)
        
        # 移除多余的换行
        content = re.sub(r'\n{3,}', '\n\n', content)
        
        # 去除首尾空白
        content = content.strip()
        
        return content
    
    async def batch_extract(self,
                          urls: List[str],
                          include_metadata: bool = True,
                          **kwargs) -> List[Dict[str, Any]]:
        """
        批量异步提取多个URL
        
        Args:
            urls: URL列表
            include_metadata: 是否包含元数据
            **kwargs: 其他提取参数
        
        Returns:
            提取结果列表
        """
        tasks = []
        for url in urls:
            task = self.extract_content(url, include_metadata, **kwargs)
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 处理异常结果
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed_results.append({
                    'success': False,
                    'url': urls[i],
                    'error': str(result)
                })
            else:
                processed_results.append(result)
        
        return processed_results
    
    async def extract_for_deepsearch(self,
                                   url: str,
                                   context: Optional[Dict] = None) -> Dict[str, Any]:
        """
        为DeepSearch优化的提取方法
        
        Args:
            url: 要提取的URL
            context: 搜索上下文信息（可选）
        
        Returns:
            优化后的提取结果
        """
        context = context or {}
        
        # DeepSearch优化参数
        result = await self.extract_content(
            url,
            include_metadata=True,
            include_links=False,
            include_images=False,
            include_tables=True,
            deduplicate=True
        )
        
        # 后处理：限制内容长度
        if result['success'] and result.get('content'):
            content = result['content']
            if len(content) > 10000:
                content = content[:10000] + '...[内容已截断]'
                result['content'] = content
                result['truncated'] = True
            
            # 添加元信息
            result['crawl_metadata'] = {
                'crawled_at': datetime.now().isoformat(),
                'url': url,
                'context': context.get('query', ''),
                'extractor': 'trafilatura'
            }
        
        return result
    
    async def extract_with_fallback(self,
                                  url: str,
                                  fallback_to_raw: bool = True) -> Dict[str, Any]:
        """
        带失败回退的提取方法
        
        Args:
            url: 要提取的URL
            fallback_to_raw: 失败时是否返回原始HTML
        
        Returns:
            提取结果
        """
        result = await self.extract_content(url)
        
        # 如果提取失败但获取到了HTML，返回原始内容
        if not result['success'] and fallback_to_raw:
            html_content = await self._fetch_url(url)
            if html_content:
                # 使用BeautifulSoup提取文本作为后备
                try:
                    from bs4 import BeautifulSoup
                    soup = BeautifulSoup(html_content, 'html.parser')
                    
                    # 移除script和style标签
                    for script in soup(["script", "style"]):
                        script.decompose()
                    
                    # 获取文本
                    text = soup.get_text()
                    text = self._clean_content(text)
                    
                    if text:
                        result = {
                            'success': True,
                            'url': url,
                            'content': text,
                            'fallback': True,
                            'method': 'beautifulsoup'
                        }
                except:
                    pass
        
        return result


# 使用示例
async def example_usage():
    """Trafilatura客户端使用示例"""
    
    # 创建客户端
    async with TrafilaturaAsyncClient(max_concurrent=3) as client:
        
        # 1. 简单提取
        result = await client.extract_content('https://example.com')
        print(f"提取结果: {result['success']}")
        if result['success']:
            print(f"内容长度: {len(result['content'])} 字符")
            print(f"标题: {result.get('metadata', {}).get('title', 'N/A')}")
        
        # 2. 批量提取
        urls = [
            'https://example.com/page1',
            'https://example.com/page2',
            'https://example.com/page3'
        ]
        results = await client.batch_extract(urls)
        print(f"批量提取: {len([r for r in results if r['success']])} 成功")
        
        # 3. DeepSearch优化提取
        search_result = await client.extract_for_deepsearch(
            'https://example.com',
            context={'query': 'AI technology'}
        )
        print(f"搜索优化提取: {search_result['success']}")
        
        # 4. 带回退的提取
        fallback_result = await client.extract_with_fallback(
            'https://difficult-site.com'
        )
        print(f"回退提取: {fallback_result['success']}")
        if fallback_result.get('fallback'):
            print("使用了回退方法")


if __name__ == "__main__":
    # 运行示例
    asyncio.run(example_usage())
    asyncio.run(example_usage()) 