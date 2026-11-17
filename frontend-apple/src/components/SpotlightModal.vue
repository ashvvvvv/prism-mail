<script setup>
import { ref, computed, watch, nextTick } from 'vue'
import { useMailStore } from '../stores/mail'
import {
  Search,
  Inbox,
  SquarePen,
  MailPlus,
  Globe,
  Sun,
  Moon,
  Monitor,
  RotateCw,
  Terminal,
  PanelLeft,
  CornerDownLeft,
  Layers,
  Settings,
  LogOut
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
    icon: SquarePen,
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
    run: () => store.resetAllFilters()
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
    id: 'cmd_sidebar',
    type: 'command',
    label: store.isSidebarCollapsed ? '展开左侧边栏' : '收起左侧边栏',
    hint: '',
    icon: PanelLeft,
    run: () => store.toggleSidebar()
  },
  {
    id: 'cmd_theme',
    type: 'command',
    label: store.theme === 'cupertino-light' ? '切换为深色外观' : '切换为浅色外观',
    hint: '',
    icon: store.theme === 'cupertino-light' ? Moon : Sun,
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
  const rawQ = query.value.trim()
  const q = rawQ.toLowerCase()

  const searchMailAction = rawQ
    ? [{
        id: 'cmd_search_mails',
        type: 'search',
        label: `在当前文件夹搜索邮件：「${rawQ}」`,
        icon: Search,
        run: () => {
          store.searchQuery = rawQ
          store.fetchMails()
        }
      }]
    : []

  const mbs = store.allMailboxes
    .filter(m =>
      !q ||
      (m.address && m.address.toLowerCase().includes(q)) ||
      (m.name && m.name.toLowerCase().includes(q)) ||
      (m.prefix && m.prefix.toLowerCase().includes(q))
    )
    .slice(0, q ? 10 : 5)
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

  return q
    ? [...searchMailAction, ...mbs, ...cmds]
    : [...cmds.slice(0, 5), ...mbs, ...cmds.slice(5)]
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
  <Transition name="mac-sheet-fade">
    <div
      v-if="store.isCommandOpen"
      class="fixed inset-0 mac-backdrop z-[60] flex items-start justify-center pt-[8vh] sm:pt-[13vh] px-3 sm:px-4 select-none"
      @click.self="close"
    >
      <div class="mac-spotlight rounded-[16px] w-full max-w-[540px] overflow-hidden">
        <!-- macOS Spotlight Search Input -->
        <div class="flex items-center px-3.5 sm:px-4 h-[50px] sm:h-[52px] mac-hairline-b gap-3">
          <Search class="w-[19px] h-[19px] text-[var(--label-secondary)] stroke-[2] flex-shrink-0" />
          <input
            ref="inputRef"
            v-model="query"
            @keydown.down.prevent="move(1)"
            @keydown.up.prevent="move(-1)"
            @keydown.enter.prevent="handleEnter"
            @keydown.esc.prevent="close"
            type="text"
            placeholder="搜索邮件、邮箱或执行命令..."
            class="flex-1 min-w-0 bg-transparent text-[15px] text-[var(--label-primary)] placeholder-[var(--label-secondary)] focus:outline-none"
          />
          <kbd class="mac-kbd flex-shrink-0">ESC</kbd>
        </div>

        <!-- Results List -->
        <div class="max-h-[60dvh] sm:max-h-[360px] overflow-y-auto p-2 space-y-[2px]">
          <div
            v-if="combinedItems.length === 0"
            class="py-8 text-center text-[13px] text-[var(--label-secondary)]"
          >
            未找到匹配的邮箱或命令
          </div>

          <button
            v-for="(item, idx) in combinedItems"
            :key="item.id"
            type="button"
            @mouseenter="activeIdx = idx"
            @click="executeItem(item)"
            :class="[
              'w-full h-[36px] px-3 rounded-[9px] flex items-center justify-between text-[13px] transition-colors text-left',
              activeIdx === idx
                ? 'bg-[var(--selection-bg)] text-white font-medium'
                : 'text-[var(--label-primary)] hover:bg-[var(--fill-hover)]'
            ]"
          >
            <div class="flex items-center gap-2.5 min-w-0">
              <component
                v-if="item.icon"
                :is="item.icon"
                :class="[
                  'w-4 h-4 flex-shrink-0',
                  activeIdx === idx ? 'text-white' : 'text-[var(--apple-blue)]'
                ]"
              />
              <span
                v-else
                :class="[
                  'font-mono text-[11.5px] flex-shrink-0 w-4 text-center',
                  activeIdx === idx ? 'text-white/80' : 'text-[var(--label-secondary)]'
                ]"
              >
                @
              </span>

              <span :class="[item.type === 'mailbox' ? 'font-mono text-[12.5px]' : '', 'truncate']">
                {{ item.label }}
              </span>

              <span
                v-if="item.sub"
                :class="[
                  'text-[11.5px] truncate',
                  activeIdx === idx ? 'text-white/80' : 'text-[var(--label-secondary)]'
                ]"
              >
                {{ item.sub }}
              </span>
            </div>

            <div class="flex items-center gap-2 flex-shrink-0 ml-2">
              <span
                v-if="item.vip"
                :class="[
                  'px-1.5 py-[1px] rounded-[5px] text-[10px] font-mono',
                  activeIdx === idx
                    ? 'bg-white/22 text-white'
                    : 'bg-[var(--fill-tertiary)] text-[var(--label-secondary)]'
                ]"
              >
                VIP
              </span>
              <span
                v-if="item.unread"
                :class="[
                  'px-1.5 py-[1px] rounded-[5px] text-[11px] font-mono tabular-nums',
                  activeIdx === idx
                    ? 'bg-white/22 text-white'
                    : 'bg-[var(--fill-tertiary)] text-[var(--label-secondary)]'
                ]"
              >
                {{ item.unread }}
              </span>
              <span
                v-else-if="item.hint"
                :class="[
                  'text-[11px] font-mono px-1.5 py-[1px] rounded-[5px]',
                  activeIdx === idx ? 'bg-white/20 text-white' : 'text-[var(--label-secondary)] bg-[var(--fill-quaternary)]'
                ]"
              >
                {{ item.hint }}
              </span>
              <CornerDownLeft
                v-else-if="activeIdx === idx"
                class="w-3.5 h-3.5 text-white/85"
              />
            </div>
          </button>
        </div>
      </div>
    </div>
  </Transition>
</template>
