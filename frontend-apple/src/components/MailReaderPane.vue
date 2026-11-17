<script setup>
import { ref, computed } from 'vue'
import { useMailStore } from '../stores/mail'
import {
  Reply,
  ZoomIn,
  ZoomOut,
  Star,
  Trash2,
  FileText,
  Download,
  Copy,
  Check,
  KeyRound,
  Sun,
  Moon,
  Inbox,
  Loader2
} from 'lucide-vue-next'

const store = useMailStore()
const zoom = ref(1)
const copiedCode = ref(false)
const htmlPaperMode = ref(true)

const zoomIn = () => {
  if (zoom.value < 1.4) zoom.value = Math.round((zoom.value + 0.1) * 10) / 10
}

const zoomOut = () => {
  if (zoom.value > 0.8) zoom.value = Math.round((zoom.value - 0.1) * 10) / 10
}

const toggleStar = () => {
  if (store.selectedMailDetail) {
    store.updateMailStatus(store.selectedMailDetail.id, {
      is_starred: !store.selectedMailDetail.is_starred
    })
  }
}

const handleDelete = () => {
  if (store.selectedMailDetail) {
    store.deleteMail(store.selectedMailDetail.id)
  }
}

const parseSender = (raw) => {
  if (!raw) return { name: '未知发件人', email: '' }
  const match = raw.match(/^([^<]+)<([^>]+)>$/)
  if (match) {
    return {
      name: match[1].trim().replace(/^["']|["']$/g, '') || match[2].trim(),
      email: match[2].trim()
    }
  }
  return { name: raw.trim(), email: raw.trim() }
}

const senderInfo = computed(() => parseSender(store.selectedMailDetail?.sender))

const stripHtmlTags = (html) => {
  if (!html) return ''
  return html.replace(/<style[\s\S]*?<\/style>/gi, ' ')
    .replace(/<script[\s\S]*?<\/script>/gi, ' ')
    .replace(/<[^>]+>/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
}

const extractedCode = computed(() => {
  const detail = store.selectedMailDetail
  if (!detail) return null
  const plainBody = detail.body_text || stripHtmlTags(detail.body_html)
  const text = `${detail.subject || ''} ${plainBody}`
  const kwMatch = text.match(/(?:验证码|校验码|动态码|安全码|代码|code|verification|passcode|otp|pin)[^0-9A-Za-z]{0,22}\b([0-9]{4,8})\b/i)
  if (kwMatch) return kwMatch[1]
  const reverseMatch = text.match(/\b([0-9]{4,8})\b[^0-9A-Za-z]{0,14}(?:是您的验证码|为您的验证码|验证码|is your (?:verification )?code)/i)
  if (reverseMatch) return reverseMatch[1]
  const subjMatch = (detail.subject || '').match(/\b([0-9]{6})\b/)
  if (subjMatch) return subjMatch[1]
  return null
})

const copyCode = async (code) => {
  try {
    await navigator.clipboard.writeText(code)
    copiedCode.value = true
    store.notify(`已拷贝验证码 ${code}`, 'success')
    setTimeout(() => {
      copiedCode.value = false
    }, 2000)
  } catch {}
}

const copyAddress = async (addr) => {
  if (!addr) return
  try {
    await navigator.clipboard.writeText(addr)
    store.notify(`已拷贝邮箱地址 ${addr}`)
  } catch {}
}

const handleReply = () => {
  const detail = store.selectedMailDetail
  if (!detail) return
  const replyTo = senderInfo.value.email
  const subj = detail.subject && detail.subject.toLowerCase().startsWith('re:')
    ? detail.subject
    : `Re: ${detail.subject || ''}`
  store.openCompose({
    mailboxId: detail.mailbox_id,
    recipient: replyTo,
    subject: subj,
    body: ''
  })
}

const formatFullDate = (iso) => {
  if (!iso) return ''
  return new Date(iso).toLocaleString('zh-CN', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false
  })
}

defineExpose({
  triggerReply: handleReply
})
</script>

<template>
  <main class="flex-1 bg-[var(--bg-reader)] flex flex-col overflow-hidden relative select-text">
    <div v-if="store.selectedMailDetail" class="h-full flex flex-col">
      <!-- Scrollable Apple Mail Conversation Sheet -->
      <div class="flex-1 overflow-y-auto px-4 sm:px-6 md:px-9 py-4 md:py-6 pb-safe">
        <div class="max-w-3xl mx-auto space-y-5">
          <!-- Apple Mail Conversation Header -->
          <div class="space-y-4 pb-4 mac-hairline-b select-none">
            <!-- Sender & Inline Controls Row -->
            <div class="flex items-start justify-between gap-3 sm:gap-4 flex-wrap">
              <div class="flex items-center gap-3 min-w-0">
                <!-- Apple Contact Monogram Circle -->
                <div class="w-10 h-10 rounded-full bg-gradient-to-b from-[#98A2B3] to-[#667085] text-white flex items-center justify-center text-[15px] font-semibold shadow-sm flex-shrink-0">
                  {{ senderInfo.name.charAt(0).toUpperCase() }}
                </div>

                <div class="min-w-0 space-y-0.5">
                  <div class="flex items-center gap-2 flex-wrap">
                    <span class="text-[14.5px] font-semibold text-[var(--label-primary)] tracking-[-0.01em]">
                      {{ senderInfo.name }}
                    </span>
                    <button
                      v-if="senderInfo.email && senderInfo.email !== senderInfo.name"
                      type="button"
                      @click="copyAddress(senderInfo.email)"
                      class="text-[12px] font-mono text-[var(--label-secondary)] hover:text-[var(--apple-blue)] transition truncate"
                      title="点击拷贝发件人地址"
                    >
                      &lt;{{ senderInfo.email }}&gt;
                    </button>
                  </div>

                  <div class="flex items-center gap-1.5 text-[12px] text-[var(--label-secondary)] truncate">
                    <span>收件人：</span>
                    <button
                      type="button"
                      @click="copyAddress(store.selectedMailDetail.recipient)"
                      class="font-mono text-[var(--label-primary)] hover:text-[var(--apple-blue)] transition truncate"
                      title="点击拷贝收件邮箱地址"
                    >
                      {{ store.selectedMailDetail.recipient }}
                    </button>
                  </div>
                </div>
              </div>

              <!-- Timestamp & Reader Controls -->
              <div class="w-full sm:w-auto flex flex-row sm:flex-col items-center sm:items-end justify-between sm:justify-start gap-2 flex-shrink-0 sm:ml-auto">
                <time class="text-[11.5px] sm:text-[12px] tabular-nums text-[var(--label-secondary)]">
                  {{ formatFullDate(store.selectedMailDetail.created_at) }}
                </time>

                <div class="flex items-center gap-1.5">
                  <!-- HTML Paper Toggle in Dark Mode -->
                  <button
                    v-if="store.selectedMailDetail.body_html && store.theme === 'cupertino-dark'"
                    type="button"
                    @click="htmlPaperMode = !htmlPaperMode"
                    class="h-[25px] px-2 rounded-[6px] bg-[var(--fill-quaternary)] hover:bg-[var(--fill-tertiary)] border border-[var(--separator)] text-[11px] text-[var(--label-secondary)] hover:text-[var(--label-primary)] flex items-center gap-1 transition"
                    title="切换浅色信纸或深色自适应背景"
                  >
                    <Sun v-if="htmlPaperMode" class="w-3 h-3 text-[var(--apple-amber)]" />
                    <Moon v-else class="w-3 h-3" />
                    <span>{{ htmlPaperMode ? '浅色信纸' : '深色适配' }}</span>
                  </button>

                  <!-- Zoom Controls -->
                  <div class="hidden sm:flex items-center h-[25px] rounded-[6px] bg-[var(--fill-quaternary)] border border-[var(--separator)] px-1 text-[var(--label-secondary)]">
                    <button type="button" @click="zoomOut" class="p-0.5 hover:text-[var(--label-primary)] transition" title="缩小正文">
                      <ZoomOut class="w-3 h-3" />
                    </button>
                    <span class="px-1.5 text-[10.5px] font-mono tabular-nums">
                      {{ Math.round(zoom * 100) }}%
                    </span>
                    <button type="button" @click="zoomIn" class="p-0.5 hover:text-[var(--label-primary)] transition" title="放大正文">
                      <ZoomIn class="w-3 h-3" />
                    </button>
                  </div>

                  <!-- Quick Message Actions -->
                  <div class="flex items-center h-[25px] rounded-[6px] bg-[var(--fill-quaternary)] border border-[var(--separator)] divide-x divide-[var(--separator)] overflow-hidden">
                    <button
                      type="button"
                      @click="handleReply"
                      class="px-2 h-full flex items-center gap-1 text-[11.5px] text-[var(--apple-blue)] hover:bg-[var(--fill-hover)] font-medium transition"
                      title="回复 (R)"
                    >
                      <Reply class="w-3 h-3" />
                      <span>回复</span>
                    </button>
                    <button
                      type="button"
                      @click="toggleStar"
                      :class="[
                        'w-[26px] h-full flex items-center justify-center hover:bg-[var(--fill-hover)] transition',
                        store.selectedMailDetail.is_starred ? 'text-[var(--apple-orange)]' : 'text-[var(--label-secondary)]'
                      ]"
                      title="标记星标"
                    >
                      <Star class="w-3 h-3" :fill="store.selectedMailDetail.is_starred ? 'currentColor' : 'none'" />
                    </button>
                    <button
                      type="button"
                      @click="handleDelete"
                      class="w-[26px] h-full flex items-center justify-center text-[var(--label-secondary)] hover:text-[var(--apple-red)] hover:bg-[var(--fill-hover)] transition"
                      title="移至废纸篓"
                    >
                      <Trash2 class="w-3 h-3" />
                    </button>
                  </div>
                </div>
              </div>
            </div>

            <!-- Subject Title -->
            <h2 class="text-[19px] md:text-[21px] font-semibold tracking-[-0.02em] text-[var(--label-primary)] leading-snug select-text">
              {{ store.selectedMailDetail.subject || '(无主题)' }}
            </h2>

            <!-- Authentic Apple iOS / macOS AutoFill Verification Code Pill -->
            <button
              v-if="extractedCode"
              type="button"
              @click="copyCode(extractedCode)"
              class="w-full py-2.5 px-3.5 rounded-[12px] bg-[#007AFF]/[0.08] hover:bg-[#007AFF]/[0.13] active:scale-[0.995] border border-[#007AFF]/25 flex items-center justify-between gap-3 transition group"
            >
              <div class="flex items-center gap-2.5 min-w-0">
                <div class="w-7 h-7 rounded-[8px] bg-[var(--apple-blue)] text-white flex items-center justify-center shadow-[0_2px_6px_rgba(0,122,255,0.3)] flex-shrink-0">
                  <KeyRound class="w-3.5 h-3.5 stroke-[2]" />
                </div>
                <div class="flex items-center flex-wrap gap-x-1.5 text-left">
                  <span class="text-[13px] font-medium text-[var(--label-primary)]">
                    来自邮件的验证码：<span class="font-mono font-semibold text-[14.5px] tracking-[0.06em] text-[var(--apple-blue)] tabular-nums">{{ extractedCode }}</span>
                  </span>
                  <span class="text-[12.5px] text-[var(--apple-blue)] font-medium">
                    · {{ copiedCode ? '已拷贝至剪贴板' : '点击拷贝' }}
                  </span>
                </div>
              </div>

              <span class="inline-flex items-center gap-1 px-2.5 py-1 rounded-[8px] bg-[var(--apple-blue)]/15 text-[var(--apple-blue)] text-[11.5px] font-medium flex-shrink-0">
                <Check v-if="copiedCode" class="w-3.5 h-3.5" />
                <Copy v-else class="w-3.5 h-3.5" />
                <span>{{ copiedCode ? '已拷贝' : '拷贝' }}</span>
              </span>
            </button>
          </div>

          <!-- Mail Body Content -->
          <div
            class="transition-transform origin-top"
            :style="{ transform: `scale(${zoom})` }"
          >
            <div
              v-if="store.selectedMailDetail.body_html"
              v-html="store.selectedMailDetail.body_html"
              :class="[
                'text-[14px] leading-[1.68]',
                htmlPaperMode || store.theme === 'cupertino-light'
                  ? 'apple-mail-paper'
                  : 'apple-mail-adaptive'
              ]"
            />
            <div
              v-else
              class="text-[var(--label-primary)] text-[14px] whitespace-pre-wrap leading-[1.72] font-sans py-1"
            >{{ store.selectedMailDetail.body_text }}</div>

            <!-- Attachments Section -->
            <div
              v-if="store.selectedMailDetail.has_attachments && store.selectedMailDetail.attachments?.length"
              class="mt-7 pt-5 mac-hairline-t select-none"
            >
              <h4 class="text-[12px] font-semibold text-[var(--label-secondary)] mb-2.5">
                附件（{{ store.selectedMailDetail.attachments.length }} 个文件）
              </h4>
              <div class="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                <a
                  v-for="(att, idx) in store.selectedMailDetail.attachments"
                  :key="`${idx}-${att.name}`"
                  :href="att.download_url || `/api/mails/${store.selectedMailDetail.id}/attachments/${att.index ?? idx}`"
                  :download="att.name"
                  class="p-3 rounded-[10px] bg-[var(--fill-quaternary)] hover:bg-[var(--fill-tertiary)] border border-[var(--separator)] flex items-center justify-between transition cursor-pointer no-underline"
                >
                  <div class="flex items-center gap-2.5 min-w-0">
                    <div class="w-8 h-8 rounded-[8px] bg-[var(--apple-blue)]/12 text-[var(--apple-blue)] flex items-center justify-center flex-shrink-0">
                      <FileText class="w-4 h-4" />
                    </div>
                    <div class="min-w-0">
                      <p class="text-[12.5px] font-medium text-[var(--label-primary)] truncate">{{ att.name }}</p>
                      <p class="text-[11px] font-mono text-[var(--label-secondary)]">{{ att.size }}</p>
                    </div>
                  </div>
                  <Download class="w-4 h-4 text-[var(--label-secondary)] flex-shrink-0 ml-2" />
                </a>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Mobile / Async Detail Loading State -->
    <div v-else-if="store.selectedMail" class="h-full flex flex-col items-center justify-center text-[var(--label-secondary)]">
      <Loader2 class="w-5 h-5 animate-spin text-[var(--apple-blue)] opacity-75" />
    </div>

    <!-- Authentic macOS Mail Empty State -->
    <div v-else class="h-full flex flex-col items-center justify-center p-8 select-none">
      <div class="flex flex-col items-center space-y-4 max-w-xs text-center">
        <div class="w-14 h-14 rounded-[16px] bg-[var(--fill-quaternary)] border border-[var(--separator)] flex items-center justify-center text-[var(--label-tertiary)]">
          <Inbox class="w-7 h-7 stroke-[1.4]" />
        </div>
        <div class="space-y-1">
          <p class="text-[15px] font-semibold text-[var(--label-secondary)]">未选择邮件</p>
          <p class="text-[12px] text-[var(--label-tertiary)]">从左侧列表选取一封信件以阅读正文</p>
        </div>
        <div class="flex items-center gap-3 pt-1 text-[11.5px] text-[var(--label-secondary)]">
          <span class="flex items-center gap-1">
            <kbd class="mac-kbd">⌘K</kbd>
            <span>聚焦搜索</span>
          </span>
          <span class="flex items-center gap-1">
            <kbd class="mac-kbd">C</kbd>
            <span>新邮件</span>
          </span>
          <span class="flex items-center gap-1">
            <kbd class="mac-kbd">↑↓</kbd>
            <span>浏览</span>
          </span>
        </div>
      </div>
    </div>
  </main>
</template>
