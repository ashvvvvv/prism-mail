<script setup>
import { ref, watch } from 'vue'
import { useMailStore } from '../stores/mail'
import {
  Inbox,
  ChevronRight,
  Paperclip,
  Star,
  KeyRound,
  Search,
  X
} from 'lucide-vue-next'

const store = useMailStore()
const mobileQuery = ref(store.searchQuery || '')

watch(
  () => store.searchQuery,
  (val) => {
    if (val !== mobileQuery.value) {
      mobileQuery.value = val || ''
    }
  }
)

let mobileDebounce = null
const handleMobileSearch = () => {
  clearTimeout(mobileDebounce)
  mobileDebounce = setTimeout(() => {
    store.searchQuery = mobileQuery.value.trim()
    store.fetchMails()
  }, 180)
}

const formatSenderName = (raw) => {
  if (!raw) return '未知发件人'
  const match = raw.match(/^([^<]+)<([^>]+)>$/)
  if (match) {
    const name = match[1].trim().replace(/^["']|["']$/g, '')
    return name || match[2].trim()
  }
  return raw.trim()
}

const extractQuickOtp = (mail) => {
  const text = `${mail.subject || ''} ${mail.preview || ''}`
  const m = text.match(/(?:验证码|校验码|动态码|代码|code|verification|passcode|otp|pin)[^0-9A-Za-z]{0,20}\b([0-9]{4,8})\b/i)
  if (m) return m[1]
  const rev = text.match(/\b([0-9]{4,8})\b[^0-9A-Za-z]{0,12}(?:是您的验证码|为您的验证码|验证码|is your (?:verification )?code)/i)
  if (rev) return rev[1]
  const s = (mail.subject || '').match(/\b([0-9]{6})\b/)
  return s ? s[1] : null
}

const copyQuickOtp = async (code) => {
  try {
    await navigator.clipboard.writeText(code)
    store.notify(`已拷贝验证码 ${code}`, 'success')
  } catch {}
}

const toggleStar = (mail) => {
  store.updateMailStatus(mail.id, { is_starred: !mail.is_starred })
}

const clearSearchOnly = () => {
  store.searchQuery = ''
  store.fetchMails()
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
  if (dt.getFullYear() === now.getFullYear()) {
    return `${dt.getMonth() + 1}月${dt.getDate()}日`
  }
  return `${dt.getFullYear()}/${dt.getMonth() + 1}/${dt.getDate()}`
}

const isSelected = (mail) => store.selectedMail?.id === mail.id

const shouldHideBottomDivider = (idx) => {
  const list = store.displayedMails
  if (idx >= list.length - 1) return true
  const cur = list[idx]
  const next = list[idx + 1]
  return isSelected(cur) || isSelected(next)
}
</script>

<template>
  <section class="bg-[var(--bg-list)] lg:mac-hairline-r flex-shrink-0 flex flex-col overflow-hidden select-none">
    <!-- Mobile / Tablet iOS Mail Search & Filter Strip -->
    <div class="lg:hidden px-3 pt-2.5 pb-2 mac-hairline-b space-y-2">
      <div class="flex items-center gap-2">
        <div class="relative flex-1 flex items-center h-[34px] rounded-[9px] bg-[var(--bg-input)] border border-[var(--separator-subtle)] focus-within:border-[var(--apple-blue)] transition">
          <Search class="w-[14px] h-[14px] text-[var(--label-secondary)] ml-2.5 flex-shrink-0" />
          <input
            v-model="mobileQuery"
            @input="handleMobileSearch"
            type="text"
            placeholder="搜索邮件"
            class="w-full bg-transparent px-2 text-[13px] text-[var(--label-primary)] placeholder-[var(--label-secondary)] focus:outline-none"
          />
          <button
            v-if="mobileQuery"
            type="button"
            @click="mobileQuery = ''; clearSearchOnly()"
            class="mr-2 text-[var(--label-secondary)] hover:text-[var(--label-primary)]"
          >
            <X class="w-3.5 h-3.5" />
          </button>
        </div>

        <div class="md:hidden mac-segmented h-[32px] w-[96px] flex-shrink-0">
          <div
            class="mac-segmented-thumb absolute top-[2px] bottom-[2px] left-[2px] w-[45px] pointer-events-none"
            :style="{
              transform: store.streamUnreadOnly ? 'translateX(47px)' : 'translateX(0px)'
            }"
          />
          <button
            type="button"
            @click="store.streamUnreadOnly = false"
            :class="[
              'relative z-10 flex-1 h-full text-[11.5px] rounded-[6px] transition-colors',
              !store.streamUnreadOnly
                ? 'font-medium text-[var(--label-primary)]'
                : 'text-[var(--label-secondary)]'
            ]"
          >
            全部
          </button>
          <button
            type="button"
            @click="store.streamUnreadOnly = true"
            :class="[
              'relative z-10 flex-1 h-full text-[11.5px] rounded-[6px] transition-colors',
              store.streamUnreadOnly
                ? 'font-medium text-[var(--label-primary)]'
                : 'text-[var(--label-secondary)]'
            ]"
          >
            未读
          </button>
        </div>
      </div>
    </div>

    <!-- Active Search / Filter Banner (when searchQuery is active on Desktop) -->
    <div
      v-if="store.searchQuery"
      class="hidden lg:flex px-3.5 py-2 mac-hairline-b bg-[var(--fill-quaternary)] items-center justify-between text-[11.5px]"
    >
      <span class="text-[var(--label-secondary)] truncate">
        搜索「<span class="text-[var(--label-primary)] font-medium">{{ store.searchQuery }}</span>」· {{ store.displayedMails.length }} 封结果
      </span>
      <button
        type="button"
        @click="clearSearchOnly"
        class="text-[var(--apple-blue)] hover:opacity-80 flex items-center gap-0.5 flex-shrink-0 ml-2 font-medium"
      >
        <span>完成</span>
        <X class="w-3 h-3" />
      </button>
    </div>

    <!-- Scrollable Apple Mail List -->
    <div class="flex-1 overflow-y-auto py-1.5 pb-safe">
      <!-- Skeleton Loading -->
      <div v-if="store.isLoadingMails && store.mails.length === 0" class="px-3 py-2 space-y-3">
        <div
          v-for="n in 7"
          :key="n"
          class="px-3 py-2.5 rounded-[10px] animate-pulse space-y-2"
        >
          <div class="flex items-center justify-between">
            <div class="h-3.5 bg-[var(--fill-tertiary)] rounded w-28" />
            <div class="h-2.5 bg-[var(--fill-quaternary)] rounded w-10" />
          </div>
          <div class="h-3 bg-[var(--fill-tertiary)] rounded w-4/5" />
          <div class="h-2.5 bg-[var(--fill-quaternary)] rounded w-3/5" />
        </div>
      </div>

      <!-- Empty State -->
      <div
        v-else-if="store.displayedMails.length === 0"
        class="h-full flex flex-col items-center justify-center p-8 text-center text-[var(--label-secondary)] space-y-2"
      >
        <Inbox class="w-8 h-8 stroke-[1.4] opacity-45" />
        <p class="text-[13px] font-medium text-[var(--label-secondary)]">
          {{ store.streamUnreadOnly ? '无未读邮件' : '无邮件' }}
        </p>
        <p v-if="store.searchQuery || store.hasActiveScope" class="text-[11.5px] text-[var(--label-tertiary)]">
          当前筛选范围内没有匹配的信件
        </p>
      </div>

      <!-- Authentic macOS Sequoia Mail Cards -->
      <div v-else>
        <div
          v-for="(mail, idx) in store.displayedMails"
          :key="mail.id"
          class="relative"
        >
          <article
            @click="store.selectMail(mail)"
            :class="[
              'mx-2 my-0.5 pl-2.5 pr-3 py-2.5 rounded-[10px] cursor-pointer transition-colors duration-100 group relative flex items-start gap-2',
              isSelected(mail)
                ? 'bg-[var(--selection-bg)] text-[var(--selection-text)] shadow-[0_1px_3px_rgba(0,122,255,0.24)]'
                : 'hover:bg-[var(--fill-hover)] text-[var(--label-primary)]'
            ]"
          >
            <!-- Left Margin: Classic 9px #007AFF Unread Dot (+ Star Indicator) -->
            <div class="w-[12px] pt-[5px] flex flex-col items-center gap-1.5 flex-shrink-0">
              <span
                v-if="!mail.is_read"
                :class="[
                  'w-[9px] h-[9px] rounded-full transition-colors',
                  isSelected(mail) ? 'bg-white' : 'bg-[var(--apple-blue)]'
                ]"
              />
              <span v-else class="w-[9px] h-[9px]" />

              <button
                type="button"
                @click.stop="toggleStar(mail)"
                :class="[
                  'transition-opacity',
                  mail.is_starred
                    ? 'opacity-100'
                    : 'opacity-0 group-hover:opacity-80 mac-touch-show'
                ]"
                title="切换星标"
              >
                <Star
                  :class="[
                    'w-[11px] h-[11px]',
                    isSelected(mail)
                      ? 'text-white'
                      : mail.is_starred
                        ? 'text-[var(--apple-orange)]'
                        : 'text-[var(--label-secondary)]'
                  ]"
                  :fill="mail.is_starred ? 'currentColor' : 'none'"
                />
              </button>
            </div>

            <!-- Right Body Column -->
            <div class="flex-1 min-w-0">
              <!-- Row 1: Bold Sender Name + Right-Aligned Time & Subtle Chevron -->
              <div class="flex items-center justify-between gap-2">
                <span
                  :class="[
                    'text-[13.5px] leading-[1.28] tracking-[-0.012em] truncate',
                    isSelected(mail)
                      ? 'font-semibold text-white'
                      : !mail.is_read
                        ? 'font-semibold text-[var(--label-primary)]'
                        : 'font-semibold text-[var(--label-primary)]'
                  ]"
                  :title="mail.sender"
                >
                  {{ formatSenderName(mail.sender) }}
                </span>

                <span
                  :class="[
                    'flex items-center gap-0.5 text-[11.5px] tabular-nums flex-shrink-0',
                    isSelected(mail) ? 'text-[var(--selection-subtext)]' : 'text-[var(--label-secondary)]'
                  ]"
                >
                  <span>{{ formatTime(mail.created_at) }}</span>
                  <ChevronRight
                    :class="[
                      'w-3 h-3 stroke-[2]',
                      isSelected(mail) ? 'text-white/75' : 'text-[var(--label-tertiary)]'
                    ]"
                  />
                </span>
              </div>

              <!-- Row 2: Subject + Attachment / Quick OTP Chip -->
              <div class="flex items-center justify-between gap-1.5 mt-[2px]">
                <p
                  :class="[
                    'text-[12.5px] leading-[1.32] truncate',
                    isSelected(mail)
                      ? 'font-medium text-white/95'
                      : !mail.is_read
                        ? 'font-medium text-[var(--label-primary)]'
                        : 'font-normal text-[var(--label-primary)]'
                  ]"
                >
                  {{ mail.subject || '(无主题)' }}
                </p>

                <div class="flex items-center gap-1 flex-shrink-0">
                  <button
                    v-if="extractQuickOtp(mail)"
                    type="button"
                    @click.stop="copyQuickOtp(extractQuickOtp(mail))"
                    :class="[
                      'inline-flex items-center gap-0.5 px-1.5 py-[1px] rounded-[5px] text-[10.5px] font-mono font-medium transition',
                      isSelected(mail)
                        ? 'bg-white/20 text-white hover:bg-white/30'
                        : 'bg-[var(--fill-active-subtle)] text-[var(--apple-blue)] hover:opacity-85'
                    ]"
                    title="点击直接拷贝验证码"
                  >
                    <KeyRound class="w-2.5 h-2.5" />
                    <span>{{ extractQuickOtp(mail) }}</span>
                  </button>

                  <Paperclip
                    v-if="mail.has_attachments"
                    :class="[
                      'w-3 h-3',
                      isSelected(mail) ? 'text-white/80' : 'text-[var(--label-secondary)]'
                    ]"
                  />
                </div>
              </div>

              <!-- Row 3: Clean 2-Line Preview -->
              <p
                :class="[
                  'text-[12px] leading-[1.38] mt-[2px] line-clamp-2 break-words',
                  isSelected(mail) ? 'text-[var(--selection-muted)]' : 'text-[var(--label-secondary)]'
                ]"
              >
                {{ mail.preview || '无邮件正文预览' }}
              </p>

              <!-- Row 4: Unified Inbox Recipient Pill / Tags (when viewing multi-mailbox scope) -->
              <div
                v-if="(!store.selectedMailboxId && mail.mailbox_address) || (mail.tags && mail.tags.length)"
                class="flex items-center gap-1.5 mt-1.5 overflow-hidden"
              >
                <span
                  v-if="!store.selectedMailboxId && mail.mailbox_address"
                  :class="[
                    'inline-flex items-center px-1.5 py-[0.5px] rounded-[4px] text-[10.5px] font-mono truncate max-w-[190px]',
                    isSelected(mail)
                      ? 'bg-white/18 text-white/90'
                      : 'bg-[var(--fill-quaternary)] text-[var(--label-secondary)]'
                  ]"
                >
                  {{ mail.mailbox_address }}
                </span>

                <span
                  v-for="tag in mail.tags"
                  :key="tag"
                  :class="[
                    'px-1.5 py-[0.5px] rounded-[4px] text-[10px] truncate',
                    isSelected(mail)
                      ? 'bg-white/18 text-white/90'
                      : 'bg-[var(--fill-tertiary)] text-[var(--label-secondary)]'
                  ]"
                >
                  {{ tag }}
                </span>
              </div>
            </div>
          </article>

          <!-- Authentic Apple Inset Hairline Separator -->
          <div
            v-if="!shouldHideBottomDivider(idx)"
            class="ml-8 mr-3 mac-hairline-b pointer-events-none"
          />
        </div>
      </div>
    </div>
  </section>
</template>
