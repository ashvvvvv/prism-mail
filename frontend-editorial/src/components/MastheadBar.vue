<script setup>
import { computed } from 'vue'
import { useMailStore } from '../stores/mail'
import PrismWordmark from './PrismWordmark.vue'
import {
  Search, MailPlus, Globe, PenLine, Sun, Moon, Settings, Menu
} from 'lucide-vue-next'

const store = useMailStore()

const formattedEditionDate = computed(() => {
  const now = new Date()
  const weekdays = ['星期日', '星期一', '星期二', '星期三', '星期四', '星期五', '星期六']
  const y = now.getFullYear()
  const m = String(now.getMonth() + 1).padStart(2, '0')
  const d = String(now.getDate()).padStart(2, '0')
  return `${y}.${m}.${d} · ${weekdays[now.getDay()]}`
})

const inboxTotal = computed(() => {
  return store.folderCounts?.inbox ?? store.totalMails ?? 0
})
</script>

<template>
  <header
    class="h-11 w-full flex-shrink-0 bg-[var(--bg-linen)] border-b border-[var(--rule-medium)] px-2.5 sm:px-3.5 flex items-center justify-between gap-2 sm:gap-3 select-none z-30"
  >
    <!-- Left: Masthead & Date / Inbox Count -->
    <div class="flex items-center gap-2 sm:gap-3 min-w-0">
      <button
        type="button"
        @click="store.isMobileNavOpen = true"
        class="lg:hidden h-7 w-7 ed-btn-outline flex items-center justify-center text-[var(--ink-secondary)] flex-shrink-0"
        title="打开导航目录"
      >
        <Menu class="w-3.5 h-3.5" />
      </button>

      <div class="flex items-center flex-shrink-0 py-0.5">
        <PrismWordmark class="h-[18px] sm:h-[20px] w-auto text-[var(--ink-primary)]" />
      </div>

      <span class="hidden lg:block h-3.5 w-[1px] bg-[var(--rule-medium)]" />

      <div class="hidden lg:flex items-center gap-2.5 text-[11px] font-mono text-[var(--ink-muted)] truncate">
        <span>{{ formattedEditionDate }}</span>
        <span class="text-[var(--ink-faint)]">/</span>
        <span class="tabular-nums text-[var(--ink-secondary)]">
          收件箱 <strong class="font-semibold text-[var(--ink-primary)]">{{ inboxTotal }}</strong> 封
        </span>
      </div>
    </div>

    <!-- Right: Actions -->
    <div class="flex items-center gap-1.5 sm:gap-2 flex-shrink-0">
      <button
        @click="store.isCommandOpen = true"
        class="h-7 px-2 sm:px-2.5 ed-btn-outline flex items-center gap-1.5 sm:gap-2 text-[11.5px] text-[var(--ink-secondary)]"
        title="搜索与命令 (⌘K)"
      >
        <Search class="w-3 h-3 text-[var(--ink-muted)]" />
        <span class="hidden md:inline">搜索</span>
        <kbd class="hidden md:inline font-mono text-[10px] text-[var(--ink-muted)] border-l border-[var(--rule-faint)] pl-1.5">⌘K</kbd>
      </button>

      <button
        @click="store.openExternalModal()"
        class="hidden sm:flex h-7 px-2.5 ed-btn-outline items-center gap-1.5 text-[11.5px] text-[var(--ink-secondary)]"
        title="添加外部邮箱"
      >
        <MailPlus class="w-3 h-3 text-[var(--accent-vermilion)]" />
        <span class="hidden sm:inline">添加邮箱</span>
      </button>

      <button
        @click="store.isDomainModalOpen = true"
        class="hidden sm:flex h-7 px-2.5 ed-btn-outline items-center gap-1.5 text-[11.5px] text-[var(--ink-secondary)]"
        title="域名管理"
      >
        <Globe class="w-3 h-3 text-[var(--ink-muted)]" />
        <span class="hidden sm:inline">域名管理</span>
      </button>

      <button
        @click="store.toggleTheme()"
        class="h-7 px-2 sm:px-2.5 ed-btn-outline flex items-center gap-1.5 text-[11.5px] font-medium"
        :title="store.theme === 'paper' ? '切换为深色外观' : '切换为浅色外观'"
      >
        <Moon v-if="store.theme === 'paper'" class="w-3 h-3 text-[var(--ink-secondary)]" />
        <Sun v-else class="w-3 h-3 text-[var(--accent-ochre)]" />
        <span class="hidden sm:inline">{{ store.theme === 'paper' ? '浅色' : '深色' }}</span>
      </button>

      <button
        @click="store.isSettingsOpen = true"
        class="h-7 px-2 sm:px-2.5 ed-btn-outline flex items-center gap-1.5 text-[11.5px] text-[var(--ink-secondary)]"
        title="设置 (⌘,)"
      >
        <Settings class="w-3 h-3 text-[var(--ink-muted)]" />
        <span class="hidden sm:inline">设置</span>
      </button>

      <button
        @click="store.openCompose()"
        class="h-7 px-2.5 sm:px-3 ed-btn-ink text-[11.5px] font-medium flex items-center gap-1.5"
        title="写邮件 (C)"
      >
        <PenLine class="w-3 h-3 stroke-[2]" />
        <span>写邮件</span>
      </button>
    </div>
  </header>
</template>
