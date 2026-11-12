<script setup>
import { ref, computed } from 'vue'
import { useMailStore } from '../stores/mail'
import { Search, X, RotateCw, Inbox, Paperclip, Star, Copy } from 'lucide-vue-next'

const store = useMailStore()
const chibiRiceUrl = `${import.meta.env.BASE_URL}deepseek-chibi-rice.png`
const chibiThinkUrl = `${import.meta.env.BASE_URL}deepseek-chibi-think.png`
const searchInputRef = ref(null)
const localQuery = ref('')

const folderTitle = computed(() => {
  const map = {
    inbox: '收件箱',
    starred: '星标信件',
    sent: '已投递',
    drafts: '草稿箱',
    quarantine: '深海隔离区',
    trash: '废纸篓'
  }
  return map[store.selectedFolder] || store.selectedFolder
})

const formatSenderName = (raw) => {
  if (!raw) return '神秘来信'
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
  const m = text.match(/(?:验证码|校验码|动态码|确认码|安全码|代码|code|verification|passcode|otp|pin)[^0-9A-Za-z]{0,22}\b([0-9]{4,8})\b/i)
  if (m) return m[1]
  const s = (mail.subject || '').match(/\b([0-9]{6})\b/)
  return s ? s[1] : null
}

const quickCopyOtp = async (code) => {
  if (!code) return
  try {
    await navigator.clipboard.writeText(code)
    store.notify(`鲸鱼娘已帮你叼走验证码 ${code} ✨`, 'success')
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
    return '昨天'
  }
  return `${dt.getMonth() + 1}月${dt.getDate()}日`
}

defineExpose({
  focusSearch: () => searchInputRef.value?.focus()
})
</script>

