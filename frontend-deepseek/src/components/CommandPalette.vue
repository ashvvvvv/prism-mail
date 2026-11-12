<script setup>
import { ref, computed, watch, nextTick } from 'vue'
import { useMailStore } from '../stores/mail'
import {
  Search, Inbox, PenLine, MailPlus, Globe, Sun, Moon,
  RotateCw, Terminal, ArrowRight, Sparkles, LayoutGrid, Shield, LogOut
} from 'lucide-vue-next'

const store = useMailStore()
const query = ref('')
const activeIdx = ref(0)
const inputRef = ref(null)

const quickCommands = computed(() => [
  {
    id: 'cmd_compose',
    type: 'command',
    label: '撰写新信件',
    hint: 'C',
    icon: PenLine,
    run: () => store.openCompose()
  },
  {
    id: 'cmd_mascot',
    type: 'command',
    label: '🐋 召唤 DeepSeek 鲸鱼娘记忆大厅',
    hint: '',
    icon: Sparkles,
    run: () => store.summonMascot()
  },
  {
    id: 'cmd_panoramic_lobby',
    type: 'command',
    label: store.lobbyFullScreen ? '退出全景记忆大厅，返回三栏邮局' : '🖼️ 展开全屏沉浸式记忆大厅 (支持晴海/深海双CG)',
    hint: '',
    icon: Sparkles,
    run: () => store.toggleLobbyFullScreen()
  },
  {
    id: 'cmd_external',
    type: 'command',
    label: '接入外部邮箱 (Gmail / QQ / 163 / Outlook / iCloud / IMAP)',
    hint: '',
    icon: MailPlus,
    run: () => store.openExternalModal()
  },
  {
    id: 'cmd_inbox_all',
    type: 'command',
    label: '查看全局收件箱',
    hint: '',
    icon: Inbox,
    run: () => {
      store.selectedFolder = 'inbox'
      store.selectScope(null)
    }
  },
  {
    id: 'cmd_sync',
    type: 'command',
    label: '🫧 立即潜航捞信（同步全部收件箱）',
    hint: '',
    icon: RotateCw,
    run: () => store.fetchMails(true)
  },
  {
    id: 'cmd_domain',
    type: 'command',
    label: '绑定自定义域名与查看 DNS',
    hint: '',
    icon: Globe,
    run: () => { store.isDomainModalOpen = true }
  },
  {
    id: 'cmd_theme',
    type: 'command',
    label: store.theme === 'ocean-light' ? '切换至「深海摸鱼夜模式」🌙' : '切换至「晴海女仆昼间模式」☀️',
    hint: '',
    icon: store.theme === 'ocean-light' ? Moon : Sun,
    run: () => store.toggleTheme()
  },
  {
    id: 'cmd_ui_hub',
    type: 'command',
    label: '前往 UI 主题总览大厅 (/ui)',
    hint: '↗',
    icon: LayoutGrid,
    run: () => { window.location.href = '/ui' }
  },
  {
    id: 'cmd_docs',
    type: 'command',
    label: '打开 Agent API 接口文档 (/docs)',
    hint: '↗',
    icon: Terminal,
    run: () => window.open('/docs', '_blank', 'noopener')
  },
  {
    id: 'cmd_account',
    type: 'command',
    label: '🔒 修改管理员密码与查看 Agent API Key (/account)',
    hint: '↗',
    icon: Shield,
    run: () => { window.location.href = '/account' }
  },
  {
    id: 'cmd_logout',
    type: 'command',
    label: '退出当前管理员登录 (/logout)',
    hint: '',
    icon: LogOut,
    run: () => { window.location.href = '/logout' }
  }
])

const combinedItems = computed(() => {
  const q = query.value.trim().toLowerCase()
  const mbs = store.allMailboxes
    .filter(m =>
      !q ||
      (m.address && m.address.toLowerCase().includes(q)) ||
      (m.name && m.name.toLowerCase().includes(q)) ||
      (m.prefix && m.prefix.toLowerCase().includes(q))
    )
    .slice(0, q ? 12 : 6)
    .map(m => ({
      id: `mb_${m.id}`,
      type: 'mailbox',
      label: m.address,
      sub: m.name && m.name !== m.prefix && m.name !== m.address ? m.name : '',
      unread: m.unread_count || 0,
      vip: m.is_vip,
      run: () => {
        store.selectedFolder = 'inbox'
        store.selectScope({
          domainId: m.domain_id || null,
          mailboxId: m.id
        })
      }
    }))

  const cmds = quickCommands.value.filter(c =>
    !q || c.label.toLowerCase().includes(q)
  )

  return q ? [...mbs, ...cmds] : [...cmds.slice(0, 6), ...mbs, ...cmds.slice(6)]
})

