<template>
  <div>
    <div class="chat-sidebar-header">
      <button @click="$emit('new')">+ 新建对话</button>
    </div>
    <div class="chat-conv-list">
      <Loading v-if="loading" type="skeleton" :count="4" :height="40" />
      <div v-else-if="conversations.length === 0" class="chat-empty">暂无对话，新建一个开始吧</div>
      <div
        v-for="c in conversations"
        :key="c.id"
        class="conv-item"
        :class="{ active: c.id === activeId }"
        @click="$emit('select', c.id)"
      >
        <span class="conv-title">{{ c.summary }}</span>
        <button class="conv-del" @click.stop="$emit('delete', c.id)">✕</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import Loading from '../common/Loading.vue'
defineProps({
  conversations: { type: Array, default: () => [] },
  activeId: { type: Number, default: null },
  loading: { type: Boolean, default: false },
})
defineEmits(['new', 'select', 'delete'])
</script>

<style scoped>
.chat-sidebar-header { padding: 16px; border-bottom: 1px solid var(--card-border); }
.chat-sidebar-header button { width: 100%; padding: 10px; background: var(--accent); color: #fff; border: none; border-radius: 8px; cursor: pointer; font-size: 14px; font-weight: 600; }
.chat-sidebar-header button:hover { background: var(--accent-dim); }
.chat-conv-list { flex: 1; overflow-y: auto; padding: 8px; }
.chat-empty { text-align: center; color: var(--text-muted); padding: 40px 20px; font-size: 14px; }
.conv-item { padding: 12px; border-radius: 8px; cursor: pointer; font-size: 13px; color: var(--text); margin-bottom: 4px; display: flex; justify-content: space-between; align-items: center; transition: background 0.2s; }
.conv-item:hover { background: var(--card-border); }
.conv-item.active { background: var(--accent); color: #fff; }
.conv-title { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; flex: 1; }
.conv-del { display: none; background: none; border: none; cursor: pointer; font-size: 14px; padding: 2px 6px; border-radius: 4px; color: var(--text-muted); line-height: 1; }
.conv-item:hover .conv-del { display: block; }
.conv-del:hover { background: rgba(239,68,68,0.15); color: var(--red); }
.conv-item.active .conv-del:hover { background: rgba(255,255,255,0.2); color: #fff; }
</style>
