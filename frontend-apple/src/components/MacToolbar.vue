<script setup>
import { ref, computed, watch } from 'vue'
import { useMailStore } from '../stores/mail'
import {
  PanelLeft,
  ChevronLeft,
  SquarePen,
  Reply,
  Star,
  Trash2,
  MailPlus,
  Globe,
  Search,
  X,
  RotateCw,
  Sun,
  Moon,
  Settings
} from 'lucide-vue-next'

const emit = defineEmits(['reply'])

const store = useMailStore()
const searchInputRef = ref(null)
const localQuery = ref(store.searchQuery || '')

watch(
  () => store.searchQuery,
  (val) => {
    if (val !== localQuery.value) {
      localQuery.value = val || ''
    }
  }
)

const folderTitle = computed(() => {
  const map = {
    inbox: '收件箱',
    starred: '星标邮件',
    sent: '已发送',
    drafts: '草稿箱',
    quarantine: '隔离区',
    trash: '废纸篓'
  }
  return map[store.selectedFolder] || store.selectedFolder
})

const unreadInStream = computed(() => {
  return store.mails.filter(m => !m.is_read).length
})

const subtitleText = computed(() => {
  const count = store.displayedMails.length
  if (store.scopeLabel) {
    return `${store.scopeLabel} · ${count} 封邮件`
  }
  if (unreadInStream.value > 0 && !store.streamUnreadOnly) {
    return `${folderTitle.value} · ${count} 封邮件（${unreadInStream.value} 封未读）`
  }
  return `${folderTitle.value} · ${count} 封邮件`
})

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

const handleTrafficReset = () => {
  localQuery.value = ''
  store.resetAllFilters()
}

const clearScopeFilter = () => {
  store.selectScope({
    domainId: null,
    mailboxId: null,
    labelId: null,
    smartFilter: null,
    groupId: null,
    role: null,
    tag: null
  })
}

const activeMail = computed(() => store.selectedMailDetail || store.selectedMail)

const handleToggleStar = () => {
  if (!activeMail.value) return
  store.updateMailStatus(activeMail.value.id, {
    is_starred: !activeMail.value.is_starred
  })
}

const handleTrash = () => {
  if (!activeMail.value) return
  store.deleteMail(activeMail.value.id)
}

const handleReplyClick = () => {
  if (!store.selectedMailDetail) return
  emit('reply')
}

const handleMobileBack = () => {
  if (window.history.state?.prismReader) {
    window.history.back()
  } else {
    store.closeMail()
  }
}

defineExpose({
  focusSearch: () => searchInputRef.value?.focus()
})
</script>

