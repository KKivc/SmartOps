from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL, pool_pre_ping=True)

def get_session():
    return sessionmaker(bind=engine)()

def init_db():
    # 延迟导入，避免循环依赖
    from store.models import Base
    Base.metadata.create_all(bind=engine)