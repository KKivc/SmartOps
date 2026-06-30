from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os

DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine)     # 模块加载时创建一次 factory

def get_session():
    return SessionLocal()   # 每次用同一个 factory 生产 session

def init_db():
    # 延迟导入，避免循环依赖
    from store.models import Base
    Base.metadata.create_all(bind=engine)