watch(
  () => store.isCommandOpen,
  async (open) => {
    if (open) {
      query.value = ''
      activeIdx.value = 0
      await nextTick()
      inputRef.value?.focus()
    }
  }
)

watch(query, () => {
  activeIdx.value = 0
})

const close = () => {
  store.isCommandOpen = false
}

const move = (delta) => {
  const total = combinedItems.value.length
  if (!total) return
  activeIdx.value = (activeIdx.value + delta + total) % total
}

const executeItem = (item) => {
  if (!item) return
  close()
  item.run()
}

const handleEnter = () => {
  const target = combinedItems.value[activeIdx.value]
  if (target) executeItem(target)
}
</script>

<template>
  <Transition name="fade-scale">
    <div
      v-if="store.isCommandOpen"
      class="fixed inset-0 ds-backdrop z-50 flex items-start justify-center pt-[13vh] px-4 select-none"
      @click.self="close"
    >
      <div class="ds-modal w-full max-w-lg overflow-hidden">
        <!-- Input Bar -->
        <div class="flex items-center px-4 h-[52px] border-b border-[var(--border-hairline)] gap-3 bg-gradient-to-r from-[#4D6BFE]/[0.06] to-transparent">
          <Search class="w-4 h-4 text-[#4D6BFE] flex-shrink-0" />
          <input
            ref="inputRef"
            v-model="query"
            @keydown.down.prevent="move(1)"
            @keydown.up.prevent="move(-1)"
            @keydown.enter.prevent="handleEnter"
            @keydown.esc.prevent="close"
            type="text"
            placeholder="输入信箱地址直达，或召唤大肥鱼快捷指令..."
            class="flex-1 bg-transparent text-[13.5px] font-semibold text-[var(--text-primary)] placeholder-[var(--text-muted)] focus:outline-none"
          />
          <kbd class="ds-kbd">ESC</kbd>
        </div>

        <!-- Results -->
        <div class="max-h-[350px] overflow-y-auto p-2 space-y-0.5">
          <div
            v-if="combinedItems.length === 0"
            class="py-8 text-center text-[12.5px] text-[var(--text-muted)]"
          >
            🫧 大肥鱼翻遍了海底，没有找到匹配的指令哦~
          </div>

          <button
            v-for="(item, idx) in combinedItems"
            :key="item.id"
            @mouseenter="activeIdx = idx"
            @click="executeItem(item)"
            :class="[
              'w-full h-[38px] px-3 rounded-xl flex items-center justify-between text-[12.5px] transition text-left',
              activeIdx === idx
                ? 'bg-[var(--bg-active)] text-[#4D6BFE] dark:text-[#7DD3FC] font-bold'
                : 'text-[var(--text-secondary)] hover:bg-[var(--bg-hover)]'
            ]"
          >
            <div class="flex items-center gap-2.5 min-w-0">
              <component
                v-if="item.type === 'command'"
                :is="item.icon"
                :class="[
                  'w-4 h-4 flex-shrink-0',
                  activeIdx === idx ? 'text-[#4D6BFE] dark:text-[#38BDF8]' : 'text-[var(--text-muted)]'
                ]"
              />
              <span
                v-else
                :class="[
                  'w-2 h-2 rounded-full flex-shrink-0 ml-1 mr-0.5',
                  item.unread ? 'bg-[#38BDF8]' : 'bg-[var(--border-strong)]'
                ]"
              />

              <span :class="[item.type === 'mailbox' ? 'font-mono text-[12px]' : '', 'truncate']">
                {{ item.label }}
              </span>
              <Sparkles v-if="item.vip" class="w-3 h-3 text-[var(--accent-amber)] flex-shrink-0" />
              <span v-if="item.sub" class="text-[11px] text-[var(--text-muted)] truncate">
                {{ item.sub }}
              </span>
            </div>

            <div class="flex items-center gap-2 flex-shrink-0 ml-2">
              <span
                v-if="item.unread"
                class="px-2 py-0.5 rounded-full bg-[#4D6BFE] text-white text-[10.5px] font-mono font-bold tabular-nums"
              >
                {{ item.unread }}
              </span>
              <kbd v-else-if="item.hint" class="ds-kbd">{{ item.hint }}</kbd>
              <ArrowRight
                v-else-if="activeIdx === idx"
                class="w-3.5 h-3.5 text-[#4D6BFE]"
              />
            </div>
          </button>
        </div>
      </div>
    </div>
  </Transition>
</template>
