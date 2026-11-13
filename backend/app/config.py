"""
配置管理模块 - 多 Agent 协作模式
"""
from pathlib import Path
from typing import List, Dict
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# 获取项目根目录
BASE_DIR = Path(__file__).resolve().parent.parent


def find_env_file() -> Path:
    """查找 .env 文件"""
    env_paths = [
        BASE_DIR / ".env",
        BASE_DIR.parent / ".env",
        Path.cwd() / ".env",
    ]
    for path in env_paths:
        if path.exists():
            return path
    return None

# 相当于 application.yml、配置类
class Settings(BaseSettings):
    """应用配置类"""

    model_config = SettingsConfigDict(
        env_file=find_env_file(),
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # API配置
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8002
    API_RELOAD: bool = False

    # LLM配置
    LLM_API_KEY: str
    LLM_API_BASE: str = None
    LLM_MODEL: str = None
    LLM_TEMPERATURE: float = 0.3
    LLM_MAX_TOKENS: int = 4096
    LLM_TIMEOUT: int = 60

    # 外部服务配置
    TICKET_API_URL: str = "http://localhost:9001"
    KB_API_URL: str = "http://localhost:9002"
    SEARCH_API_URL: str = "http://localhost:9003"

    # 向量数据库配置
    VECTOR_DB_TYPE: str = "QDRANT"

    # Elasticsearch 配置
    ES_URL: str = "http://localhost:9200"
    ES_INDEX: str = "knowledge_base"
    ES_VECTOR_DIMS: int = 1024

    # Qdrant 配置
    QDRANT_URL: str = ""
    QDRANT_PORT: int = 80
    QDRANT_COLLECTION: str = ""
    QDRANT_VECTOR_SIZE: int = 1024
    QDRANT_INDEXES: Dict = {}

    # 向量模型配置
    EMBEDDINGS_MODEL: str = "bge-m3"
    EMBEDDINGS_URL: str = ""
    USE_INTERNAL_VECTOR_DB: bool = True

    # 会话配置
    SESSION_TTL: int = 3600
    MAX_SESSIONS: int = 1000

    # CORS配置
    CORS_ORIGINS: List[str] = ["*"]  # 白名单列表
    CORS_ALLOW_CREDENTIALS: bool = True  # 是否允许跨域请求携带 Cookie 等凭证

    ZHIPU_API_KEY: str = ""

    # 日志配置
    LOG_LEVEL: str = "INFO"  # 日志级别

    @field_validator("QDRANT_INDEXES", mode="before")
    @classmethod
    def validate_qdrant_indexes(cls, v):
        """验证 QDRANT_INDEXES 配置"""
        if v is None:
            return {}
        if isinstance(v, dict):
            return v
        # 如果是字符串，尝试解析为 JSON
        if isinstance(v, str):
            import json
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return {}
        return {}


settings = Settings()