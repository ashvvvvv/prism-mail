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

const handleSend = async () => {
  if (!recipient.value.trim() || !subject.value.trim() || !selectedMailboxId.value || isSending.value) return
  isSending.value = true
  try {
    await store.sendMail({
      mailbox_id: selectedMailboxId.value,
      recipient: recipient.value.trim(),
      subject: subject.value.trim(),
      body_html: `<div>${bodyText.value.replace(/\n/g, '<br/>')}</div>`,
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
  <Transition name="folio-fade">
    <div
      v-if="store.isComposeOpen"
      class="fixed inset-0 ed-backdrop z-50 flex items-end sm:items-center justify-center p-0 sm:p-4"
      @click.self="closeCompose"
      @keydown.esc.prevent="closeCompose"
    >
      <div class="ed-folio-modal w-full max-w-2xl max-h-[92dvh] overflow-hidden flex flex-col">
        <!-- Editorial Letterhead -->
        <div class="px-4 sm:px-5 py-3 border-b border-[var(--rule-medium)] bg-[var(--bg-linen)] flex items-center justify-between flex-shrink-0">
          <h3 class="font-serif text-[17px] font-medium text-[var(--ink-primary)] leading-snug">
            写邮件
          </h3>
          <button
            @click="closeCompose"
            class="p-1 text-[var(--ink-muted)] hover:text-[var(--ink-primary)] transition"
            title="关闭 (ESC)"
          >
            <X class="w-4 h-4" />
          </button>
        </div>

        <!-- Architectural Specification Header Rows -->
        <div class="divide-y divide-[var(--rule-faint)] bg-[var(--bg-ledger)] text-[12.5px] flex-shrink-0">
          <div class="flex items-center px-4 sm:px-5 h-10 gap-3">
            <span class="w-14 sm:w-20 font-mono text-[10.5px] tracking-[0.06em] text-[var(--ink-muted)] flex-shrink-0">
              发件人
            </span>
            <select
              v-model="selectedMailboxId"
              class="flex-1 min-w-0 bg-transparent text-[var(--ink-primary)] font-mono text-[12px] focus:outline-none cursor-pointer"
            >
              <option
                v-for="mb in store.allMailboxes"
                :key="mb.id"
                :value="mb.id"
                class="bg-[var(--bg-elevated)] text-[var(--ink-primary)]"
              >
                {{ formatSenderOption(mb) }}
              </option>
            </select>
          </div>

          <div class="flex items-center px-4 sm:px-5 h-10 gap-3">
            <span class="w-14 sm:w-20 font-mono text-[10.5px] tracking-[0.06em] text-[var(--ink-muted)] flex-shrink-0">
              收件人
            </span>
            <input
              ref="recipientInputRef"
              v-model="recipient"
              type="email"
              placeholder="recipient@domain.com"
              class="flex-1 min-w-0 bg-transparent text-[var(--ink-primary)] font-mono text-[12px] placeholder-[var(--ink-faint)] focus:outline-none"
            />
          </div>

          <div class="flex items-center px-4 sm:px-5 h-11 gap-3">
            <span class="w-14 sm:w-20 font-mono text-[10.5px] tracking-[0.06em] text-[var(--ink-muted)] flex-shrink-0">
              主题
            </span>
            <input
              v-model="subject"
              type="text"
              placeholder="输入邮件主题..."
              class="flex-1 min-w-0 bg-transparent font-serif text-[15px] text-[var(--ink-primary)] placeholder-[var(--ink-faint)] focus:outline-none"
            />
          </div>
        </div>

        <!-- Stationery Writing Sheet -->
        <textarea
          ref="bodyInputRef"
          v-model="bodyText"
          @keydown.ctrl.enter.prevent="handleSend"
          @keydown.meta.enter.prevent="handleSend"
          rows="9"
          placeholder="输入邮件内容..."
          class="flex-1 min-h-[160px] w-full bg-[var(--bg-salon)] px-4 sm:px-5 py-4 text-[13.5px] text-[var(--ink-primary)] placeholder-[var(--ink-faint)] border-t border-[var(--rule-medium)] focus:outline-none leading-[1.8] resize-none"
        />

        <!-- Colophon Footer -->
        <div class="min-h-[48px] py-2 px-4 sm:px-5 pb-safe border-t border-[var(--rule-medium)] bg-[var(--bg-linen)] flex items-center justify-between flex-shrink-0">
          <span class="hidden sm:flex text-[11px] font-mono text-[var(--ink-muted)] items-center gap-1.5">
            <kbd class="ed-kbd">⌘ / Ctrl</kbd>
            <span>+</span>
            <kbd class="ed-kbd">↵</kbd>
            <span>快捷发送</span>
          </span>

          <div class="flex items-center gap-2 ml-auto">
            <button
              type="button"
              @click="closeCompose"
              class="ed-btn-outline px-3.5 py-1.5 text-[12px]"
            >
              取消
            </button>
            <button
              type="button"
              @click="handleSend"
              :disabled="isSending || !recipient.trim() || !subject.trim() || !selectedMailboxId"
              class="ed-btn-ink px-4 py-1.5 text-[12px] font-medium disabled:opacity-40 flex items-center gap-1.5"
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
