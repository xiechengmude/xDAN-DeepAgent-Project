"""
BrightData客户端 - SERP API优化版
基于BrightData SERP API，支持原生JSON解析和高级搜索功能
"""

import aiohttp
import asyncio
import json
import os
from typing import List, Dict, Optional, Union
from urllib.parse import quote_plus, urlencode
from bs4 import BeautifulSoup
import logging
import time
from datetime import datetime
try:
    from ..utils.logger import get_logger
except ImportError:
    # Fallback to standard logging
    def get_logger(name):
        return logging.getLogger(name)

logger = logging.getLogger(__name__)
ds_logger = get_logger(__name__)


class BrightDataAsyncClient:
    """高性能异步BrightData客户端 - SERP API优化版"""
    
    def __init__(self, api_key: str, zone: str = "xdan_search_searp", 
                 max_concurrent: int = 5, timeout: int = 40):
        """
        初始化BrightData客户端
        
        Args:
            api_key: BrightData API密钥
            zone: BrightData zone名称
            max_concurrent: 最大并发请求数
            timeout: HTTP会话默认超时时间（秒），默认40秒
                    注意：轮询阶段有独立的超时控制（BRIGHTDATA_POLL_TIMEOUT环境变量）
        """
        self.api_key = api_key
        self.zone = zone
        # 使用SERP专用API端点
        self.serp_url = "https://api.brightdata.com/serp/req"
        self.result_url = "https://api.brightdata.com/serp/get_result"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self._session = None
        self._own_session = False
        
        logger.info(f"BrightData SERP客户端初始化，zone: {zone}, 最大并发: {max_concurrent}")
    
    async def __aenter__(self):
        """异步上下文管理器入口"""
        await self._ensure_session()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        await self._close_session()
    
    async def _ensure_session(self):
        """确保 session 存在"""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=self.timeout,  # 使用客户端超时设置（现在是40秒）
                connector=aiohttp.TCPConnector(
                    limit=100,
                    ttl_dns_cache=300,
                    force_close=True
                )
            )
            self._own_session = True
    
    async def _close_session(self):
        """关闭 session"""
        if self._session and self._own_session and not self._session.closed:
            await self._session.close()
    
    async def search(self, query: str, **kwargs) -> Dict[str, any]:
        """
        异步执行搜索 - 使用SERP API优化版本，集成SearchStrategy
        
        Args:
            query: 搜索查询
            **kwargs: 搜索选项
                - search_type: web/news/academic/images/videos/shopping
                - num_results: 结果数量 (默认10)
                - date_range: 时间范围(h/d/w/m/y)
                - language: 语言代码 (默认en)
                - country: 国家代码 (默认us)
                - page: 页码 (默认1)
                - location: 地理位置
                - device: desktop/mobile/ios/android
                - use_strategy: 是否使用SearchStrategy优化 (默认True)
        
        Returns:
            搜索结果字典
        """
        async with self.semaphore:
            start_time = time.time()
            
            try:
                # 如果启用策略优化，则使用SearchStrategy
                use_strategy = kwargs.get('use_strategy', True)
                original_query = query
                
                if use_strategy:
                    # V1 策略已删除，暂时禁用策略优化
                    logger.debug(f"策略优化已禁用（V1策略已删除）")
                
                # 构建SERP API参数
                search_params = self._build_serp_params(query, kwargs)
                logger.debug(f"SERP参数: {search_params}")
                
                logger.debug(f"BrightData SERP搜索输入: query={original_query}, params={search_params}")
                
                # 准备请求数据
                data = {
                    "zone": self.zone,  # 添加 zone 参数
                    "query": search_params
                }
                
                # 只有明确指定country时才添加到请求数据中
                if "country" in kwargs:
                    data["country"] = kwargs["country"].lower()
                
                # 确保session存在
                await self._ensure_session()
                
                # 发送SERP请求
                # 从API key中提取customer ID（如果需要的话）
                # 目前先不使用customer参数，让API自动识别
                url = f"{self.serp_url}"
                
                async with self._session.post(
                    url,
                    json=data,
                    headers=self.headers
                ) as response:
                    response.raise_for_status()
                    
                    # 获取初始响应
                    initial_response = await response.json()
                    
                    # 检查是否是异步模式
                    if 'response_id' in initial_response:
                        # 异步模式：轮询结果
                        response_id = initial_response['response_id']
                        logger.debug(f"异步模式，response_id: {response_id}")
                        results_data = await self._poll_async_result(response_id)
                    else:
                        # 同步模式：直接使用结果
                        results_data = initial_response
                    
                    processed_results = self._process_serp_results(results_data)
                    
                    elapsed = time.time() - start_time
                    result_count = len(processed_results) if isinstance(processed_results, list) else 1
                    
                    logger.info(f"SERP搜索完成: {query[:50]}... 耗时: {elapsed:.2f}s, 结果数: {result_count}")
                    
                    logger.info(f"BrightData SERP搜索输出: query={query}, results={result_count}, elapsed={elapsed:.2f}s")
                    
                    return {
                        'success': True,
                        'original_query': original_query,
                        'optimized_query': query,
                        'results': processed_results,
                        'elapsed': elapsed,
                        'serp_params': search_params,
                        'strategy_used': use_strategy,
                        'timestamp': datetime.now().isoformat()
                    }
                    
            except asyncio.TimeoutError:
                logger.error(f"SERP搜索超时: {query}")
                return {
                    'success': False,
                    'query': query,
                    'error': 'Timeout',
                    'elapsed': time.time() - start_time
                }
            except aiohttp.ClientError as e:
                logger.error(f"SERP网络错误: {query}, 错误: {str(e)}")
                return {
                    'success': False,
                    'query': query,
                    'error': f'Network error: {str(e)}',
                    'elapsed': time.time() - start_time
                }
            except Exception as e:
                logger.error(f"SERP搜索错误: {query}, 错误: {str(e)}")
                logger.error(f"BrightData SERP搜索错误: query={query}, error={str(e)}")
                return {
                    'success': False,
                    'query': query,
                    'error': str(e),
                    'elapsed': time.time() - start_time
                }
    
    async def batch_search(self, queries: List[str], **kwargs) -> List[Dict]:
        """
        批量异步搜索
        
        Args:
            queries: 查询列表
            **kwargs: 搜索选项（应用于所有查询）
        
        Returns:
            搜索结果列表
        """
        tasks = []
        for query in queries:
            task = self.search(query, **kwargs)
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 处理异常
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed_results.append({
                    'success': False,
                    'query': queries[i],
                    'error': str(result)
                })
            else:
                processed_results.append(result)
        
        # 统计成功率
        success_count = sum(1 for r in processed_results if r.get('success'))
        logger.info(f"批量搜索完成: {success_count}/{len(queries)} 成功")
        
        return processed_results
    
    async def multi_type_search(self, query: str, search_types: List[str] = None) -> Dict[str, Dict]:
        """
        同时执行多种类型的搜索
        
        Args:
            query: 搜索查询
            search_types: 搜索类型列表，默认为['web', 'news']
        
        Returns:
            按类型组织的结果字典
        """
        if search_types is None:
            search_types = ['web', 'news']
        
        tasks = {}
        for search_type in search_types:
            tasks[search_type] = self.search(query, search_type=search_type)
        
        # 并发执行所有搜索
        results = await asyncio.gather(*tasks.values(), return_exceptions=True)
        
        # 组织结果
        organized_results = {}
        for i, search_type in enumerate(search_types):
            result = results[i]
            if isinstance(result, Exception):
                organized_results[search_type] = {
                    'success': False,
                    'error': str(result),
                    'search_type': search_type
                }
            else:
                organized_results[search_type] = result
        
        return organized_results
    
    async def search_with_retry(self, query: str, max_retries: int = 3, **kwargs) -> Dict:
        """
        带重试的搜索
        
        Args:
            query: 搜索查询
            max_retries: 最大重试次数
            **kwargs: 搜索选项
        
        Returns:
            搜索结果
        """
        for attempt in range(max_retries):
            result = await self.search(query, **kwargs)
            
            if result['success']:
                return result
            
            # 如果不是最后一次尝试，等待后重试
            if attempt < max_retries - 1:
                wait_time = (attempt + 1) * 2  # 指数退避
                logger.warning(f"搜索失败，{wait_time}秒后重试... (尝试 {attempt + 1}/{max_retries})")
                await asyncio.sleep(wait_time)
        
        return result  # 返回最后一次的结果
    
    async def _poll_async_result(self, response_id: str, max_retries: int = 20) -> Dict:
        """轮询异步请求结果 - 新策略：渐进式等待时间"""
        # 记录轮询统计信息
        poll_start_time = time.time()
        total_wait_time = 0
        poll_attempts = []
        
        # 动态设置总时间限制
        # 从环境变量读取，允许根据实际情况调整
        max_total_time = float(os.getenv('BRIGHTDATA_POLL_TIMEOUT', '30'))  # 默认30秒
        
        for attempt in range(max_retries):
            # 检查总时间限制
            elapsed_time = time.time() - poll_start_time
            if elapsed_time > max_total_time:
                logger.warning(f"⚠️ 轮询总时间超过 {max_total_time}秒，提前终止")
                raise Exception(f"异步结果轮询超时（总时间超限）: {response_id}")
            
            try:
                url = f"{self.result_url}?zone={self.zone}&response_id={response_id}"
                
                # 减少单次请求的超时时间，提高响应速度
                poll_timeout = aiohttp.ClientTimeout(total=5)  # 从10秒减少到5秒
                async with self._session.get(url, headers=self.headers, timeout=poll_timeout) as response:
                    if response.status == 200:
                        result = await response.json()
                        total_duration = time.time() - poll_start_time
                        logger.debug(f"✅ 异步结果获取成功，尝试 {attempt + 1}，总耗时 {total_duration:.1f}秒")
                        
                        # 记录轮询性能指标
                        logger.debug(f"BrightData轮询成功: response_id={response_id}, attempts={attempt + 1}, duration={total_duration:.1f}s")
                        
                        return result
                    elif response.status == 202:
                        # 结果还未准备好，使用新的渐进式等待策略
                        if attempt == 0:
                            wait_time = 2.0  # 第1次：等待2.0秒（给服务器初始处理时间）
                        elif attempt <= 2:
                            wait_time = 1.5  # 第2-3次：等待1.5秒（快速检查）
                        elif attempt <= 5:
                            wait_time = 2.0  # 第4-6次：等待2.0秒（正常轮询）
                        elif attempt <= 9:
                            wait_time = 3.0  # 第7-10次：等待3.0秒（减缓频率）
                        elif attempt <= 11:
                            wait_time = 4.0  # 第11-12次：等待4.0秒（处理复杂查询）
                        else:
                            wait_time = 5.0  # 第13次及以后：等待5.0秒（极慢频率）
                        
                        logger.debug(f"⏳ 结果未就绪，{wait_time}秒后重试... (尝试 {attempt + 1}/{max_retries})")
                        poll_attempts.append({"attempt": attempt + 1, "wait_time": wait_time, "status": 202})
                        total_wait_time += wait_time
                        await asyncio.sleep(wait_time)
                        continue
                    else:
                        response.raise_for_status()
                        
            except asyncio.TimeoutError:
                # 超时处理：根据当前尝试次数决定等待时间
                if attempt == 0:
                    wait_time = 2.0
                elif attempt <= 2:
                    wait_time = 1.5
                else:
                    wait_time = 2.0
                logger.warning(f"⚠️ 轮询超时，{wait_time}秒后重试 (尝试 {attempt + 1}/{max_retries})")
                if attempt == max_retries - 1:
                    raise Exception(f"异步结果轮询超时: {response_id}")
                await asyncio.sleep(wait_time)
            except Exception as e:
                if attempt == max_retries - 1:
                    logger.error(f"❌ 异步结果轮询失败: {e}")
                    raise e
                # 异常时使用较短等待时间
                await asyncio.sleep(1.0)
        
        raise Exception(f"异步结果轮询超时: {response_id}")
    
    def _get_wait_times(self, attempt: int) -> list:
        """计算到当前尝试的总等待时间"""
        times = []
        for i in range(attempt):
            if i < 5:
                times.append(0.5)
            else:
                times.append(min(3.0, 0.5 * (1.5 ** (i - 5))))
        return times
    
    def _build_serp_params(self, query: str, options: dict) -> dict:
        """构建SERP API参数 - 关键优化功能"""
        params = {
            "q": query,
            "brd_json": 1,  # 关键：使用BrightData原生JSON解析
            "num": options.get("num_results", 10)
        }
        
        # 只有明确指定时才设置语言和国家
        if "language" in options:
            params["hl"] = options["language"]
            # 为中文查询自动设置中国地区
            if options["language"] == "zh-CN" and "country" not in options:
                params["gl"] = "cn"
        if "country" in options:
            params["gl"] = options["country"].lower()
        
        # 分页支持
        page = options.get("page", 1)
        if page > 1:
            params["start"] = (page - 1) * params["num"]
        
        # 时间范围过滤
        if date_range := options.get("date_range"):
            params["tbs"] = f"qdr:{date_range}"
        
        # 搜索类型映射
        search_type = options.get("search_type", "web")
        if search_type == "news":
            params["tbm"] = "nws"
        elif search_type == "images":
            params["tbm"] = "isch"
        elif search_type == "videos":
            params["tbm"] = "vid"
        elif search_type == "shopping":
            params["tbm"] = "shop"
        elif search_type == "books":
            params["tbm"] = "bks"
        
        # 地理位置精确控制
        if location := options.get("location"):
            if location.replace(" ", "").replace(",", "").isalpha():
                params["uule"] = f"w+{location.replace(' ', '+')}"
            else:
                params["uule"] = location
        
        # 设备类型控制
        device = options.get("device", "desktop")
        if device == "mobile":
            params["brd_mobile"] = 1
        elif device == "ios":
            params["brd_mobile"] = "ios"
        elif device == "android":
            params["brd_mobile"] = "android"
        
        return params
    
    def _process_serp_results(self, results: Dict) -> List[Dict]:
        """处理SERP API返回的JSON结果 - 原生JSON解析"""
        if not results or not isinstance(results, dict):
            return []
        
        processed_results = []
        
        # 处理有机搜索结果（实际字段名是 "organic"）
        organic_results = results.get("organic", [])
        for i, result in enumerate(organic_results):
            processed_result = {
                'position': i + 1,
                'title': result.get('title', ''),
                'url': result.get('link', ''),
                'snippet': result.get('description', ''),  # BrightData使用 'description'
                'site': result.get('display_link', ''),
            }
            
            # 添加可选字段
            if 'date' in result:
                processed_result['date'] = result['date']
            if 'extensions' in result:
                processed_result['extensions'] = result['extensions']
            
            processed_results.append(processed_result)
        
        # 处理新闻结果
        if 'news' in results:
            for i, news in enumerate(results['news']):
                processed_results.append({
                    'position': len(processed_results) + 1,
                    'title': news.get('title', ''),
                    'url': news.get('link', ''),
                    'snippet': news.get('description', ''),
                    'source': news.get('source', ''),
                    'date': news.get('date', ''),
                    'type': 'news'
                })
        
        return processed_results
    
    def _build_search_url(self, query: str, options: dict) -> str:
        """构建Google搜索URL"""
        # URL编码查询
        encoded_query = quote_plus(query)
        
        # 基础URL选择
        search_type = options.get("search_type", "web")
        if search_type == "academic":
            base_url = f"https://scholar.google.com/scholar?q={encoded_query}"
        else:
            base_url = f"https://www.google.com/search?q={encoded_query}"
        
        # 构建参数
        params = []
        
        # 结果数量
        num = options.get("num_results", 10)
        params.append(f"num={num}")
        
        # 语言设置
        lang = options.get("language", "en")
        params.append(f"hl={lang}")
        
        # 国家/地区设置
        country = options.get("country", "US")
        params.append(f"gl={country}")
        
        # 时间范围
        date_range = options.get("date_range")
        if date_range:
            # h(小时), d(天), w(周), m(月), y(年)
            params.append(f"tbs=qdr:{date_range}")
        
        # 搜索类型特定参数
        if search_type == "news":
            params.append("tbm=nws")
        elif search_type == "images":
            params.append("tbm=isch")
        elif search_type == "videos":
            params.append("tbm=vid")
        elif search_type == "books":
            params.append("tbm=bks")
        elif search_type == "shopping":
            params.append("tbm=shop")
        
        # 安全搜索
        safe_search = options.get("safe_search", "off")
        if safe_search != "off":
            params.append(f"safe={safe_search}")
        
        # 组合完整URL
        if params:
            full_url = f"{base_url}&{'&'.join(params)}"
        else:
            full_url = base_url
            
        return full_url
    
    def _parse_google_html(self, html: str) -> List[Dict]:
        """解析Google搜索结果HTML - 简化版（fallback使用）"""
        # 注意：此方法仅作为fallback使用，主要使用SERP API的原生JSON解析
        soup = BeautifulSoup(html, 'html.parser')
        results = []
        
        # 查找基本结果容器
        result_selectors = ['div.g', 'div.MjjYud', 'div.tF2Cxc']
        
        search_items = []
        for selector in result_selectors:
            search_items = soup.select(selector)
            if search_items:
                break
        
        # 简化的结果提取
        for i, item in enumerate(search_items[:10]):
            try:
                h3 = item.find('h3')
                link = item.find('a', href=True)
                
                if h3 and link:
                    result = {
                        'position': i + 1,
                        'title': h3.get_text(strip=True),
                        'url': link.get('href', ''),
                        'snippet': ''  # HTML fallback模式下snippet提取简化
                    }
                    
                    # 提取摘要
                    for elem in item.find_all(['div', 'span']):
                        text = elem.get_text(strip=True)
                        if 50 <= len(text) <= 300:
                            result['snippet'] = text
                            break
                    
                    if result['url'].startswith('http'):
                        results.append(result)
            except:
                continue
        
        return results
    
    def _extract_result_info(self, item, position: int) -> Optional[Dict]:
        """从单个搜索结果项提取信息"""
        result = {'position': position}
        
        # 提取标题和链接
        link_elem = item.find('a')
        title_elem = item.find('h3')
        
        if link_elem and title_elem:
            result['title'] = title_elem.get_text(strip=True)
            result['url'] = link_elem.get('href', '')
        else:
            # 尝试其他选择器
            link_elem = item.select_one('a[href]')
            if link_elem:
                result['url'] = link_elem.get('href', '')
                title_elem = link_elem.find('h3') or link_elem.find('h2')
                if title_elem:
                    result['title'] = title_elem.get_text(strip=True)
        
        # 提取摘要
        snippet_selectors = [
            'div.VwiC3b',  # 新版Google
            'span.aCOpRe',  # 备选
            'div.s',  # 旧版
            'div.st'  # 更旧版
        ]
        
        for selector in snippet_selectors:
            snippet_elem = item.select_one(selector)
            if snippet_elem:
                result['snippet'] = snippet_elem.get_text(strip=True)
                break
        
        # 提取日期
        date_elem = item.select_one('span.MUxGbd')
        if date_elem:
            result['date'] = date_elem.get_text(strip=True)
        
        # 提取站点信息
        cite_elem = item.select_one('cite')
        if cite_elem:
            result['site'] = cite_elem.get_text(strip=True)
        
        return result if result.get('url') else None
    


    async def search_for_deepsearch(self, query: str, context: Optional[Dict] = None) -> Dict:
        """
        为DeepSearch优化的搜索方法
        
        Args:
            query: 搜索查询
            context: 搜索上下文（可选）
        
        Returns:
            优化的搜索结果
        """
        context = context or {}
        
        # 基于上下文优化搜索参数
        search_options = {
            'num_results': context.get('num_results', 10),
            'search_type': context.get('search_type', 'web'),
            'date_range': context.get('date_range', 'y'),
            'language': context.get('language', 'en'),
            'country': context.get('country', 'US')
        }
        
        # 执行搜索（带重试）
        result = await self.search_with_retry(query, **search_options)
        
        # 后处理：添加相关性评分
        if result['success'] and result.get('results'):
            for i, item in enumerate(result['results']):
                item['relevance_score'] = 1.0 - (i * 0.1)
                item['needs_crawl'] = item['relevance_score'] > 0.7
        
        return result


