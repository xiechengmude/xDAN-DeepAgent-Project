import io
import logging
from typing import Optional, Dict, Any, Tuple

# 兼容不同版本的PyPDF2
try:
    import PyPDF2
except ImportError:
    try:
        import pypdf as PyPDF2
    except ImportError:
        PyPDF2 = None

# 其他依赖
try:
    import pdfplumber
except ImportError:
    pdfplumber = None

try:
    from PIL import Image
    import pytesseract
except ImportError:
    Image = None
    pytesseract = None

try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None

try:
    import tiktoken
except ImportError:
    tiktoken = None

logger = logging.getLogger(__name__)

class PDFParser:
    """PDF解析器，支持多种PDF类型的文本提取，带token限制"""
    
    def __init__(self):
        self.max_pages = 100  # 最大处理页数限制
        self.ocr_enabled = True  # 是否启用OCR
        self.max_tokens = 8000  # 最大token数限制
        
        # 检查必要的依赖
        self.has_pymupdf = fitz is not None
        self.has_pdfplumber = pdfplumber is not None
        self.has_pypdf2 = PyPDF2 is not None
        self.has_ocr = Image is not None and pytesseract is not None
        self.has_tiktoken = tiktoken is not None
        
        # 初始化tiktoken编码器
        if self.has_tiktoken:
            try:
                self.encoding = tiktoken.encoding_for_model("gpt-4")
            except:
                # 如果获取失败，使用默认编码
                try:
                    self.encoding = tiktoken.get_encoding("cl100k_base")
                except:
                    self.encoding = None
        else:
            self.encoding = None
            logger.warning("tiktoken未安装，将使用字符计数估算token")
        
    def parse(self, file_path: str) -> Dict[str, Any]:
        """
        解析PDF文件并提取文本内容
        
        Args:
            file_path: PDF文件路径
            
        Returns:
            包含标题、内容、元数据的字典
        """
        try:
            # 尝试多种方法解析PDF
            text = self._extract_with_pymupdf(file_path)
            
            if not text or len(text.strip()) < 50:
                # 如果PyMuPDF提取失败或内容太少，尝试pdfplumber
                text = self._extract_with_pdfplumber(file_path)
            
            if not text or len(text.strip()) < 50:
                # 如果仍然失败，尝试PyPDF2
                text = self._extract_with_pypdf2(file_path)
            
            if not text or len(text.strip()) < 50:
                # 最后尝试OCR（如果启用）
                if self.ocr_enabled:
                    text = self._extract_with_ocr(file_path)
            
            # 获取PDF元数据
            metadata = self._extract_metadata(file_path)
            
            # 提取标题
            title = self._extract_title(text, metadata)
            
            # 检查并截断文本以符合token限制
            text, token_count, is_truncated = self._truncate_to_token_limit(text)
            
            return {
                "title": title,
                "content": text,
                "metadata": metadata,
                "success": bool(text and len(text.strip()) > 0),
                "token_count": token_count,
                "is_truncated": is_truncated
            }
            
        except Exception as e:
            logger.error(f"PDF解析失败: {str(e)}")
            return {
                "title": "",
                "content": "",
                "metadata": {},
                "success": False,
                "error": str(e)
            }
    
    def _extract_with_pymupdf(self, file_path: str) -> str:
        """使用PyMuPDF提取文本"""
        if not self.has_pymupdf:
            return ""
        try:
            # 设置PyMuPDF的错误处理级别，忽略非致命错误
            fitz.TOOLS.mupdf_display_errors(False)
            
            text = []
            with fitz.open(file_path) as pdf:
                num_pages = min(len(pdf), self.max_pages)
                
                for page_num in range(num_pages):
                    try:
                        page = pdf[page_num]
                        # 使用更稳健的文本提取方法
                        page_text = page.get_text("text", flags=fitz.TEXT_PRESERVE_LIGATURES | fitz.TEXT_PRESERVE_WHITESPACE)
                        if page_text:
                            # 直接添加文本内容，不添加页面标记
                            text.append(page_text.strip())
                    except Exception as page_error:
                        # 如果单页提取失败，记录但继续处理其他页
                        logger.debug(f"PyMuPDF第{page_num + 1}页提取失败: {str(page_error)}")
                        continue
                
            # 恢复错误显示
            fitz.TOOLS.mupdf_display_errors(True)
            
            # 用双换行连接各页内容
            return "\n\n".join(text)
        except Exception as e:
            logger.debug(f"PyMuPDF提取失败: {str(e)}")
            # 确保恢复错误显示
            try:
                fitz.TOOLS.mupdf_display_errors(True)
            except:
                pass
            return ""
    
    def _extract_with_pdfplumber(self, file_path: str) -> str:
        """使用pdfplumber提取文本"""
        if not self.has_pdfplumber:
            return ""
        try:
            text = []
            with pdfplumber.open(file_path) as pdf:
                num_pages = min(len(pdf.pages), self.max_pages)
                
                for i, page in enumerate(pdf.pages[:num_pages]):
                    page_text = page.extract_text()
                    if page_text:
                        text.append(page_text.strip())
                        
                    # 提取表格
                    tables = page.extract_tables()
                    for table in tables:
                        if table:
                            table_text = self._format_table(table)
                            text.append(f"\n{table_text}")
                
            return "\n\n".join(text)
        except Exception as e:
            logger.debug(f"pdfplumber提取失败: {str(e)}")
            return ""
    
    def _extract_with_pypdf2(self, file_path: str) -> str:
        """使用PyPDF2提取文本"""
        if not self.has_pypdf2:
            return ""
        try:
            text = []
            with open(file_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                num_pages = min(len(pdf_reader.pages), self.max_pages)
                
                for page_num in range(num_pages):
                    page = pdf_reader.pages[page_num]
                    page_text = page.extract_text()
                    if page_text:
                        text.append(page_text.strip())
                
            return "\n\n".join(text)
        except Exception as e:
            logger.debug(f"PyPDF2提取失败: {str(e)}")
            return ""
    
    def _extract_with_ocr(self, file_path: str) -> str:
        """使用OCR提取文本（针对扫描版PDF）"""
        if not self.has_ocr or not self.has_pymupdf:
            return ""
        try:
            # 设置PyMuPDF的错误处理级别，忽略非致命错误
            fitz.TOOLS.mupdf_display_errors(False)
            
            text = []
            with fitz.open(file_path) as pdf:
                num_pages = min(len(pdf), self.max_pages)
                
                for page_num in range(num_pages):
                    try:
                        page = pdf[page_num]
                        
                        # 将页面转换为图像
                        mat = fitz.Matrix(2, 2)  # 缩放因子
                        pix = page.get_pixmap(matrix=mat)
                        img_data = pix.tobytes("png")
                        
                        # 使用PIL打开图像
                        img = Image.open(io.BytesIO(img_data))
                        
                        # OCR识别
                        try:
                            page_text = pytesseract.image_to_string(img, lang='chi_sim+eng')
                            if page_text:
                                text.append(page_text.strip())
                        except Exception as ocr_error:
                            logger.debug(f"OCR识别第{page_num + 1}页失败: {str(ocr_error)}")
                    except Exception as page_error:
                        logger.debug(f"OCR处理第{page_num + 1}页失败: {str(page_error)}")
                        continue
                
            # 恢复错误显示
            fitz.TOOLS.mupdf_display_errors(True)
            
            return "\n\n".join(text)
        except Exception as e:
            logger.debug(f"OCR提取失败: {str(e)}")
            # 确保恢复错误显示
            try:
                fitz.TOOLS.mupdf_display_errors(True)
            except:
                pass
            return ""
    
    def _extract_metadata(self, file_path: str) -> Dict[str, Any]:
        """提取PDF元数据"""
        metadata = {}
        try:
            # 设置PyMuPDF的错误处理级别，忽略非致命错误
            if self.has_pymupdf:
                fitz.TOOLS.mupdf_display_errors(False)
            
            with fitz.open(file_path) as pdf:
                metadata = pdf.metadata or {}
                metadata['page_count'] = len(pdf)
            
            # 恢复错误显示
            if self.has_pymupdf:
                fitz.TOOLS.mupdf_display_errors(True)
                
            # 清理元数据
            cleaned_metadata = {}
            for key, value in metadata.items():
                if value and str(value).strip():
                    cleaned_metadata[key] = str(value).strip()
                    
            return cleaned_metadata
        except Exception as e:
            logger.debug(f"元数据提取失败: {str(e)}")
            # 确保恢复错误显示
            if self.has_pymupdf:
                try:
                    fitz.TOOLS.mupdf_display_errors(True)
                except:
                    pass
            return {}
    
    def _extract_title(self, text: str, metadata: Dict[str, Any]) -> str:
        """从文本或元数据中提取标题"""
        # 首先尝试从元数据获取
        if metadata.get('title'):
            return metadata['title']
        
        # 从文本的前几行尝试提取标题
        if text:
            lines = text.split('\n')
            for line in lines[:10]:  # 检查前10行
                line = line.strip()
                if line and len(line) > 5 and len(line) < 200:
                    # 简单的标题判断逻辑
                    if not any(char in line.lower() for char in ['page', '---', '___']):
                        return line
        
        return "Untitled PDF"
    
    def _format_table(self, table: list) -> str:
        """格式化表格数据"""
        if not table:
            return ""
        
        formatted_rows = []
        for row in table:
            if row:
                formatted_row = " | ".join(str(cell) if cell else "" for cell in row)
                formatted_rows.append(formatted_row)
        
        return "\n".join(formatted_rows)
    
    def set_max_pages(self, max_pages: int):
        """设置最大处理页数"""
        self.max_pages = max_pages
    
    def enable_ocr(self, enabled: bool):
        """启用或禁用OCR"""
        self.ocr_enabled = enabled
    
    def count_tokens(self, text: str) -> int:
        """计算文本的token数量"""
        if self.encoding:
            try:
                return len(self.encoding.encode(text))
            except Exception as e:
                logger.error(f"Token计数失败: {str(e)}")
        # 粗略估算：平均每4个字符约等于1个token
        return len(text) // 4
    
    def _truncate_to_token_limit(self, text: str) -> Tuple[str, int, bool]:
        """
        截断文本以符合token限制
        
        Args:
            text: 原始文本
            
        Returns:
            (截断后的文本, token数, 是否被截断)
        """
        if not text:
            return text, 0, False
        
        # 计算原始token数
        token_count = self.count_tokens(text)
        
        # 如果未超过限制，直接返回
        if token_count <= self.max_tokens:
            return text, token_count, False
        
        # 需要截断
        logger.info(f"PDF内容超过token限制 ({token_count} > {self.max_tokens})，进行截断")
        
        # 使用二分法找到合适的截断点
        left, right = 0, len(text)
        best_length = 0
        
        while left <= right:
            mid = (left + right) // 2
            mid_text = text[:mid]
            mid_tokens = self.count_tokens(mid_text)
            
            if mid_tokens <= self.max_tokens:
                best_length = mid
                left = mid + 1
            else:
                right = mid - 1
        
        # 在最佳长度处寻找合适的断句点
        truncated_text = text[:best_length]
        
        # 尝试在句号、换行等位置截断
        for delimiter in ['\n\n', '\n', '。', '. ', '！', '! ', '？', '? ']:
            last_pos = truncated_text.rfind(delimiter)
            if last_pos > best_length * 0.8:  # 如果找到的位置不会损失太多内容
                truncated_text = truncated_text[:last_pos + len(delimiter)]
                break
        
        # 添加截断标记
        truncated_text += "\n\n[内容已截断，原文过长]"
        
        # 重新计算截断后的token数
        final_token_count = self.count_tokens(truncated_text)
        
        return truncated_text, final_token_count, True
    
    def set_max_tokens(self, max_tokens: int):
        """设置最大token数限制"""
        self.max_tokens = max_tokens