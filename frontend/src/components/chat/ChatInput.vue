<template>
  <div class="chat-input-area">
    <input
      ref="inputRef"
      v-model="text"
      type="text"
      placeholder="输入你的问题，回车发送"
      @keydown.enter="send"
    />
    <button :disabled="sending || !text.trim()" @click="send">{{ sending ? '发送中...' : '发送' }}</button>
  </div>
</template>

<script setup>
import { ref, nextTick } from 'vue'

const emit = defineEmits(['send'])
const props = defineProps({ sending: { type: Boolean, default: false } })
const text = ref('')
const inputRef = ref(null)

function send() {
  const msg = text.value.trim()
  if (!msg || props.sending) return
  text.value = ''
  emit('send', msg)
  nextTick(() => inputRef.value?.focus())
}

function focus() { nextTick(() => inputRef.value?.focus()) }

defineExpose({ focus })
</script>

<style scoped>
.chat-input-area { padding: 16px 24px; border-top: 1px solid var(--card-border); display: flex; gap: 12px; }
.chat-input-area input { flex: 1; padding: 12px 16px; border: 1px solid var(--card-border); border-radius: 8px; font-size: 14px; outline: none; background: var(--bg); color: var(--text); }
.chat-input-area input:focus { border-color: var(--accent); }
.chat-input-area button { padding: 12px 24px; background: var(--accent); color: #fff; border: none; border-radius: 8px; cursor: pointer; font-size: 14px; font-weight: 600; }
.chat-input-area button:hover { background: var(--accent-dim); }
.chat-input-area button:disabled { opacity: 0.5; cursor: not-allowed; }
</style>
