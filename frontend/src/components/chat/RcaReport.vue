<template>
  <div class="rca-card">
    <div class="rca-header" @click="collapsed = !collapsed">
      <span>⚠️ RCA 诊断报告</span>
      <span class="rca-toggle">{{ collapsed ? '展开' : '收起' }}</span>
    </div>
    <div v-if="!collapsed" class="rca-body">
      <div class="rca-section">
        <div class="rca-section-title">📋 概要</div>
        <div class="rca-section-body">{{ report.summary }}</div>
      </div>

      <div v-if="report.timeline?.length" class="rca-section">
        <div class="rca-section-title">🕐 时间线</div>
        <div class="rca-timeline">
          <div v-for="(t, i) in report.timeline" :key="i" class="timeline-item">
            <span class="timeline-time">{{ t.time }}</span>
            <span class="timeline-event">{{ t.event }}</span>
            <span class="timeline-source" :class="t.source">{{ t.source }}</span>
          </div>
        </div>
      </div>

      <div v-if="report.root_cause" class="rca-section">
        <div class="rca-section-title">🔍 根因</div>
        <div class="rca-section-body">{{ report.root_cause }}</div>
      </div>

      <div v-if="report.evidence" class="rca-section">
        <div class="rca-section-title">📊 证据</div>
        <div class="evidence-grid">
          <div v-if="report.evidence.log_analysis" class="evidence-item">
            <span class="evidence-label">日志分析</span>
            <span class="evidence-value">{{ report.evidence.log_analysis }}</span>
          </div>
          <div v-if="report.evidence.metric_analysis" class="evidence-item">
            <span class="evidence-label">指标分析</span>
            <span class="evidence-value">{{ report.evidence.metric_analysis }}</span>
          </div>
          <div v-if="report.evidence.knowledge_ref" class="evidence-item">
            <span class="evidence-label">知识库参考</span>
            <span class="evidence-value">{{ report.evidence.knowledge_ref }}</span>
          </div>
        </div>
      </div>

      <div v-if="report.recommendation?.length" class="rca-section">
        <div class="rca-section-title">🔧 修复建议</div>
        <ol class="recommendation-list">
          <li v-for="(r, i) in report.recommendation" :key="i">{{ r }}</li>
        </ol>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'

defineProps({ report: { type: Object, required: true } })
const collapsed = ref(false)
</script>

<style scoped>
.rca-card { border: 1px solid var(--accent); border-radius: 12px; overflow: hidden; margin-bottom: 8px; }
.rca-header { display: flex; justify-content: space-between; align-items: center; padding: 12px 16px; background: rgba(6,182,212,0.08); cursor: pointer; font-weight: 600; font-size: 14px; }
.rca-toggle { font-size: 12px; color: var(--text-muted); }
.rca-body { padding: 16px; }
.rca-section { margin-bottom: 16px; }
.rca-section:last-child { margin-bottom: 0; }
.rca-section-title { font-size: 13px; font-weight: 600; color: var(--accent); margin-bottom: 6px; }
.rca-section-body { font-size: 14px; line-height: 1.6; }
.rca-timeline { display: flex; flex-direction: column; gap: 6px; }
.timeline-item { display: flex; align-items: center; gap: 8px; font-size: 13px; padding: 4px 8px; background: var(--bg); border-radius: 6px; }
.timeline-time { color: var(--text-muted); font-family: monospace; min-width: 50px; }
.timeline-event { flex: 1; }
.timeline-source { font-size: 11px; padding: 2px 8px; border-radius: 4px; font-weight: 600; }
.timeline-source.loki { background: rgba(6,182,212,0.1); color: #06b6d4; }
.timeline-source.prometheus { background: rgba(245,158,11,0.1); color: #f59e0b; }
.evidence-grid { display: flex; flex-direction: column; gap: 8px; }
.evidence-item { display: flex; gap: 8px; font-size: 13px; padding: 8px; background: var(--bg); border-radius: 6px; }
.evidence-label { font-weight: 600; min-width: 80px; color: var(--text-muted); }
.evidence-value { flex: 1; }
.recommendation-list { margin: 0; padding-left: 20px; }
.recommendation-list li { margin-bottom: 4px; font-size: 14px; line-height: 1.6; }
</style>
