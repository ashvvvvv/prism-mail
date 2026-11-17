<script setup>
import { ref, computed } from 'vue'
import { useMailStore } from '../stores/mail'
import PrismWordmark from './PrismWordmark.vue'
import {
  Reply, ZoomIn, ZoomOut, Star, Trash2, FileText,
  Download, Copy, Check, KeyRound, Sun, Moon, ArrowLeft, Loader2
} from 'lucide-vue-next'

const store = useMailStore()
const zoom = ref(1)
const copiedCode = ref(false)
const htmlPaperMode = ref(true) // true = crisp white paper for HTML mails, false = adaptive dark

const handleBack = () => {
  if (window.history.state?.prismReader) {
    window.history.back()
  } else {
    store.closeMail()
  }
}

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

const extractedCode = computed(() => {
  const detail = store.selectedMailDetail
  if (!detail) return null
  const text = `${detail.subject || ''} ${detail.body_text || ''}`
  const kwMatch = text.match(/(?:验证码|代码|code|verification|passcode|otp|pin)[^0-9A-Za-z]{0,20}\b([0-9]{4,8})\b/i)
  if (kwMatch) return kwMatch[1]
  const subjMatch = (detail.subject || '').match(/\b([0-9]{6})\b/)
  if (subjMatch) return subjMatch[1]
  return null
})

const copyCode = async (code) => {
  try {
    await navigator.clipboard.writeText(code)
    copiedCode.value = true
    store.notify(`验证码 ${code} 已复制`, 'success')
    setTimeout(() => {
      copiedCode.value = false
    }, 1800)
  } catch {}
}

