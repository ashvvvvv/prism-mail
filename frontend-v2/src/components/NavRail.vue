<script setup>
import { ref, computed } from 'vue'
import { useMailStore } from '../stores/mail'
import PrismWordmark from './PrismWordmark.vue'
import {
  Plus, Search, X, Inbox, Star, Send, FileText, Trash2,
  ChevronRight, ShieldCheck, SlidersHorizontal, Globe,
  Check, MailPlus, RefreshCw, KeyRound,
  PenLine, Sun, Moon, Settings
} from 'lucide-vue-next'

const store = useMailStore()

const collapsedGroups = ref(new Set())
const syncingMailboxIds = ref(new Set())

// Custom Micro-Modals
const showNewLabelModal = ref(false)
const newLabelName = ref('')
const assignNewLabelToEdit = ref(false)

const newMailboxDomain = ref(null)
const newMailboxPrefix = ref('')
const newMailboxNote = ref('')

const editingMailbox = ref(null)
const editForm = ref({ label_ids: [], is_vip: false })

// Drag & Drop State
const dragMode = ref(null) // 'group' | 'mailbox' | null
const draggingGroupId = ref(null)
const groupDropTargetId = ref(null)
const groupDropPosition = ref(null) // 'before' | 'after' | null
const dragOverGroupId = ref(null)
const pendingDropAction = ref(null)
let currentDragPayload = null

const isCollapsed = (groupId) => collapsedGroups.value.has(groupId)
const toggleGroupCollapse = (groupId) => {
  if (collapsedGroups.value.has(groupId)) {
    collapsedGroups.value.delete(groupId)
  } else {
    collapsedGroups.value.add(groupId)
  }
}

const displayGroups = computed(() => {
  if (store.groupedData && store.groupedData.groups) {
    return store.groupedData.groups
  }
  return store.domains.map(d => ({
    group_id: `domain_${d.id}`,
    name: `@${d.name}`,
    domain_id: d.id,
    is_external: d.is_external,
    color: '#3b82f6',
    unread_count: d.unread_count || 0,
    mailboxes: (d.mailboxes || []).map(m => ({ ...m, domain_name: d.name }))
  }))
})

const availableLabels = computed(() => {
  if (store.mailboxLabels && store.mailboxLabels.length > 0) {
    return store.mailboxLabels
  }
  if (store.groupedData?.groups) {
    return store.groupedData.groups
      .filter(g => g.label_id && g.label_id !== 0)
      .map(g => ({ id: g.label_id, name: g.name }))
  }
  return []
})

const formatMailboxLabel = (mb) => {
  if (mb.is_external) {
    const hasCustomName = mb.name && mb.name !== mb.prefix && mb.name !== mb.address
    return hasCustomName ? `${mb.address} · ${mb.name}` : mb.address
  }
  return mb.name && mb.name !== mb.prefix ? `${mb.prefix} · ${mb.name}` : mb.prefix
}

const handleSyncExternal = async (mb) => {
  if (syncingMailboxIds.value.has(mb.id)) return
  syncingMailboxIds.value.add(mb.id)
  try {
    const res = await store.syncExternalMailbox(mb.id)
    const syncStatus = String(res?.sync_status || '')
    if (res?.status === 'error' || syncStatus.startsWith('error')) {
      const reason = res?.detail || res?.error || syncStatus.replace(/^error:\s*/i, '') || '请检查授权码'
      store.notify(`同步异常: ${reason}`, 'error')
    } else {
      store.notify(`${mb.address} 同步完成`, 'success')
    }
  } catch (err) {
    store.notify(`同步失败: ${err.message}`, 'error')
  } finally {
    syncingMailboxIds.value.delete(mb.id)
  }
}

const isGroupSelected = (grp) => {
  if (store.selectedMailboxId || store.selectedSmartFilter) return false
  return Boolean(
    (store.groupingMode === 'tags' && grp.label_id !== undefined && store.selectedLabelId === grp.label_id) ||
    (grp.domain_id && store.selectedDomainId === grp.domain_id)
  )
}

const handleSelectGroup = (grp) => {
  if (store.groupingMode === 'tags') {
    store.selectScope({ labelId: grp.label_id })
  } else if (grp.domain_id) {
    store.selectScope({ domainId: grp.domain_id })
  } else {
    store.selectScope({ domainId: null, mailboxId: null })
  }
}

const handleSelectMailbox = (mb) => {
  store.selectScope({
    domainId: mb.domain_id || null,
    mailboxId: mb.id,
    labelId: store.selectedLabelId,
    smartFilter: store.selectedSmartFilter
  })
}

const handleSelectFolder = (folderId) => {
  store.isMobileNavOpen = false
  if (typeof window !== 'undefined' && window.innerWidth < 1024) {
    store.closeMail()
  }
  if (store.selectedFolder === folderId && folderId === 'inbox' && store.hasActiveScope) {
    store.selectScope({ domainId: null, mailboxId: null, labelId: null, smartFilter: null })
  } else {
    store.selectedFolder = folderId
    store.fetchMails()
  }
}

