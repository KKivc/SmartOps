import os
from flask import Flask, request, jsonify, render_template
from store.db import init_db, get_session
from store.models import Server, Metric, Log, Probe, Conversation, Message, Alert
from datetime import datetime, timezone
from llm import agent
from collector.scheduler import start_scheduler
from collector.ssh_client import SSHClient
from store.crypto import password_encrypt
from llm.retriever import build_bm25_index

app = Flask(__name__,
            static_folder=os.path.join(os.path.dirname(__file__), 'static'),
            static_url_path='/static')


@app.route('/api/logs', methods=['POST'])
def receive_logs():
    data = request.get_json()
    name = data.get('server_name')
    if not name:
        return jsonify({"error": "server_name required"}), 400
    
    session = get_session()
    server = session.query(Server).filter_by(name=name).first()
    if not server:
        session.close()
        return jsonify({"error": "server not found"}), 404
    entries = data.get('logs', []) 
    for entry in entries:
        log = Log(
            server_id=server.id,
            log_name=entry.get('log_name'),
            content=entry.get('content'),
            level=entry.get('level', 'info')
        )
        session.add(log)
    session.commit()
    session.close()
    return jsonify({"status": "ok", "count": len(entries)})

#  前端拿到数据
@app.route("/api/servers")
def list_servers():
    """返回所有服务器的最新状态"""
    session = get_session()
    servers = session.query(Server).all()
    data = []
    for s in servers:
        metric = session.query(Metric).filter_by(
            server_id=s.id
        ).order_by(Metric.id.desc()).first()

        data.append({
            "name": s.name,
            "ip": s.ip,
            "os": s.os,
            "status": s.status,
            "last_heartbeat": str(s.last_heartbeat)[:19] if s.last_heartbeat else None,
            "cpu": metric.cpu if metric else None,
            "memory": metric.memory if metric else None,
            "disk": metric.disk if metric else None,
        })
    session.close()
    return jsonify(data)

@app.route('/api/servers', methods=['POST'])
def add_server():
    """添加服务器"""
    data = request.get_json()
    name = data.get('name')
    session = get_session()
    servers = session.query(Server).filter(Server.name==name).all()
    
    if servers:
        session.close()
        return jsonify({"error": "server already exists"})
    
    server = Server(
        name=name, 
        user=data.get('user'), 
        ip=data.get('ip'), 
        password=password_encrypt(data.get('password')),
        status='offline'
        )

    session.add(server)
    session.commit()

    try:
        # ssh连接
        client = SSHClient(
            host=data.get('ip'),
            port='22',      # 端口固定22
            user=data.get('user'),
            password=data.get("password"),
            key_path=data.get("key")
        )
        cpu = client.get_cpu()
        mem = client.get_memory()
        disk = client.get_disk()
        os_info = client.exec("cat /etc/os-release | grep '^PRETTY_NAME' | cut -d'=' -f2 | tr -d '\"'")

        metric = Metric(
            server_id=server.id,
            cpu=cpu,
            memory=mem,
            disk=disk
        )
        server.status = 'online'
        server.os=os_info
        server.last_heartbeat = datetime.now(timezone.utc)

        session.add(metric) 
        session.commit()
        client.close()
        session.close()
        
    except Exception:
        session.close()
        return jsonify({ "error": "SSH 连接失败，请检查用户名和密码"})

    # 尝试自动更新云服务器 Prometheus 目标
    try:
        from collector.cloud_helper import update_prometheus_targets
        session2 = get_session()
        all_servers = [
            {"name": s.name, "ip": s.ip, "status": s.status}
            for s in session2.query(Server).all()
        ]
        session2.close()
        update_prometheus_targets(all_servers)
    except Exception:
        pass  # 云服务器 SSH 未配或失败，静默跳过

    return jsonify({
        "success": "add success",
        "prometheus": "如需监控指标，请在云服务器上配置 node_exporter 抓取。"
    })

