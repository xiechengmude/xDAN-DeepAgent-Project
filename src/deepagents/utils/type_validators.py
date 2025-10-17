#!/usr/bin/env python3
"""
严格类型验证工具
==============
为整个研究流程提供统一的类型检查和验证机制
"""

from typing import Dict, List, Any, Optional, Union, TypeVar, Callable, Tuple
from dataclasses import dataclass
import logging
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage

logger = logging.getLogger(__name__)

T = TypeVar('T')


@dataclass
class ValidationResult:
    """验证结果"""
    is_valid: bool
    error_message: str = ""
    error_code: str = ""
    field_name: str = ""


class StrictTypeValidator:
    """严格类型验证器"""
    
    @staticmethod
    def validate_string(value: Any, field_name: str, allow_empty: bool = False) -> ValidationResult:
        """验证字符串类型"""
        if not isinstance(value, str):
            return ValidationResult(
                is_valid=False,
                error_message=f"{field_name} must be string, got {type(value).__name__}",
                error_code="TYPE_ERROR",
                field_name=field_name
            )
        
        if not allow_empty and not value.strip():
            return ValidationResult(
                is_valid=False,
                error_message=f"{field_name} cannot be empty or whitespace-only",
                error_code="EMPTY_VALUE",
                field_name=field_name
            )
        
        return ValidationResult(is_valid=True)
    
    @staticmethod
    def validate_list(value: Any, field_name: str, item_type: type = None, allow_empty: bool = True) -> ValidationResult:
        """验证列表类型"""
        if not isinstance(value, list):
            return ValidationResult(
                is_valid=False,
                error_message=f"{field_name} must be list, got {type(value).__name__}",
                error_code="TYPE_ERROR",
                field_name=field_name
            )
        
        if not allow_empty and len(value) == 0:
            return ValidationResult(
                is_valid=False,
                error_message=f"{field_name} cannot be empty list",
                error_code="EMPTY_LIST",
                field_name=field_name
            )
        
        # 验证列表项类型
        if item_type is not None:
            for i, item in enumerate(value):
                if not isinstance(item, item_type):
                    return ValidationResult(
                        is_valid=False,
                        error_message=f"{field_name}[{i}] must be {item_type.__name__}, got {type(item).__name__}",
                        error_code="LIST_ITEM_TYPE_ERROR",
                        field_name=field_name
                    )
        
        return ValidationResult(is_valid=True)
    
    @staticmethod
    def validate_dict(value: Any, field_name: str, required_keys: List[str] = None) -> ValidationResult:
        """验证字典类型"""
        if not isinstance(value, dict):
            return ValidationResult(
                is_valid=False,
                error_message=f"{field_name} must be dict, got {type(value).__name__}",
                error_code="TYPE_ERROR",
                field_name=field_name
            )
        
        # 验证必需键
        if required_keys:
            missing_keys = [key for key in required_keys if key not in value]
            if missing_keys:
                return ValidationResult(
                    is_valid=False,
                    error_message=f"{field_name} missing required keys: {missing_keys}",
                    error_code="MISSING_KEYS",
                    field_name=field_name
                )
        
        return ValidationResult(is_valid=True)
    
    @staticmethod
    def validate_messages(value: Any, field_name: str = "messages") -> ValidationResult:
        """验证 messages 字段"""
        if not isinstance(value, list):
            return ValidationResult(
                is_valid=False,
                error_message=f"{field_name} must be list, got {type(value).__name__}",
                error_code="TYPE_ERROR",
                field_name=field_name
            )
        
        if len(value) == 0:
            return ValidationResult(
                is_valid=False,
                error_message=f"{field_name} cannot be empty",
                error_code="EMPTY_MESSAGES",
                field_name=field_name
            )
        
        # 验证每个消息
        for i, msg in enumerate(value):
            if not isinstance(msg, BaseMessage):
                return ValidationResult(
                    is_valid=False,
                    error_message=f"{field_name}[{i}] must be BaseMessage, got {type(msg).__name__}",
                    error_code="MESSAGE_TYPE_ERROR",
                    field_name=field_name
                )
            
            if not hasattr(msg, 'content') or not isinstance(msg.content, str):
                return ValidationResult(
                    is_valid=False,
                    error_message=f"{field_name}[{i}].content must be string",
                    error_code="MESSAGE_CONTENT_ERROR",
                    field_name=field_name
                )
        
        return ValidationResult(is_valid=True)