const openDomainDns = (domainId) => {
  const dom = store.domains.find(d => d.id === domainId)
  if (dom) {
    store.isMobileNavOpen = false
    store.activeDomainDns = dom
  }
}

const openAddMailboxModal = (domainId) => {
  const dom = store.domains.find(d => d.id === domainId)
  if (!dom) return
  newMailboxDomain.value = dom
  newMailboxPrefix.value = ''
  newMailboxNote.value = ''
}

const submitAddMailbox = async () => {
  const pfx = newMailboxPrefix.value.trim()
  if (!pfx || !newMailboxDomain.value) return
  const note = newMailboxNote.value.trim() || pfx
  try {
    await store.createMailbox(newMailboxDomain.value.id, pfx, note)
    newMailboxDomain.value = null
  } catch {}
}

const openNewLabelModal = (fromEditModal = false) => {
  assignNewLabelToEdit.value = fromEditModal
  newLabelName.value = ''
  showNewLabelModal.value = true
}

const submitCreateLabel = async () => {
  const name = newLabelName.value.trim()
  if (!name) return
  try {
    const created = await store.createMailboxLabel(name, '', '#71717a')
    if (assignNewLabelToEdit.value && created?.id && editingMailbox.value) {
      editForm.value.label_ids.push(created.id)
    }
    showNewLabelModal.value = false
  } catch {}
}

const handleDeleteLabel = async (grp) => {
  const ok = await store.askConfirm({
    title: '移除分组',
    message: `确定移除「${grp.name}」吗？组内邮箱不会被删除。`,
    confirmText: '移除',
    danger: true
  })
  if (ok) {
    try {
      await store.deleteMailboxLabel(grp.label_id)
    } catch {}
  }
}

const handleDeleteMailbox = async (mb) => {
  const ok = await store.askConfirm({
    title: '删除邮箱',
    message: `确定删除 ${mb.address} 吗？`,
    confirmText: '删除',
    danger: true
  })
  if (ok) {
    try {
      await store.deleteMailbox(mb.id)
    } catch {}
  }
}

const canDragDesktop = () => typeof window !== 'undefined' && window.innerWidth >= 1024

// Drag & Drop Handlers
const canReorderGroup = (grp) => {
  return canDragDesktop() && store.groupingMode === 'tags' && Boolean(grp.label_id && grp.label_id !== 0)
}

const resetDragState = () => {
  dragMode.value = null
  draggingGroupId.value = null
  groupDropTargetId.value = null
  groupDropPosition.value = null
  dragOverGroupId.value = null
  currentDragPayload = null
}

const handleGroupDragStart = (evt, grp) => {
  if (!canReorderGroup(grp)) {
    evt.preventDefault()
    return
  }
  dragMode.value = 'group'
  draggingGroupId.value = grp.group_id
  evt.dataTransfer.effectAllowed = 'move'
  evt.dataTransfer.setData('text/plain', JSON.stringify({
    type: 'group',
    groupId: grp.group_id,
    labelId: grp.label_id
  }))
}

const handleMailboxDragStart = (evt, mb, grp) => {
  evt.stopPropagation()
  dragMode.value = 'mailbox'
  currentDragPayload = { mailbox: mb, sourceLabelId: grp.label_id || null }
  evt.dataTransfer.setData('text/plain', JSON.stringify({
    type: 'mailbox',
    mailboxId: mb.id,
    sourceLabelId: grp.label_id || null
  }))
  evt.dataTransfer.effectAllowed = 'copyMove'
}

const handleGroupDragOver = (evt, grp) => {
  evt.preventDefault()
  if (dragMode.value === 'group') {
    if (!canReorderGroup(grp) || grp.group_id === draggingGroupId.value) {
      groupDropTargetId.value = null
      groupDropPosition.value = null
      return
    }
    const rect = evt.currentTarget.getBoundingClientRect()
    const thresholdY = rect.top + Math.min(rect.height / 2, 18)
    groupDropTargetId.value = grp.group_id
    groupDropPosition.value = evt.clientY < thresholdY ? 'before' : 'after'
  } else if (dragMode.value === 'mailbox') {
    if (store.groupingMode === 'tags' && grp.label_id !== undefined) {
      dragOverGroupId.value = grp.group_id
    }
  }
}

const handleGroupDragLeave = (evt, grp) => {
  if (evt.currentTarget.contains(evt.relatedTarget)) return
  if (dragMode.value === 'group' && groupDropTargetId.value === grp.group_id) {
    groupDropTargetId.value = null
    groupDropPosition.value = null
  } else if (dragMode.value === 'mailbox' && dragOverGroupId.value === grp.group_id) {
    dragOverGroupId.value = null
  }
}