const copyAddress = async (addr) => {
  if (!addr) return
  try {
    await navigator.clipboard.writeText(addr)
    store.notify(`已复制 ${addr}`)
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
    month: '2-digit',
    day: '2-digit',
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
  <main class="flex-1 bg-[var(--bg-reader)] flex flex-col overflow-hidden relative">
    <div v-if="store.selectedMailDetail" class="h-full flex flex-col">
      <!-- Minimalist Sticky Action Bar -->
      <header class="h-12 px-3.5 sm:px-5 border-b border-[var(--border-hairline)] flex items-center justify-between gap-2 flex-shrink-0">
        <div class="flex items-center gap-1.5">
          <button
            @click="handleBack"
            class="lg:hidden h-7 px-2.5 -ml-1 rounded-lg bg-[var(--bg-subtle)] hover:bg-[var(--bg-active)] border border-[var(--border-hairline)] text-[var(--text-primary)] text-[12px] font-medium flex items-center gap-1 transition"
          >
            <ArrowLeft class="w-3.5 h-3.5" />
            <span>返回</span>
          </button>

          <button
            @click="handleReply"
            class="h-7 px-3 rounded-lg bg-[var(--bg-subtle)] hover:bg-[var(--bg-active)] border border-[var(--border-hairline)] text-[var(--text-primary)] text-[12px] font-medium flex items-center gap-1.5 transition"
          >
            <Reply class="w-3.5 h-3.5" />
            <span>回复</span>
            <kbd class="hidden sm:inline text-[10px] font-mono text-[var(--text-muted)] ml-0.5">R</kbd>
          </button>

          <button
            @click="toggleStar"
            :class="[
              'h-7 w-7 rounded-lg flex items-center justify-center hover:bg-[var(--bg-hover)] transition',
              store.selectedMailDetail.is_starred ? 'text-[var(--accent-amber)]' : 'text-[var(--text-muted)] hover:text-[var(--text-primary)]'
            ]"
            title="星标"
          >
            <Star class="w-3.5 h-3.5" :fill="store.selectedMailDetail.is_starred ? 'currentColor' : 'none'" />
          </button>

          <button
            @click="handleDelete"
            class="h-7 w-7 rounded-lg flex items-center justify-center text-[var(--text-muted)] hover:text-[var(--accent-rose)] hover:bg-[var(--bg-hover)] transition"
            title="移至废纸篓"
          >
            <Trash2 class="w-3.5 h-3.5" />
          </button>
        </div>

        <div class="flex items-center gap-2 text-[var(--text-muted)]">
          <!-- HTML Paper vs Adaptive Toggle -->
          <button
            v-if="store.selectedMailDetail.body_html && store.theme === 'obsidian'"
            @click="htmlPaperMode = !htmlPaperMode"
            class="h-7 px-2.5 rounded-lg bg-[var(--bg-subtle)] hover:bg-[var(--bg-hover)] border border-[var(--border-hairline)] text-[11px] flex items-center gap-1.5 transition text-[var(--text-secondary)]"
            title="切换信纸底色"
          >
            <Sun v-if="htmlPaperMode" class="w-3 h-3" />
            <Moon v-else class="w-3 h-3" />
            <span>{{ htmlPaperMode ? '白纸' : '暗底' }}</span>
          </button>

          <div class="hidden sm:flex items-center h-7 bg-[var(--bg-subtle)] rounded-lg border border-[var(--border-hairline)] px-1">
            <button @click="zoomOut" class="p-1 hover:text-[var(--text-primary)] transition" title="缩小">
              <ZoomOut class="w-3 h-3" />
            </button>
            <span class="px-1.5 text-[10.5px] font-mono tabular-nums text-[var(--text-secondary)]">
              {{ Math.round(zoom * 100) }}%
            </span>
            <button @click="zoomIn" class="p-1 hover:text-[var(--text-primary)] transition" title="放大">
              <ZoomIn class="w-3 h-3" />
            </button>
          </div>
        </div>
      </header>

      <!-- Scrollable Editorial Canvas -->
      <div class="flex-1 overflow-y-auto px-4 sm:px-6 md:px-10 py-5 md:py-7 pb-safe">
        <div class="max-w-3xl mx-auto space-y-6">
          <!-- Subject & Sender Editorial Header -->
          <div class="space-y-4 pb-5 border-b border-[var(--border-hairline)]">
            <h1 class="text-[19px] md:text-[21px] font-semibold tracking-[-0.02em] text-[var(--text-primary)] leading-snug">
              {{ store.selectedMailDetail.subject || '(无主题)' }}
            </h1>

            <div class="flex items-center justify-between gap-4 flex-wrap">
              <div class="flex items-center gap-3 min-w-0">
                <div class="w-9 h-9 rounded-full bg-[var(--bg-subtle)] border border-[var(--border-strong)] flex items-center justify-center text-[13px] font-semibold text-[var(--text-primary)] flex-shrink-0">
                  {{ senderInfo.name.charAt(0).toUpperCase() }}
                </div>
                <div class="min-w-0 space-y-0.5">
                  <div class="flex items-center gap-2 text-[13px] truncate">
                    <span class="font-semibold text-[var(--text-primary)]">{{ senderInfo.name }}</span>
                    <button
                      v-if="senderInfo.email && senderInfo.email !== senderInfo.name"
                      @click="copyAddress(senderInfo.email)"
                      class="text-[11.5px] font-mono text-[var(--text-muted)] hover:text-[var(--text-secondary)] truncate transition"
                      title="点击复制发件人地址"
                    >
                      {{ senderInfo.email }}
                    </button>
                  </div>
                  <div class="flex items-center gap-1.5 text-[11.5px] text-[var(--text-muted)] font-mono truncate">
                    <span>收件</span>
                    <button
                      @click="copyAddress(store.selectedMailDetail.recipient)"
                      class="text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition"
                      title="点击复制收件邮箱"
                    >
                      {{ store.selectedMailDetail.recipient }}
                    </button>
                  </div>
                </div>
              </div>

              <time class="text-[11.5px] font-mono tabular-nums text-[var(--text-muted)] flex-shrink-0">
                {{ formatFullDate(store.selectedMailDetail.created_at) }}
              </time>
            </div>

            <!-- Hero Verification Code Capsule -->
            <button
              v-if="extractedCode"
              @click="copyCode(extractedCode)"
              class="w-full py-2.5 px-4 rounded-xl bg-emerald-500/[0.08] hover:bg-emerald-500/[0.13] border border-emerald-500/25 flex items-center justify-between transition group"
            >
              <div class="flex items-center gap-3">
                <div class="w-7 h-7 rounded-lg bg-emerald-500/15 flex items-center justify-center text-[var(--accent-emerald)]">
                  <KeyRound class="w-3.5 h-3.5" />
                </div>
                <div class="text-left">
                  <span class="text-[11px] text-[var(--text-secondary)] block">动态验证码</span>
                  <span class="text-[16px] font-mono font-semibold tracking-[0.16em] text-[var(--accent-emerald)] tabular-nums">
                    {{ extractedCode }}
                  </span>
                </div>
              </div>
              <span class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-emerald-500/15 text-[var(--accent-emerald)] text-[11.5px] font-medium">
                <Check v-if="copiedCode" class="w-3.5 h-3.5" />
                <Copy v-else class="w-3.5 h-3.5" />
                <span>{{ copiedCode ? '已复制' : '复制验证码' }}</span>
              </span>
            </button>
          </div>

          <!-- Mail Body -->
          <div
            class="transition-transform origin-top"
            :style="{ transform: `scale(${zoom})` }"
          >
            <div
              v-if="store.selectedMailDetail.body_html"
              v-html="store.selectedMailDetail.body_html"
              :class="[
                'text-[14px] leading-relaxed',
                htmlPaperMode || store.theme === 'porcelain' ? 'pm-mail-paper' : 'pm-mail-adaptive'
              ]"
            />
            <div
              v-else
              class="text-[var(--text-primary)] text-[14px] whitespace-pre-wrap leading-[1.75] font-sans py-1"
            >{{ store.selectedMailDetail.body_text }}</div>

            <!-- Attachments -->
            <div
              v-if="store.selectedMailDetail.has_attachments && store.selectedMailDetail.attachments?.length"
              class="mt-8 pt-6 border-t border-[var(--border-hairline)]"
            >
              <h4 class="text-[11.5px] font-medium text-[var(--text-muted)] mb-3">
                附件 · {{ store.selectedMailDetail.attachments.length }}
              </h4>
              <div class="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                <a
                  v-for="(att, idx) in store.selectedMailDetail.attachments"
                  :key="`${idx}-${att.name}`"
                  :href="att.download_url || `/api/mails/${store.selectedMailDetail.id}/attachments/${att.index ?? idx}`"
                  :download="att.name"
                  class="p-3 rounded-xl bg-[var(--bg-subtle)] hover:bg-[var(--bg-hover)] border border-[var(--border-hairline)] flex items-center justify-between transition cursor-pointer no-underline"
                >
                  <div class="flex items-center gap-2.5 truncate">
                    <FileText class="w-4 h-4 text-[var(--text-secondary)] flex-shrink-0" />
                    <div class="truncate">
                      <p class="text-[12.5px] font-medium text-[var(--text-primary)] truncate">{{ att.name }}</p>
                      <p class="text-[10.5px] font-mono text-[var(--text-muted)]">{{ att.size }}</p>
                    </div>
                  </div>
                  <Download class="w-3.5 h-3.5 text-[var(--text-muted)]" />
                </a>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Mobile / Async Detail Loading State -->
    <div v-else-if="store.selectedMail" class="h-full flex flex-col">
      <header class="lg:hidden h-12 px-3.5 border-b border-[var(--border-hairline)] flex items-center flex-shrink-0">
        <button
          @click="handleBack"
          class="h-7 px-2.5 -ml-1 rounded-lg bg-[var(--bg-subtle)] hover:bg-[var(--bg-active)] border border-[var(--border-hairline)] text-[var(--text-primary)] text-[12px] font-medium flex items-center gap-1 transition"
        >
          <ArrowLeft class="w-3.5 h-3.5" />
          <span>返回</span>
        </button>
      </header>
      <div class="flex-1 flex items-center justify-center text-[var(--text-muted)]">
        <Loader2 class="w-5 h-5 animate-spin opacity-60" />
      </div>
    </div>

    <!-- Architectural Empty State -->
    <div v-else class="h-full flex flex-col items-center justify-center p-8 select-none">
      <div class="flex flex-col items-center space-y-5 max-w-xs text-center">
        <PrismWordmark class="h-[18px] w-auto text-[var(--text-muted)] opacity-40" />

        <div class="flex items-center gap-4 text-[11.5px] text-[var(--text-muted)]">
          <span class="flex items-center gap-1.5">
            <kbd class="pm-kbd">⌘K</kbd>
            <span>命令面板</span>
          </span>
          <span class="flex items-center gap-1.5">
            <kbd class="pm-kbd">C</kbd>
            <span>撰写</span>
          </span>
          <span class="flex items-center gap-1.5">
            <kbd class="pm-kbd">J</kbd>
            <kbd class="pm-kbd">K</kbd>
            <span>翻阅</span>
          </span>
        </div>
      </div>
    </div>
  </main>
</template>
