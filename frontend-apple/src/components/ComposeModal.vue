<script setup>
import { ref, watch, nextTick } from 'vue'
import { useMailStore } from '../stores/mail'
import { Send } from 'lucide-vue-next'

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
  return hasNote ? `${mb.address} (${mb.name})` : mb.address
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
  <Transition name="mac-sheet-fade">
    <div
      v-if="store.isComposeOpen"
      class="fixed inset-0 mac-backdrop z-50 flex items-end sm:items-center justify-center p-0 sm:p-4 select-none"
      @click.self="closeCompose"
      @keydown.esc.prevent="closeCompose"
    >
      <div class="mac-sheet rounded-t-[18px] sm:rounded-[16px] w-full max-w-[600px] max-h-[92dvh] overflow-hidden flex flex-col">
        <!-- macOS New Message Window Titlebar -->
        <div class="h-[44px] px-4 mac-hairline-b bg-[var(--fill-quaternary)] flex items-center justify-between flex-shrink-0">
          <div class="flex items-center gap-2">
            <button
              type="button"
              @click="closeCompose"
              class="w-3 h-3 rounded-full bg-[#FF5F57] border border-black/10 flex items-center justify-center group/close"
              title="关闭窗口"
            >
              <span class="text-[8px] font-bold text-[#4D0000] opacity-0 group-hover/close:opacity-100">×</span>
            </button>
            <span class="hidden sm:inline-block w-3 h-3 rounded-full bg-[var(--fill-secondary)]" />
            <span class="hidden sm:inline-block w-3 h-3 rounded-full bg-[var(--fill-secondary)]" />
          </div>

          <span class="text-[13px] font-semibold text-[var(--label-primary)] truncate px-2">
            {{ subject ? subject : '新信息' }}
          </span>

          <button
            type="button"
            @click="handleSend"
            :disabled="isSending || !recipient.trim() || !subject.trim() || !selectedMailboxId"
            class="mac-btn-blue h-[28px] px-3 rounded-[7px] text-[12px] font-medium disabled:opacity-35 flex items-center gap-1.5 flex-shrink-0"
            title="发送邮件 (⌘↵)"
          >
            <Send class="w-3.5 h-3.5" />
            <span>{{ isSending ? '正在发送...' : '发送' }}</span>
          </button>
        </div>

        <!-- Apple Mail Hairline Address & Subject Fields -->
        <div class="px-4 divide-y divide-[var(--separator)] text-[13px] bg-[var(--bg-reader)] flex-shrink-0">
          <div class="flex items-center h-[42px] sm:h-[38px] gap-2">
            <span class="w-14 text-[var(--label-secondary)] flex-shrink-0">收件人：</span>
            <input
              ref="recipientInputRef"
              v-model="recipient"
              type="email"
              placeholder="name@example.com"
              class="flex-1 min-w-0 bg-transparent text-[var(--label-primary)] font-mono text-[12.5px] placeholder-[var(--label-tertiary)] focus:outline-none"
            />
          </div>

          <div class="flex items-center h-[42px] sm:h-[38px] gap-2">
            <span class="w-14 text-[var(--label-secondary)] flex-shrink-0">主题：</span>
            <input
              v-model="subject"
              type="text"
              placeholder="输入邮件主题"
              class="flex-1 min-w-0 bg-transparent text-[var(--label-primary)] placeholder-[var(--label-tertiary)] focus:outline-none"
            />
          </div>

          <div class="flex items-center h-[42px] sm:h-[38px] gap-2">
            <span class="w-14 text-[var(--label-secondary)] flex-shrink-0">发件人：</span>
            <select
              v-model="selectedMailboxId"
              class="flex-1 min-w-0 truncate bg-transparent text-[var(--label-primary)] font-mono text-[12px] focus:outline-none cursor-pointer"
            >
              <option
                v-for="mb in store.allMailboxes"
                :key="mb.id"
                :value="mb.id"
                class="bg-[var(--bg-reader)] text-[var(--label-primary)]"
              >
                {{ formatSenderOption(mb) }}
              </option>
            </select>
          </div>
        </div>

        <!-- Writing Canvas -->
        <textarea
          ref="bodyInputRef"
          v-model="bodyText"
          @keydown.ctrl.enter.prevent="handleSend"
          @keydown.meta.enter.prevent="handleSend"
          rows="8"
          placeholder="在此输入邮件正文..."
          class="w-full flex-1 min-h-[150px] overflow-y-auto bg-[var(--bg-reader)] px-4 py-3.5 text-[13.5px] text-[var(--label-primary)] placeholder-[var(--label-tertiary)] mac-hairline-t focus:outline-none leading-[1.68] resize-none select-text"
        />

        <!-- Subtle Status Bar -->
        <div class="min-h-[38px] py-2 px-4 pb-safe mac-hairline-t bg-[var(--fill-quaternary)] flex items-center justify-between text-[11.5px] text-[var(--label-secondary)] flex-shrink-0">
          <span class="hidden sm:flex items-center gap-1">
            <kbd class="mac-kbd">⌘</kbd>
            <kbd class="mac-kbd">↵</kbd>
            <span>立即发送</span>
          </span>

          <button
            type="button"
            @click="closeCompose"
            class="text-[var(--label-secondary)] hover:text-[var(--label-primary)] transition ml-auto"
          >
            取消
          </button>
        </div>
      </div>
    </div>
  </Transition>
</template>