class SubAgentStateValidator:
    """SubAgent 状态验证器"""
    
    @staticmethod
    def validate_input_state(state: Dict[str, Any]) -> ValidationResult:
        """验证 SubAgent 输入状态"""
        validator = StrictTypeValidator()
        
        # 验证 task_id
        if "task_id" in state:
            result = validator.validate_string(state["task_id"], "task_id")
            if not result.is_valid:
                return result
        
        # 验证 task (必需)
        if "task" not in state:
            return ValidationResult(
                is_valid=False,
                error_message="task field is required",
                error_code="MISSING_FIELD",
                field_name="task"
            )
        
        result = validator.validate_string(state["task"], "task", allow_empty=False)
        if not result.is_valid:
            return result
        
        # 验证 messages (必需)
        if "messages" not in state:
            return ValidationResult(
                is_valid=False,
                error_message="messages field is required",
                error_code="MISSING_FIELD",
                field_name="messages"
            )
        
        result = validator.validate_messages(state["messages"])
        if not result.is_valid:
            return result
        
        # 验证 iteration_round (可选)
        if "iteration_round" in state and not isinstance(state["iteration_round"], int):
            return ValidationResult(
                is_valid=False,
                error_message="iteration_round must be int",
                error_code="TYPE_ERROR",
                field_name="iteration_round"
            )
        
        return ValidationResult(is_valid=True)
    
    @staticmethod
    def validate_output_result(result: Dict[str, Any]) -> ValidationResult:
        """验证 SubAgent 输出结果"""
        validator = StrictTypeValidator()
        
        # 验证顶级结构
        if "subagent_results" not in result:
            return ValidationResult(
                is_valid=False,
                error_message="subagent_results field is required",
                error_code="MISSING_FIELD",
                field_name="subagent_results"
            )
        
        result_val = validator.validate_list(result["subagent_results"], "subagent_results", allow_empty=False)
        if not result_val.is_valid:
            return result_val
        
        # 验证每个子代理结果
        for i, subagent_result in enumerate(result["subagent_results"]):
            field_prefix = f"subagent_results[{i}]"
            
            # 验证必需字段
            required_fields = ["agent_id", "task", "result"]
            for field in required_fields:
                if field not in subagent_result:
                    return ValidationResult(
                        is_valid=False,
                        error_message=f"{field_prefix}.{field} is required",
                        error_code="MISSING_FIELD",
                        field_name=f"{field_prefix}.{field}"
                    )
            
            # 验证字段类型
            str_result = validator.validate_string(subagent_result["agent_id"], f"{field_prefix}.agent_id")
            if not str_result.is_valid:
                return str_result
            
            str_result = validator.validate_string(subagent_result["task"], f"{field_prefix}.task")
            if not str_result.is_valid:
                return str_result
            
            # 验证 result 结构
            inner_result = subagent_result["result"]
            dict_result = validator.validate_dict(inner_result, f"{field_prefix}.result", 
                                                 required_keys=["content", "sources", "key_findings"])
            if not dict_result.is_valid:
                return dict_result
            
            # 验证 result 内部字段
            str_result = validator.validate_string(inner_result["content"], f"{field_prefix}.result.content")
            if not str_result.is_valid:
                return str_result
            
            list_result = validator.validate_list(inner_result["sources"], f"{field_prefix}.result.sources", str)
            if not list_result.is_valid:
                return list_result
            
            list_result = validator.validate_list(inner_result["key_findings"], f"{field_prefix}.result.key_findings", str)
            if not list_result.is_valid:
                return list_result
        
        return ValidationResult(is_valid=True)


