<script setup>
import { ref, computed, watch, nextTick } from 'vue'
import { useMailStore } from '../stores/mail'
import {
  Search, Inbox, PenLine, MailPlus, Globe, Sun, Moon, Monitor,
  RotateCw, Terminal, ArrowRight, Layers, Settings, LogOut
} from 'lucide-vue-next'

const store = useMailStore()
const query = ref('')
const activeIdx = ref(0)
const inputRef = ref(null)

const quickCommands = computed(() => [
  {
    id: 'cmd_compose',
    type: 'command',
    label: '写邮件',
    hint: 'C',
    icon: PenLine,
    run: () => store.openCompose()
  },
  {
    id: 'cmd_external',
    type: 'command',
    label: '添加外部邮箱',
    hint: '',
    icon: MailPlus,
    run: () => store.openExternalModal()
  },
  {
    id: 'cmd_inbox_all',
    type: 'command',
    label: '查看全部收件箱',
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
    label: '同步收件箱',
    hint: '',
    icon: RotateCw,
    run: () => store.fetchMails(true)
  },
  {
    id: 'cmd_domain',
    type: 'command',
    label: '域名管理',
    hint: '',
    icon: Globe,
    run: () => { store.isDomainModalOpen = true }
  },
  {
    id: 'cmd_theme',
    type: 'command',
    label: store.theme === 'paper' ? '切换为深色外观' : '切换为浅色外观',
    hint: '',
    icon: store.theme === 'paper' ? Moon : Sun,
    run: () => store.toggleTheme()
  },
  {
    id: 'cmd_theme_system',
    type: 'command',
    label: '外观设为跟随系统',
    hint: '',
    icon: Monitor,
    run: () => store.setColorMode('system')
  },
  {
    id: 'cmd_settings',
    type: 'command',
    label: '打开设置',
    hint: '⌘,',
    icon: Settings,
    run: () => { store.isSettingsOpen = true }
  },
  {
    id: 'cmd_ui_hub',
    type: 'command',
    label: '切换界面主题',
    hint: '↗',
    icon: Layers,
    run: () => { window.location.href = '/ui' }
  },
  {
    id: 'cmd_docs',
    type: 'command',
    label: '接口文档',
    hint: '↗',
    icon: Terminal,
    run: () => window.open('/docs', '_blank', 'noopener')
  },
  {
    id: 'cmd_logout',
    type: 'command',
    label: '退出登录',
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

  return q ? [...mbs, ...cmds] : [...cmds.slice(0, 5), ...mbs, ...cmds.slice(5)]
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
  <Transition name="folio-fade">
    <div
      v-if="store.isCommandOpen"
      class="fixed inset-0 ed-backdrop z-50 flex items-start justify-center pt-[8vh] sm:pt-[12vh] px-3 sm:px-4 select-none"
      @click.self="close"
    >
      <div class="ed-folio-modal w-full max-w-lg overflow-hidden">
        <!-- Top Rubric Strip -->
        <div class="px-4 py-1.5 bg-[var(--bg-linen)] border-b border-[var(--rule-faint)] flex items-center justify-between">
          <span class="ed-rubric text-[var(--accent-vermilion)]">快捷命令</span>
          <kbd class="ed-kbd">ESC</kbd>
        </div>

        <!-- Search Input -->
        <div class="flex items-center px-3.5 sm:px-4 h-11 border-b border-[var(--rule-medium)] bg-[var(--bg-salon)] gap-3">
          <Search class="w-4 h-4 text-[var(--ink-muted)] flex-shrink-0" />
          <input
            ref="inputRef"
            v-model="query"
            @keydown.down.prevent="move(1)"
            @keydown.up.prevent="move(-1)"
            @keydown.enter.prevent="handleEnter"
            @keydown.esc.prevent="close"
            type="text"
            placeholder="输入邮箱地址或搜索命令..."
            class="flex-1 min-w-0 bg-transparent text-[13px] text-[var(--ink-primary)] placeholder-[var(--ink-faint)] focus:outline-none"
          />
        </div>

        <!-- Index Entries -->
        <div class="max-h-[60dvh] sm:max-h-[340px] overflow-y-auto divide-y divide-[var(--rule-faint)] bg-[var(--bg-ledger)]">
          <div
            v-if="combinedItems.length === 0"
            class="py-8 text-center text-[12.5px] font-serif text-[var(--ink-muted)]"
          >
            未找到匹配的邮箱或命令
          </div>

          <button
            v-for="(item, idx) in combinedItems"
            :key="item.id"
            @mouseenter="activeIdx = idx"
            @click="executeItem(item)"
            :class="[
              'w-full h-9 px-4 flex items-center justify-between text-[12.5px] transition text-left border-l-[3px]',
              activeIdx === idx
                ? 'border-[var(--accent-vermilion)] bg-[var(--bg-active)] text-[var(--ink-primary)] font-medium'
                : 'border-transparent text-[var(--ink-secondary)] hover:bg-[var(--bg-hover)]'
            ]"
          >
            <div class="flex items-center gap-2.5 min-w-0">
              <component
                v-if="item.type === 'command'"
                :is="item.icon"
                class="w-3.5 h-3.5 text-[var(--ink-muted)] flex-shrink-0"
              />
              <span
                v-else
                class="font-mono text-[11px] text-[var(--ink-muted)] flex-shrink-0 w-3.5 text-center"
              >
                @
              </span>

              <span :class="[item.type === 'mailbox' ? 'font-mono text-[12px]' : '', 'truncate']">
                {{ item.label }}
              </span>
              <span v-if="item.sub" class="text-[11px] text-[var(--ink-muted)] truncate">
                · {{ item.sub }}
              </span>
            </div>

            <div class="flex items-center gap-2 flex-shrink-0 ml-2">
              <span
                v-if="item.vip"
                class="px-1.5 py-[1px] border border-[var(--rule-medium)] text-[10px] font-mono text-[var(--ink-muted)]"
              >
                重点
              </span>
              <span
                v-if="item.unread"
                class="px-1.5 py-[1px] border border-[var(--accent-vermilion-border)] bg-[var(--accent-vermilion-soft)] text-[10.5px] font-mono tabular-nums text-[var(--accent-vermilion)]"
              >
                {{ item.unread }}
              </span>
              <kbd v-else-if="item.hint" class="ed-kbd">{{ item.hint }}</kbd>
              <ArrowRight
                v-else-if="activeIdx === idx"
                class="w-3.5 h-3.5 text-[var(--accent-vermilion)]"
              />
            </div>
          </button>
        </div>
      </div>
    </div>
  </Transition>
</template>
