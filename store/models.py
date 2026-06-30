from sqlalchemy import Column, ForeignKey, Boolean, BigInteger, Integer, Float, String, Text, DateTime, func
from sqlalchemy.orm import declarative_base
from datetime import datetime, timezone

Base = declarative_base()   # 父类

# 服务器
class Server(Base):
    __tablename__ = 'servers'
    id = Column(Integer, primary_key=True)
    name = Column(String(20), unique=True)
    user = Column(String(20))
    password = Column(String(100))
    ip = Column(String(45))
    os = Column(String(20))     # 系统
    last_heartbeat = Column(DateTime)   # 最后心跳时间
    status = Column(String(10))     # 在线状态

# 指标
class Metric(Base):
    __tablename__ = 'metrics'
    server_id = Column(Integer, ForeignKey('servers.id'), nullable=False)
    id = Column(Integer, primary_key=True)
    cpu = Column(Float)
    memory = Column(Float)
    disk = Column(Float)
    net_recv = Column(BigInteger)      # 网络接收字节数
    net_sent = Column(BigInteger)      # 网络发送字节数
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))       # 采集时间

# 服务
class Probe(Base):
    __tablename__ = 'probes'
    server_id = Column(Integer, ForeignKey('servers.id'), nullable=False)
    id = Column(Integer, primary_key=True)
    name = Column(String(20))       # 服务名
    url = Column(String(50))        # 服务url
    status = Column(Boolean)        # 是否正常
    latency = Column(Integer)       # 响应时间
    diagnosis = Column(Text)        # llm生成的故障诊断

# 日志
class Log(Base):
    __tablename__ = 'logs'
    server_id = Column(Integer, ForeignKey('servers.id'), nullable=False)
    id = Column(Integer, primary_key=True)
    log_name = Column(String(20))
    content = Column(Text)
    level = Column(String(20))      # 级别："error" / "warn" / "info"

# 对话
class Conversation(Base):
    __tablename__ = 'conversations'
    server_id = Column(Integer, ForeignKey('servers.id'), nullable=True)
    id = Column(Integer, primary_key=True)
    summary = Column(Text)      # 对话摘要
    started_at = Column(DateTime)# 对话开始时间

# 消息
class Message(Base):
    __tablename__ = 'messages'
    conversation_id = Column(Integer, ForeignKey('conversations.id', ondelete='CASCADE'), nullable=False)
    id = Column(Integer, primary_key=True)
    role = Column(Text)
    content = Column(Text)
    token = Column(Integer)

# 告警
class Alert(Base):
    __tablename__ = 'alert'
    id = Column(Integer, primary_key=True)
    server_name  = Column(String(20))
    type = Column(String(20))   # 告警类型 offline、cpu、memory、disk
    message = Column(Text)
    value = Column(Integer)     # 触发时的数值
    status = Column(String(20)) # 状态：open / acknowledged / resolved
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    resolved_at = Column(DateTime, default=None)