<template>
  <header class="mac-toolbar-vibrancy h-[52px] px-3 sm:px-3.5 flex items-center justify-between gap-2 sm:gap-3 flex-shrink-0 z-30 select-none">
    <!-- Left: Interactive macOS Traffic Lights + Sidebar & Sync Controls -->
    <div class="flex items-center gap-2 sm:gap-3 min-w-0 flex-1">
      <!-- Authentic macOS 3 Traffic Light Dots (Desktop) -->
      <div class="hidden lg:flex items-center gap-[8px] pl-1 pr-0.5 group/lights flex-shrink-0">
        <button
          type="button"
          @click="handleTrafficReset"
          class="w-[12px] h-[12px] rounded-full bg-[#FF5F57] border border-black/10 flex items-center justify-center shadow-[inset_0_0.5px_0_rgba(255,255,255,0.35)] active:brightness-90 transition"
          title="重置筛选与搜索"
        >
          <span class="text-[8.5px] font-bold leading-none text-[#4D0000] opacity-0 group-hover/lights:opacity-100 transition-opacity">×</span>
        </button>

        <button
          type="button"
          @click="store.toggleSidebar()"
          class="w-[12px] h-[12px] rounded-full bg-[#FEBC2E] border border-black/10 flex items-center justify-center shadow-[inset_0_0.5px_0_rgba(255,255,255,0.35)] active:brightness-90 transition"
          title="收起 / 展开边栏"
        >
          <span class="text-[9px] font-bold leading-none text-[#5C3B00] opacity-0 group-hover/lights:opacity-100 transition-opacity">−</span>
        </button>

        <button
          type="button"
          @click="store.toggleTheme()"
          class="w-[12px] h-[12px] rounded-full bg-[#28C840] border border-black/10 flex items-center justify-center shadow-[inset_0_0.5px_0_rgba(255,255,255,0.35)] active:brightness-90 transition"
          title="切换浅色 / 深色外观"
        >
          <span class="text-[7.5px] font-bold leading-none text-[#0B4613] opacity-0 group-hover/lights:opacity-100 transition-opacity">⤢</span>
        </button>
      </div>

      <!-- Mobile Reader Back Button (< 收件箱) -->
      <button
        v-if="store.selectedMail"
        type="button"
        @click="handleMobileBack"
        class="lg:hidden h-[30px] px-1.5 -ml-1 rounded-[8px] flex items-center gap-0.5 text-[var(--apple-blue)] font-medium text-[14px] active:opacity-70 transition flex-shrink-0"
      >
        <ChevronLeft class="w-[19px] h-[19px] stroke-[2.2]" />
        <span class="truncate max-w-[110px]">{{ folderTitle }}</span>
      </button>

      <!-- Sidebar Toggle & Sync (Always on Desktop, on Mobile only when in Mail List) -->
      <div :class="['items-center gap-0.5 flex-shrink-0', store.selectedMail ? 'hidden lg:flex' : 'flex']">
        <button
          type="button"
          @click="store.toggleSidebar()"
          :class="[
            'h-[30px] w-[32px] lg:h-[28px] lg:w-[30px] rounded-[7px] flex items-center justify-center mac-toolbar-icon-btn',
            store.isSidebarCollapsed ? 'lg:text-[var(--apple-blue)] lg:bg-[var(--fill-active-subtle)] text-[var(--label-secondary)]' : 'text-[var(--label-secondary)] hover:text-[var(--label-primary)]'
          ]"
          title="切换边栏显示"
        >
          <PanelLeft class="w-[17px] h-[17px] lg:w-[16px] lg:h-[16px] stroke-[1.75]" />
        </button>

        <button
          type="button"
          @click="store.fetchMails(true)"
          class="h-[30px] w-[30px] lg:h-[28px] lg:w-[28px] rounded-[7px] flex items-center justify-center mac-toolbar-icon-btn text-[var(--label-secondary)] hover:text-[var(--label-primary)]"
          title="获取新邮件（立即同步）"
        >
          <RotateCw :class="['w-[15px] h-[15px] lg:w-[14.5px] lg:h-[14.5px] stroke-[1.75]', { 'animate-spin text-[var(--apple-blue)]': store.isLoadingMails }]" />
        </button>
      </div>

      <div class="h-4 w-[1px] bg-[var(--separator)] hidden sm:block flex-shrink-0" />

      <!-- Center-Left: Folder Title & Subtitle + macOS Segmented Control -->
      <div :class="['items-center gap-3 min-w-0', store.selectedMail ? 'hidden lg:flex' : 'flex']">
        <div class="min-w-0 leading-tight">
          <div class="flex items-center gap-1.5 min-w-0">
            <h1 class="text-[14px] lg:text-[13.5px] font-semibold tracking-[-0.015em] text-[var(--label-primary)] truncate">
              {{ folderTitle }}
            </h1>
            <button
              v-if="store.scopeLabel"
              type="button"
              @click="clearScopeFilter"
              class="inline-flex items-center gap-1 px-1.5 py-[1px] rounded-md bg-[var(--fill-active-subtle)] text-[var(--apple-blue)] text-[10.5px] font-medium max-w-[110px] sm:max-w-[140px] truncate hover:opacity-85 transition flex-shrink-0"
              title="点击清除邮箱/分组筛选"
            >
              <span class="truncate">{{ store.scopeLabel }}</span>
              <X class="w-2.5 h-2.5 flex-shrink-0" />
            </button>
          </div>
          <p class="text-[11px] text-[var(--label-secondary)] tabular-nums truncate">
            {{ subtitleText }}
          </p>
        </div>

        <!-- Authentic macOS Segmented Control (全部 | 未读) -->
        <div class="mac-segmented hidden md:inline-flex h-[26px] w-[108px] flex-shrink-0">
          <!-- Sliding White Elevated Pill Thumb -->
          <div
            class="mac-segmented-thumb absolute top-[2px] bottom-[2px] left-[2px] w-[51px] pointer-events-none"
            :style="{
              transform: store.streamUnreadOnly ? 'translateX(53px)' : 'translateX(0px)'
            }"
          />
          <button
            type="button"
            @click="store.streamUnreadOnly = false"
            :class="[
              'relative z-10 flex-1 h-full text-[11.5px] rounded-[6px] transition-colors',
              !store.streamUnreadOnly
                ? 'font-medium text-[var(--label-primary)]'
                : 'text-[var(--label-secondary)] hover:text-[var(--label-primary)]'
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
                : 'text-[var(--label-secondary)] hover:text-[var(--label-primary)]'
            ]"
          >
            未读
          </button>
        </div>
      </div>
    </div>

    <!-- Right: Grouped macOS Toolbar Buttons + Spotlight Search + Edition Switcher -->
    <div class="flex items-center gap-1.5 sm:gap-2 flex-shrink-0">
      <!-- Compose Button Capsule -->
      <div class="mac-toolbar-group flex items-center p-[1px]">
        <button
          type="button"
          @click="store.openCompose()"
          class="h-[26px] px-2.5 rounded-[7px] mac-toolbar-icon-btn flex items-center gap-1.5 text-[12px] font-medium"
          title="撰写新邮件 (快捷键 C)"
        >
          <SquarePen class="w-[14.5px] h-[14.5px] stroke-[1.75] text-[var(--apple-blue)]" />
          <span class="hidden xl:inline">写邮件</span>
        </button>
      </div>

      <!-- Mail Action Group (Reply | Star | Trash) -->
      <div :class="['mac-toolbar-group items-center p-[1px] divide-x divide-[var(--separator-subtle)]', store.selectedMail ? 'flex' : 'hidden md:flex']">
        <button
          type="button"
          @click="handleReplyClick"
          :disabled="!store.selectedMailDetail"
          class="h-[26px] w-[31px] rounded-l-[7px] mac-toolbar-icon-btn flex items-center justify-center disabled:opacity-35"
          title="回复此邮件 (快捷键 R)"
        >
          <Reply class="w-[14.5px] h-[14.5px] stroke-[1.75]" />
        </button>
        <button
          type="button"
          @click="handleToggleStar"
          :disabled="!activeMail"
          :class="[
            'h-[26px] w-[31px] mac-toolbar-icon-btn flex items-center justify-center disabled:opacity-35',
            activeMail?.is_starred ? 'text-[var(--apple-orange)]' : ''
          ]"
          title="标记星标"
        >
          <Star class="w-[14.5px] h-[14.5px] stroke-[1.75]" :fill="activeMail?.is_starred ? 'currentColor' : 'none'" />
        </button>
        <button
          type="button"
          @click="handleTrash"
          :disabled="!activeMail"
          class="h-[26px] w-[31px] rounded-r-[7px] mac-toolbar-icon-btn flex items-center justify-center hover:text-[var(--apple-red)] disabled:opacity-35"
          title="移至废纸篓"
        >
          <Trash2 class="w-[14.5px] h-[14.5px] stroke-[1.75]" />
        </button>
      </div>

      <!-- Integration & Appearance Group (External Mail | Domains | Light/Dark) -->
      <div class="mac-toolbar-group hidden sm:flex items-center p-[1px] divide-x divide-[var(--separator-subtle)]">
        <button
          type="button"
          @click="store.openExternalModal()"
          class="h-[26px] w-[31px] rounded-l-[7px] mac-toolbar-icon-btn flex items-center justify-center"
          title="添加外部邮箱"
        >
          <MailPlus class="w-[14.5px] h-[14.5px] stroke-[1.75]" />
        </button>
        <button
          type="button"
          @click="store.isDomainModalOpen = true"
          class="h-[26px] w-[31px] mac-toolbar-icon-btn flex items-center justify-center"
          title="域名管理"
        >
          <Globe class="w-[14.5px] h-[14.5px] stroke-[1.75]" />
        </button>
        <button
          type="button"
          @click="store.toggleTheme()"
          class="h-[26px] w-[31px] rounded-r-[7px] mac-toolbar-icon-btn flex items-center justify-center"
          :title="store.theme === 'cupertino-light' ? '切换为深色外观' : '切换为浅色外观'"
        >
          <Moon v-if="store.theme === 'cupertino-light'" class="w-[14px] h-[14px] stroke-[1.75]" />
          <Sun v-else class="w-[14px] h-[14px] stroke-[1.75] text-[var(--apple-amber)]" />
        </button>
      </div>

      <!-- macOS Spotlight Search Field (Desktop) -->
      <div class="hidden lg:flex relative items-center w-[210px] h-[28px] rounded-[8px] bg-[var(--bg-input)] border border-[var(--separator-subtle)] focus-within:border-[var(--apple-blue)] focus-within:ring-2 focus-within:ring-[var(--apple-blue)]/20 transition">
        <Search class="w-[13.5px] h-[13.5px] text-[var(--label-secondary)] ml-2.5 flex-shrink-0" />
        <input
          ref="searchInputRef"
          v-model="localQuery"
          @input="handleSearchInput"
          type="text"
          placeholder="搜索邮件"
          class="w-full bg-transparent px-1.5 text-[12px] text-[var(--label-primary)] placeholder-[var(--label-secondary)] focus:outline-none"
        />
        <button
          v-if="localQuery"
          type="button"
          @click="clearSearch"
          class="mr-1.5 text-[var(--label-secondary)] hover:text-[var(--label-primary)]"
          title="清除搜索"
        >
          <X class="w-3.5 h-3.5" />
        </button>
        <button
          v-else
          type="button"
          @click="store.isCommandOpen = true"
          class="mr-1.5 px-1.5 py-[1px] rounded-[5px] bg-[var(--fill-tertiary)] hover:bg-[var(--fill-secondary)] text-[10px] font-mono text-[var(--label-secondary)] transition flex-shrink-0"
          title="快捷命令 (⌘K)"
        >
          ⌘K
        </button>
      </div>

      <!-- Compact Spotlight Search Button (Mobile / Tablet) -->
      <div class="mac-toolbar-group flex lg:hidden items-center p-[1px] flex-shrink-0">
        <button
          type="button"
          @click="store.isCommandOpen = true"
          class="h-[26px] w-[31px] rounded-[7px] mac-toolbar-icon-btn flex items-center justify-center"
          title="搜索与命令 (⌘K)"
        >
          <Search class="w-[14.5px] h-[14.5px] stroke-[1.75]" />
        </button>
      </div>

      <!-- macOS System Settings Capsule -->
      <div class="mac-toolbar-group flex items-center p-[1px] flex-shrink-0">
        <button
          type="button"
          @click="store.isSettingsOpen = true"
          class="h-[26px] w-[31px] rounded-[7px] mac-toolbar-icon-btn flex items-center justify-center"
          title="设置 (⌘,)"
        >
          <Settings class="w-[14.5px] h-[14.5px] stroke-[1.75]" />
        </button>
      </div>
    </div>
  </header>
</template>
