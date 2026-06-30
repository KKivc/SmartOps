import os
from cryptography.fernet import Fernet

# 从环境变量读取密钥
key = os.getenv("ENCRYPTION_KEY")

try:
    # 初始化key
    key_bytes = key.encode()
    f = Fernet(key_bytes)
except Exception:
    print("error")

def password_encrypt(password: str) -> str:
    """加密"""
    # 将原生密码-->bytes
    password_bytes = password.encode()

    # 加密
    pwd_bytes = f.encrypt(password_bytes)
    # 转成str
    pwd_str = pwd_bytes.decode()
    return pwd_str

def password_decrypt(password: str)-> str:
    """解密"""
    # 将加密后的字符串-->bytes
    password_bytes = password.encode()
    # 解密
    pwd_bytes = f.decrypt(password_bytes)
    # 转成str
    pwd_str = pwd_bytes.decode()
    return pwd_str