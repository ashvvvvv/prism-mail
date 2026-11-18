<script setup>
import { ref, watch, nextTick } from 'vue'
import { useMailStore } from '../stores/mail'
import { X, Send } from 'lucide-vue-next'

const store = useMailStore()

const selectedMailboxId = ref(null)
const recipient = ref('')
const subject = ref('')
const bodyText = ref('')
const isSending = ref(false)
const recipientInputRef = ref(null)
const bodyInputRef = ref(null)

watch(
  () => store.isComposeOpen,
  async (isOpen) => {
    if (isOpen) {
      const preset = store.composePreset
      selectedMailboxId.value =
        preset?.mailboxId ||
        store.selectedMailboxId ||
        store.allMailboxes[0]?.id ||
        null
      recipient.value = preset?.recipient || ''
      subject.value = preset?.subject || ''
      bodyText.value = preset?.body || ''
      await nextTick()
      if (preset?.recipient) {
        bodyInputRef.value?.focus()
      } else {
        recipientInputRef.value?.focus()
      }
    } else {
      store.composePreset = null
    }
  }
)

const closeCompose = () => {
  store.isComposeOpen = false
}

const formatSenderOption = (mb) => {
  const hasNote = mb.name && mb.name !== mb.prefix && mb.name !== mb.address
  return hasNote ? `${mb.address} · ${mb.name}` : mb.address
}

const escapeHtml = (str) =>
  String(str || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')

const handleSend = async () => {
  if (!recipient.value.trim() || !subject.value.trim() || !selectedMailboxId.value || isSending.value) return
  isSending.value = true
  try {
    await store.sendMail({
      mailbox_id: selectedMailboxId.value,
      recipient: recipient.value.trim(),
      subject: subject.value.trim(),
      body_html: `<div>${escapeHtml(bodyText.value).replace(/\n/g, '<br/>')}</div>`,
      body_text: bodyText.value
    })
    recipient.value = ''
    subject.value = ''
    bodyText.value = ''
    closeCompose()
  } catch (e) {
    store.notify(`发送失败: ${e.message}`, 'error')
  } finally {
    isSending.value = false
  }
}
</script>

<template>
  <Transition name="fade-scale">
    <div
      v-if="store.isComposeOpen"
      class="fixed inset-0 pm-backdrop z-50 flex items-end sm:items-center justify-center p-0 sm:p-4"
      @click.self="closeCompose"
      @keydown.esc.prevent="closeCompose"
    >
      <div class="pm-modal rounded-t-2xl sm:rounded-2xl w-full max-w-xl max-h-[92dvh] overflow-hidden flex flex-col">
        <!-- Header -->
        <div class="h-11 px-4 border-b border-[var(--border-hairline)] flex items-center justify-between flex-shrink-0">
          <span class="text-[13px] font-semibold text-[var(--text-primary)]">撰写邮件</span>
          <button
            @click="closeCompose"
            class="p-1 rounded-lg text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-hover)] transition"
          >
            <X class="w-4 h-4" />
          </button>
        </div>

        <!-- Hairline Form Rows -->
        <div class="divide-y divide-[var(--border-hairline)] text-[12.5px] flex-shrink-0">
          <div class="flex items-center px-4 h-11 sm:h-10 gap-3">
            <span class="w-12 text-[var(--text-muted)] flex-shrink-0">发件人</span>
            <select
              v-model="selectedMailboxId"
              class="flex-1 min-w-0 truncate bg-transparent text-[var(--text-primary)] font-mono text-[12px] focus:outline-none cursor-pointer"
            >
              <option
                v-for="mb in store.allMailboxes"
                :key="mb.id"
                :value="mb.id"
                class="bg-[var(--bg-sheet)] text-[var(--text-primary)]"
              >
                {{ formatSenderOption(mb) }}
              </option>
            </select>
          </div>

          <div class="flex items-center px-4 h-11 sm:h-10 gap-3">
            <span class="w-12 text-[var(--text-muted)] flex-shrink-0">收件人</span>
            <input
              ref="recipientInputRef"
              v-model="recipient"
              type="email"
              placeholder="name@example.com"
              class="flex-1 min-w-0 bg-transparent text-[var(--text-primary)] font-mono text-[12px] placeholder-[var(--text-muted)] focus:outline-none"
            />
          </div>

          <div class="flex items-center px-4 h-11 sm:h-10 gap-3">
            <span class="w-12 text-[var(--text-muted)] flex-shrink-0">主题</span>
            <input
              v-model="subject"
              type="text"
              placeholder="邮件主题"
              class="flex-1 min-w-0 bg-transparent text-[var(--text-primary)] placeholder-[var(--text-muted)] focus:outline-none"
            />
          </div>
        </div>

        <!-- Writing Canvas -->
        <textarea
          ref="bodyInputRef"
          v-model="bodyText"
          @keydown.ctrl.enter.prevent="handleSend"
          @keydown.meta.enter.prevent="handleSend"
          rows="8"
          placeholder="输入邮件内容..."
          class="w-full flex-1 min-h-[150px] overflow-y-auto bg-transparent px-4 py-3.5 text-[13px] text-[var(--text-primary)] placeholder-[var(--text-muted)] border-t border-[var(--border-hairline)] focus:outline-none leading-[1.7] resize-none"
        />

        <!-- Footer -->
        <div class="min-h-[48px] py-2 px-4 pb-safe border-t border-[var(--border-hairline)] bg-[var(--bg-subtle)] flex items-center justify-between flex-shrink-0">
          <span class="hidden sm:flex text-[11px] text-[var(--text-muted)] items-center gap-1.5">
            <kbd class="pm-kbd">⌘</kbd>
            <kbd class="pm-kbd">↵</kbd>
            <span>快捷发送</span>
          </span>

          <div class="flex items-center gap-2 ml-auto">
            <button
              type="button"
              @click="closeCompose"
              class="px-3.5 py-1.5 rounded-lg text-[12px] text-[var(--text-secondary)] hover:bg-[var(--bg-hover)] transition"
            >
              取消
            </button>
            <button
              type="button"
              @click="handleSend"
              :disabled="isSending || !recipient.trim() || !subject.trim() || !selectedMailboxId"
              class="pm-btn-primary px-4 py-1.5 rounded-lg text-[12px] font-medium disabled:opacity-40 flex items-center gap-1.5"
            >
              <Send class="w-3.5 h-3.5" />
              <span>{{ isSending ? '发送中...' : '发送' }}</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  </Transition>
</template>