@app.route('/api/servers/<name>', methods=['DELETE'])
def delete_server(name):
    """删除服务器"""
    session = get_session()
    server = session.query(Server).filter(Server.name == name).first()
    if not server:
        session.close()
        return jsonify({"error": "server not found"}), 404

    # 先删关联的子记录（外键无 CASCADE）
    session.query(Metric).filter(Metric.server_id == server.id).delete()
    session.query(Log).filter(Log.server_id == server.id).delete()
    session.query(Probe).filter(Probe.server_id == server.id).delete()

    session.delete(server)
    session.commit()
    session.close()

    # 更新 Prometheus 目标
    try:
        from collector.cloud_helper import update_prometheus_targets
        session2 = get_session()
        all_servers = [
            {"name": s.name, "ip": s.ip, "status": s.status}
            for s in session2.query(Server).all()
        ]
        session2.close()
        update_prometheus_targets(all_servers)
    except Exception:
        pass

    return jsonify({"success": True})

# 历史趋势接口
@app.route('/api/servers/<name>/history')
def server_history(name):
    """
        历史趋势接口
        返回某台服务器最近的指标趋势
        按服务器名字查最近的指标记录
    """
    session = get_session()
    server = session.query(Server).filter_by(name=name).first()
    if not server:
        session.close()
        return jsonify({"error": "server not found"}), 404
    
    metric = session.query(Metric).filter_by(
        server_id=server.id
    ).order_by(Metric.id.desc()).limit(60).all()
    session.close()

    data = []
    for m in reversed(metric):
        data.append({
            "time": str(m.created_at)[:16],
            "cpu": m.cpu,
            "memory": m.memory,
            "disk": m.disk
        })
    return jsonify(data)

@app.route('/api/servers/<name>/logs')
def server_logs(name):
    data = []
    session = get_session()
    server = session.query(Server).filter_by(name=name).first()
    if not server:
        session.close()
        return jsonify({"error": "server not found"}), 404
    
    limit = request.args.get('limit', 50, type=int)
    level = request.args.get('level')

    query = session.query(Log).filter(Log.server_id==server.id) 
    if level:
        query = query.filter(Log.level == level)

    logs = query.order_by(Log.id.desc()).limit(limit).all()

    for l in logs:
        data.append({
            'log_name': l.log_name,
            'content': l.content,
            "level": l.level,
            "id": l.id
        })

    session.close()
    return jsonify(data)

@app.route('/')
def dashboard():
    return render_template('index.html')


@app.route('/api/conversations')
def list_conversations():
    """列出所有对话"""
    data = []
    session = get_session()
    conversations = session.query(Conversation).all()
    session.close()
    for c in conversations:
        data.append({
            "id": c.id,
            "summary": c.summary,
            "started_at": str(c.started_at)[:19] if c.started_at else None
        })
    return jsonify(data)

@app.route('/api/conversations', methods=['POST'])
def new_conversation():
    session = get_session()
    conv = Conversation(summary="新对话", started_at=datetime.now(timezone.utc))
    session.add(conv)
    session.commit()

    data = {
        "id": conv.id,
        "summary": conv.summary,
        "started_at": str(conv.started_at)[:19] if conv.started_at else None
    }
    session.close()
    return jsonify(data)

@app.route('/api/conversations/<int:conversation_id>', methods=['DELETE'])
def delete_conversation(conversation_id):
    """删除对话及其全部消息"""
    session = get_session()
    conv = session.query(Conversation).filter(Conversation.id == conversation_id).first()
    if not conv:
        session.close()
        return jsonify({"error": "conversation not found"}), 404
    # 先删消息，再删对话（数据库可能没有级联）
    session.query(Message).filter(Message.conversation_id == conversation_id).delete()
    session.delete(conv)
    session.commit()
    session.close()
    return jsonify({"success": True})


