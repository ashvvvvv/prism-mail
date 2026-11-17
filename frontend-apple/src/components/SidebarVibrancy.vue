<script setup>
import { ref, computed } from 'vue'
import { useMailStore } from '../stores/mail'
import PrismWordmark from './PrismWordmark.vue'
import {
  Plus,
  X,
  Inbox,
  Star,
  Send,
  FileText,
  Trash2,
  ChevronRight,
  ShieldCheck,
  SlidersHorizontal,
  Check,
  RefreshCw,
  KeyRound,
  Search,
  Settings
} from 'lucide-vue-next'

const store = useMailStore()

const collapsedGroups = ref(new Set())
const syncingMailboxIds = ref(new Set())

// Micro-Sheets State
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

const coreFolders = computed(() => [
  { id: 'inbox', label: '收件箱', icon: Inbox, count: store.folderCounts.inbox },
  { id: 'starred', label: '星标邮件', icon: Star, count: store.folderCounts.starred },
  { id: 'sent', label: '已发送', icon: Send, count: store.folderCounts.sent },
  { id: 'drafts', label: '草稿箱', icon: FileText, count: store.folderCounts.drafts },
  { id: 'trash', label: '废纸篓', icon: Trash2, count: store.folderCounts.trash }
])

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
    if (res.status === 'error') {
      store.notify(`同步异常: ${res.error || '请检查授权码'}`, 'error')
    } else {
      store.notify(`${mb.address} 同步完成`, 'success')
    }
  } catch (err) {
    store.notify(`同步失败: ${err.message}`, 'error')
  } finally {
    syncingMailboxIds.value.delete(mb.id)
  }
}

const isFolderPrimarySelected = (folderId) => {
  return store.selectedFolder === folderId && !store.hasActiveScope
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
  if (store.selectedFolder === folderId && store.hasActiveScope) {
    store.selectScope({ domainId: null, mailboxId: null, labelId: null, smartFilter: null })
  } else {
    store.selectedFolder = folderId
    if (folderId !== 'inbox' && store.hasActiveScope) {
      store.fetchMails()
      if (typeof window !== 'undefined' && window.innerWidth < 1024) {
        store.closeMail()
      }
    } else {
      store.selectScope({ domainId: null, mailboxId: null, labelId: null, smartFilter: null })
    }
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
  await store.createMailbox(newMailboxDomain.value.id, pfx, note)
  newMailboxDomain.value = null
}

const openNewLabelModal = (fromEditModal = false) => {
  assignNewLabelToEdit.value = fromEditModal
  newLabelName.value = ''
  showNewLabelModal.value = true
}

const submitCreateLabel = async () => {
  const name = newLabelName.value.trim()
  if (!name) return
  const created = await store.createMailboxLabel(name, '')
  if (assignNewLabelToEdit.value && created?.id && editingMailbox.value) {
    editForm.value.label_ids.push(created.id)
  }
  showNewLabelModal.value = false
}

const handleDeleteLabel = async (grp) => {
  const ok = await store.askConfirm({
    title: `移除分组「${grp.name}」？`,
    message: '移除该分组标签不会删除组内的任何邮箱与邮件。',
    confirmText: '移除分组',
    danger: true
  })
  if (ok) {
    await store.deleteMailboxLabel(grp.label_id)
  }
}

const handleDeleteMailbox = async (mb) => {
  const ok = await store.askConfirm({
    title: `删除邮箱 ${mb.address}？`,
    message: '此操作将删除该邮箱地址及其关联的本地邮件记录。',
    confirmText: '删除邮箱',
    danger: true
  })
  if (ok) {
    await store.deleteMailbox(mb.id)
  }
}

// Drag & Drop Reorder + Mailbox Move/Copy
const canDragDesktop = () => typeof window !== 'undefined' && window.innerWidth >= 1024

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
  await store.updateMailboxMetadata(mailbox.id, { label_ids: labelIds })
  store.notify(`已更新 ${mailbox.address} 归属分组`, 'success')
  pendingDropAction.value = null
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
    await store.updateMailboxMetadata(editingMailbox.value.id, {
      label_ids: editForm.value.label_ids,
      is_vip: editForm.value.is_vip
    })
    store.notify('邮箱偏好设置已保存', 'success')
    editingMailbox.value = null
  }
}
</script>