const handleDrop = async (evt, grp) => {
  evt.preventDefault()

  if (dragMode.value === 'group') {
    const sourceId = draggingGroupId.value
    const pos = groupDropPosition.value || 'after'
    resetDragState()
    if (!sourceId || !canReorderGroup(grp) || sourceId === grp.group_id) return

    const reorderable = displayGroups.value.filter(g => g.label_id && g.label_id !== 0)
    const fromIdx = reorderable.findIndex(g => g.group_id === sourceId)
    if (fromIdx === -1) return
    const [moved] = reorderable.splice(fromIdx, 1)
    const targetIdx = reorderable.findIndex(g => g.group_id === grp.group_id)
    if (targetIdx === -1) return
    const insertIdx = pos === 'before' ? targetIdx : targetIdx + 1
    reorderable.splice(insertIdx, 0, moved)

    await store.reorderMailboxLabels(reorderable.map(g => g.label_id))
    return
  }

  dragOverGroupId.value = null
  if (!currentDragPayload) {
    try {
      const raw = evt.dataTransfer.getData('text/plain')
      if (raw) {
        const parsed = JSON.parse(raw)
        if (parsed.type === 'mailbox' || parsed.mailboxId) {
          const mb = store.allMailboxes.find(m => m.id === parsed.mailboxId)
          if (mb) {
            currentDragPayload = { mailbox: mb, sourceLabelId: parsed.sourceLabelId }
          }
        }
      }
    } catch {}
  }
  const payload = currentDragPayload
  resetDragState()
  if (!payload || store.groupingMode !== 'tags' || grp.label_id === undefined) return
  if (payload.sourceLabelId !== grp.label_id) {
    pendingDropAction.value = {
      mailbox: payload.mailbox,
      sourceLabelId: payload.sourceLabelId,
      targetGroup: grp
    }
  }
}

const executeDropAction = async (mode) => {
  if (!pendingDropAction.value) return
  const { mailbox, sourceLabelId, targetGroup } = pendingDropAction.value
  let labelIds = [...(mailbox.labels ? mailbox.labels.map(l => l.id) : mailbox.label_ids || [])]
  if (mode === 'move') {
    if (sourceLabelId) {
      labelIds = labelIds.filter(id => id !== sourceLabelId)
    }
    if (targetGroup.label_id && targetGroup.label_id !== 0 && !labelIds.includes(targetGroup.label_id)) {
      labelIds.push(targetGroup.label_id)
    }
  } else if (mode === 'copy') {
    if (targetGroup.label_id && targetGroup.label_id !== 0 && !labelIds.includes(targetGroup.label_id)) {
      labelIds.push(targetGroup.label_id)
    }
  }
  try {
    await store.updateMailboxMetadata(mailbox.id, { label_ids: labelIds })
    store.notify(`已更新 ${mailbox.address} 归属分组`, 'success')
    pendingDropAction.value = null
  } catch {}
}

const openMailboxSettings = (mb) => {
  editingMailbox.value = mb
  const ids = mb.label_ids || (mb.labels ? mb.labels.map(l => l.id) : [])
  editForm.value = {
    label_ids: [...ids],
    is_vip: Boolean(mb.is_vip)
  }
}

const toggleEditLabel = (labelId) => {
  const idx = editForm.value.label_ids.indexOf(labelId)
  if (idx > -1) {
    editForm.value.label_ids.splice(idx, 1)
  } else {
    editForm.value.label_ids.push(labelId)
  }
}

const saveMailboxSettings = async () => {
  if (editingMailbox.value) {
    try {
      await store.updateMailboxMetadata(editingMailbox.value.id, {
        label_ids: editForm.value.label_ids,
        is_vip: editForm.value.is_vip
      })
      store.notify('设置已保存', 'success')
      editingMailbox.value = null
    } catch {}
  }
}
</script>