@app.route('/api/conversations/<int:conversation_id>/messages')
def get_conversation_messages(conversation_id):
    """获取某个对话的全部消息"""
    session = get_session()
    messages = session.query(Message).filter(
        Message.conversation_id == conversation_id
    ).order_by(Message.id).all()
    session.close()
    data = []
    for m in messages:
        data.append({
            "id": m.id,
            "role": m.role,
            "content": m.content
        })
    return jsonify(data)


@app.route('/api/alerts')
def list_alerts():
    session = get_session()
    alerts = session.query(Alert).order_by(Alert.id.desc()).limit(100).all()
    session.close()
    data = []
    for a in alerts:
        data.append({'id': a.id, 'server_name': a.server_name, 'type': a.type,
                     'message': a.message, 'value': a.value, 'status': a.status,
                     'created_at': str(a.created_at)[:19] if a.created_at else None})
    return jsonify(data)

@app.route('/api/alerts/<int:alert_id>', methods=['PATCH'])
def update_alert(alert_id):
    data = request.get_json()
    status = data.get('status')
    if status not in ('acknowledged', 'resolved'):
        return jsonify({'error': 'invalid status'}), 400
    session = get_session()
    alert = session.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        session.close()
        return jsonify({'error': 'alert not found'}), 404
    alert.status = status
    session.commit()
    session.close()
    return jsonify({'success': True})

# 提问，ai返回答案
@app.route('/api/chat', methods=['POST'])
def query_conversation():
    data = request.get_json()   # 需要前端传东西回来
    conversation_id = data.get('conversation_id')
    message = data.get('message')
    if not conversation_id or not message:
        return jsonify({"error": "conversation_id and message required"}), 400

    reply = agent.chat(conversation_id, message)
    return jsonify({"reply": reply})


@app.route('/api/logs/query', methods=['POST'])
def query_logs_direct():
    """前端直接查 Loki（绕过 Agent），返回结构化日志行列表"""
    data = request.get_json()
    from llm.mcp.loki_mcp import query_logs
    raw = query_logs.invoke(data)
    # query_logs 返回的可能是 str（空日志消息或 "\n" 拼接的行）
    if isinstance(raw, str):
        lines = raw.split("\n") if "\n" in raw else []
        # 过滤掉空结果提示信息
        if not lines:
            return jsonify([])
        return jsonify([
            {"content": line, "timestamp": "", "level": ""}
            for line in lines if line.strip()
        ])
    return jsonify([])


@app.route('/api/logs/analyze', methods=['POST'])
def analyze_logs_direct():
    """前端直接分析 Loki 错误"""
    data = request.get_json()
    from llm.mcp.loki_mcp import analyze_errors
    return jsonify(analyze_errors.invoke(data))


@app.route('/api/metrics/current', methods=['POST'])
def metrics_current():
    """前端直接查 Prometheus 即时指标"""
    data = request.get_json()
    from llm.mcp.prometheus_mcp import query_metric
    return jsonify(query_metric.invoke(data))


@app.route('/api/prometheus/targets')
def prometheus_targets():
    """返回 Prometheus HTTP SD 格式的 node_exporter 抓取目标列表"""
    session = get_session()
    servers = session.query(Server).filter_by(status='online').all()
    session.close()

    targets = []
    for s in servers:
        if s.ip:
            targets.append({
                "targets": [f"{s.ip}:9100"],
                "labels": {"server": s.name},
            })

    return jsonify(targets)


# Vue Router 支持：所有非 API / 非 static 路径返回 index.html
@app.route('/<path:path>')
def spa_fallback(path):
    if path.startswith('api/') or path.startswith('static/'):
        return jsonify({"error": "not found"}), 404
    return render_template('index.html')


if __name__ == '__main__':
    # 启动自动建表
    with app.app_context():
        init_db()
    # 启动 BM25 索引构建
    build_bm25_index()
    # 启动定时任务
    start_scheduler()
    app.run(host="127.0.0.1", port=5001, debug=True)
    


