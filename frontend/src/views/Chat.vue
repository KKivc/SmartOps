<template>
  <div id="chat-page">
    <div class="chat-container">
      <div class="chat-sidebar">
        <ConversationList
          :conversations="store.conversations"
          :active-id="store.currentConvId"
          :loading="store.convLoading"
          @new="handleNew"
          @select="handleSelect"
          @delete="handleDelete"
        />
      </div>
      <div class="chat-main">
        <div v-if="!store.currentConvId" class="chat-welcome">
          <h2>👋 你好，我是 SmartOps AI 助手</h2>
          <p>我可以帮你分析服务器、排查故障、查询日志</p>
          <div class="template-grid">
            <div class="template-btn" @click="quickAsk('检查所有服务器的运行状态')">📊 检查所有服务器状态</div>
            <div class="template-btn" @click="quickAsk('分析最近的错误日志')">🔍 分析最近的错误日志</div>
            <div class="template-btn" @click="quickAsk('总结一下当前的系统资源使用情况')">📈 系统资源使用情况</div>
            <div class="template-btn" @click="quickAsk('最近有没有需要关注的告警')">🚨 当前告警汇总</div>
          </div>
        </div>

        <div v-show="store.currentConvId" ref="msgContainer" class="chat-messages">
          <Loading v-if="store.loading" type="skeleton" :count="3" :height="50" />
          <div v-else-if="store.messages.length === 0" class="chat-empty">新对话，开始提问吧</div>
          <template v-else>
            <MessageBubble v-for="m in store.messages" :key="m.id || m._key" :role="m.role" :content="m.content" />
            <div v-if="store.sending" class="message ai">
              <div class="msg-bubble">
                <div class="typing-dots"><span></span><span></span><span></span></div>
              </div>
            </div>
          </template>
        </div>

        <ChatInput
          v-show="store.currentConvId"
          ref="chatInput"
          :sending="store.sending"
          @send="handleSend"
        />
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, nextTick, onMounted } from 'vue'
import { useChatStore } from '../stores/chat'
import ConversationList from '../components/chat/ConversationList.vue'
import ChatInput from '../components/chat/ChatInput.vue'
import MessageBubble from '../components/chat/MessageBubble.vue'
import Loading from '../components/common/Loading.vue'

const store = useChatStore()
const msgContainer = ref(null)
const chatInput = ref(null)

function scrollToBottom() {
  nextTick(() => {
    if (msgContainer.value) {
      msgContainer.value.scrollTop = msgContainer.value.scrollHeight
    }
  })
}

watch(() => store.messages.length, scrollToBottom)
watch(() => store.sending, scrollToBottom)

onMounted(() => store.fetchConversations())

async function handleNew() {
  const conv = await store.createConversation()
  store.currentConvId = conv.id
  nextTick(() => chatInput.value?.focus())
}

async function handleSelect(id) {
  await store.selectConversation(id)
  nextTick(() => chatInput.value?.focus())
}

async function handleDelete(id) {
  await store.deleteConversation(id)
}

async function handleSend(text) {
  await store.sendMessage(text)
  scrollToBottom()
}

async function quickAsk(text) {
  if (!store.currentConvId) {
    const conv = await store.createConversation()
    store.currentConvId = conv.id
  }
  await handleSend(text)
}
</script>

<style scoped>
#chat-page { height: calc(100vh - 120px); }
.chat-container { display: flex; height: 100%; background: var(--card-bg); border: 1px solid var(--card-border); border-radius: 12px; overflow: hidden; box-shadow: var(--shadow); }
.chat-sidebar { width: 260px; min-width: 260px; border-right: 1px solid var(--card-border); display: flex; flex-direction: column; background: var(--bg); }
.chat-main { flex: 1; display: flex; flex-direction: column; min-width: 0; }
.chat-welcome { flex: 1; display: flex; flex-direction: column; justify-content: center; align-items: center; padding: 40px; text-align: center; color: var(--text-muted); }
.chat-welcome h2 { font-size: 22px; margin-bottom: 8px; color: var(--text); }
.chat-welcome p { margin-bottom: 24px; font-size: 14px; }
.template-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; max-width: 480px; width: 100%; }
.template-btn { padding: 16px; border: 1px solid var(--card-border); border-radius: 12px; cursor: pointer; font-size: 14px; color: var(--text); background: var(--card-bg); transition: all 0.2s; text-align: center; }
.template-btn:hover { border-color: var(--accent); color: var(--accent); }
.chat-messages { flex: 1; overflow-y: auto; padding: 24px; }
.chat-empty { text-align: center; color: var(--text-muted); padding: 40px 20px; font-size: 14px; }
.typing-dots { display: flex; gap: 4px; align-items: center; padding: 4px 0; }
.typing-dots span { width: 8px; height: 8px; background: var(--text-muted); border-radius: 50%; animation: typing 1.4s infinite; }
.typing-dots span:nth-child(2) { animation-delay: 0.2s; }
.typing-dots span:nth-child(3) { animation-delay: 0.4s; }
@keyframes typing { 0%, 60%, 100% { opacity: 0.3; transform: translateY(0); } 30% { opacity: 1; transform: translateY(-4px); } }
</style>
