#!/bin/bash
# SmartOps Prometheus 抓取目标同步脚本
# 在云服务器上运行，从本地 Flask API 获取 node_exporter 目标列表
# 推荐通过 crontab 定时执行：*/5 * * * * /root/smartops-infra/sync-prometheus-targets.sh

FLASK_API_URL="http://<替换为本地FlaskIP>:5001"
TARGETS_DIR="/etc/prometheus/targets"

mkdir -p "$TARGETS_DIR"
curl -sf "$FLASK_API_URL/api/prometheus/targets" -o "$TARGETS_DIR/nodes.json" && \
  echo "✅ Prometheus targets 已更新: $(date)" || \
  echo "❌ 获取 targets 失败: $(date)"
