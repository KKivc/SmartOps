<template>
  <div class="message" :class="role">
    <div class="msg-bubble">
      <RcaReport v-if="rca" :report="rca" />
      <div v-else v-html="rendered"></div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { renderMarkdown } from '../../utils/markdown'
import { extractRcaReport } from '../../utils/rca-parser'
import RcaReport from './RcaReport.vue'

const props = defineProps({ role: { type: String, required: true }, content: { type: String, default: '' } })

const rca = computed(() => props.role === 'ai' ? extractRcaReport(props.content) : null)
const rendered = computed(() => renderMarkdown(props.content))
</script>

<style scoped>
.message { margin-bottom: 20px; max-width: 80%; }
.message.user { margin-left: auto; }
.message.ai { margin-right: auto; }
.msg-bubble { padding: 14px 18px; border-radius: 12px; font-size: 14px; line-height: 1.7; word-break: break-word; }
.message.user .msg-bubble { background: var(--accent); color: #fff; border-bottom-right-radius: 4px; }
.message.ai .msg-bubble { background: var(--bg); color: var(--text); border: 1px solid var(--card-border); border-bottom-left-radius: 4px; }
.message.ai .msg-bubble :deep(pre) { background: rgba(0,0,0,0.05); padding: 12px; border-radius: 8px; overflow-x: auto; margin: 8px 0; }
.message.ai .msg-bubble :deep(code) { background: rgba(0,0,0,0.08); padding: 2px 6px; border-radius: 4px; font-size: 13px; font-family: monospace; }
</style>