# 使用示例
async def example_usage():
    """BrightData异步客户端使用示例"""
    
    # 创建客户端
    async with BrightDataAsyncClient(
        api_key="7f43b8faf2b1e3ccb9c6982c443d9138edc76fb0384bdc551d9ca2da5576ee4a"
    ) as client:
        
        # 1. 简单搜索
        result = await client.search("Agentic RAG implementation")
        if result['success']:
            print(f"找到 {len(result['results'])} 个结果")
            for item in result['results'][:3]:
                print(f"- {item['title']}")
                print(f"  {item['url']}")
        
        # 2. 批量搜索
        queries = [
            "S3 framework search",
            "LLM routing strategies",
            "RAG optimization techniques"
        ]
        batch_results = await client.batch_search(queries, num_results=5)
        print(f"\n批量搜索完成: {len([r for r in batch_results if r['success']])} 成功")
        
        # 3. 多类型搜索
        multi_results = await client.multi_type_search(
            "AI research 2024",
            search_types=['web', 'news', 'academic']
        )
        for search_type, result in multi_results.items():
            if result['success']:
                print(f"\n{search_type.upper()}: {len(result['results'])} 结果")
        
        # 4. 带重试的搜索
        retry_result = await client.search_with_retry(
            "complex query that might fail",
            max_retries=3
        )
        print(f"\n重试搜索: {'成功' if retry_result['success'] else '失败'}")


# DeepSearch集成示例
async def deepsearch_integration():
    """DeepSearch集成示例"""
    
    async with BrightDataAsyncClient(
        api_key="7f43b8faf2b1e3ccb9c6982c443d9138edc76fb0384bdc551d9ca2da5576ee4a"
    ) as client:
        
        # DeepSearch优化搜索
        context = {
            'search_type': 'web',
            'date_range': 'y',
            'num_results': 20
        }
        
        result = await client.search_for_deepsearch(
            "Agentic RAG best practices",
            context
        )
        
        if result['success']:
            print(f"\nDeepSearch搜索结果:")
            high_relevance = [r for r in result['results'] if r.get('needs_crawl')]
            print(f"高相关性结果（需要深度爬取）: {len(high_relevance)}")
            
            for item in high_relevance:
                print(f"- [{item['relevance_score']:.2f}] {item['title']}")


if __name__ == "__main__":
    # 运行示例
    asyncio.run(example_usage())