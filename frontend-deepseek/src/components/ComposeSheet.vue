<script setup>
import { ref, watch, nextTick } from 'vue'
import { useMailStore } from '../stores/mail'
import { X, Send, Sparkles } from 'lucide-vue-next'

const store = useMailStore()
const portraitLetterUrl = `${import.meta.env.BASE_URL}deepseek-portrait-letter.jpg`
const chibiThinkUrl = `${import.meta.env.BASE_URL}deepseek-chibi-think.png`

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
    store.notify(`投递失败: ${e.message}`, 'error')
  } finally {
    isSending.value = false
  }
}
</script>

<template>
  <Transition name="fade-scale">
    <div
      v-if="store.isComposeOpen"
      class="fixed inset-0 ds-backdrop z-50 flex items-center justify-center p-4"
      @click.self="closeCompose"
      @keydown.esc.prevent="closeCompose"
    >
      <div class="ds-modal w-full max-w-3xl overflow-hidden flex flex-col md:flex-row">
        <!-- Left Companion Artwork Column: Sea-Breeze Gold-Whale Wax-Seal Portrait -->
        <div class="hidden md:flex w-[245px] relative flex-shrink-0 overflow-hidden border-r border-[var(--border-hairline)] select-none">
          <img
            :src="portraitLetterUrl"
            alt="DeepSeek娘 递送火漆信件"
            class="w-full h-full object-cover object-top transition-transform duration-700 hover:scale-105"
            draggable="false"
          />
          <div class="absolute inset-x-0 bottom-0 pt-16 pb-4 px-4 bg-gradient-to-t from-[#0A142E]/90 via-[#0A142E]/55 to-transparent text-white">
            <div class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-[#D4AF6A]/25 border border-[#F5D799]/50 text-[#FDE68A] text-[10px] font-mono font-bold mb-1.5">
              <span>★ 金鲸火漆专递</span>
            </div>
            <p class="text-[11.5px] leading-relaxed font-semibold text-white/95">
              “写好的信件交给我和大肥鱼，一定会乘着海风平安送到对方手里哦~”
            </p>
          </div>
        </div>

        <!-- Right Stationery Form Column -->
        <div class="flex-1 min-w-0 flex flex-col">
          <!-- Header -->
          <div class="h-12 px-5 border-b border-[var(--border-hairline)] bg-gradient-to-r from-[#4D6BFE]/[0.08] via-[#38BDF8]/[0.05] to-transparent flex items-center justify-between">
            <div class="flex items-center gap-2">
              <img
                :src="chibiThinkUrl"
                alt=""
                class="w-7 h-7 object-contain select-none pointer-events-none"
                draggable="false"
              />
              <span class="text-[14px] font-extrabold text-[var(--text-primary)]">撰写新信件</span>
              <span class="px-2 py-0.5 rounded-full bg-[#4D6BFE]/12 text-[#4D6BFE] dark:text-[#7DD3FC] text-[10.5px] font-mono font-bold">
                大肥鱼特快专递
              </span>
            </div>
            <button
              @click="closeCompose"
              class="p-1.5 rounded-xl text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-hover)] transition"
            >
              <X class="w-4 h-4" />
            </button>
          </div>

          <!-- Form Fields -->
          <div class="divide-y divide-[var(--border-hairline)] text-[12.5px]">
            <div class="flex items-center px-5 h-11 gap-3">
              <span class="w-14 font-bold text-[var(--text-muted)] flex-shrink-0">发件信箱</span>
              <select
                v-model="selectedMailboxId"
                class="flex-1 bg-transparent text-[var(--text-primary)] font-mono font-semibold text-[12px] focus:outline-none cursor-pointer"
              >
                <option
                  v-for="mb in store.allMailboxes"
                  :key="mb.id"
                  :value="mb.id"
                  class="bg-[var(--bg-elevated)] text-[var(--text-primary)]"
                >
                  {{ formatSenderOption(mb) }}
                </option>
              </select>
            </div>

            <div class="flex items-center px-5 h-11 gap-3">
              <span class="w-14 font-bold text-[var(--text-muted)] flex-shrink-0">收件地址</span>
              <input
                ref="recipientInputRef"
                v-model="recipient"
                type="email"
                placeholder="name@example.com"
                class="flex-1 bg-transparent text-[var(--text-primary)] font-mono text-[12.5px] placeholder-[var(--text-muted)] focus:outline-none"
              />
            </div>

            <div class="flex items-center px-5 h-11 gap-3">
              <span class="w-14 font-bold text-[var(--text-muted)] flex-shrink-0">信件主题</span>
              <input
                v-model="subject"
                type="text"
                placeholder="输入信件主题..."
                class="flex-1 bg-transparent font-semibold text-[var(--text-primary)] placeholder-[var(--text-muted)] focus:outline-none"
              />
            </div>
          </div>

          <!-- Writing Canvas -->
          <textarea
            ref="bodyInputRef"
            v-model="bodyText"
            @keydown.ctrl.enter.prevent="handleSend"
            @keydown.meta.enter.prevent="handleSend"
            rows="10"
            placeholder="在这里写下信件内容，大肥鱼会叼着金鲸火漆信封护送它抵达彼岸..."
            class="flex-1 w-full bg-transparent px-5 py-4 text-[13.5px] text-[var(--text-primary)] placeholder-[var(--text-muted)] border-t border-[var(--border-hairline)] focus:outline-none leading-[1.75] resize-none"
          />

          <!-- Footer -->
          <div class="h-[52px] px-5 border-t border-[var(--border-hairline)] bg-[var(--bg-subtle)] flex items-center justify-between">
            <span class="text-[11px] font-semibold text-[var(--text-muted)] flex items-center gap-1.5">
              <kbd class="ds-kbd">⌘ / Ctrl</kbd>
              <span>+</span>
              <kbd class="ds-kbd">↵</kbd>
              <span>极速投递</span>
            </span>

            <div class="flex items-center gap-2">
              <button
                type="button"
                @click="closeCompose"
                class="px-4 py-1.5 rounded-xl text-[12px] font-semibold text-[var(--text-secondary)] hover:bg-[var(--bg-hover)] transition"
              >
                取消
              </button>
              <button
                type="button"
                @click="handleSend"
                :disabled="isSending || !recipient.trim() || !subject.trim() || !selectedMailboxId"
                class="ds-btn-primary px-5 py-1.5 rounded-xl text-[12.5px] font-bold disabled:opacity-40 flex items-center gap-1.5"
              >
                <Send class="w-3.5 h-3.5" />
                <span>{{ isSending ? '潜航投递中...' : '盖上火漆投递' }}</span>
                <Sparkles class="w-3 h-3 opacity-80" />
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </Transition>
</template>
