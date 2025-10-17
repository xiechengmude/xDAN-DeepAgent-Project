"""
FireCrawl客户端 - 高性能异步实现
支持网页爬取、内容提取和智能交互
"""

import asyncio
import aiohttp
from typing import List, Dict, Any, Optional, Union
from datetime import datetime
import logging
from pydantic import BaseModel
from firecrawl import FirecrawlApp
import time
try:
    from ..utils.logger import get_logger
except ImportError:
    # Fallback to standard logging
    def get_logger(name):
        return logging.getLogger(name)

logger = logging.getLogger(__name__)
ds_logger = get_logger(__name__)


class FireCrawlAsyncClient:
    """
    FireCrawl异步客户端
    提供高性能的并发爬取能力
    """
    
    def __init__(self, api_key: str, max_concurrent: int = 5):
        """
        初始化FireCrawl客户端
        
        Args:
            api_key: FireCrawl API密钥
            max_concurrent: 最大并发数
        """
        self.api_key = api_key
        self.app = FirecrawlApp(api_key=api_key)
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.session = None
        
        logger.info(f"FireCrawl客户端初始化完成，最大并发数: {max_concurrent}")
    
    async def __aenter__(self):
        """异步上下文管理器入口"""
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        if self.session:
            await self.session.close()
    
    async def scrape_url(self, 
                        url: str, 
                        formats: List[str] = ['markdown', 'html'],
                        options: Optional[Dict] = None) -> Dict[str, Any]:
        """
        异步爬取单个URL
        
        Args:
            url: 要爬取的URL
            formats: 返回格式列表
            options: 其他选项
        
        Returns:
            爬取结果
        """
        async with self.semaphore:
            try:
                start_time = time.time()
                
                logger.debug(f"FireCrawl爬取输入: url={url}, formats={formats}")
                
                # 在线程池中运行同步方法
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(
                    None,
                    self._scrape_sync,
                    url,
                    formats,
                    options
                )
                
                elapsed = time.time() - start_time
                logger.info(f"成功爬取 {url}，耗时 {elapsed:.2f}秒")
                
                logger.info(f"FireCrawl爬取输出: url={url}, elapsed={elapsed:.2f}s, content_length={len(str(result.get('markdown', '')))}")
                
                return {
                    'success': True,
                    'url': url,
                    'data': result,
                    'elapsed': elapsed
                }
                
            except Exception as e:
                logger.error(f"爬取 {url} 失败: {str(e)}")
                logger.error(f"FireCrawl爬取错误: url={url}, error={str(e)}")
                return {
                    'success': False,
                    'url': url,
                    'error': str(e)
                }
    
    def _scrape_sync(self, url: str, formats: List[str], options: Optional[Dict]) -> Dict:
        """同步爬取方法（在线程池中运行）"""
        scrape_options = options or {}
        
        # 添加默认选项
        if 'timeout' not in scrape_options:
            scrape_options['timeout'] = 60000  # 60秒超时
        
        # 调用FireCrawl SDK
        response = self.app.scrape(
            url,
            formats=formats,
            **scrape_options
        )
        
        # 处理ScrapeResponse对象
        if hasattr(response, 'data'):
            # FireCrawl SDK 返回的是对象，提取data属性
            return response.data
        elif hasattr(response, '__dict__'):
            # 转换为字典
            return response.__dict__
        else:
            # 如果已经是字典，直接返回
            return response
    
    async def batch_scrape(self, 
                          urls: List[str], 
                          formats: List[str] = ['markdown', 'html'],
                          options: Optional[Dict] = None) -> List[Dict]:
        """
        批量异步爬取多个URL
        
        Args:
            urls: URL列表
            formats: 返回格式
            options: 爬取选项
        
        Returns:
            爬取结果列表
        """
        tasks = []
        for url in urls:
            task = self.scrape_url(url, formats, options)
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
    
    async def scrape_with_extraction(self,
                                   url: str,
                                   schema: Optional[BaseModel] = None,
                                   prompt: Optional[str] = None) -> Dict:
        """
        爬取并提取结构化数据
        
        Args:
            url: 要爬取的URL
            schema: Pydantic模型用于数据提取
            prompt: 提取提示（当没有schema时使用）
        
        Returns:
            包含提取数据的结果
        """
        async with self.semaphore:
            try:
                loop = asyncio.get_event_loop()
                
                if schema:
                    # 使用schema提取
                    result = await loop.run_in_executor(
                        None,
                        self.app.scrape,
                        url,
                        ['json'],
                        None,  # formats参数
                        {'schema': schema},
                        False,  # only_main_content
                        120000  # timeout
                    )
                else:
                    # 使用prompt提取
                    result = await loop.run_in_executor(
                        None,
                        self._scrape_with_prompt,
                        url,
                        prompt
                    )
                
                return {
                    'success': True,
                    'url': url,
                    'data': result
                }
                
            except Exception as e:
                logger.error(f"提取数据失败 {url}: {str(e)}")
                return {
                    'success': False,
                    'url': url,
                    'error': str(e)
                }
    
    def _scrape_with_prompt(self, url: str, prompt: str) -> Dict:
        """使用prompt提取数据"""
        return self.app.scrape(
            url,
            formats=['json'],
            json_options={'prompt': prompt}
        )
    
    async def scrape_with_actions(self,
                                url: str,
                                actions: List[Dict],
                                formats: List[str] = ['markdown', 'html']) -> Dict:
        """
        使用交互动作爬取页面
        
        Args:
            url: 起始URL
            actions: 动作列表
            formats: 返回格式
        
        Returns:
            爬取结果
        """
        async with self.semaphore:
            try:
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(
                    None,
                    self.app.scrape_url,
                    url,
                    formats,
                    None,  # scrape_options
                    None,  # json_options
                    False,  # only_main_content
                    120000,  # timeout
                    actions
                )
                
                return {
                    'success': True,
                    'url': url,
                    'data': result,
                    'actions_executed': len(actions)
                }
                
            except Exception as e:
                logger.error(f"动作执行失败 {url}: {str(e)}")
                return {
                    'success': False,
                    'url': url,
                    'error': str(e)
                }
    
    async def crawl_website(self,
                          url: str,
                          limit: int = 10,
                          formats: List[str] = ['markdown', 'html']) -> Dict:
        """
        爬取整个网站
        
        Args:
            url: 网站URL
            limit: 最大页面数
            formats: 返回格式
        
        Returns:
            爬取任务信息
        """
        try:
            loop = asyncio.get_event_loop()
            
            # 提交爬取任务
            crawl_result = await loop.run_in_executor(
                None,
                self.app.crawl_url,
                url,
                limit,
                {'formats': formats}
            )
            
            # 如果是异步模式，返回任务ID
            if isinstance(crawl_result, dict) and 'id' in crawl_result:
                return {
                    'success': True,
                    'crawl_id': crawl_result['id'],
                    'status_url': crawl_result.get('url'),
                    'message': '爬取任务已提交'
                }
            else:
                # 同步模式，直接返回结果
                return {
                    'success': True,
                    'data': crawl_result
                }
                
        except Exception as e:
            logger.error(f"提交爬取任务失败 {url}: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def check_crawl_status(self, crawl_id: str) -> Dict:
        """
        检查爬取任务状态
        
        Args:
            crawl_id: 爬取任务ID
        
        Returns:
            任务状态和结果
        """
        try:
            loop = asyncio.get_event_loop()
            status = await loop.run_in_executor(
                None,
                self.app.check_crawl_status,
                crawl_id
            )
            
            return {
                'success': True,
                'crawl_id': crawl_id,
                'status': status
            }
            
        except Exception as e:
            logger.error(f"检查爬取状态失败 {crawl_id}: {str(e)}")
            return {
                'success': False,
                'crawl_id': crawl_id,
                'error': str(e)
            }


    async def scrape_for_deepsearch(self,
                                   url: str,
                                   context: Optional[Dict] = None) -> Dict:
        """
        为DeepSearch优化的爬取方法
        
        Args:
            url: 要爬取的URL
            context: 搜索上下文信息（可选）
        
        Returns:
            优化后的爬取结果
        """
        context = context or {}
        
        # DeepSearch优化选项
        options = {
            'only_main_content': True,
            'timeout': 60000,
            'wait_for': 2000
        }
        
        # 只获取markdown格式以优化性能
        result = await self.scrape_url(url, formats=['markdown'], options=options)
        
        # 后处理：限制内容长度
        if result['success'] and result.get('data'):
            data = result['data']
            if 'markdown' in data:
                markdown = data['markdown']
                if len(markdown) > 5000:
                    markdown = markdown[:5000] + '...[内容已截断]'
                data['markdown'] = markdown
            
            # 添加元信息
            data['crawl_metadata'] = {
                'crawled_at': datetime.now().isoformat(),
                'url': url,
                'context': context.get('query', '')
            }
        
        return result


# 使用示例
async def example_usage():
    """FireCrawl客户端使用示例"""
    
    # 创建客户端
    async with FireCrawlAsyncClient(api_key="fc-YOUR_API_KEY") as client:
        
        # 1. 简单爬取
        result = await client.scrape_url('https://firecrawl.dev')
        print(f"爬取结果: {result['success']}")
        
        # 2. 批量爬取
        urls = [
            'https://example.com/page1',
            'https://example.com/page2',
            'https://example.com/page3'
        ]
        results = await client.batch_scrape(urls)
        print(f"批量爬取: {len([r for r in results if r['success']])} 成功")
        
        # 3. 数据提取
        class CompanyInfo(BaseModel):
            name: str
            mission: str
            founded_year: Optional[int]
            
        extracted = await client.scrape_with_extraction(
            'https://company.com',
            schema=CompanyInfo
        )
        print(f"提取的数据: {extracted.get('data', {}).get('json')}")
        
        # 4. 带交互的爬取
        actions = [
            {"type": "wait", "milliseconds": 2000},
            {"type": "click", "selector": "button.load-more"},
            {"type": "wait", "milliseconds": 3000},
            {"type": "scrape"}
        ]
        
        action_result = await client.scrape_with_actions(
            'https://dynamic-site.com',
            actions
        )
        print(f"动作执行结果: {action_result['success']}")


# DeepSearch集成示例
async def deepsearch_integration():
    """DeepSearch集成示例"""
    
    async with FireCrawlAsyncClient(api_key="fc-87533b34d5834363b71adc2d3870da92") as client:
        
        # 模拟搜索结果需要爬取的URL
        urls_to_crawl = [
            'https://example.com/article1',
            'https://example.com/research'
        ]
        
        # 使用DeepSearch优化的爬取
        tasks = []
        for url in urls_to_crawl:
            context = {'query': 'AI advances', 'search_type': 'web'}
            task = client.scrape_for_deepsearch(url, context)
            tasks.append(task)
        
        results = await asyncio.gather(*tasks)
        
        for result in results:
            if result['success']:
                print(f"成功爬取: {result['url']}")
                data = result.get('data', {})
                print(f"内容长度: {len(data.get('markdown', ''))}")


if __name__ == "__main__":
    # 运行示例
    asyncio.run(example_usage())