class LeadAgentStateValidator:
    """LeadAgent 状态验证器"""
    
    @staticmethod
    def validate_state(state: Dict[str, Any]) -> ValidationResult:
        """验证 LeadAgent 状态 - 适配 feat/langfuse_integration 分支的字段名"""
        validator = StrictTypeValidator()
        
        # 验证基础字段类型
        if not isinstance(state, dict):
            return ValidationResult(
                is_valid=False,
                error_message="state must be dict",
                error_code="TYPE_ERROR",
                field_name="state"
            )
        
        # 验证 user_query (优先) 或 query (兼容旧版)
        query_field = "user_query" if "user_query" in state else "query"
        if query_field in state:
            result = validator.validate_string(state[query_field], query_field, allow_empty=True)
            if not result.is_valid:
                return result
        
        # 验证 messages (如果存在)
        if "messages" in state and state["messages"] is not None:
            result = validator.validate_list(state["messages"], "messages")
            if not result.is_valid:
                return result
        
        # 验证其他字符串字段 (如果存在)
        optional_string_fields = ["refined_query", "refined_context", "query_type", "final_report"]
        for field in optional_string_fields:
            if field in state and state[field] is not None:
                result = validator.validate_string(state[field], field, allow_empty=True)
                if not result.is_valid:
                    return result
        
        # 验证列表字段 (如果存在)
        optional_list_fields = ["subagent_tasks", "subagent_results", "current_round_tasks"]
        for field in optional_list_fields:
            if field in state and state[field] is not None:
                result = validator.validate_list(state[field], field)
                if not result.is_valid:
                    return result
        
        # 验证整数字段 (如果存在)
        if "iteration_count" in state and state["iteration_count"] is not None:
            if not isinstance(state["iteration_count"], int):
                return ValidationResult(
                    is_valid=False,
                    error_message="iteration_count must be int",
                    error_code="TYPE_ERROR", 
                    field_name="iteration_count"
                )
        
        return ValidationResult(is_valid=True)
    
    @staticmethod
    def validate_send_data(state: Dict[str, Any]) -> ValidationResult:
        """验证 Send 分发的数据"""
        return SubAgentStateValidator.validate_input_state(state)
    
    @staticmethod
    def validate_parsed_results(parsed_results: List[Dict[str, Any]]) -> ValidationResult:
        """验证解析后的结果"""
        validator = StrictTypeValidator()
        
        if not isinstance(parsed_results, list):
            return ValidationResult(
                is_valid=False,
                error_message="parsed_results must be list",
                error_code="TYPE_ERROR",
                field_name="parsed_results"
            )
        
        for i, result in enumerate(parsed_results):
            field_prefix = f"parsed_results[{i}]"
            
            # 验证必需字段和类型
            required_string_fields = ["content", "task"]
            for field in required_string_fields:
                if field not in result:
                    return ValidationResult(
                        is_valid=False,
                        error_message=f"{field_prefix}.{field} is required",
                        error_code="MISSING_FIELD",
                        field_name=f"{field_prefix}.{field}"
                    )
                
                str_result = validator.validate_string(result[field], f"{field_prefix}.{field}")
                if not str_result.is_valid:
                    return str_result
            
            # 验证列表字段
            required_list_fields = ["sources", "key_findings"]
            for field in required_list_fields:
                if field not in result:
                    return ValidationResult(
                        is_valid=False,
                        error_message=f"{field_prefix}.{field} is required",
                        error_code="MISSING_FIELD",
                        field_name=f"{field_prefix}.{field}"
                    )
                
                list_result = validator.validate_list(result[field], f"{field_prefix}.{field}", str)
                if not list_result.is_valid:
                    return list_result
        
        return ValidationResult(is_valid=True)
    
    @staticmethod
    def validate_source_documents(source_documents: List[Dict[str, Any]]) -> ValidationResult:
        """验证源文档结构"""
        validator = StrictTypeValidator()
        
        if not isinstance(source_documents, list):
            return ValidationResult(
                is_valid=False,
                error_message="source_documents must be list",
                error_code="TYPE_ERROR",
                field_name="source_documents"
            )
        
        for i, doc in enumerate(source_documents):
            field_prefix = f"source_documents[{i}]"
            
            # 验证必需字段
            required_fields = ["url", "title", "content"]
            for field in required_fields:
                if field not in doc:
                    return ValidationResult(
                        is_valid=False,
                        error_message=f"{field_prefix}.{field} is required",
                        error_code="MISSING_FIELD",
                        field_name=f"{field_prefix}.{field}"
                    )
                
                str_result = validator.validate_string(doc[field], f"{field_prefix}.{field}")
                if not str_result.is_valid:
                    return str_result
        
        return ValidationResult(is_valid=True)


class CitationAgentValidator:
    """CitationAgent 验证器"""
    
    @staticmethod
    def validate_input_state(state: Dict[str, Any]) -> ValidationResult:
        """验证 CitationAgent 输入状态"""
        validator = StrictTypeValidator()
        
        # 验证 final_report
        if "final_report" not in state:
            return ValidationResult(
                is_valid=False,
                error_message="final_report is required",
                error_code="MISSING_FIELD",
                field_name="final_report"
            )
        
        str_result = validator.validate_string(state["final_report"], "final_report", allow_empty=False)
        if not str_result.is_valid:
            return str_result
        
        # 验证 source_documents
        if "source_documents" in state:
            result = LeadAgentStateValidator.validate_source_documents(state["source_documents"])
            if not result.is_valid:
                return result
        
        return ValidationResult(is_valid=True)


def create_validation_error_response(validation_result: ValidationResult, agent_id: str = "unknown") -> Dict[str, Any]:
    """创建验证错误响应"""
    return {
        "subagent_results": [{
            "agent_id": agent_id,
            "task": "Validation failed",
            "result": {
                "content": f"Validation error: {validation_result.error_message}",
                "sources": [],
                "key_findings": []
            },
            "error": f"{validation_result.error_code}: {validation_result.error_message}",
            "validation_error": True
        }]
    }


def strict_validate(validator_func: Callable[[Any], ValidationResult], error_response_creator: Callable = None):
    """严格验证装饰器"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            # 获取第一个参数作为验证目标 (通常是 state)
            if args:
                validation_result = validator_func(args[0])
                if not validation_result.is_valid:
                    logger.error(f"Validation failed: {validation_result.error_message}")
                    if error_response_creator:
                        return error_response_creator(validation_result)
                    else:
                        raise ValueError(validation_result.error_message)
            
            return func(*args, **kwargs)
        return wrapper
    return decorator


# 导出常用验证器实例
subagent_validator = SubAgentStateValidator()
leadagent_validator = LeadAgentStateValidator()
citation_validator = CitationAgentValidator()
type_validator = StrictTypeValidator()