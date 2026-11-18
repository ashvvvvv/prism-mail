<script setup>
import { ref, computed } from 'vue'
import { useMailStore, extractVerificationCode } from '../stores/mail'
import PrismWordmark from './PrismWordmark.vue'
import SafeMailHtml from './SafeMailHtml.vue'
import {
  Reply, ZoomIn, ZoomOut, Star, Trash2, FileText,
  Download, Copy, Check, Stamp, Sun, Moon, ArrowLeft, Loader2
} from 'lucide-vue-next'

const store = useMailStore()
const zoom = ref(1)
const copiedCode = ref(false)
const htmlStationeryPaper = ref(true) // true = crisp ivory stationery for HTML in dark theme

const handleBackMobile = () => {
  if (typeof window !== 'undefined' && window.history.state?.prismReader) {
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
  return extractVerificationCode(detail.subject, detail.body_text, detail.body_html)
})

const copyCode = async (code) => {
  try {
    await navigator.clipboard.writeText(code)
    copiedCode.value = true
    store.notify(`已复制验证码 ${code}`, 'success')
    setTimeout(() => {
      copiedCode.value = false
    }, 1800)
  } catch {}
}

const copyAddress = async (addr) => {
  if (!addr) return
  try {
    await navigator.clipboard.writeText(addr)
    store.notify(`已复制地址 ${addr}`)
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
  if (!iso) return '—'
  return new Date(iso).toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false
  })
}

const folioSerial = computed(() => {
  const id = store.selectedMailDetail?.id
  if (!id) return '0000'
  return String(id).padStart(4, '0')
})

defineExpose({
  triggerReply: handleReply
})
</script>

