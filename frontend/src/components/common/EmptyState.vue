<template>
  <div class="empty-state">
    <p>{{ message }}</p>
    <button v-if="actionText" class="add-btn" @click="$emit('action')">{{ actionText }}</button>
  </div>
</template>

<script setup>
defineProps({ message: { type: String, required: true }, actionText: { type: String, default: '' } })
defineEmits(['action'])
</script>

<style scoped>
.empty-state { width: 100%; text-align: center; padding: 60px 20px; color: var(--text-muted); }
.empty-state p { font-size: 15px; margin-bottom: 16px; }
.add-btn {
  padding: 8px 18px; background: var(--accent); color: #fff;
  border: none; border-radius: 8px; cursor: pointer;
  font-size: 14px; font-weight: 600; transition: background 0.2s;
}
.add-btn:hover { background: var(--accent-dim); }
</style>
