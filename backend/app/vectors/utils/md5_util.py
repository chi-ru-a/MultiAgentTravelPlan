"""
MD5 工具函数
"""
import hashlib


def md5_string(s: str) -> str:
    """
    将字符串转换为 MD5 哈希

    Args:
        s: 输入字符串

    Returns:
        MD5 哈希字符串（32位）
    """
    return hashlib.md5(str(s).encode('utf-8')).hexdigest()