<template>
  <aside class="flex-shrink-0 flex flex-col select-none pt-3.5 pb-3 pl-3.5 pr-2.5 pb-safe">
    <!-- Brand & Quick Utility Icons -->
    <div class="flex items-center justify-between px-1.5 mb-3">
      <div class="flex items-center py-1">
        <PrismWordmark class="h-[13.5px] w-auto text-[var(--text-primary)]" />
      </div>

      <div class="flex items-center gap-0.5 text-[var(--text-muted)]">
        <button
          @click="store.toggleTheme()"
          class="p-1.5 rounded-lg hover:bg-[var(--bg-hover)] hover:text-[var(--text-primary)] transition"
          :title="store.theme === 'obsidian' ? '切换为浅色外观' : '切换为深色外观'"
        >
          <Sun v-if="store.theme === 'obsidian'" class="w-3.5 h-3.5" />
          <Moon v-else class="w-3.5 h-3.5" />
        </button>
        <button
          @click="store.openExternalModal()"
          class="p-1.5 rounded-lg hover:bg-[var(--bg-hover)] hover:text-[var(--text-primary)] transition"
          title="添加外部邮箱"
        >
          <MailPlus class="w-3.5 h-3.5" />
        </button>
        <button
          @click="store.isMobileNavOpen = false; store.isDomainModalOpen = true"
          class="p-1.5 rounded-lg hover:bg-[var(--bg-hover)] hover:text-[var(--text-primary)] transition"
          title="域名管理"
        >
          <Globe class="w-3.5 h-3.5" />
        </button>
        <button
          @click="store.isMobileNavOpen = false; store.isSettingsOpen = true"
          class="p-1.5 rounded-lg hover:bg-[var(--bg-hover)] hover:text-[var(--text-primary)] transition"
          title="设置 (⌘,)"
        >
          <Settings class="w-3.5 h-3.5" />
        </button>
        <button
          @click="store.isMobileNavOpen = false"
          class="lg:hidden p-1.5 rounded-lg hover:bg-[var(--bg-hover)] hover:text-[var(--text-primary)] transition"
          aria-label="关闭菜单"
        >
          <X class="w-4 h-4" />
        </button>
      </div>
    </div>

    <!-- Primary Compose + Command Bar Trigger -->
    <div class="px-1 space-y-2 mb-3.5">
      <button
        @click="store.openCompose()"
        class="pm-btn-primary w-full h-8 px-3 rounded-lg text-[12px] font-medium flex items-center justify-between shadow-sm"
      >
        <span class="flex items-center gap-2">
          <PenLine class="w-3.5 h-3.5 stroke-[2]" />
          <span>撰写新邮件</span>
        </span>
        <kbd class="hidden lg:inline text-[10px] font-mono opacity-60">C</kbd>
      </button>

      <button
        @click="store.isMobileNavOpen = false; store.isCommandOpen = true"
        class="w-full h-8 px-2.5 rounded-lg bg-[var(--bg-input)] hover:bg-[var(--bg-hover)] border border-[var(--border-hairline)] flex items-center justify-between text-[12px] text-[var(--text-muted)] transition"
      >
        <span class="flex items-center gap-2">
          <Search class="w-3.5 h-3.5" />
          <span>跳转邮箱或执行命令...</span>
        </span>
        <span class="hidden lg:inline pm-kbd">⌘K</span>
      </button>
    </div>

    <!-- Scrollable Navigation Tree -->
    <div class="flex-1 overflow-y-auto px-1 space-y-5">
      <!-- Core Folders -->
      <nav class="space-y-0.5">
        <button
          v-for="item in [
            { id: 'inbox', label: '收件箱', icon: Inbox, count: store.folderCounts.inbox, highlight: true },
            { id: 'starred', label: '星标', icon: Star, count: store.folderCounts.starred },
            { id: 'sent', label: '已发送', icon: Send, count: store.folderCounts.sent },
            { id: 'drafts', label: '草稿', icon: FileText, count: store.folderCounts.drafts },
            { id: 'trash', label: '废纸篓', icon: Trash2, count: store.folderCounts.trash }
          ]"
          :key="item.id"
          @click="handleSelectFolder(item.id)"
          :class="[
            'w-full h-7 px-2.5 rounded-lg text-[12.5px] flex items-center justify-between transition',
            store.selectedFolder === item.id && !store.hasActiveScope
              ? 'bg-[var(--bg-active)] text-[var(--text-primary)] font-medium'
              : store.selectedFolder === item.id
                ? 'bg-[var(--bg-subtle)] text-[var(--text-primary)] font-medium'
                : 'text-[var(--text-secondary)] hover:bg-[var(--bg-hover)] hover:text-[var(--text-primary)]'
          ]"
        >
          <span class="flex items-center gap-2.5">
            <component
              :is="item.icon"
              :class="[
                'w-3.5 h-3.5 stroke-[1.75]',
                store.selectedFolder === item.id ? 'text-[var(--text-primary)]' : 'text-[var(--text-muted)]'
              ]"
            />
            <span>{{ item.label }}</span>
          </span>
          <span
            v-if="item.count"
            :class="[
              'text-[11px] font-mono tabular-nums',
              item.highlight && store.selectedFolder === item.id
                ? 'text-[var(--text-primary)] font-semibold'
                : 'text-[var(--text-muted)]'
            ]"
          >
            {{ item.count }}
          </span>
        </button>
      </nav>

      <!-- Borderless Tree Matrix: Groups / Domains -->
      <div class="space-y-1">
        <!-- Section Bar -->
        <div class="flex items-center justify-between px-2 pb-1">
          <div class="flex items-center gap-3 text-[11px] font-medium">
            <button
              @click="store.switchGroupingMode('tags')"
              :class="[
                'transition',
                store.groupingMode === 'tags'
                  ? 'text-[var(--text-primary)] font-semibold'
                  : 'text-[var(--text-muted)] hover:text-[var(--text-secondary)]'
              ]"
            >
              分组
            </button>
            <span class="text-[var(--border-strong)]">/</span>
            <button
              @click="store.switchGroupingMode('domain_first')"
              :class="[
                'transition',
                store.groupingMode === 'domain_first'
                  ? 'text-[var(--text-primary)] font-semibold'
                  : 'text-[var(--text-muted)] hover:text-[var(--text-secondary)]'
              ]"
            >
              域名
            </button>
          </div>

          <div class="flex items-center gap-0.5">
            <button
              @click="store.openExternalModal()"
              class="px-1.5 py-0.5 rounded text-[11px] text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-hover)] transition"
              title="接入外部邮箱"
            >
              + 外部
            </button>
            <button
              @click="store.groupingMode === 'tags' ? openNewLabelModal(false) : (store.isDomainModalOpen = true)"
              class="p-1 rounded text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-hover)] transition"
              :title="store.groupingMode === 'tags' ? '新建分组' : '添加域名'"
            >
              <Plus class="w-3.5 h-3.5" />
            </button>
          </div>
        </div>

        <!-- Tree Nodes -->
        <div>
          <div
            v-for="grp in displayGroups"
            :key="grp.group_id"
            class="relative py-[1px]"
            @dragover.prevent="handleGroupDragOver($event, grp)"
            @dragleave="handleGroupDragLeave($event, grp)"
            @drop="handleDrop($event, grp)"
          >
            <!-- Drop Indicator (Before) -->
            <div
              v-if="dragMode === 'group' && groupDropTargetId === grp.group_id && groupDropPosition === 'before'"
              class="absolute -top-[1px] left-2 right-2 h-[1.5px] bg-[var(--accent-blue)] rounded-full z-20 pointer-events-none"
            />

            <!-- Group Row (Clean Tree Branch — No Heavy Borders) -->
            <div
              :draggable="canReorderGroup(grp)"
              @dragstart="handleGroupDragStart($event, grp)"
              @dragend="resetDragState"
              @click="handleSelectGroup(grp)"
              :class="[
                'h-7 px-2 rounded-lg flex items-center justify-between cursor-pointer transition group/hdr',
                dragOverGroupId === grp.group_id
                  ? 'bg-[var(--bg-active)] ring-1 ring-[var(--border-focus)]'
                  : isGroupSelected(grp)
                    ? 'bg-[var(--bg-active)] text-[var(--text-primary)] font-medium'
                    : 'text-[var(--text-secondary)] hover:bg-[var(--bg-hover)] hover:text-[var(--text-primary)]',
                draggingGroupId === grp.group_id ? 'opacity-40' : ''
              ]"
            >
              <div class="flex items-center gap-1.5 min-w-0">
                <button
                  @click.stop="toggleGroupCollapse(grp.group_id)"
                  class="p-0.5 text-[var(--text-muted)] hover:text-[var(--text-primary)] transition flex-shrink-0"
                >
                  <ChevronRight
                    :class="[
                      'w-3.5 h-3.5 transition-transform duration-150',
                      !isCollapsed(grp.group_id) ? 'rotate-90' : ''
                    ]"
                  />
                </button>
                <span class="text-[12.5px] truncate">{{ grp.name }}</span>
                <span class="text-[10.5px] text-[var(--text-faint)] font-mono tabular-nums">
                  {{ grp.mailboxes?.length || 0 }}
                </span>
              </div>

              <div class="flex items-center gap-1 flex-shrink-0">
                <button
                  v-if="grp.domain_id && !grp.is_external"
                  @click.stop="openDomainDns(grp.domain_id)"
                  class="pm-touch-show p-0.5 text-[var(--text-muted)] hover:text-[var(--accent-emerald)] opacity-0 group-hover/hdr:opacity-100 transition"
                  title="DNS 记录"
                >
                  <ShieldCheck class="w-3 h-3" />
                </button>
                <button
                  v-if="grp.domain_id"
                  @click.stop="grp.is_external ? store.openExternalModal() : openAddMailboxModal(grp.domain_id)"
                  class="pm-touch-show p-0.5 text-[var(--text-muted)] hover:text-[var(--text-primary)] opacity-0 group-hover/hdr:opacity-100 transition"
                  :title="grp.is_external ? '接入外部邮箱' : '新建邮箱'"
                >
                  <Plus class="w-3 h-3" />
                </button>
                <button
                  v-if="store.groupingMode === 'tags' && grp.label_id && grp.label_id !== 0"
                  @click.stop="handleDeleteLabel(grp)"
                  class="pm-touch-show p-0.5 text-[var(--text-muted)] hover:text-[var(--accent-rose)] opacity-0 group-hover/hdr:opacity-100 transition"
                  title="移除分组"
                >
                  <Trash2 class="w-3 h-3" />
                </button>
                <span
                  v-if="grp.unread_count"
                  class="text-[11px] font-mono tabular-nums text-[var(--text-secondary)] pl-0.5"
                >
                  {{ grp.unread_count }}
                </span>
              </div>
            </div>

            <!-- Nested Mailboxes along 1px Tree Guide Line -->
            <div
              v-if="grp.mailboxes && grp.mailboxes.length > 0 && !isCollapsed(grp.group_id)"
              class="ml-[15px] pl-2.5 border-l border-[var(--border-hairline)] my-0.5 space-y-[1px]"
            >
              <div
                v-for="mb in grp.mailboxes"
                :key="`${grp.group_id}_${mb.id}`"
                :draggable="canDragDesktop()"
                @dragstart="handleMailboxDragStart($event, mb, grp)"
                @dragend="resetDragState"
                @click.stop="handleSelectMailbox(mb)"
                :class="[
                  'h-7 px-2 rounded-md flex items-center justify-between text-[12px] cursor-pointer transition group/mb',
                  store.selectedMailboxId === mb.id
                    ? 'bg-[var(--bg-active)] text-[var(--text-primary)] font-medium'
                    : 'text-[var(--text-muted)] hover:bg-[var(--bg-hover)] hover:text-[var(--text-primary)]'
                ]"
                :title="mb.address"
              >
                <div class="flex items-center min-w-0">
                  <span
                    :class="[
                      'font-mono text-[11.5px] truncate',
                      mb.unread_count && store.selectedMailboxId !== mb.id ? 'text-[var(--text-primary)] font-medium' : ''
                    ]"
                  >
                    {{ formatMailboxLabel(mb) }}
                  </span>
                </div>

                <div class="flex items-center gap-1 flex-shrink-0">
                  <span
                    v-if="mb.is_external && mb.sync_status && mb.sync_status.startsWith('error')"
                    class="text-[9.5px] font-mono px-1 rounded bg-[var(--accent-rose)]/15 text-[var(--accent-rose)]"
                    :title="mb.sync_status"
                  >
                    异常
                  </span>
                  <span
                    v-if="mb.is_vip"
                    class="text-[9.5px] font-mono px-1 rounded border border-[var(--border-hairline)] text-[var(--text-muted)] lg:group-hover/mb:hidden"
                  >
                    VIP
                  </span>
                  <button
                    v-if="mb.is_external"
                    @click.stop="handleSyncExternal(mb)"
                    class="pm-touch-show p-0.5 text-[var(--text-muted)] hover:text-[var(--text-primary)] opacity-0 group-hover/mb:opacity-100 transition"
                    title="同步"
                  >
                    <RefreshCw :class="['w-2.5 h-2.5', { 'animate-spin': syncingMailboxIds.has(mb.id) }]" />
                  </button>
                  <button
                    v-if="mb.is_external"
                    @click.stop="store.openExternalModal(mb)"
                    class="pm-touch-show p-0.5 text-[var(--text-muted)] hover:text-[var(--text-primary)] opacity-0 group-hover/mb:opacity-100 transition"
                    title="凭据设置"
                  >
                    <KeyRound class="w-2.5 h-2.5" />
                  </button>
                  <button
                    @click.stop="openMailboxSettings(mb)"
                    class="pm-touch-show p-0.5 text-[var(--text-muted)] hover:text-[var(--text-primary)] opacity-0 group-hover/mb:opacity-100 transition"
                    title="分组与重点标记"
                  >
                    <SlidersHorizontal class="w-2.5 h-2.5" />
                  </button>
                  <button
                    v-if="!mb.is_default"
                    @click.stop="handleDeleteMailbox(mb)"
                    class="pm-touch-show p-0.5 text-[var(--text-muted)] hover:text-[var(--accent-rose)] opacity-0 group-hover/mb:opacity-100 transition"
                    title="删除"
                  >
                    <Trash2 class="w-2.5 h-2.5" />
                  </button>
                  <span
                    v-if="mb.unread_count"
                    class="text-[10.5px] font-mono tabular-nums text-[var(--text-primary)] font-medium pl-1"
                  >
                    {{ mb.unread_count }}
                  </span>
                </div>
              </div>
            </div>

            <!-- Drop Indicator (After) -->
            <div
              v-if="dragMode === 'group' && groupDropTargetId === grp.group_id && groupDropPosition === 'after'"
              class="absolute -bottom-[1px] left-2 right-2 h-[1.5px] bg-[var(--accent-blue)] rounded-full z-20 pointer-events-none"
            />
          </div>
        </div>
      </div>

      <!-- Mail Content Tags -->
      <div v-if="store.tags && store.tags.length > 0" class="space-y-0.5 pt-2 border-t border-[var(--border-hairline)]">
        <button
          v-for="t in store.tags"
          :key="t.id"
          @click="store.selectScope({ tag: store.selectedTag === t.name ? null : t.name })"
          :class="[
            'w-full h-7 px-2.5 rounded-lg text-[12px] flex items-center gap-2 transition',
            store.selectedTag === t.name
              ? 'bg-[var(--bg-active)] text-[var(--text-primary)] font-medium'
              : 'text-[var(--text-secondary)] hover:bg-[var(--bg-hover)]'
          ]"
        >
          <span class="font-mono text-[11px] text-[var(--text-muted)]">#</span>
          <span>{{ t.name }}</span>
        </button>
      </div>
    </div>

    <!-- Clean Bottom Settings Entry -->
    <div class="pt-2 mt-1 px-1 border-t border-[var(--border-hairline)] flex-shrink-0">
      <button
        type="button"
        @click="store.isMobileNavOpen = false; store.isSettingsOpen = true"
        class="w-full h-7 px-2.5 rounded-lg text-[12px] text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-hover)] flex items-center justify-between transition"
      >
        <span class="flex items-center gap-2">
          <Settings class="w-3.5 h-3.5 text-[var(--text-muted)]" />
          <span>设置</span>
        </span>
        <span class="hidden lg:inline pm-kbd">⌘,</span>
      </button>
    </div>

    <Teleport to="body">
      <!-- Micro Modal 1: Create Group -->
      <Transition name="fade-scale">
        <div
          v-if="showNewLabelModal"
          class="fixed inset-0 pm-backdrop z-[60] flex items-center justify-center p-4"
          @click.self="showNewLabelModal = false"
        >
        <div class="pm-modal rounded-2xl w-full max-w-xs p-4 space-y-3.5">
          <div class="flex items-center justify-between">
            <h3 class="text-[13px] font-semibold text-[var(--text-primary)]">新建分组</h3>
            <button @click="showNewLabelModal = false" class="text-[var(--text-muted)] hover:text-[var(--text-primary)]">
              <X class="w-4 h-4" />
            </button>
          </div>
          <input
            v-model="newLabelName"
            @keydown.enter.prevent="submitCreateLabel"
            type="text"
            placeholder="输入分组名称"
            autofocus
            class="w-full bg-[var(--bg-input)] border border-[var(--border-hairline)] focus:border-[var(--border-focus)] rounded-xl px-3 py-2 text-[12.5px] text-[var(--text-primary)] placeholder-[var(--text-muted)] focus:outline-none transition"
          />
          <div class="flex items-center justify-end gap-2 pt-1">
            <button
              @click="showNewLabelModal = false"
              class="px-3 py-1.5 rounded-lg text-[12px] text-[var(--text-secondary)] hover:bg-[var(--bg-hover)] transition"
            >
              取消
            </button>
            <button
              @click="submitCreateLabel"
              :disabled="!newLabelName.trim()"
              class="pm-btn-primary px-3.5 py-1.5 rounded-lg text-[12px] font-medium disabled:opacity-40"
            >
              创建
            </button>
          </div>
        </div>
      </div>
    </Transition>

      <!-- Micro Modal 2: Create Local Mailbox -->
      <Transition name="fade-scale">
        <div
          v-if="newMailboxDomain"
          class="fixed inset-0 pm-backdrop z-[60] flex items-center justify-center p-4"
          @click.self="newMailboxDomain = null"
        >
          <div class="pm-modal rounded-2xl w-full max-w-sm p-4 space-y-3.5">
            <div class="flex items-center justify-between">
              <h3 class="text-[13px] font-semibold text-[var(--text-primary)]">开通新邮箱</h3>
              <button @click="newMailboxDomain = null" class="text-[var(--text-muted)] hover:text-[var(--text-primary)]">
                <X class="w-4 h-4" />
              </button>
            </div>
            <div class="space-y-2.5">
              <div class="flex items-center bg-[var(--bg-input)] border border-[var(--border-hairline)] focus-within:border-[var(--border-focus)] rounded-xl overflow-hidden transition">
                <input
                  v-model="newMailboxPrefix"
                  @keydown.enter.prevent="submitAddMailbox"
                  type="text"
                  placeholder="前缀 (如 hello)"
                  autofocus
                  class="flex-1 min-w-0 bg-transparent px-3 py-2 text-[12.5px] font-mono text-[var(--text-primary)] placeholder-[var(--text-muted)] focus:outline-none"
                />
              <span class="px-3 py-2 text-[12px] font-mono text-[var(--text-secondary)] border-l border-[var(--border-hairline)] bg-[var(--bg-subtle)]">
                @{{ newMailboxDomain.name }}
              </span>
            </div>
            <input
              v-model="newMailboxNote"
              @keydown.enter.prevent="submitAddMailbox"
              type="text"
              placeholder="备注名称 (选填)"
              class="w-full bg-[var(--bg-input)] border border-[var(--border-hairline)] focus:border-[var(--border-focus)] rounded-xl px-3 py-2 text-[12.5px] text-[var(--text-primary)] placeholder-[var(--text-muted)] focus:outline-none transition"
            />
          </div>
          <div class="flex items-center justify-end gap-2 pt-1">
            <button
              @click="newMailboxDomain = null"
              class="px-3 py-1.5 rounded-lg text-[12px] text-[var(--text-secondary)] hover:bg-[var(--bg-hover)] transition"
            >
              取消
            </button>
            <button
              @click="submitAddMailbox"
              :disabled="!newMailboxPrefix.trim()"
              class="pm-btn-primary px-3.5 py-1.5 rounded-lg text-[12px] font-medium disabled:opacity-40"
            >
              创建
            </button>
          </div>
        </div>
      </div>
    </Transition>

      <!-- Micro Modal 3: Drag & Drop Move/Copy -->
      <Transition name="fade-scale">
        <div
          v-if="pendingDropAction"
          class="fixed inset-0 pm-backdrop z-[60] flex items-center justify-center p-4"
          @click.self="pendingDropAction = null"
        >
        <div class="pm-modal rounded-2xl w-full max-w-xs p-4 space-y-4">
          <div class="flex items-center justify-between">
            <h3 class="text-[13px] font-semibold text-[var(--text-primary)]">归入分组</h3>
            <button @click="pendingDropAction = null" class="text-[var(--text-muted)] hover:text-[var(--text-primary)]">
              <X class="w-4 h-4" />
            </button>
          </div>
          <p class="text-[12.5px] text-[var(--text-secondary)] leading-relaxed">
            将 <span class="font-mono text-[var(--text-primary)] font-medium">{{ pendingDropAction.mailbox.address }}</span>
            归入 <span class="text-[var(--text-primary)] font-medium">「{{ pendingDropAction.targetGroup.name }}」</span>
          </p>
          <div class="flex items-center justify-end gap-2">
            <button
              @click="pendingDropAction = null"
              class="px-3 py-1.5 rounded-lg text-[12px] text-[var(--text-muted)] hover:text-[var(--text-primary)] transition"
            >
              取消
            </button>
            <button
              @click="executeDropAction('move')"
              class="px-3 py-1.5 rounded-lg text-[12px] bg-[var(--bg-hover)] hover:bg-[var(--bg-active)] text-[var(--text-primary)] border border-[var(--border-hairline)] font-medium transition"
            >
              移动
            </button>
            <button
              @click="executeDropAction('copy')"
              class="pm-btn-primary px-3.5 py-1.5 rounded-lg text-[12px] font-medium"
            >
              多组共存
            </button>
          </div>
        </div>
      </div>
    </Transition>

      <!-- Micro Modal 4: Mailbox Group & VIP Settings -->
      <Transition name="fade-scale">
        <div
          v-if="editingMailbox"
          class="fixed inset-0 pm-backdrop z-[60] flex items-center justify-center p-4"
          @click.self="editingMailbox = null"
        >
        <div class="pm-modal rounded-2xl w-full max-w-sm p-4 space-y-4">
          <div class="flex items-center justify-between">
            <span class="font-mono text-[12.5px] font-semibold text-[var(--text-primary)] truncate">
              {{ editingMailbox.address }}
            </span>
            <button @click="editingMailbox = null" class="text-[var(--text-muted)] hover:text-[var(--text-primary)]">
              <X class="w-4 h-4" />
            </button>
          </div>

          <div class="space-y-3">
            <div>
              <div class="flex items-center justify-between mb-2">
                <span class="text-[11.5px] text-[var(--text-muted)]">所属分组</span>
                <button
                  @click="openNewLabelModal(true)"
                  class="text-[11.5px] text-[var(--text-secondary)] hover:text-[var(--text-primary)] flex items-center gap-0.5 transition"
                >
                  <Plus class="w-3 h-3" />
                  <span>新建</span>
                </button>
              </div>
              <div class="flex flex-wrap gap-1.5">
                <button
                  v-for="lbl in availableLabels"
                  :key="lbl.id"
                  type="button"
                  @click="toggleEditLabel(lbl.id)"
                  :class="[
                    'px-2.5 py-1 rounded-lg text-[12px] flex items-center gap-1.5 transition border',
                    editForm.label_ids.includes(lbl.id)
                      ? 'bg-[var(--bg-active)] border-[var(--border-focus)] text-[var(--text-primary)] font-medium'
                      : 'bg-[var(--bg-subtle)] border-[var(--border-hairline)] text-[var(--text-secondary)] hover:text-[var(--text-primary)]'
                  ]"
                >
                  <span>{{ lbl.name }}</span>
                  <Check v-if="editForm.label_ids.includes(lbl.id)" class="w-3 h-3" />
                </button>
              </div>
            </div>

            <label class="flex items-center justify-between px-3 py-2.5 rounded-xl bg-[var(--bg-subtle)] border border-[var(--border-hairline)] cursor-pointer">
              <span class="text-[12.5px] text-[var(--text-primary)]">重点关注邮箱 (VIP)</span>
              <input
                type="checkbox"
                v-model="editForm.is_vip"
                class="w-4 h-4 rounded accent-zinc-900 dark:accent-white cursor-pointer"
              />
            </label>
          </div>

          <div class="flex items-center justify-end gap-2">
            <button
              @click="editingMailbox = null"
              class="px-3 py-1.5 rounded-lg text-[12px] text-[var(--text-secondary)] hover:bg-[var(--bg-hover)] transition"
            >
              取消
            </button>
            <button
              @click="saveMailboxSettings"
              class="pm-btn-primary px-4 py-1.5 rounded-lg text-[12px] font-medium"
            >
              保存
            </button>
          </div>
        </div>
      </div>
    </Transition>
    </Teleport>
  </aside>
</template>
