<script setup>
import { ref, computed } from 'vue'
import { useMailStore, extractVerificationCode } from '../stores/mail'
import { Search, X, RotateCw, Inbox, Paperclip, Star } from 'lucide-vue-next'

const store = useMailStore()
const searchInputRef = ref(null)
const localQuery = ref('')

const folderMeta = computed(() => {
  const map = {
    inbox: { cn: '收件箱', en: 'INBOX' },
    starred: { cn: '星标邮件', en: 'STARRED' },
    sent: { cn: '已发送', en: 'SENT' },
    drafts: { cn: '草稿箱', en: 'DRAFTS' },
    quarantine: { cn: '隔离区', en: 'QUARANTINE' },
    trash: { cn: '废纸篓', en: 'TRASH' }
  }
  return map[store.selectedFolder] || { cn: store.selectedFolder, en: 'MAIL' }
})

const formatSenderName = (raw) => {
  if (!raw) return '未知发件人'
  const match = raw.match(/^([^<]+)<([^>]+)>$/)
  if (match) {
    const name = match[1].trim().replace(/^["']|["']$/g, '')
    return name || match[2].trim()
  }
  return raw.trim()
}

const getQuickOtp = (mail) => {
  return extractVerificationCode(mail.subject, mail.preview, '')
}

const copyQuickOtp = async (code) => {
  if (!code) return
  try {
    await navigator.clipboard.writeText(code)
    store.notify(`已复制验证码 ${code}`, 'success')
  } catch {}
}

let debounceTimer = null
const handleSearchInput = () => {
  clearTimeout(debounceTimer)
  debounceTimer = setTimeout(() => {
    store.searchQuery = localQuery.value.trim()
    store.fetchMails()
  }, 180)
}

const clearSearch = () => {
  localQuery.value = ''
  store.searchQuery = ''
  store.fetchMails()
}

const clearScopeFilter = () => {
  store.selectScope({ domainId: null, mailboxId: null, labelId: null, smartFilter: null })
}

const toggleStar = (mail) => {
  store.updateMailStatus(mail.id, { is_starred: !mail.is_starred })
}

const formatTime = (iso) => {
  if (!iso) return ''
  const dt = new Date(iso)
  const now = new Date()
  if (dt.toDateString() === now.toDateString()) {
    return dt.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', hour12: false })
  }
  const yesterday = new Date(now)
  yesterday.setDate(now.getDate() - 1)
  if (dt.toDateString() === yesterday.toDateString()) {
    return '昨日'
  }
  const m = String(dt.getMonth() + 1).padStart(2, '0')
  const d = String(dt.getDate()).padStart(2, '0')
  return `${m}/${d}`
}

defineExpose({
  focusSearch: () => searchInputRef.value?.focus()
})
</script>

<template>
  <section
    class="flex-shrink-0 bg-[var(--bg-ledger)] border-r border-[var(--rule-faint)] flex flex-col select-none overflow-hidden"
  >
    <!-- Ledger Architectural Header -->
    <div class="px-4 pt-3 pb-3 border-b border-[var(--rule-medium)] space-y-2.5">
      <!-- Top Rubric & Sync -->
      <div class="flex items-center justify-between">
        <span class="ed-rubric">02 / {{ folderMeta.en }}</span>
        <button
          @click="store.fetchMails(true)"
          class="inline-flex items-center gap-1 text-[10.5px] font-mono text-[var(--ink-muted)] hover:text-[var(--ink-primary)] transition"
          title="同步校验最新函件"
        >
          <RotateCw :class="['w-3 h-3', { 'animate-spin text-[var(--accent-vermilion)]': store.isLoadingMails }]" />
          <span>同步</span>
        </button>
      </div>

      <!-- Serif Section Headline + Filter Tabs -->
      <div class="flex items-baseline justify-between gap-2">
        <div class="flex items-baseline gap-2 min-w-0">
          <h2 class="font-serif text-[19px] font-medium tracking-[-0.01em] text-[var(--ink-primary)] flex-shrink-0 leading-tight">
            {{ folderMeta.cn }}
          </h2>
          <span class="text-[11px] font-mono tabular-nums text-[var(--ink-muted)]">
            / {{ store.displayedMails.length }}
          </span>

          <button
            v-if="store.scopeLabel"
            @click="clearScopeFilter"
            class="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-[2px] bg-[var(--accent-vermilion-soft)] border border-[var(--accent-vermilion-border)] text-[var(--accent-vermilion)] text-[10.5px] font-mono truncate max-w-[140px] transition"
            title="点击清除范围筛选"
          >
            <span class="truncate">{{ store.scopeLabel }}</span>
            <X class="w-2.5 h-2.5 flex-shrink-0" />
          </button>
        </div>

        <!-- All / Unread Tabs -->
        <div class="inline-flex border border-[var(--rule-medium)] rounded-[2px] bg-[var(--bg-subtle)] p-[1px] text-[11px] flex-shrink-0">
          <button
            @click="store.streamUnreadOnly = false"
            :class="[
              'px-2 py-0.5 rounded-[1px] transition',
              !store.streamUnreadOnly
                ? 'bg-[var(--ink-primary)] text-[var(--bg-salon)] font-medium'
                : 'text-[var(--ink-muted)] hover:text-[var(--ink-primary)]'
            ]"
          >
            全部
          </button>
          <button
            @click="store.streamUnreadOnly = true"
            :class="[
              'px-2 py-0.5 rounded-[1px] transition',
              store.streamUnreadOnly
                ? 'bg-[var(--ink-primary)] text-[var(--bg-salon)] font-medium'
                : 'text-[var(--ink-muted)] hover:text-[var(--ink-primary)]'
            ]"
          >
            未读
          </button>
        </div>
      </div>

      <!-- Crisp Architectural Search Input -->
      <div class="relative">
        <Search class="w-3.5 h-3.5 text-[var(--ink-muted)] absolute left-2.5 top-2.5 sm:top-[8px]" />
        <input
          ref="searchInputRef"
          v-model="localQuery"
          @input="handleSearchInput"
          type="text"
          placeholder="搜索主题、发件人或内容..."
          class="w-full h-9 sm:h-[30px] pl-8 pr-7 rounded-[2px] bg-[var(--bg-input)] border border-[var(--rule-medium)] focus:border-[var(--rule-strong)] text-[12px] text-[var(--ink-primary)] placeholder-[var(--ink-faint)] focus:outline-none transition"
        />
        <button
          v-if="localQuery"
          @click="clearSearch"
          class="absolute right-2 top-2.5 sm:top-[8px] text-[var(--ink-muted)] hover:text-[var(--ink-primary)]"
        >
          <X class="w-3.5 h-3.5" />
        </button>
      </div>
    </div>

    <!-- Correspondence Ledger List -->
    <div class="flex-1 overflow-y-auto pb-safe">
      <!-- Loading Skeleton -->
      <div v-if="store.isLoadingMails && store.mails.length === 0" class="divide-y divide-[var(--rule-faint)]">
        <div v-for="n in 6" :key="n" class="px-4 py-3.5 animate-pulse space-y-2">
          <div class="flex justify-between">
            <div class="h-3 bg-[var(--bg-hover)] w-1/3" />
            <div class="h-2.5 bg-[var(--bg-subtle)] w-10" />
          </div>
          <div class="h-3.5 bg-[var(--bg-hover)] w-4/5" />
          <div class="h-2.5 bg-[var(--bg-subtle)] w-3/5" />
        </div>
      </div>

      <!-- Empty Ledger -->
      <div
        v-else-if="store.displayedMails.length === 0"
        class="h-full flex flex-col items-center justify-center p-8 text-center text-[var(--ink-muted)] space-y-2"
      >
        <Inbox class="w-6 h-6 stroke-[1.25] opacity-55" />
        <p class="font-serif text-[14px] text-[var(--ink-secondary)]">
          {{ store.streamUnreadOnly ? '暂无未读邮件' : '暂无邮件' }}
        </p>
        <span class="ed-rubric">NO MESSAGES</span>
      </div>

      <!-- Ledger Entries -->
      <div v-else class="divide-y divide-[var(--rule-faint)]">
        <article
          v-for="mail in store.displayedMails"
          :key="mail.id"
          @click="store.selectMail(mail)"
          :class="[
            'px-4 py-3 cursor-pointer transition relative group border-l-[3px]',
            store.selectedMail?.id === mail.id
              ? 'border-[var(--accent-vermilion)] bg-[var(--bg-active)]'
              : 'border-transparent hover:bg-[var(--bg-hover)]'
          ]"
        >
          <!-- Row 1: Sender in Medium Grotesque + Tabular Timestamp -->
          <div class="flex items-center justify-between gap-2">
            <div class="flex items-center gap-2 min-w-0">
              <span
                v-if="!mail.is_read"
                class="w-1.5 h-1.5 bg-[var(--accent-vermilion)] flex-shrink-0"
                title="未读函件"
              />
              <span
                :class="[
                  'text-[12.5px] truncate',
                  !mail.is_read
                    ? 'font-semibold text-[var(--ink-primary)]'
                    : 'font-medium text-[var(--ink-secondary)]'
                ]"
                :title="mail.sender"
              >
                {{ formatSenderName(mail.sender) }}
              </span>
            </div>

            <time class="text-[11px] font-mono tabular-nums text-[var(--ink-muted)] flex-shrink-0">
              {{ formatTime(mail.created_at) }}
            </time>
          </div>

          <!-- Row 2: Refined Subject + Perforated Stamp OTP Badge -->
          <div class="flex items-center justify-between gap-2 mt-1">
            <h3
              :class="[
                'font-serif text-[14px] leading-snug truncate',
                !mail.is_read
                  ? 'font-semibold text-[var(--ink-primary)]'
                  : 'font-normal text-[var(--ink-primary)] opacity-90'
              ]"
            >
              {{ mail.subject || '(无主题)' }}
            </h3>

            <button
              v-if="getQuickOtp(mail)"
              @click.stop="copyQuickOtp(getQuickOtp(mail))"
              class="ed-stamp-otp flex-shrink-0 hover:opacity-80 transition"
              title="点击一键复制验证码"
            >
              CODE {{ getQuickOtp(mail) }}
            </button>
          </div>

          <!-- Row 3: Excerpt -->
          <p class="text-[11.5px] text-[var(--ink-muted)] truncate mt-1 leading-relaxed">
            {{ mail.preview || '—' }}
          </p>

          <!-- Row 4: Dispatch Metadata & Star -->
          <div
            v-if="(!store.selectedMailboxId && mail.mailbox_address) || mail.has_attachments || mail.is_starred || (mail.tags && mail.tags.length)"
            class="flex items-center justify-between mt-1.5 pt-1 border-t border-dashed border-[var(--rule-faint)]"
          >
            <div class="flex items-center gap-1.5 min-w-0">
              <span
                v-if="!store.selectedMailboxId && mail.mailbox_address"
                class="text-[10.5px] font-mono text-[var(--ink-muted)] truncate"
              >
                → {{ mail.mailbox_address }}
              </span>
              <span
                v-for="tag in mail.tags"
                :key="tag"
                class="px-1.5 py-[1px] border border-[var(--rule-faint)] bg-[var(--bg-subtle)] text-[var(--ink-secondary)] text-[10px] font-mono"
              >
                #{{ tag }}
              </span>
            </div>

            <div class="flex items-center gap-1.5 text-[var(--ink-muted)] flex-shrink-0">
              <Paperclip v-if="mail.has_attachments" class="w-3 h-3" />
              <button
                @click.stop="toggleStar(mail)"
                :class="[
                  'transition',
                  mail.is_starred
                    ? 'text-[var(--accent-ochre)]'
                    : 'opacity-0 group-hover:opacity-100 ed-touch-show hover:text-[var(--accent-ochre)]'
                ]"
                title="星标邮件"
              >
                <Star class="w-3.5 h-3.5" :fill="mail.is_starred ? 'currentColor' : 'none'" />
              </button>
            </div>
          </div>
        </article>
      </div>
    </div>
  </section>
</template>