<template>
  <section class="flex-shrink-0 ds-card flex flex-col select-none overflow-hidden">
    <!-- Stream Header -->
    <div class="px-4 pt-3.5 pb-3 border-b border-[var(--border-hairline)] space-y-2.5">
      <div class="flex items-center justify-between gap-2">
        <div class="flex items-center gap-2 min-w-0">
          <h2 class="text-[14.5px] font-extrabold tracking-[-0.01em] text-[var(--text-primary)] flex-shrink-0">
            {{ folderTitle }}
          </h2>
          <span class="px-2 py-0.5 rounded-full bg-[var(--bg-pill)] text-[#4D6BFE] dark:text-[#7DD3FC] text-[11px] font-mono font-bold tabular-nums">
            {{ store.displayedMails.length }}
          </span>
          <button
            v-if="store.scopeLabel"
            @click="clearScopeFilter"
            class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-[#4D6BFE]/14 hover:bg-[#4D6BFE]/22 text-[#4D6BFE] dark:text-[#7DD3FC] text-[11px] font-mono font-bold truncate max-w-[135px] transition"
            title="点击清除范围筛选"
          >
            <span class="truncate">{{ store.scopeLabel }}</span>
            <X class="w-3 h-3 opacity-75 hover:opacity-100 flex-shrink-0" />
          </button>
        </div>

        <div class="flex items-center gap-1.5 flex-shrink-0">
          <!-- All / Unread Segmented Pill -->
          <div class="inline-flex p-0.5 rounded-xl bg-[var(--bg-subtle)] border border-[var(--border-hairline)] text-[11px]">
            <button
              @click="store.streamUnreadOnly = false"
              :class="[
                'px-2 py-0.5 rounded-lg transition font-bold',
                !store.streamUnreadOnly
                  ? 'bg-[#4D6BFE] text-white shadow-sm'
                  : 'text-[var(--text-muted)] hover:text-[var(--text-primary)]'
              ]"
            >
              全部
            </button>
            <button
              @click="store.streamUnreadOnly = true"
              :class="[
                'px-2 py-0.5 rounded-lg transition font-bold',
                store.streamUnreadOnly
                  ? 'bg-[#4D6BFE] text-white shadow-sm'
                  : 'text-[var(--text-muted)] hover:text-[var(--text-primary)]'
              ]"
            >
              未读
            </button>
          </div>

          <!-- Playful Sync Button: 潜航捞信中... -->
          <button
            @click="store.fetchMails(true)"
            :disabled="store.isLoadingMails"
            :class="[
              'h-7 px-2.5 rounded-xl border text-[11px] font-bold flex items-center gap-1.5 ds-spring',
              store.isLoadingMails
                ? 'bg-[#4D6BFE]/15 border-[#4D6BFE]/40 text-[#4D6BFE] dark:text-[#7DD3FC]'
                : 'bg-[var(--bg-subtle)] hover:bg-[var(--bg-hover)] border-[var(--border-hairline)] text-[var(--text-secondary)] hover:text-[#4D6BFE]'
            ]"
            title="潜航同步全部信件"
          >
            <RotateCw :class="['w-3.5 h-3.5', { 'animate-spin text-[#4D6BFE]': store.isLoadingMails }]" />
            <span>{{ store.isLoadingMails ? '潜航捞信中...' : '捞信' }}</span>
          </button>
        </div>
      </div>

      <!-- Search Input -->
      <div class="relative">
        <Search class="w-3.5 h-3.5 text-[#4D6BFE]/70 absolute left-3 top-2.5" />
        <input
          ref="searchInputRef"
          v-model="localQuery"
          @input="handleSearchInput"
          type="text"
          placeholder="搜索信件标题、发件人或正文 (按 / 聚焦)..."
          class="w-full h-[34px] py-1.5 pl-9 pr-7 rounded-xl bg-[var(--bg-input)] border border-[var(--border-hairline)] focus:border-[var(--border-focus)] text-[12px] text-[var(--text-primary)] placeholder-[var(--text-muted)] focus:outline-none transition"
        />
        <button
          v-if="localQuery"
          @click="clearSearch"
          class="absolute right-2.5 top-2 text-[var(--text-muted)] hover:text-[var(--text-primary)]"
        >
          <X class="w-3.5 h-3.5" />
        </button>
      </div>
    </div>

    <!-- Stream Rows -->
    <div class="flex-1 overflow-y-auto p-2 space-y-1.5">
      <!-- Live Chibi Courier Strip While Syncing -->
      <div
        v-if="store.isLoadingMails"
        class="mx-1 mb-1 px-3 py-2 rounded-2xl bg-gradient-to-r from-[#4D6BFE]/12 via-[#38BDF8]/12 to-transparent border border-[#4D6BFE]/25 flex items-center gap-2.5"
      >
        <img
          :src="chibiThinkUrl"
          alt="潜航捞信中"
          class="w-9 h-9 object-contain animate-whale-bob flex-shrink-0 select-none pointer-events-none"
          draggable="false"
        />
        <div class="min-w-0">
          <p class="text-[11.5px] font-extrabold text-[#4D6BFE] dark:text-[#7DD3FC] truncate">
            戴上小眼镜，骑着大肥鱼深海捞信中... 🫧
          </p>
          <p class="text-[10px] text-[var(--text-muted)] truncate">R1-Maid 正在扫描全部绑定信箱</p>
        </div>
      </div>

      <!-- Skeleton -->
      <div v-if="store.isLoadingMails && store.mails.length === 0" class="p-3 space-y-3.5">
        <div v-for="n in 5" :key="n" class="animate-pulse flex items-start gap-3 p-2.5 rounded-2xl bg-[var(--bg-subtle)]">
          <div class="w-9 h-9 rounded-2xl bg-[var(--bg-hover)] flex-shrink-0" />
          <div class="flex-1 space-y-2 pt-0.5">
            <div class="h-3 bg-[var(--bg-hover)] rounded-full w-1/3" />
            <div class="h-3 bg-[var(--bg-hover)] rounded-full w-4/5" />
            <div class="h-2.5 bg-[var(--bg-subtle)] rounded-full w-3/5" />
          </div>
        </div>
      </div>

      <!-- Empty State: Iconic Chibi Eating 3 Bowls of Steaming White Rice! -->
      <div
        v-else-if="store.displayedMails.length === 0"
        class="h-full flex flex-col items-center justify-center p-6 text-center text-[var(--text-muted)] space-y-3"
      >
        <div class="relative w-36 h-36 flex items-center justify-center">
          <div class="absolute inset-3 rounded-full bg-gradient-to-tr from-[#4D6BFE]/15 via-[#38BDF8]/15 to-transparent blur-xl pointer-events-none" />
          <img
            :src="chibiRiceUrl"
            alt="先干三碗大白米饭"
            class="relative w-36 h-36 object-contain ds-chibi-sticker animate-whale-bob select-none pointer-events-none"
            draggable="false"
          />
        </div>
        <div class="space-y-1 max-w-[240px]">
          <p class="text-[13px] font-extrabold text-[var(--text-primary)]">
            {{ store.streamUnreadOnly ? '未读信件清零啦！奖励干三碗白米饭 🍚' : '海面风平浪静，先干三碗大白米饭吧！🍚' }}
          </p>
          <p class="text-[11.5px] text-[var(--text-muted)] leading-relaxed">
            大肥鱼在旁边眼巴巴流口水呢~ 点击右上角「捞信」潜入深海找找新邮件吧！
          </p>
        </div>
      </div>

      <!-- Momotalk-inspired Mail Cards -->
      <template v-else>
        <article
          v-for="mail in store.displayedMails"
          :key="mail.id"
          @click="store.selectMail(mail)"
          :class="[
            'px-3.5 py-3 rounded-2xl cursor-pointer transition-all relative group flex items-start gap-3 border',
            store.selectedMail?.id === mail.id && !store.showMascotStage
              ? 'bg-[var(--bg-active)] border-[#4D6BFE]/40 shadow-sm'
              : 'bg-transparent border-transparent hover:bg-[var(--bg-hover)] hover:border-[var(--border-hairline)]'
          ]"
        >
          <!-- Active Left Accent Pill -->
          <span
            v-if="store.selectedMail?.id === mail.id && !store.showMascotStage"
            class="absolute left-1 top-3 bottom-3 w-[3.5px] rounded-full bg-gradient-to-b from-[#4D6BFE] to-[#38BDF8]"
          />

          <!-- Sender Avatar + Unread Bubble Dot -->
          <div class="relative flex-shrink-0 mt-0.5">
            <div
              :class="[
                'w-9 h-9 rounded-2xl flex items-center justify-center text-[13px] font-extrabold border transition',
                !mail.is_read
                  ? 'bg-gradient-to-br from-[#4D6BFE]/18 to-[#38BDF8]/22 border-[#4D6BFE]/35 text-[#4D6BFE] dark:text-[#7DD3FC]'
                  : 'bg-[var(--bg-subtle)] border-[var(--border-hairline)] text-[var(--text-secondary)]'
              ]"
            >
              {{ getInitial(mail.sender) }}
            </div>
            <span
              v-if="!mail.is_read"
              class="absolute -top-0.5 -right-0.5 w-2.5 h-2.5 rounded-full bg-[#4D6BFE] ring-2 ring-[var(--bg-card)]"
            />
          </div>

          <!-- Content Column -->
          <div class="flex-1 min-w-0">
            <div class="flex items-center justify-between gap-2">
              <span
                :class="[
                  'text-[12.5px] truncate',
                  !mail.is_read
                    ? 'font-extrabold text-[var(--text-primary)]'
                    : 'font-semibold text-[var(--text-secondary)]'
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
                    ? 'font-bold text-[var(--text-primary)]'
                    : 'font-medium text-[var(--text-secondary)]'
                ]"
              >
                {{ mail.subject || '(无主题信件)' }}
              </p>

              <!-- Quick 1-Click Copy OTP Pill -->
              <button
                v-if="extractQuickOtp(mail)"
                @click.stop="quickCopyOtp(extractQuickOtp(mail))"
                class="px-1.5 py-0.5 rounded-lg bg-[#4D6BFE]/14 hover:bg-[#4D6BFE] text-[#4D6BFE] dark:text-[#7DD3FC] hover:text-white border border-[#4D6BFE]/30 text-[10px] font-mono font-bold flex items-center gap-1 flex-shrink-0 transition"
                title="点击一键复制验证码"
              >
                <span>🐋 {{ extractQuickOtp(mail) }}</span>
                <Copy class="w-2.5 h-2.5" />
              </button>
            </div>

            <p class="text-[11.5px] text-[var(--text-muted)] truncate mt-0.5 leading-relaxed">
              {{ mail.preview }}
            </p>

            <!-- Meta Footer -->
            <div
              v-if="(!store.selectedMailboxId && mail.mailbox_address) || mail.has_attachments || mail.is_starred || (mail.tags && mail.tags.length)"
              class="flex items-center justify-between mt-1.5"
            >
              <div class="flex items-center gap-1.5 min-w-0">
                <span
                  v-if="!store.selectedMailboxId && mail.mailbox_address"
                  class="px-1.5 py-0.5 rounded-md bg-[var(--bg-subtle)] text-[10px] font-mono text-[var(--text-muted)] truncate"
                >
                  → {{ mail.mailbox_address }}
                </span>
                <span
                  v-for="tag in mail.tags"
                  :key="tag"
                  class="px-1.5 py-0.5 rounded-md bg-[var(--bg-pill)] text-[#4D6BFE] dark:text-[#7DD3FC] text-[10px] font-bold"
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
                      : 'opacity-0 group-hover:opacity-100 hover:text-[var(--accent-amber)]'
                  ]"
                  title="星标"
                >
                  <Star class="w-3.5 h-3.5" :fill="mail.is_starred ? 'currentColor' : 'none'" />
                </button>
              </div>
            </div>
          </div>
        </article>
      </template>
    </div>
  </section>
</template>