<template>
  <main class="flex-1 bg-[var(--bg-salon)] flex flex-col overflow-hidden relative">
    <div v-if="store.selectedMailDetail" class="h-full flex flex-col">
      <!-- Top Salon Utility Bar -->
      <header
        class="h-11 px-3.5 sm:px-6 border-b border-[var(--rule-faint)] bg-[var(--bg-ledger)] flex items-center justify-between gap-2 sm:gap-3 flex-shrink-0 select-none"
      >
        <div class="flex items-center gap-1.5 sm:gap-2">
          <button
            type="button"
            @click="handleBackMobile"
            class="lg:hidden h-7 px-2.5 ed-btn-outline text-[12px] font-medium flex items-center gap-1"
            title="返回列表"
          >
            <ArrowLeft class="w-3.5 h-3.5" />
            <span>返回</span>
          </button>

          <span class="ed-rubric hidden sm:inline-block pr-2 border-r border-[var(--rule-faint)]">
            #{{ folioSerial }}
          </span>

          <button
            @click="handleReply"
            class="h-7 px-2.5 sm:px-3 ed-btn-outline text-[12px] font-medium flex items-center gap-1.5"
          >
            <Reply class="w-3.5 h-3.5" />
            <span>回复</span>
            <kbd class="hidden sm:inline font-mono text-[10px] text-[var(--ink-muted)] ml-0.5">R</kbd>
          </button>

          <button
            @click="toggleStar"
            :class="[
              'h-7 w-7 ed-btn-outline flex items-center justify-center',
              store.selectedMailDetail.is_starred
                ? 'text-[var(--accent-ochre)] border-[var(--accent-ochre)]'
                : 'text-[var(--ink-muted)]'
            ]"
            title="星标邮件"
          >
            <Star class="w-3.5 h-3.5" :fill="store.selectedMailDetail.is_starred ? 'currentColor' : 'none'" />
          </button>

          <button
            @click="handleDelete"
            class="h-7 w-7 ed-btn-outline flex items-center justify-center text-[var(--ink-muted)] hover:text-[var(--accent-vermilion)]"
            title="移入废纸篓"
          >
            <Trash2 class="w-3.5 h-3.5" />
          </button>
        </div>

        <div class="flex items-center gap-2">
          <button
            v-if="store.selectedMailDetail.body_html && store.theme === 'espresso'"
            @click="htmlStationeryPaper = !htmlStationeryPaper"
            class="h-7 px-2 sm:px-2.5 ed-btn-outline text-[11px] flex items-center gap-1.5 text-[var(--ink-secondary)]"
            title="切换邮件背景"
          >
            <Sun v-if="htmlStationeryPaper" class="w-3 h-3" />
            <Moon v-else class="w-3 h-3" />
            <span>{{ htmlStationeryPaper ? '浅色信纸' : '深色背景' }}</span>
          </button>

          <div class="hidden sm:flex items-center h-7 border border-[var(--rule-medium)] rounded-[2px] bg-[var(--bg-input)] px-1 text-[var(--ink-muted)]">
            <button @click="zoomOut" class="p-1 hover:text-[var(--ink-primary)] transition" title="缩小版面">
              <ZoomOut class="w-3 h-3" />
            </button>
            <span class="px-1.5 text-[10.5px] font-mono tabular-nums text-[var(--ink-secondary)]">
              {{ Math.round(zoom * 100) }}%
            </span>
            <button @click="zoomIn" class="p-1 hover:text-[var(--ink-primary)] transition" title="放大版面">
              <ZoomIn class="w-3 h-3" />
            </button>
          </div>
        </div>
      </header>

      <!-- Literary Reading Salon Canvas -->
      <div class="flex-1 overflow-y-auto px-4 sm:px-6 md:px-12 xl:px-16 py-5 md:py-8 pb-safe">
        <div class="max-w-[760px] mx-auto space-y-5 sm:space-y-6">
          <!-- Rubric & Editorial Serif Subject Headline -->
          <div class="space-y-2.5 sm:space-y-3">
            <div class="flex items-center justify-between">
              <span class="ed-rubric text-[var(--accent-vermilion)]">
                邮件正文
              </span>
              <span class="ed-rubric">
                {{ store.selectedMailDetail.is_starred ? '★ 已星标' : `#${folioSerial}` }}
              </span>
            </div>

            <h1 class="font-serif text-[20px] sm:text-[24px] md:text-[27px] font-medium tracking-[-0.015em] text-[var(--ink-primary)] leading-[1.35] break-words">
              {{ store.selectedMailDetail.subject || '(无主题)' }}
            </h1>

            <div class="ed-double-rule pt-1" />
          </div>

          <!-- Structured 2-Column Architectural Specification Table -->
          <div class="border border-[var(--rule-medium)] bg-[var(--bg-ledger)] rounded-[2px] divide-y divide-[var(--rule-faint)] text-[12px]">
            <div class="grid grid-cols-1 md:grid-cols-2 divide-y md:divide-y-0 md:divide-x divide-[var(--rule-faint)]">
              <!-- FROM -->
              <div class="px-3.5 py-2.5 flex items-baseline gap-3 min-w-0">
                <span class="w-14 sm:w-20 flex-shrink-0 font-mono text-[10px] tracking-[0.08em] uppercase text-[var(--ink-muted)]">
                  发件人
                </span>
                <div class="min-w-0 flex-1 truncate">
                  <span class="font-semibold text-[var(--ink-primary)] mr-1.5">{{ senderInfo.name }}</span>
                  <button
                    v-if="senderInfo.email"
                    @click="copyAddress(senderInfo.email)"
                    class="font-mono text-[11px] text-[var(--ink-muted)] hover:text-[var(--accent-vermilion)] transition underline decoration-dotted underline-offset-2"
                    title="点击复制发件人地址"
                  >
                    &lt;{{ senderInfo.email }}&gt;
                  </button>
                </div>
              </div>

              <!-- TO -->
              <div class="px-3.5 py-2.5 flex items-baseline gap-3 min-w-0">
                <span class="w-14 sm:w-20 flex-shrink-0 font-mono text-[10px] tracking-[0.08em] uppercase text-[var(--ink-muted)]">
                  收件人
                </span>
                <button
                  @click="copyAddress(store.selectedMailDetail.recipient)"
                  class="font-mono text-[11.5px] text-[var(--ink-primary)] hover:text-[var(--accent-vermilion)] truncate transition text-left underline decoration-dotted underline-offset-2"
                  title="点击复制收件邮箱"
                >
                  {{ store.selectedMailDetail.recipient }}
                </button>
              </div>
            </div>

            <div class="grid grid-cols-1 md:grid-cols-2 divide-y md:divide-y-0 md:divide-x divide-[var(--rule-faint)]">
              <!-- DATE -->
              <div class="px-3.5 py-2 flex items-baseline gap-3">
                <span class="w-14 sm:w-20 flex-shrink-0 font-mono text-[10px] tracking-[0.08em] uppercase text-[var(--ink-muted)]">
                  时间
                </span>
                <time class="font-mono text-[11.5px] tabular-nums text-[var(--ink-secondary)]">
                  {{ formatFullDate(store.selectedMailDetail.created_at) }}
                </time>
              </div>

              <!-- REF / ENCLOSURES -->
              <div class="px-3.5 py-2 flex items-baseline gap-3">
                <span class="w-14 sm:w-20 flex-shrink-0 font-mono text-[10px] tracking-[0.08em] uppercase text-[var(--ink-muted)]">
                  编号
                </span>
                <span class="font-mono text-[11px] text-[var(--ink-secondary)]">
                  #{{ folioSerial }}
                  <template v-if="store.selectedMailDetail.attachments?.length">
                    · 附件 {{ store.selectedMailDetail.attachments.length }} 个
                  </template>
                </span>
              </div>
            </div>
          </div>

          <!-- Perforated Ticket-Stub Verification Code Copy Block -->
          <div
            v-if="extractedCode"
            @click="copyCode(extractedCode)"
            class="ed-ticket-stub cursor-pointer flex items-stretch justify-between overflow-hidden hover:opacity-95 transition select-none"
            title="点击复制验证码"
          >
            <div class="px-3.5 sm:px-4 py-3 flex items-center gap-3 min-w-0">
              <div class="w-8 h-8 border border-[var(--accent-forest-border)] bg-[var(--bg-salon)] flex items-center justify-center text-[var(--accent-forest)] rounded-[2px] flex-shrink-0">
                <Stamp class="w-4 h-4" />
              </div>
              <div class="min-w-0">
                <span class="font-mono text-[10px] tracking-[0.14em] uppercase text-[var(--accent-forest)] block">
                  验证码
                </span>
                <span class="font-mono text-[18px] sm:text-[20px] font-semibold tracking-[0.16em] sm:tracking-[0.22em] text-[var(--ink-primary)] tabular-nums truncate block">
                  {{ extractedCode }}
                </span>
              </div>
            </div>

            <!-- Perforated Tear Line & Stub Action -->
            <div class="px-3.5 sm:px-5 border-l-2 border-dashed border-[var(--accent-forest-border)] flex items-center gap-1.5 text-[12px] font-mono font-medium text-[var(--accent-forest)] bg-[var(--bg-subtle)] flex-shrink-0">
              <Check v-if="copiedCode" class="w-3.5 h-3.5" />
              <Copy v-else class="w-3.5 h-3.5" />
              <span>{{ copiedCode ? '已复制' : '复制' }}</span>
            </div>
          </div>

          <!-- Crisp Stationery Reader Body -->
          <div
            class="transition-transform origin-top-left pt-1"
            :style="{ transform: `scale(${zoom})` }"
          >
            <SafeMailHtml
              v-if="store.selectedMailDetail.body_html"
              :html="store.selectedMailDetail.body_html"
              :class="[
                'text-[14.5px] leading-[1.8]',
                htmlStationeryPaper || store.theme === 'paper' ? 'ed-mail-paper' : 'ed-mail-adaptive'
              ]"
            />
            <div
              v-else
              class="text-[var(--ink-primary)] text-[14.5px] whitespace-pre-wrap leading-[1.88] font-sans py-2 px-1"
            >{{ store.selectedMailDetail.body_text }}</div>

            <!-- Archival Enclosures (Attachments) -->
            <div
              v-if="store.selectedMailDetail.has_attachments && store.selectedMailDetail.attachments?.length"
              class="mt-10 pt-5 border-t border-[var(--rule-medium)]"
            >
              <div class="flex items-center justify-between mb-3">
                <span class="ed-rubric">附件 ({{ store.selectedMailDetail.attachments.length }})</span>
              </div>
              <div class="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                <a
                  v-for="(att, idx) in store.selectedMailDetail.attachments"
                  :key="`${idx}-${att.name}`"
                  :href="att.download_url || `/api/mails/${store.selectedMailDetail.id}/attachments/${att.index ?? idx}`"
                  :download="att.name"
                  class="p-3 rounded-[2px] bg-[var(--bg-ledger)] hover:bg-[var(--bg-hover)] border border-[var(--rule-medium)] flex items-center justify-between transition cursor-pointer no-underline"
                >
                  <div class="flex items-center gap-2.5 truncate">
                    <FileText class="w-4 h-4 text-[var(--accent-vermilion)] flex-shrink-0" />
                    <div class="truncate">
                      <p class="text-[12.5px] font-medium text-[var(--ink-primary)] truncate">{{ att.name }}</p>
                      <p class="text-[10.5px] font-mono text-[var(--ink-muted)]">{{ att.size }}</p>
                    </div>
                  </div>
                  <Download class="w-3.5 h-3.5 text-[var(--ink-muted)] flex-shrink-0" />
                </a>
              </div>
            </div>

            <!-- End-of-Letter Printer's Mark -->
            <div class="mt-12 pt-4 border-t border-[var(--rule-faint)] flex items-center justify-between text-[10px] font-mono text-[var(--ink-faint)] select-none">
              <span>PRISMMAIL</span>
              <span>∎</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Loading Mail Detail State -->
    <div v-else-if="store.selectedMail" class="h-full flex flex-col">
      <header class="lg:hidden h-11 px-3.5 border-b border-[var(--rule-faint)] bg-[var(--bg-ledger)] flex items-center flex-shrink-0">
        <button
          type="button"
          @click="handleBackMobile"
          class="h-7 px-2.5 ed-btn-outline text-[12px] font-medium flex items-center gap-1"
        >
          <ArrowLeft class="w-3.5 h-3.5" />
          <span>返回</span>
        </button>
      </header>
      <div class="flex-1 flex flex-col items-center justify-center gap-2.5 text-[var(--ink-muted)]">
        <Loader2 class="w-5 h-5 animate-spin text-[var(--accent-vermilion)]" />
        <span class="text-[12px]">正在加载邮件内容...</span>
      </div>
    </div>

    <!-- Editorial Empty State -->
    <div v-else class="h-full flex flex-col items-center justify-center p-8 select-none">
      <div class="max-w-sm w-full border border-[var(--rule-medium)] bg-[var(--bg-ledger)] p-8 text-center space-y-5 rounded-[2px]">
        <!-- Editorial Wordmark Colophon -->
        <div class="pt-1 flex justify-center">
          <PrismWordmark class="h-[23px] w-auto text-[var(--ink-primary)]" />
        </div>

        <div class="space-y-1.5">
          <h3 class="font-serif text-[18px] text-[var(--ink-primary)] font-medium leading-tight">
            未选择邮件
          </h3>
          <p class="text-[12px] text-[var(--ink-muted)] leading-relaxed">
            从左侧列表选择一封邮件查看内容
          </p>
        </div>

        <div class="hidden lg:flex pt-4 border-t border-[var(--rule-faint)] items-center justify-center gap-4 text-[11px] text-[var(--ink-muted)]">
          <span class="flex items-center gap-1.5">
            <kbd class="ed-kbd">⌘K</kbd>
            <span>搜索</span>
          </span>
          <span class="flex items-center gap-1.5">
            <kbd class="ed-kbd">C</kbd>
            <span>写邮件</span>
          </span>
          <span class="flex items-center gap-1.5">
            <kbd class="ed-kbd">J</kbd>
            <kbd class="ed-kbd">K</kbd>
            <span>上下封</span>
          </span>
        </div>
      </div>
    </div>
  </main>
</template>
