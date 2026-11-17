<script setup>
import { ref, computed } from 'vue'
import { useMailStore } from '../stores/mail'
import { Search, X, RotateCw, Inbox, Paperclip, Star, Menu, PenLine } from 'lucide-vue-next'

const store = useMailStore()
const searchInputRef = ref(null)
const localQuery = ref('')

const folderTitle = computed(() => {
  const map = {
    inbox: '收件箱',
    starred: '星标',
    sent: '已发送',
    drafts: '草稿',
    quarantine: '隔离区',
    trash: '废纸篓'
  }
  return map[store.selectedFolder] || store.selectedFolder
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

const getInitial = (raw) => {
  const name = formatSenderName(raw)
  return (name.charAt(0) || '?').toUpperCase()
}

const extractQuickOtp = (mail) => {
  const text = `${mail.subject || ''} ${mail.preview || ''}`
  const m = text.match(/(?:验证码|代码|code|verification|passcode|otp)[^0-9A-Za-z]{0,18}\b([0-9]{4,8})\b/i)
  if (m) return m[1]
  const s = (mail.subject || '').match(/\b([0-9]{6})\b/)
  return s ? s[1] : null
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
    return '昨天'
  }
  return `${dt.getMonth() + 1}月${dt.getDate()}日`
}

defineExpose({
  focusSearch: () => searchInputRef.value?.focus()
})
</script>

<template>
  <section class="flex-shrink-0 lg:border-r border-[var(--border-hairline)] flex flex-col select-none bg-[var(--bg-sheet)]">
    <!-- Stream Header -->
    <div class="px-4 pt-3.5 pb-3 border-b border-[var(--border-hairline)] space-y-2.5">
      <div class="flex items-center justify-between gap-2">
        <div class="flex items-center gap-2 min-w-0">
          <button
            @click="store.isMobileNavOpen = true"
            class="lg:hidden -ml-1.5 p-1.5 rounded-lg text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-hover)] transition flex-shrink-0"
            title="打开导航"
          >
            <Menu class="w-4 h-4" />
          </button>
          <h2 class="text-[14px] font-semibold tracking-[-0.01em] text-[var(--text-primary)] flex-shrink-0">
            {{ folderTitle }}
          </h2>
          <span class="text-[11.5px] font-mono tabular-nums text-[var(--text-muted)]">
            {{ store.displayedMails.length }}
          </span>
          <button
            v-if="store.scopeLabel"
            @click="clearScopeFilter"
            class="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-[var(--bg-pill)] hover:bg-[var(--bg-active)] text-[var(--text-primary)] text-[11px] font-mono truncate max-w-[130px] sm:max-w-[150px] transition"
            title="清除筛选"
          >
            <span class="truncate">{{ store.scopeLabel }}</span>
            <X class="w-2.5 h-2.5 opacity-60 hover:opacity-100 flex-shrink-0" />
          </button>
        </div>

        <div class="flex items-center gap-1 flex-shrink-0">
          <!-- All / Unread Quick Filter -->
          <div class="inline-flex p-0.5 rounded-lg bg-[var(--bg-subtle)] border border-[var(--border-hairline)] text-[11px]">
            <button
              @click="store.streamUnreadOnly = false"
              :class="[
                'px-2 py-0.5 rounded-md transition',
                !store.streamUnreadOnly
                  ? 'bg-[var(--bg-active)] text-[var(--text-primary)] font-medium'
                  : 'text-[var(--text-muted)] hover:text-[var(--text-secondary)]'
              ]"
            >
              全部
            </button>
            <button
              @click="store.streamUnreadOnly = true"
              :class="[
                'px-2 py-0.5 rounded-md transition',
                store.streamUnreadOnly
                  ? 'bg-[var(--bg-active)] text-[var(--text-primary)] font-medium'
                  : 'text-[var(--text-muted)] hover:text-[var(--text-secondary)]'
              ]"
            >
              未读
            </button>
          </div>

          <button
            @click="store.fetchMails(true)"
            class="p-1.5 rounded-lg text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-hover)] transition"
            title="同步收件箱"
          >
            <RotateCw :class="['w-3.5 h-3.5', { 'animate-spin text-[var(--text-primary)]': store.isLoadingMails }]" />
          </button>

          <button
            @click="store.openCompose()"
            class="lg:hidden p-1.5 rounded-lg text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-hover)] transition"
            title="撰写邮件"
          >
            <PenLine class="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      <!-- Search Input -->
      <div class="relative">
        <Search class="w-3.5 h-3.5 text-[var(--text-muted)] absolute left-2.5 top-2.5 sm:top-2" />
        <input
          ref="searchInputRef"
          v-model="localQuery"
          @input="handleSearchInput"
          type="text"
          placeholder="搜索邮件..."
          class="w-full h-9 sm:h-7.5 py-1.5 pl-8 pr-7 rounded-lg bg-[var(--bg-input)] border border-[var(--border-hairline)] focus:border-[var(--border-focus)] text-[12px] text-[var(--text-primary)] placeholder-[var(--text-muted)] focus:outline-none transition"
        />
        <button
          v-if="localQuery"
          @click="clearSearch"
          class="absolute right-2 top-2.5 sm:top-2 text-[var(--text-muted)] hover:text-[var(--text-primary)]"
        >
          <X class="w-3.5 h-3.5" />
        </button>
      </div>
    </div>

    <!-- Stream Rows -->
    <div class="flex-1 overflow-y-auto pb-safe">
      <!-- Skeleton -->
      <div v-if="store.isLoadingMails && store.mails.length === 0" class="p-4 space-y-4">
        <div v-for="n in 6" :key="n" class="animate-pulse flex items-start gap-3">
          <div class="w-8 h-8 rounded-full bg-[var(--bg-hover)] flex-shrink-0" />
          <div class="flex-1 space-y-2 pt-0.5">
            <div class="h-3 bg-[var(--bg-hover)] rounded w-1/3" />
            <div class="h-3 bg-[var(--bg-subtle)] rounded w-4/5" />
            <div class="h-2.5 bg-[var(--bg-subtle)] rounded w-3/5" />
          </div>
        </div>
      </div>

      <!-- Empty -->
      <div
        v-else-if="store.displayedMails.length === 0"
        class="h-full flex flex-col items-center justify-center p-8 text-center text-[var(--text-muted)] space-y-2"
      >
        <Inbox class="w-7 h-7 stroke-[1.3] opacity-50" />
        <p class="text-[12px]">{{ store.streamUnreadOnly ? '没有未读邮件' : '暂无信件' }}</p>
      </div>

      <!-- Items -->
      <div v-else class="divide-y divide-[var(--border-hairline)]">
        <article
          v-for="mail in store.displayedMails"
          :key="mail.id"
          @click="store.selectMail(mail)"
          :class="[
            'px-4 py-3 cursor-pointer transition relative group flex items-start gap-3',
            store.selectedMail?.id === mail.id
              ? 'bg-[var(--bg-active)]'
              : 'hover:bg-[var(--bg-hover)]'
          ]"
        >
          <!-- Active Selection Indicator Bar -->
          <span
            v-if="store.selectedMail?.id === mail.id"
            class="absolute left-0 top-2.5 bottom-2.5 w-[2.5px] rounded-r-full bg-[var(--text-primary)]"
          />

          <!-- Monogram Avatar + Unread Dot -->
          <div class="relative flex-shrink-0 mt-0.5">
            <div
              :class="[
                'w-8 h-8 rounded-full flex items-center justify-center text-[12px] font-medium border transition',
                !mail.is_read
                  ? 'bg-[var(--bg-active)] border-[var(--border-strong)] text-[var(--text-primary)]'
                  : 'bg-[var(--bg-subtle)] border-[var(--border-hairline)] text-[var(--text-secondary)]'
              ]"
            >
              {{ getInitial(mail.sender) }}
            </div>
            <span
              v-if="!mail.is_read"
              class="absolute -top-0.5 -right-0.5 w-2.5 h-2.5 rounded-full bg-[var(--accent-blue)] ring-2 ring-[var(--bg-sheet)]"
            />
          </div>

          <!-- Mail Content Column -->
          <div class="flex-1 min-w-0">
            <div class="flex items-center justify-between gap-2">
              <span
                :class="[
                  'text-[12.5px] truncate',
                  !mail.is_read
                    ? 'font-semibold text-[var(--text-primary)]'
                    : 'font-medium text-[var(--text-secondary)]'
                ]"
                :title="mail.sender"
              >
                {{ formatSenderName(mail.sender) }}
              </span>
              <span class="text-[11px] font-mono tabular-nums text-[var(--text-muted)] flex-shrink-0">
                {{ formatTime(mail.created_at) }}
              </span>
            </div>

            <div class="flex items-center gap-1.5 mt-0.5">
              <p
                :class="[
                  'text-[12.5px] truncate',
                  !mail.is_read
                    ? 'font-medium text-[var(--text-primary)]'
                    : 'font-normal text-[var(--text-secondary)]'
                ]"
              >
                {{ mail.subject || '(无主题)' }}
              </p>
              <span
                v-if="extractQuickOtp(mail)"
                class="px-1.5 py-0.2 rounded bg-emerald-500/10 text-[var(--accent-emerald)] border border-emerald-500/20 text-[10px] font-mono font-medium flex-shrink-0"
              >
                {{ extractQuickOtp(mail) }}
              </span>
            </div>

            <p class="text-[11.5px] text-[var(--text-muted)] truncate mt-0.5 leading-relaxed">
              {{ mail.preview }}
            </p>

            <!-- Meta Footer (Only when unified view or starred/attachments) -->
            <div
              v-if="(!store.selectedMailboxId && mail.mailbox_address) || mail.has_attachments || mail.is_starred || (mail.tags && mail.tags.length)"
              class="flex items-center justify-between mt-1.5"
            >
              <div class="flex items-center gap-1.5 min-w-0">
                <span
                  v-if="!store.selectedMailboxId && mail.mailbox_address"
                  class="text-[10.5px] font-mono text-[var(--text-muted)] truncate"
                >
                  → {{ mail.mailbox_address }}
                </span>
                <span
                  v-for="tag in mail.tags"
                  :key="tag"
                  class="px-1.5 py-0.2 rounded bg-[var(--bg-pill)] text-[var(--text-secondary)] text-[10px]"
                >
                  {{ tag }}
                </span>
              </div>

              <div class="flex items-center gap-1.5 text-[var(--text-muted)] flex-shrink-0">
                <Paperclip v-if="mail.has_attachments" class="w-3 h-3" />
                <button
                  @click.stop="toggleStar(mail)"
                  :class="[
                    'transition',
                    mail.is_starred
                      ? 'text-[var(--accent-amber)]'
                      : 'opacity-0 group-hover:opacity-100 pm-touch-show hover:text-[var(--accent-amber)]'
                  ]"
                >
                  <Star class="w-3.5 h-3.5" :fill="mail.is_starred ? 'currentColor' : 'none'" />
                </button>
              </div>
            </div>
          </div>
        </article>
      </div>
    </div>
  </section>
</template>
