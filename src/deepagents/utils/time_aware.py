"""
时间感知提示类
提供时间相关的上下文信息
"""

import datetime
from typing import Dict


class TimeAwarePrompt:
    """时间感知提示类"""
    
    def __init__(self):
        self.now = datetime.datetime.now()
    
    def get_current_datetime_string(self) -> str:
        """获取当前日期时间字符串"""
        beijing_tz = datetime.timezone(datetime.timedelta(hours=8))
        beijing_time = self.now.astimezone(beijing_tz)
        return beijing_time.strftime("%Y-%m-%d %H:%M:%S")
    
    def get_current_time_info(self) -> Dict[str, str]:
        """获取当前时间信息"""
        # 北京时间
        beijing_tz = datetime.timezone(datetime.timedelta(hours=8))
        beijing_time = self.now.astimezone(beijing_tz)
        
        # 计算本周和本月范围
        weekday = beijing_time.weekday()
        week_start = beijing_time - datetime.timedelta(days=weekday)
        week_end = week_start + datetime.timedelta(days=6)
        
        month_start = beijing_time.replace(day=1)
        if beijing_time.month == 12:
            month_end = beijing_time.replace(year=beijing_time.year + 1, month=1, day=1) - datetime.timedelta(days=1)
        else:
            month_end = beijing_time.replace(month=beijing_time.month + 1, day=1) - datetime.timedelta(days=1)
        
        # 市场状态判断
        hour = beijing_time.hour
        if 9 <= hour < 15:
            market_status = "交易时间"
        elif 15 <= hour < 20:
            market_status = "盘后时间"
        else:
            market_status = "休市时间"
        
        # 星期中文
        weekdays_cn = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
        weekday_cn = weekdays_cn[weekday]
        
        return {
            "beijing_time": beijing_time.strftime("%Y-%m-%d %H:%M:%S"),
            "current_date": beijing_time.strftime("%Y-%m-%d"),
            "weekday_cn": weekday_cn,
            "week_start": week_start.strftime("%Y-%m-%d"),
            "week_end": week_end.strftime("%Y-%m-%d"),
            "month_start": month_start.strftime("%Y-%m-%d"),
            "month_end": month_end.strftime("%Y-%m-%d"),
            "market_status": market_status
        }
    
    def get_current_time_context(self) -> str:
        """获取当前时间上下文 - v1.1.7兼容方法"""
        time_info = self.get_current_time_info()
        return f"Current time: {time_info['beijing_time']} (UTC+8 Beijing)"
    
    def get_time_aware_context(self) -> str:
        """获取时间感知上下文 - 统一注入版本"""
        time_info = self.get_current_time_info()
        market_context = self.get_market_context()
        
        # 统一注入：始终包含时间和市场状态信息
        context = f"""时间: {time_info['current_date']} {time_info['weekday_cn']} | 市场: {market_context['market_status']} | {market_context['data_priority']}"""
        
        return context
    
    def get_detailed_time_context(self, query: str = "") -> str:
        """获取详细时间上下文，用于需要完整时间信息的场景"""
        time_info = self.get_current_time_info()
        
        context = f"""当前时间上下文：
- 北京时间：{time_info['beijing_time']} ({time_info['weekday_cn']})
- 市场状态：{time_info['market_status']}
- 本周范围：{time_info['week_start']} 至 {time_info['week_end']}
- 本月范围：{time_info['month_start']} 至 {time_info['month_end']}"""
        
        if query:
            time_keywords = self._extract_time_keywords(query)
            if time_keywords:
                context += f"\n- 查询时间关键词：{', '.join(time_keywords)}"
        
        return context
    
    def is_time_sensitive_query(self, query: str) -> bool:
        """判断查询是否对时间敏感，决定是否启用时间感知"""
        time_sensitive_keywords = [
            # 时间相关
            "最新", "今天", "今日", "本周", "本月", "近期", "最近", "实时", "当前", "现在",
            "latest", "today", "current", "recent", "real-time", "now",
            # 市场相关  
            "股市", "行情", "股票", "市场", "财经", "盘中", "收盘", "开盘",
            # 预测相关
            "未来", "预测", "forecast", "predict", "projection", "outlook",
            # 财报相关
            "季度", "年报", "财报", "earnings", "quarterly", "annual"
        ]
        
        query_lower = query.lower()
        return any(keyword in query_lower for keyword in time_sensitive_keywords)
    
    def get_smart_time_context(self, query: str) -> str:
        """智能时间上下文 - 根据查询敏感度决定详细程度"""
        if not self.is_time_sensitive_query(query):
            return ""  # 非时间敏感查询，不添加时间信息
        
        # 时间敏感查询，使用轻量化时间上下文
        return self.get_time_aware_context(query)
    
    def _extract_time_keywords(self, query: str) -> list:
        """提取查询中的时间关键词"""
        time_keywords = [
            "最新", "今天", "今日", "本周", "本月", "近期", "最近",
            "实时", "当前", "现在", "今年", "去年", "未来", "预测",
            "latest", "today", "current", "recent", "real-time", "now"
        ]
        
        found_keywords = []
        query_lower = query.lower()
        
        for keyword in time_keywords:
            if keyword in query_lower:
                found_keywords.append(keyword)
        
        return found_keywords
    
    def get_market_context(self) -> Dict[str, str]:
        """获取市场相关的时间上下文"""
        time_info = self.get_current_time_info()
        market_status = time_info['market_status']
        
        context = {
            "market_status": market_status,
            "time_strategy": "real_time" if market_status == "交易时间" else "latest_close"
        }
        
        # 根据市场状态提供建议
        if market_status == "交易时间":
            context["data_priority"] = "实时数据优先，关注盘中动态"
            context["search_strategy"] = "优先使用实时数据源"
        elif market_status == "盘后时间":
            context["data_priority"] = "最新收盘数据，盘后公告"
            context["search_strategy"] = "关注盘后新闻和公告"
        else:
            context["data_priority"] = "最新可用数据，隔夜新闻"
            context["search_strategy"] = "综合历史和预测数据"
        
        return context