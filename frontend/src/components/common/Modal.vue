<template>
  <Teleport to="body">
    <div v-if="visible" class="modal-overlay" @click.self="$emit('close')">
      <div class="modal-box">
        <h3>{{ title }}</h3>
        <slot />
        <div class="modal-actions">
          <button class="btn-cancel" @click="$emit('close')">取消</button>
          <button class="btn-confirm" @click="$emit('confirm')">确认</button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
defineProps({ visible: { type: Boolean, default: false }, title: { type: String, default: '' } })
defineEmits(['close', 'confirm'])
</script>

<style scoped>
.modal-overlay { position: fixed; inset: 0; z-index: 1000; background: rgba(0,0,0,0.4); display: flex; justify-content: center; align-items: center; }
.modal-box { background: var(--card-bg); border-radius: 16px; padding: 32px; width: 400px; max-width: 90vw; box-shadow: 0 20px 60px rgba(0,0,0,0.3); }
.modal-box h3 { font-size: 18px; margin-bottom: 20px; }
.modal-actions { display: flex; gap: 12px; justify-content: flex-end; margin-top: 24px; }
.modal-actions button { padding: 10px 20px; border-radius: 8px; cursor: pointer; font-size: 14px; font-weight: 600; transition: all 0.2s; }
.btn-cancel { background: var(--bg); color: var(--text-muted); border: 1px solid var(--card-border); }
.btn-confirm { background: var(--accent); color: #fff; border: none; }
.btn-confirm:hover { background: var(--accent-dim); }
</style>