<template>
  <aside class="mac-sidebar-vibrancy mac-hairline-r flex-shrink-0 flex flex-col overflow-hidden select-none">
    <!-- Mobile Drawer Header -->
    <div class="lg:hidden h-[52px] px-3.5 mac-hairline-b flex items-center justify-between flex-shrink-0">
      <PrismWordmark class="h-[23px] w-auto" />
      <button
        type="button"
        @click="store.isMobileNavOpen = false"
        class="w-7 h-7 rounded-full bg-[var(--fill-tertiary)] hover:bg-[var(--fill-secondary)] flex items-center justify-center text-[var(--label-secondary)] transition"
        title="收起边栏"
      >
        <X class="w-4 h-4" />
      </button>
    </div>

    <!-- Scrollable macOS Mail Outline View -->
    <div class="flex-1 overflow-y-auto px-2.5 pt-3 pb-3 space-y-5">
      <!-- Desktop Cupertino Wordmark -->
      <div class="hidden lg:flex items-center px-2.5 pt-0.5">
        <PrismWordmark class="h-[22px] w-auto" />
      </div>

      <!-- Section 1: 个人收藏 (Favorites / Core Folders) -->
      <div class="space-y-1">
        <div class="px-2.5 flex items-center justify-between">
          <span class="text-[11px] font-semibold tracking-[-0.005em] text-[var(--label-secondary)]">
            个人收藏
          </span>
        </div>

        <nav class="space-y-[2px]">
          <button
            v-for="item in coreFolders"
            :key="item.id"
            type="button"
            @click="handleSelectFolder(item.id)"
            :class="[
              'w-full h-[30px] px-2.5 rounded-[8px] text-[13px] flex items-center justify-between transition-colors',
              isFolderPrimarySelected(item.id)
                ? 'bg-[var(--selection-bg)] text-[var(--selection-text)] font-medium shadow-[0_1px_2px_rgba(0,122,255,0.22)]'
                : store.selectedFolder === item.id
                  ? 'bg-[var(--fill-active-subtle)] text-[var(--apple-blue)] font-medium'
                  : 'text-[var(--label-primary)] hover:bg-[var(--fill-hover)]'
            ]"
          >
            <span class="flex items-center gap-2.5 min-w-0">
              <component
                :is="item.icon"
                :class="[
                  'w-[15.5px] h-[15.5px] stroke-[1.85] flex-shrink-0',
                  isFolderPrimarySelected(item.id)
                    ? 'text-white'
                    : store.selectedFolder === item.id
                      ? 'text-[var(--apple-blue)]'
                      : 'text-[var(--label-secondary)]'
                ]"
              />
              <span class="truncate">{{ item.label }}</span>
            </span>

            <span
              v-if="item.count"
              :class="[
                'text-[12px] tabular-nums font-medium pl-1.5',
                isFolderPrimarySelected(item.id)
                  ? 'text-[var(--selection-subtext)]'
                  : 'text-[var(--label-secondary)]'
              ]"
            >
              {{ item.count }}
            </span>
          </button>
        </nav>
      </div>

      <!-- Section 2: 智能信箱 · 分组 / 域名 (Groups / Domains Tree) -->
      <div class="space-y-1.5">
        <div class="px-2 flex items-center justify-between gap-1">
          <!-- Mini Segmented Switch: 分组 | 域名 -->
          <div class="mac-segmented h-[22px] text-[11px]">
            <button
              type="button"
              @click="store.switchGroupingMode('tags')"
              :class="[
                'px-2 h-[18px] rounded-[5px] transition',
                store.groupingMode === 'tags'
                  ? 'bg-[var(--seg-thumb)] text-[var(--label-primary)] font-semibold shadow-[var(--seg-thumb-shadow)]'
                  : 'text-[var(--label-secondary)] hover:text-[var(--label-primary)]'
              ]"
            >
              分组
            </button>
            <button
              type="button"
              @click="store.switchGroupingMode('domain_first')"
              :class="[
                'px-2 h-[18px] rounded-[5px] transition',
                store.groupingMode === 'domain_first'
                  ? 'bg-[var(--seg-thumb)] text-[var(--label-primary)] font-semibold shadow-[var(--seg-thumb-shadow)]'
                  : 'text-[var(--label-secondary)] hover:text-[var(--label-primary)]'
              ]"
            >
              域名
            </button>
          </div>

          <div class="flex items-center gap-0.5">
            <button
              type="button"
              @click="store.openExternalModal()"
              class="px-1.5 py-0.5 rounded-[5px] text-[11px] font-medium text-[var(--apple-blue)] hover:bg-[var(--fill-active-subtle)] transition"
              title="接入外部邮箱 (Gmail / QQ / 163 / Outlook / iCloud)"
            >
              + 外部
            </button>
            <button
              type="button"
              @click="store.groupingMode === 'tags' ? openNewLabelModal(false) : (store.isDomainModalOpen = true, store.isMobileNavOpen = false)"
              class="w-[22px] h-[22px] rounded-[5px] flex items-center justify-center text-[var(--label-secondary)] hover:text-[var(--label-primary)] hover:bg-[var(--fill-hover)] transition"
              :title="store.groupingMode === 'tags' ? '新建邮箱分组' : '绑定自定义域名'"
            >
              <Plus class="w-3.5 h-3.5 stroke-[2]" />
            </button>
          </div>
        </div>

        <!-- Draggable Outline Groups & Mailboxes -->
        <div class="space-y-[2px]">
          <div
            v-for="grp in displayGroups"
            :key="grp.group_id"
            class="relative"
            @dragover.prevent="handleGroupDragOver($event, grp)"
            @dragleave="handleGroupDragLeave($event, grp)"
            @drop="handleDrop($event, grp)"
          >
            <!-- macOS Finder-Style Drop Line (Before) -->
            <div
              v-if="dragMode === 'group' && groupDropTargetId === grp.group_id && groupDropPosition === 'before'"
              class="absolute -top-[1px] left-2 right-2 h-[2px] bg-[var(--apple-blue)] rounded-full z-20 pointer-events-none flex items-center"
            >
              <span class="w-2 h-2 -ml-1 rounded-full bg-[var(--apple-blue)] ring-2 ring-white dark:ring-[#1c1c1e]" />
            </div>

            <!-- Group Row -->
            <div
              :draggable="canReorderGroup(grp)"
              @dragstart="handleGroupDragStart($event, grp)"
              @dragend="resetDragState"
              @click="handleSelectGroup(grp)"
              :class="[
                'h-[29px] px-2 rounded-[8px] flex items-center justify-between cursor-pointer transition-colors group/hdr',
                dragOverGroupId === grp.group_id
                  ? 'bg-[var(--fill-active-subtle)] ring-1.5 ring-[var(--apple-blue)]'
                  : isGroupSelected(grp)
                    ? 'bg-[var(--selection-bg)] text-[var(--selection-text)] font-medium shadow-[0_1px_2px_rgba(0,122,255,0.2)]'
                    : 'text-[var(--label-primary)] hover:bg-[var(--fill-hover)]',
                draggingGroupId === grp.group_id ? 'opacity-40' : ''
              ]"
            >
              <div class="flex items-center gap-1.5 min-w-0">
                <button
                  type="button"
                  @click.stop="toggleGroupCollapse(grp.group_id)"
                  :class="[
                    'p-0.5 rounded flex-shrink-0 transition-colors',
                    isGroupSelected(grp)
                      ? 'text-[var(--selection-subtext)] hover:text-white'
                      : 'text-[var(--label-secondary)] hover:text-[var(--label-primary)]'
                  ]"
                >
                  <ChevronRight
                    :class="[
                      'w-3.5 h-3.5 stroke-[2] transition-transform duration-150',
                      !isCollapsed(grp.group_id) ? 'rotate-90' : ''
                    ]"
                  />
                </button>

                <span class="text-[12.5px] truncate">{{ grp.name }}</span>

                <span
                  :class="[
                    'text-[10.5px] font-mono tabular-nums',
                    isGroupSelected(grp) ? 'text-[var(--selection-muted)]' : 'text-[var(--label-tertiary)]'
                  ]"
                >
                  {{ grp.mailboxes?.length || 0 }}
                </span>
              </div>

              <div class="flex items-center gap-0.5 flex-shrink-0">
                <button
                  v-if="grp.domain_id && !grp.is_external"
                  type="button"
                  @click.stop="openDomainDns(grp.domain_id)"
                  :class="[
                    'p-0.5 rounded opacity-0 group-hover/hdr:opacity-100 mac-touch-show transition',
                    isGroupSelected(grp) ? 'text-white/85 hover:text-white' : 'text-[var(--label-secondary)] hover:text-[var(--apple-green)]'
                  ]"
                  title="查看与拷贝 DNS 记录"
                >
                  <ShieldCheck class="w-3.5 h-3.5" />
                </button>

                <button
                  v-if="grp.domain_id"
                  type="button"
                  @click.stop="grp.is_external ? store.openExternalModal() : openAddMailboxModal(grp.domain_id)"
                  :class="[
                    'p-0.5 rounded opacity-0 group-hover/hdr:opacity-100 mac-touch-show transition',
                    isGroupSelected(grp) ? 'text-white/85 hover:text-white' : 'text-[var(--label-secondary)] hover:text-[var(--apple-blue)]'
                  ]"
                  :title="grp.is_external ? '接入外部邮箱' : '在此域名下开通新邮箱'"
                >
                  <Plus class="w-3.5 h-3.5" />
                </button>

                <button
                  v-if="store.groupingMode === 'tags' && grp.label_id && grp.label_id !== 0"
                  type="button"
                  @click.stop="handleDeleteLabel(grp)"
                  :class="[
                    'p-0.5 rounded opacity-0 group-hover/hdr:opacity-100 mac-touch-show transition',
                    isGroupSelected(grp) ? 'text-white/85 hover:text-white' : 'text-[var(--label-secondary)] hover:text-[var(--apple-red)]'
                  ]"
                  title="移除分组"
                >
                  <Trash2 class="w-3 h-3" />
                </button>

                <span
                  v-if="grp.unread_count"
                  :class="[
                    'text-[11.5px] tabular-nums font-medium pl-1',
                    isGroupSelected(grp) ? 'text-[var(--selection-subtext)]' : 'text-[var(--label-secondary)]'
                  ]"
                >
                  {{ grp.unread_count }}
                </span>
              </div>
            </div>

            <!-- Nested Mailboxes -->
            <div
              v-if="grp.mailboxes && grp.mailboxes.length > 0 && !isCollapsed(grp.group_id)"
              class="ml-[16px] pl-2 border-l border-[var(--separator)] my-0.5 space-y-[1px]"
            >
              <div
                v-for="mb in grp.mailboxes"
                :key="`${grp.group_id}_${mb.id}`"
                :draggable="canDragDesktop()"
                @dragstart="handleMailboxDragStart($event, mb, grp)"
                @dragend="resetDragState"
                @click.stop="handleSelectMailbox(mb)"
                :class="[
                  'h-[28px] px-2 rounded-[7px] flex items-center justify-between text-[12px] cursor-pointer transition-colors group/mb',
                  store.selectedMailboxId === mb.id
                    ? 'bg-[var(--selection-bg)] text-[var(--selection-text)] font-medium shadow-[0_1px_2px_rgba(0,122,255,0.2)]'
                    : 'text-[var(--label-primary)] hover:bg-[var(--fill-hover)]'
                ]"
                :title="mb.address"
              >
                <div class="flex items-center min-w-0">
                  <span
                    :class="[
                      'font-mono text-[11.5px] truncate',
                      store.selectedMailboxId === mb.id
                        ? 'text-white'
                        : mb.unread_count
                          ? 'text-[var(--label-primary)] font-medium'
                          : 'text-[var(--label-secondary)] group-hover/mb:text-[var(--label-primary)]'
                    ]"
                  >
                    {{ formatMailboxLabel(mb) }}
                  </span>
                </div>

                <div class="flex items-center gap-0.5 flex-shrink-0">
                  <span
                    v-if="mb.is_external && mb.sync_status && mb.sync_status.startsWith('error')"
                    :class="[
                      'text-[9.5px] font-mono px-1 rounded',
                      store.selectedMailboxId === mb.id
                        ? 'bg-white/22 text-white'
                        : 'bg-[#FF3B30]/12 text-[var(--apple-red)]'
                    ]"
                    :title="mb.sync_status"
                  >
                    异常
                  </span>

                  <span
                    v-if="mb.is_vip"
                    :class="[
                      'text-[9.5px] font-mono px-1 rounded border lg:group-hover/mb:hidden',
                      store.selectedMailboxId === mb.id
                        ? 'border-white/35 text-white'
                        : 'border-[var(--separator)] text-[var(--label-secondary)]'
                    ]"
                  >
                    VIP
                  </span>
                  <button
                    v-if="mb.is_external"
                    type="button"
                    @click.stop="handleSyncExternal(mb)"
                    :class="[
                      'p-0.5 rounded opacity-0 group-hover/mb:opacity-100 mac-touch-show transition',
                      store.selectedMailboxId === mb.id ? 'text-white/85 hover:text-white' : 'text-[var(--label-secondary)] hover:text-[var(--apple-blue)]'
                    ]"
                    title="立即同步此外部邮箱"
                  >
                    <RefreshCw :class="['w-2.5 h-2.5', { 'animate-spin': syncingMailboxIds.has(mb.id) }]" />
                  </button>

                  <button
                    v-if="mb.is_external"
                    type="button"
                    @click.stop="store.openExternalModal(mb)"
                    :class="[
                      'p-0.5 rounded opacity-0 group-hover/mb:opacity-100 mac-touch-show transition',
                      store.selectedMailboxId === mb.id ? 'text-white/85 hover:text-white' : 'text-[var(--label-secondary)] hover:text-[var(--label-primary)]'
                    ]"
                    title="编辑 IMAP/SMTP 凭据"
                  >
                    <KeyRound class="w-2.5 h-2.5" />
                  </button>

                  <button
                    type="button"
                    @click.stop="openMailboxSettings(mb)"
                    :class="[
                      'p-0.5 rounded opacity-0 group-hover/mb:opacity-100 mac-touch-show transition',
                      store.selectedMailboxId === mb.id ? 'text-white/85 hover:text-white' : 'text-[var(--label-secondary)] hover:text-[var(--label-primary)]'
                    ]"
                    title="多分组与 VIP 设置"
                  >
                    <SlidersHorizontal class="w-2.5 h-2.5" />
                  </button>

                  <button
                    v-if="!mb.is_default"
                    type="button"
                    @click.stop="handleDeleteMailbox(mb)"
                    :class="[
                      'p-0.5 rounded opacity-0 group-hover/mb:opacity-100 mac-touch-show transition',
                      store.selectedMailboxId === mb.id ? 'text-white/85 hover:text-white' : 'text-[var(--label-secondary)] hover:text-[var(--apple-red)]'
                    ]"
                    title="删除邮箱"
                  >
                    <Trash2 class="w-2.5 h-2.5" />
                  </button>

                  <span
                    v-if="mb.unread_count"
                    :class="[
                      'text-[11px] tabular-nums font-medium pl-1',
                      store.selectedMailboxId === mb.id ? 'text-[var(--selection-subtext)]' : 'text-[var(--label-secondary)]'
                    ]"
                  >
                    {{ mb.unread_count }}
                  </span>
                </div>
              </div>
            </div>

            <!-- macOS Finder-Style Drop Line (After) -->
            <div
              v-if="dragMode === 'group' && groupDropTargetId === grp.group_id && groupDropPosition === 'after'"
              class="absolute -bottom-[1px] left-2 right-2 h-[2px] bg-[var(--apple-blue)] rounded-full z-20 pointer-events-none flex items-center"
            >
              <span class="w-2 h-2 -ml-1 rounded-full bg-[var(--apple-blue)] ring-2 ring-white dark:ring-[#1c1c1e]" />
            </div>
          </div>
        </div>
      </div>

      <!-- Section 3: 邮件标签 (Tags) -->
      <div v-if="store.tags && store.tags.length > 0" class="space-y-1 pt-2 border-t border-[var(--separator)]">
        <div class="px-2.5 text-[11px] font-semibold text-[var(--label-secondary)]">
          标签
        </div>
        <div class="space-y-[2px]">
          <button
            v-for="t in store.tags"
            :key="t.id"
            type="button"
            @click="store.selectScope({ tag: store.selectedTag === t.name ? null : t.name })"
            :class="[
              'w-full h-[28px] px-2.5 rounded-[7px] text-[12.5px] flex items-center gap-2 transition-colors',
              store.selectedTag === t.name
                ? 'bg-[var(--selection-bg)] text-white font-medium'
                : 'text-[var(--label-primary)] hover:bg-[var(--fill-hover)]'
            ]"
          >
            <span
              :class="[
                'font-mono text-[11px] flex-shrink-0',
                store.selectedTag === t.name ? 'text-white/85' : 'text-[var(--label-tertiary)]'
              ]"
            >
              #
            </span>
            <span class="truncate">{{ t.name }}</span>
          </button>
        </div>
      </div>
    </div>

    <!-- Bottom Status & Quick Spotlight / Settings Bar -->
    <div class="min-h-[36px] py-1.5 px-3 pb-safe mac-hairline-t flex items-center justify-between text-[11px] text-[var(--label-secondary)] flex-shrink-0">
      <button
        type="button"
        @click="store.isCommandOpen = true; store.isMobileNavOpen = false"
        class="flex items-center gap-1.5 hover:text-[var(--label-primary)] transition"
      >
        <Search class="w-3 h-3" />
        <span>快捷命令</span>
        <kbd class="mac-kbd hidden sm:inline">⌘K</kbd>
      </button>

      <button
        type="button"
        @click="store.isSettingsOpen = true; store.isMobileNavOpen = false"
        class="flex items-center gap-1 hover:text-[var(--label-primary)] transition"
        title="设置 (⌘,)"
      >
        <Settings class="w-3.5 h-3.5" />
        <span>设置</span>
      </button>
    </div>

    <!-- Teleported macOS Sheets so backdrop-filter & z-index render above whole window -->
    <Teleport to="body">
      <!-- Sheet 1: Create Group -->
      <Transition name="mac-sheet-fade">
        <div
          v-if="showNewLabelModal"
          class="fixed inset-0 mac-backdrop z-[60] flex items-center justify-center p-4 select-none"
          @click.self="showNewLabelModal = false"
        >
          <div class="mac-sheet rounded-[16px] w-full max-w-[320px] p-5 space-y-4">
            <div class="flex items-center justify-between">
              <h3 class="text-[14px] font-semibold text-[var(--label-primary)]">新建智能分组</h3>
              <button
                type="button"
                @click="showNewLabelModal = false"
                class="w-6 h-6 rounded-full bg-[var(--fill-tertiary)] hover:bg-[var(--fill-secondary)] flex items-center justify-center text-[var(--label-secondary)] transition"
              >
                <X class="w-3.5 h-3.5" />
              </button>
            </div>

            <input
              v-model="newLabelName"
              @keydown.enter.prevent="submitCreateLabel"
              type="text"
              placeholder="输入分组名称..."
              autofocus
              class="w-full h-9 px-3 rounded-[9px] bg-[var(--bg-input-solid)] border border-[var(--separator-strong)] focus:border-[var(--apple-blue)] focus:ring-2 focus:ring-[var(--apple-blue)]/20 text-[13px] text-[var(--label-primary)] placeholder-[var(--label-secondary)] focus:outline-none transition"
            />

            <div class="flex items-center justify-end gap-2 pt-1">
              <button
                type="button"
                @click="showNewLabelModal = false"
                class="mac-btn-secondary h-[30px] px-3.5 rounded-[8px] text-[12.5px] font-medium"
              >
                取消
              </button>
              <button
                type="button"
                @click="submitCreateLabel"
                :disabled="!newLabelName.trim()"
                class="mac-btn-blue h-[30px] px-4 rounded-[8px] text-[12.5px] font-medium disabled:opacity-40"
              >
                创建
              </button>
            </div>
          </div>
        </div>
      </Transition>

      <!-- Sheet 2: Create Local Mailbox -->
      <Transition name="mac-sheet-fade">
        <div
          v-if="newMailboxDomain"
          class="fixed inset-0 mac-backdrop z-[60] flex items-center justify-center p-4 select-none"
          @click.self="newMailboxDomain = null"
        >
          <div class="mac-sheet rounded-[16px] w-full max-w-[360px] p-5 space-y-4">
            <div class="flex items-center justify-between">
              <h3 class="text-[14px] font-semibold text-[var(--label-primary)]">开通新邮箱</h3>
              <button
                type="button"
                @click="newMailboxDomain = null"
                class="w-6 h-6 rounded-full bg-[var(--fill-tertiary)] hover:bg-[var(--fill-secondary)] flex items-center justify-center text-[var(--label-secondary)] transition"
              >
                <X class="w-3.5 h-3.5" />
              </button>
            </div>

            <div class="space-y-2.5">
              <div class="flex items-center h-9 rounded-[9px] bg-[var(--bg-input-solid)] border border-[var(--separator-strong)] focus-within:border-[var(--apple-blue)] focus-within:ring-2 focus-within:ring-[var(--apple-blue)]/20 overflow-hidden transition">
                <input
                  v-model="newMailboxPrefix"
                  @keydown.enter.prevent="submitAddMailbox"
                  type="text"
                  placeholder="前缀 (如 hello)"
                  autofocus
                  class="flex-1 min-w-0 bg-transparent px-3 text-[13px] font-mono text-[var(--label-primary)] placeholder-[var(--label-secondary)] focus:outline-none"
                />
                <span class="h-full flex items-center px-3 text-[12.5px] font-mono text-[var(--label-secondary)] bg-[var(--fill-quaternary)] border-l border-[var(--separator)]">
                  @{{ newMailboxDomain.name }}
                </span>
              </div>

              <input
                v-model="newMailboxNote"
                @keydown.enter.prevent="submitAddMailbox"
                type="text"
                placeholder="备注名称 (选填)"
                class="w-full h-9 px-3 rounded-[9px] bg-[var(--bg-input-solid)] border border-[var(--separator-strong)] focus:border-[var(--apple-blue)] focus:ring-2 focus:ring-[var(--apple-blue)]/20 text-[13px] text-[var(--label-primary)] placeholder-[var(--label-secondary)] focus:outline-none transition"
              />
            </div>

            <div class="flex items-center justify-end gap-2 pt-1">
              <button
                type="button"
                @click="newMailboxDomain = null"
                class="mac-btn-secondary h-[30px] px-3.5 rounded-[8px] text-[12.5px] font-medium"
              >
                取消
              </button>
              <button
                type="button"
                @click="submitAddMailbox"
                :disabled="!newMailboxPrefix.trim()"
                class="mac-btn-blue h-[30px] px-4 rounded-[8px] text-[12.5px] font-medium disabled:opacity-40"
              >
                开通
              </button>
            </div>
          </div>
        </div>
      </Transition>

      <!-- Sheet 3: Drag & Drop Move vs Co-exist -->
      <Transition name="mac-sheet-fade">
        <div
          v-if="pendingDropAction"
          class="fixed inset-0 mac-backdrop z-[60] flex items-center justify-center p-4 select-none"
          @click.self="pendingDropAction = null"
        >
          <div class="mac-sheet rounded-[16px] w-full max-w-[340px] p-5 space-y-4">
            <div class="space-y-1.5">
              <h3 class="text-[14px] font-semibold text-[var(--label-primary)]">归入智能分组</h3>
              <p class="text-[12.5px] text-[var(--label-secondary)] leading-relaxed">
                选择如何将 <span class="font-mono text-[var(--label-primary)] font-medium">{{ pendingDropAction.mailbox.address }}</span>
                归入 <span class="text-[var(--label-primary)] font-medium">「{{ pendingDropAction.targetGroup.name }}」</span>：
              </p>
            </div>

            <div class="flex items-center justify-end gap-2 pt-1">
              <button
                type="button"
                @click="pendingDropAction = null"
                class="mac-btn-secondary h-[30px] px-3 rounded-[8px] text-[12.5px] font-medium"
              >
                取消
              </button>
              <button
                type="button"
                @click="executeDropAction('move')"
                class="mac-btn-secondary h-[30px] px-3.5 rounded-[8px] text-[12.5px] font-medium text-[var(--apple-blue)]"
              >
                移动至此组
              </button>
              <button
                type="button"
                @click="executeDropAction('copy')"
                class="mac-btn-blue h-[30px] px-3.5 rounded-[8px] text-[12.5px] font-medium"
              >
                多组共存
              </button>
            </div>
          </div>
        </div>
      </Transition>

      <!-- Sheet 4: Mailbox Multi-Group & VIP Settings -->
      <Transition name="mac-sheet-fade">
        <div
          v-if="editingMailbox"
          class="fixed inset-0 mac-backdrop z-[60] flex items-center justify-center p-4 select-none"
          @click.self="editingMailbox = null"
        >
          <div class="mac-sheet rounded-[16px] w-full max-w-[360px] p-5 space-y-4">
            <div class="flex items-center justify-between gap-2">
              <div class="min-w-0">
                <h3 class="text-[13.5px] font-semibold text-[var(--label-primary)]">邮箱分组与 VIP</h3>
                <p class="text-[11.5px] font-mono text-[var(--label-secondary)] truncate">
                  {{ editingMailbox.address }}
                </p>
              </div>
              <button
                type="button"
                @click="editingMailbox = null"
                class="w-6 h-6 rounded-full bg-[var(--fill-tertiary)] hover:bg-[var(--fill-secondary)] flex items-center justify-center text-[var(--label-secondary)] transition flex-shrink-0"
              >
                <X class="w-3.5 h-3.5" />
              </button>
            </div>

            <div class="space-y-3.5">
              <div>
                <div class="flex items-center justify-between mb-2">
                  <span class="text-[12px] font-medium text-[var(--label-secondary)]">所属分组（可多选）</span>
                  <button
                    type="button"
                    @click="openNewLabelModal(true)"
                    class="text-[12px] text-[var(--apple-blue)] hover:opacity-80 flex items-center gap-0.5 font-medium transition"
                  >
                    <Plus class="w-3.5 h-3.5" />
                    <span>新建分组</span>
                  </button>
                </div>

                <div class="flex flex-wrap gap-1.5">
                  <button
                    v-for="lbl in availableLabels"
                    :key="lbl.id"
                    type="button"
                    @click="toggleEditLabel(lbl.id)"
                    :class="[
                      'px-2.5 py-1 rounded-[8px] text-[12px] flex items-center gap-1.5 transition border',
                      editForm.label_ids.includes(lbl.id)
                        ? 'bg-[var(--fill-active-subtle)] border-[var(--apple-blue)] text-[var(--apple-blue)] font-medium'
                        : 'bg-[var(--fill-quaternary)] border-[var(--separator)] text-[var(--label-primary)] hover:bg-[var(--fill-hover)]'
                    ]"
                  >
                    <span>{{ lbl.name }}</span>
                    <Check v-if="editForm.label_ids.includes(lbl.id)" class="w-3 h-3" />
                  </button>
                </div>
              </div>

              <!-- Authentic macOS/iOS Switch Row for VIP -->
              <div
                @click="editForm.is_vip = !editForm.is_vip"
                class="flex items-center justify-between px-3.5 py-2.5 rounded-[10px] bg-[var(--fill-quaternary)] border border-[var(--separator)] cursor-pointer"
              >
                <span class="text-[13px] text-[var(--label-primary)] font-medium">
                  设为 VIP 重点邮箱
                </span>

                <button
                  type="button"
                  role="switch"
                  :aria-checked="editForm.is_vip"
                  :class="[
                    'w-[38px] h-[22px] rounded-full p-[2px] transition-colors duration-200 flex items-center',
                    editForm.is_vip ? 'bg-[#34C759]' : 'bg-[var(--fill-secondary)]'
                  ]"
                >
                  <span
                    :class="[
                      'w-[18px] h-[18px] rounded-full bg-white shadow transition-transform duration-200',
                      editForm.is_vip ? 'translate-x-[16px]' : 'translate-x-0'
                    ]"
                  />
                </button>
              </div>
            </div>

            <div class="flex items-center justify-end gap-2 pt-1">
              <button
                type="button"
                @click="editingMailbox = null"
                class="mac-btn-secondary h-[30px] px-3.5 rounded-[8px] text-[12.5px] font-medium"
              >
                取消
              </button>
              <button
                type="button"
                @click="saveMailboxSettings"
                class="mac-btn-blue h-[30px] px-4 rounded-[8px] text-[12.5px] font-medium"
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
