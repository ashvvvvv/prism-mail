<script setup>
import { useMailStore } from '../stores/mail'
import {
  Search, MailPlus, Globe, Sun, Moon, Terminal, Sparkles, Maximize2, Minimize2, Shield, LogOut
} from 'lucide-vue-next'

const store = useMailStore()
const chibiAvatarUrl = `${import.meta.env.BASE_URL}deepseek-chibi-hug.png`

const EDITIONS = [
  { id: 'hub', label: '总览', href: '/ui', active: false },
  { id: 'apple', label: 'Apple', href: '/apple', active: false },
  { id: 'editorial', label: '杂志', href: '/editorial', active: false },
  { id: 'spatial', label: '空间', href: '/spatial', active: false },
  { id: 'deepseek', label: '大肥鱼', href: '/deepseek', active: true }
]

const handleLogoClick = () => {
  store.summonMascot()
  store.pokeWhale()
}
</script>

<template>
  <header class="mx-3 mt-2.5 h-[54px] px-3.5 rounded-[20px] ds-hud flex items-center justify-between gap-3 select-none flex-shrink-0 z-20 relative overflow-hidden">
    <!-- Subtle Royal Gold & Ocean Top Accent Line -->
    <div class="absolute top-0 left-6 right-6 h-[2px] bg-gradient-to-r from-transparent via-[#4D6BFE]/50 to-transparent pointer-events-none" />

    <!-- Left: Chibi DeepSeek-tan Badge + Title + Gold-Trimmed R1-Maid OS Pill -->
    <div class="flex items-center gap-2.5 min-w-0">
      <button
        @click="handleLogoClick"
        class="group relative w-9 h-9 rounded-2xl bg-gradient-to-br from-[#4D6BFE]/18 to-[#38BDF8]/25 border border-[#4D6BFE]/30 flex items-center justify-center ds-spring hover:scale-105 flex-shrink-0 overflow-hidden shadow-sm"
        title="点击召唤 DeepSeek 鲸鱼娘记忆大厅"
      >
        <img
          :src="chibiAvatarUrl"
          alt="DeepSeek娘"
          class="w-8 h-8 object-contain transition-transform duration-300 group-hover:scale-110 select-none pointer-events-none"
          draggable="false"
        />
      </button>

      <div class="flex items-center gap-2 min-w-0">
        <span class="text-[14.5px] font-extrabold tracking-[-0.01em] text-[var(--text-primary)] truncate">
          DeepSeek Mail
          <span class="text-[#4D6BFE] dark:text-[#60A5FA] font-bold">· 大肥鱼信使</span>
        </span>

        <!-- Slanted Schale / Royal Maid Tactical Pill Badge -->
        <span class="hidden sm:inline-flex items-center px-2 py-0.5 rounded-md bg-gradient-to-r from-[#4D6BFE]/14 via-[#38BDF8]/16 to-[#D4AF6A]/18 border border-[#4D6BFE]/25 ds-slanted-badge flex-shrink-0">
          <span class="inline-flex items-center gap-1.5 text-[10.5px] font-mono font-bold text-[#4D6BFE] dark:text-[#7DD3FC] tracking-wide">
            <span class="text-[#D4AF6A] text-[10px]">★</span>
            <span>R1-Maid Lobby</span>
          </span>
        </span>
      </div>
    </div>

    <!-- Right: Quick ⌘K Search, External Mailbox, Domain Manager, Full Lobby Toggle, Day/Night CG Switch, Edition Switcher -->
    <div class="flex items-center gap-1.5 sm:gap-2 flex-shrink-0">
      <!-- Quick ⌘K Command Capsule -->
      <button
        @click="store.isCommandOpen = true"
        class="h-8 px-2.5 sm:px-3 rounded-full bg-[var(--bg-input)] hover:bg-[var(--bg-hover)] border border-[var(--border-hairline)] hover:border-[var(--border-strong)] flex items-center gap-2 text-[12px] text-[var(--text-muted)] hover:text-[var(--text-primary)] ds-spring"
        title="打开指令面板 (⌘K / Ctrl+K)"
      >
        <Search class="w-3.5 h-3.5 text-[#4D6BFE]" />
        <span class="hidden md:inline">搜邮箱 / 召唤指令</span>
        <kbd class="ds-kbd">⌘K</kbd>
      </button>

      <!-- + 外部邮箱 -->
      <button
        @click="store.openExternalModal()"
        class="h-8 px-2.5 sm:px-3 rounded-full bg-[var(--bg-subtle)] hover:bg-[var(--bg-hover)] border border-[var(--border-hairline)] text-[12px] font-semibold text-[var(--text-secondary)] hover:text-[var(--text-primary)] flex items-center gap-1.5 ds-spring"
        title="接入外部邮箱 (Gmail / QQ / 163 / Outlook / iCloud / IMAP)"
      >
        <MailPlus class="w-3.5 h-3.5 text-[#4D6BFE]" />
        <span class="hidden lg:inline">+ 外部邮箱</span>
      </button>

      <!-- 域名管理 -->
      <button
        @click="store.isDomainModalOpen = true"
        class="h-8 px-2.5 sm:px-3 rounded-full bg-[var(--bg-subtle)] hover:bg-[var(--bg-hover)] border border-[var(--border-hairline)] text-[12px] font-semibold text-[var(--text-secondary)] hover:text-[var(--text-primary)] flex items-center gap-1.5 ds-spring"
        title="绑定与管理自定义域名"
      >
        <Globe class="w-3.5 h-3.5 text-[#38BDF8]" />
        <span class="hidden lg:inline">域名管理</span>
      </button>

      <!-- 全景记忆大厅 1-Click Toggle -->
      <button
        @click="store.toggleLobbyFullScreen()"
        :class="[
          'h-8 px-2.5 sm:px-3 rounded-full border text-[12px] font-bold flex items-center gap-1.5 ds-spring',
          store.lobbyFullScreen
            ? 'bg-[#4D6BFE] text-white border-[#4D6BFE] shadow-sm shadow-[#4D6BFE]/35'
            : 'bg-[var(--bg-subtle)] hover:bg-[var(--bg-hover)] border-[var(--border-strong)] text-[var(--text-primary)]'
        ]"
        :title="store.lobbyFullScreen ? '退出全景大厅，返回三栏邮局 (ESC)' : '展开全屏记忆大厅欣赏看板娘 CG'"
      >
        <Minimize2 v-if="store.lobbyFullScreen" class="w-3.5 h-3.5" />
        <Maximize2 v-else class="w-3.5 h-3.5 text-[#4D6BFE] dark:text-[#60A5FA]" />
        <span class="hidden sm:inline">{{ store.lobbyFullScreen ? '返回信箱' : '全景大厅' }}</span>
      </button>

      <!-- 晴海 / 深海 1-Click Dual-CG Theme Switch -->
      <button
        @click="store.toggleTheme()"
        class="h-8 px-2.5 sm:px-3 rounded-full bg-gradient-to-r from-[#4D6BFE]/10 to-[#38BDF8]/12 hover:from-[#4D6BFE]/20 hover:to-[#38BDF8]/22 border border-[var(--border-strong)] text-[12px] font-bold text-[var(--text-primary)] flex items-center gap-1.5 ds-spring"
        :title="store.theme === 'ocean-light' ? '切换至「深海星夜荧光水母」夜间大厅' : '切换至「晴海阳光温室」昼间大厅'"
      >
        <Sun v-if="store.theme === 'ocean-light'" class="w-3.5 h-3.5 text-amber-500" />
        <Moon v-else class="w-3.5 h-3.5 text-[#38BDF8]" />
        <span>{{ store.theme === 'ocean-light' ? '晴海' : '深海' }}</span>
      </button>

      <!-- Edition Switcher Capsule -->
      <nav
        aria-label="主题版本切换"
        class="hidden xl:flex items-center p-0.5 rounded-full bg-[var(--bg-input)] border border-[var(--border-hairline)] text-[11.5px]"
      >
        <a
          v-for="ed in EDITIONS"
          :key="ed.id"
          :href="ed.href"
          :class="[
            'px-2.5 py-1 rounded-full transition-all flex items-center gap-1 font-semibold',
            ed.active
              ? 'bg-[#4D6BFE] text-white shadow-sm shadow-[#4D6BFE]/35'
              : 'text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-hover)]'
          ]"
        >
          <Sparkles v-if="ed.active" class="w-3 h-3" />
          <span>{{ ed.label }}</span>
        </a>
      </nav>

      <!-- Compact Edition Link for Narrower Viewports (< xl) -->
      <a
        href="/ui"
        class="xl:hidden h-8 px-2.5 rounded-full bg-[var(--bg-subtle)] hover:bg-[var(--bg-hover)] border border-[var(--border-hairline)] text-[11.5px] font-semibold text-[var(--text-secondary)] flex items-center gap-1 ds-spring"
        title="切换 UI 主题版本 (/ui /apple /editorial /spatial)"
      >
        <span>总览</span>
      </a>

      <!-- API Docs -->
      <a
        href="/docs"
        target="_blank"
        rel="noopener"
        class="hidden sm:flex w-8 h-8 rounded-full bg-[var(--bg-subtle)] hover:bg-[var(--bg-hover)] border border-[var(--border-hairline)] items-center justify-center text-[var(--text-muted)] hover:text-[var(--text-primary)] ds-spring"
        title="Agent API 接口文档 (/docs)"
      >
        <Terminal class="w-3.5 h-3.5" />
      </a>

      <!-- Account & API Key Security Center -->
      <a
        href="/account"
        class="w-8 h-8 rounded-full bg-[var(--bg-subtle)] hover:bg-[var(--bg-hover)] border border-[var(--border-hairline)] flex items-center justify-center text-[#4D6BFE] dark:text-[#7DD3FC] ds-spring"
        title="修改密码与 Agent API 密钥管理 (/account)"
      >
        <Shield class="w-3.5 h-3.5" />
      </a>

      <!-- Logout -->
      <a
        href="/logout"
        class="w-8 h-8 rounded-full bg-[var(--bg-subtle)] hover:bg-rose-500/15 border border-[var(--border-hairline)] hover:border-rose-400/40 flex items-center justify-center text-[var(--text-muted)] hover:text-[var(--accent-rose)] ds-spring"
        title="退出登录"
      >
        <LogOut class="w-3.5 h-3.5" />
      </a>
    </div>
  </header>
</template>
