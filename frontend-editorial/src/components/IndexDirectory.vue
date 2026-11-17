<script setup>
import { ref, computed } from 'vue'
import { useMailStore } from '../stores/mail'
import PrismWordmark from './PrismWordmark.vue'
import {
  Plus, X, Inbox, Star, Send, FileText, Trash2,
  ChevronRight, ShieldCheck, SlidersHorizontal,
  Check, RefreshCw, KeyRound, Settings
} from 'lucide-vue-next'

const store = useMailStore()

const collapsedGroups = ref(new Set())
const syncingMailboxIds = ref(new Set())

// Editorial Micro-Modals
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

const folderItems = computed(() => [
  { id: 'inbox', code: '01', label: '收件箱', icon: Inbox, count: store.folderCounts.inbox, primary: true },
  { id: 'starred', code: '02', label: '星标邮件', icon: Star, count: store.folderCounts.starred },
  { id: 'sent', code: '03', label: '已发送', icon: Send, count: store.folderCounts.sent },
  { id: 'drafts', code: '04', label: '草稿箱', icon: FileText, count: store.folderCounts.drafts },
  { id: 'trash', code: '05', label: '废纸篓', icon: Trash2, count: store.folderCounts.trash }
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
      store.notify(`同步异常: ${res.error || '请检查授权密码'}`, 'error')
    } else {
      store.notify(`${mb.address} 已同步`, 'success')
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
  if (store.selectedFolder === folderId && folderId === 'inbox' && store.hasActiveScope) {
    store.selectScope({ domainId: null, mailboxId: null, labelId: null, smartFilter: null })
  } else {
    store.selectedFolder = folderId
    store.isMobileNavOpen = false
    if (typeof window !== 'undefined' && window.innerWidth < 1024) {
      store.closeMail()
    }
    store.fetchMails()
  }
}

const openDomainDns = (domainId) => {
  const dom = store.domains.find(d => d.id === domainId)
  if (dom) {
    store.activeDomainDns = dom
    store.isMobileNavOpen = false
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
    title: '移除分组',
    message: `确定移除「${grp.name}」吗？组内邮箱不会被删除。`,
    confirmText: '移除',
    danger: true
  })
  if (ok) {
    await store.deleteMailboxLabel(grp.label_id)
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
    await store.deleteMailbox(mb.id)
  }
}

// Drag & Drop Reordering & Categorization
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
  store.notify(`已更新 ${mailbox.address} 所属分组`, 'success')
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
    store.notify('邮箱设置已保存', 'success')
    editingMailbox.value = null
  }
}
</script>

<template>
  <aside
    class="flex-shrink-0 flex flex-col select-none bg-[var(--bg-linen)] border-r border-[var(--rule-faint)] overflow-hidden"
  >
    <!-- Mobile Drawer Header -->
    <div class="lg:hidden h-11 px-3.5 border-b border-[var(--rule-medium)] flex items-center justify-between flex-shrink-0">
      <PrismWordmark class="h-[17px] w-auto text-[var(--ink-primary)]" />
      <button
        type="button"
        @click="store.isMobileNavOpen = false"
        class="h-7 w-7 ed-btn-outline flex items-center justify-center text-[var(--ink-muted)] hover:text-[var(--ink-primary)]"
        title="收起目录"
      >
        <X class="w-3.5 h-3.5" />
      </button>
    </div>

    <!-- Scrollable Architectural Index -->
    <div class="flex-1 overflow-y-auto py-3.5 space-y-5">
      <!-- SECTION 01: ARCHIVE FOLDERS -->
      <section>
        <div class="px-3.5 pb-2 flex items-center justify-between border-b border-[var(--rule-faint)]">
          <span class="ed-rubric">邮箱目录</span>
          <span class="ed-rubric opacity-65">FOLDERS</span>
        </div>

        <nav class="mt-1">
          <button
            v-for="item in folderItems"
            :key="item.id"
            @click="handleSelectFolder(item.id)"
            :class="[
              'w-full h-8 px-3.5 flex items-center justify-between text-[12.5px] transition relative border-l-[2.5px]',
              store.selectedFolder === item.id && !store.hasActiveScope
                ? 'border-[var(--accent-vermilion)] bg-[var(--bg-active)] text-[var(--ink-primary)] font-medium'
                : store.selectedFolder === item.id
                  ? 'border-[var(--ink-primary)] bg-[var(--bg-subtle)] text-[var(--ink-primary)] font-medium'
                  : 'border-transparent text-[var(--ink-secondary)] hover:bg-[var(--bg-hover)] hover:text-[var(--ink-primary)]'
            ]"
          >
            <span class="flex items-center gap-2.5 min-w-0">
              <component
                :is="item.icon"
                :class="[
                  'w-3.5 h-3.5 stroke-[1.6]',
                  store.selectedFolder === item.id
                    ? 'text-[var(--accent-vermilion)]'
                    : 'text-[var(--ink-muted)]'
                ]"
              />
              <span class="truncate">{{ item.label }}</span>
            </span>

            <span
              v-if="item.count"
              :class="[
                'text-[11px] font-mono tabular-nums',
                item.primary && store.selectedFolder === item.id
                  ? 'text-[var(--accent-vermilion)] font-semibold'
                  : 'text-[var(--ink-muted)]'
              ]"
            >
              {{ item.count }}
            </span>
          </button>
        </nav>
      </section>

      <!-- SECTION 02: BUSINESS MATRIX / DOMAIN ASSETS -->
      <section>
        <div class="px-3.5 pb-2 border-b border-[var(--rule-faint)] space-y-2">
          <div class="flex items-center justify-between">
            <span class="ed-rubric">
              {{ store.groupingMode === 'tags' ? '邮箱分组' : '域名列表' }}
            </span>

            <div class="flex items-center gap-1">
              <button
                @click="store.openExternalModal()"
                class="px-1.5 py-0.5 text-[10.5px] font-mono text-[var(--ink-muted)] hover:text-[var(--accent-vermilion)] hover:bg-[var(--bg-hover)] rounded-[2px] transition"
                title="添加外部邮箱"
              >
                +外部
              </button>
              <button
                @click="store.groupingMode === 'tags' ? openNewLabelModal(false) : (store.isDomainModalOpen = true, store.isMobileNavOpen = false)"
                class="p-0.5 text-[var(--ink-muted)] hover:text-[var(--ink-primary)] hover:bg-[var(--bg-hover)] rounded-[2px] transition"
                :title="store.groupingMode === 'tags' ? '新建分组' : '添加域名'"
              >
                <Plus class="w-3.5 h-3.5" />
              </button>
            </div>
          </div>

          <!-- Architectural Segmented Mode Switch -->
          <div class="grid grid-cols-2 border border-[var(--rule-medium)] rounded-[2px] p-[1px] bg-[var(--bg-subtle)] text-[11px]">
            <button
              @click="store.switchGroupingMode('tags')"
              :class="[
                'py-1 text-center transition rounded-[1px]',
                store.groupingMode === 'tags'
                  ? 'bg-[var(--ink-primary)] text-[var(--bg-salon)] font-medium'
                  : 'text-[var(--ink-muted)] hover:text-[var(--ink-primary)]'
              ]"
            >
              分组
            </button>
            <button
              @click="store.switchGroupingMode('domain_first')"
              :class="[
                'py-1 text-center transition rounded-[1px]',
                store.groupingMode === 'domain_first'
                  ? 'bg-[var(--ink-primary)] text-[var(--bg-salon)] font-medium'
                  : 'text-[var(--ink-muted)] hover:text-[var(--ink-primary)]'
              ]"
            >
              域名
            </button>
          </div>
        </div>

        <!-- Group / Domain Tree -->
        <div class="mt-1.5">
          <div
            v-for="grp in displayGroups"
            :key="grp.group_id"
            class="relative"
            @dragover.prevent="handleGroupDragOver($event, grp)"
            @dragleave="handleGroupDragLeave($event, grp)"
            @drop="handleDrop($event, grp)"
          >
            <!-- Vermilion Reorder Indicator (Before) -->
            <div
              v-if="dragMode === 'group' && groupDropTargetId === grp.group_id && groupDropPosition === 'before'"
              class="absolute top-0 left-3 right-3 h-[2px] bg-[var(--accent-vermilion)] z-20 pointer-events-none"
            />

            <!-- Group Header Row -->
            <div
              :draggable="canReorderGroup(grp)"
              @dragstart="handleGroupDragStart($event, grp)"
              @dragend="resetDragState"
              @click="handleSelectGroup(grp)"
              :class="[
                'h-8 px-3 flex items-center justify-between cursor-pointer transition group/hdr border-l-[2.5px]',
                dragOverGroupId === grp.group_id
                  ? 'border-[var(--accent-vermilion)] bg-[var(--accent-vermilion-soft)] ring-1 ring-inset ring-[var(--accent-vermilion-border)]'
                  : isGroupSelected(grp)
                    ? 'border-[var(--accent-vermilion)] bg-[var(--bg-active)] text-[var(--ink-primary)] font-medium'
                    : 'border-transparent text-[var(--ink-secondary)] hover:bg-[var(--bg-hover)] hover:text-[var(--ink-primary)]',
                draggingGroupId === grp.group_id ? 'opacity-40' : ''
              ]"
            >
              <div class="flex items-center gap-1.5 min-w-0">
                <button
                  @click.stop="toggleGroupCollapse(grp.group_id)"
                  class="p-0.5 text-[var(--ink-muted)] hover:text-[var(--ink-primary)] transition flex-shrink-0"
                >
                  <ChevronRight
                    :class="[
                      'w-3.5 h-3.5 transition-transform duration-150',
                      !isCollapsed(grp.group_id) ? 'rotate-90' : ''
                    ]"
                  />
                </button>
                <span class="text-[12.5px] truncate">{{ grp.name }}</span>
                <span class="text-[10px] font-mono tabular-nums text-[var(--ink-faint)]">
                  [{{ grp.mailboxes?.length || 0 }}]
                </span>
              </div>

              <div class="flex items-center gap-1 flex-shrink-0">
                <button
                  v-if="grp.domain_id && !grp.is_external"
                  @click.stop="openDomainDns(grp.domain_id)"
                  class="p-0.5 text-[var(--ink-muted)] hover:text-[var(--accent-forest)] opacity-0 group-hover/hdr:opacity-100 ed-touch-show transition"
                  title="查看 DNS 解析记录"
                >
                  <ShieldCheck class="w-3 h-3" />
                </button>
                <button
                  v-if="grp.domain_id"
                  @click.stop="grp.is_external ? store.openExternalModal() : openAddMailboxModal(grp.domain_id)"
                  class="p-0.5 text-[var(--ink-muted)] hover:text-[var(--ink-primary)] opacity-0 group-hover/hdr:opacity-100 ed-touch-show transition"
                  :title="grp.is_external ? '添加外部邮箱' : '在此域名下创建邮箱'"
                >
                  <Plus class="w-3 h-3" />
                </button>
                <button
                  v-if="store.groupingMode === 'tags' && grp.label_id && grp.label_id !== 0"
                  @click.stop="handleDeleteLabel(grp)"
                  class="p-0.5 text-[var(--ink-muted)] hover:text-[var(--accent-vermilion)] opacity-0 group-hover/hdr:opacity-100 ed-touch-show transition"
                  title="移除此分组"
                >
                  <Trash2 class="w-3 h-3" />
                </button>
                <span
                  v-if="grp.unread_count"
                  class="text-[11px] font-mono tabular-nums text-[var(--accent-vermilion)] font-medium pl-0.5"
                >
                  {{ grp.unread_count }}
                </span>
              </div>
            </div>

            <!-- Nested Mailboxes along Architectural Vertical Rule -->
            <div
              v-if="grp.mailboxes && grp.mailboxes.length > 0 && !isCollapsed(grp.group_id)"
              class="ml-[21px] border-l border-[var(--rule-medium)] my-0.5"
            >
              <div
                v-for="mb in grp.mailboxes"
                :key="`${grp.group_id}_${mb.id}`"
                :draggable="canDragDesktop()"
                @dragstart="handleMailboxDragStart($event, mb, grp)"
                @dragend="resetDragState"
                @click.stop="handleSelectMailbox(mb)"
                :class="[
                  'h-7 pl-2.5 pr-3 flex items-center justify-between text-[11.5px] cursor-pointer transition group/mb border-l-[2px] -ml-[1px]',
                  store.selectedMailboxId === mb.id
                    ? 'border-[var(--accent-vermilion)] bg-[var(--bg-active)] text-[var(--ink-primary)] font-medium'
                    : 'border-transparent text-[var(--ink-muted)] hover:bg-[var(--bg-hover)] hover:text-[var(--ink-primary)]'
                ]"
                :title="mb.address"
              >
                <div class="flex items-center min-w-0">
                  <span
                    :class="[
                      'font-mono text-[11px] truncate',
                      mb.unread_count && store.selectedMailboxId !== mb.id
                        ? 'text-[var(--ink-primary)] font-medium'
                        : ''
                    ]"
                  >
                    {{ formatMailboxLabel(mb) }}
                  </span>
                </div>

                <div class="flex items-center gap-0.5 flex-shrink-0">
                  <span
                    v-if="mb.is_external && mb.sync_status && mb.sync_status.startsWith('error')"
                    class="text-[9.5px] font-mono px-1 border border-[var(--accent-vermilion-border)] bg-[var(--accent-vermilion-soft)] text-[var(--accent-vermilion)]"
                    :title="mb.sync_status"
                  >
                    异常
                  </span>
                  <span
                    v-if="mb.is_vip"
                    class="text-[9.5px] font-mono px-1 border border-[var(--rule-faint)] text-[var(--ink-muted)] lg:group-hover/mb:hidden"
                  >
                    重点
                  </span>
                  <button
                    v-if="mb.is_external"
                    @click.stop="handleSyncExternal(mb)"
                    class="p-0.5 text-[var(--ink-muted)] hover:text-[var(--ink-primary)] opacity-0 group-hover/mb:opacity-100 ed-touch-show transition"
                    title="立即同步"
                  >
                    <RefreshCw :class="['w-2.5 h-2.5', { 'animate-spin': syncingMailboxIds.has(mb.id) }]" />
                  </button>
                  <button
                    v-if="mb.is_external"
                    @click.stop="store.openExternalModal(mb)"
                    class="p-0.5 text-[var(--ink-muted)] hover:text-[var(--ink-primary)] opacity-0 group-hover/mb:opacity-100 ed-touch-show transition"
                    title="编辑连接凭据"
                  >
                    <KeyRound class="w-2.5 h-2.5" />
                  </button>
                  <button
                    @click.stop="openMailboxSettings(mb)"
                    class="p-0.5 text-[var(--ink-muted)] hover:text-[var(--ink-primary)] opacity-0 group-hover/mb:opacity-100 ed-touch-show transition"
                    title="分组归属与重点标记"
                  >
                    <SlidersHorizontal class="w-2.5 h-2.5" />
                  </button>
                  <button
                    v-if="!mb.is_default"
                    @click.stop="handleDeleteMailbox(mb)"
                    class="p-0.5 text-[var(--ink-muted)] hover:text-[var(--accent-vermilion)] opacity-0 group-hover/mb:opacity-100 ed-touch-show transition"
                    title="删除邮箱"
                  >
                    <Trash2 class="w-2.5 h-2.5" />
                  </button>
                  <span
                    v-if="mb.unread_count"
                    class="text-[10.5px] font-mono tabular-nums text-[var(--ink-primary)] font-semibold pl-1"
                  >
                    {{ mb.unread_count }}
                  </span>
                </div>
              </div>
            </div>

            <!-- Vermilion Reorder Indicator (After) -->
            <div
              v-if="dragMode === 'group' && groupDropTargetId === grp.group_id && groupDropPosition === 'after'"
              class="absolute bottom-0 left-3 right-3 h-[2px] bg-[var(--accent-vermilion)] z-20 pointer-events-none"
            />
          </div>
        </div>
      </section>

      <!-- SECTION 03: CONTENT TAGS -->
      <section v-if="store.tags && store.tags.length > 0">
        <div class="px-3.5 pb-1.5 flex items-center justify-between border-b border-[var(--rule-faint)]">
          <span class="ed-rubric">邮件标签</span>
          <span class="ed-rubric opacity-65">TAGS</span>
        </div>
        <div class="mt-1">
          <button
            v-for="t in store.tags"
            :key="t.id"
            @click="store.selectScope({ tag: store.selectedTag === t.name ? null : t.name })"
            :class="[
              'w-full h-7 px-3.5 flex items-center gap-2 text-[12px] transition border-l-[2.5px]',
              store.selectedTag === t.name
                ? 'border-[var(--accent-vermilion)] bg-[var(--bg-active)] text-[var(--ink-primary)] font-medium'
                : 'border-transparent text-[var(--ink-secondary)] hover:bg-[var(--bg-hover)]'
            ]"
          >
            <span class="font-mono text-[11px] text-[var(--ink-muted)]">#</span>
            <span class="truncate">{{ t.name }}</span>
          </button>
        </div>
      </section>
    </div>

    <!-- Bottom Colophon Strip -->
    <div class="min-h-[32px] py-1.5 px-3.5 pb-safe border-t border-[var(--rule-faint)] flex items-center justify-between text-[11px] text-[var(--ink-muted)]">
      <PrismWordmark class="h-[11.5px] w-auto text-[var(--ink-muted)] opacity-70" />
      <button
        type="button"
        @click="store.isSettingsOpen = true; store.isMobileNavOpen = false"
        class="inline-flex items-center gap-1 text-[var(--ink-secondary)] hover:text-[var(--ink-primary)] transition"
        title="设置 (⌘,)"
      >
        <Settings class="w-3 h-3" />
        <span>设置</span>
      </button>
    </div>

    <Teleport to="body">
      <!-- MICRO MODAL 1: Create Group -->
      <Transition name="folio-fade">
        <div
          v-if="showNewLabelModal"
          class="fixed inset-0 ed-backdrop z-[60] flex items-center justify-center p-4"
          @click.self="showNewLabelModal = false"
        >
          <div class="ed-folio-modal w-full max-w-xs p-5 space-y-4">
            <div class="flex items-start justify-between border-b border-[var(--rule-faint)] pb-2.5">
              <div>
                <h3 class="font-serif text-[16px] font-medium text-[var(--ink-primary)]">新建分组</h3>
              </div>
              <button @click="showNewLabelModal = false" class="text-[var(--ink-muted)] hover:text-[var(--ink-primary)]">
                <X class="w-4 h-4" />
              </button>
            </div>

            <input
              v-model="newLabelName"
              @keydown.enter.prevent="submitCreateLabel"
              type="text"
              placeholder="输入分组名称..."
              autofocus
              class="w-full bg-[var(--bg-input)] border border-[var(--rule-medium)] focus:border-[var(--rule-strong)] rounded-[2px] px-3 py-2 text-[12.5px] text-[var(--ink-primary)] placeholder-[var(--ink-faint)] focus:outline-none transition"
            />

            <div class="flex items-center justify-end gap-2 pt-2 border-t border-[var(--rule-faint)]">
              <button
                @click="showNewLabelModal = false"
                class="ed-btn-outline px-3 py-1.5 text-[12px]"
              >
                取消
              </button>
              <button
                @click="submitCreateLabel"
                :disabled="!newLabelName.trim()"
                class="ed-btn-ink px-4 py-1.5 text-[12px] font-medium disabled:opacity-40"
              >
                创建
              </button>
            </div>
          </div>
        </div>
      </Transition>

      <!-- MICRO MODAL 2: Create Local Mailbox -->
      <Transition name="folio-fade">
        <div
          v-if="newMailboxDomain"
          class="fixed inset-0 ed-backdrop z-[60] flex items-center justify-center p-4"
          @click.self="newMailboxDomain = null"
        >
          <div class="ed-folio-modal w-full max-w-sm p-5 space-y-4">
            <div class="flex items-start justify-between border-b border-[var(--rule-faint)] pb-2.5">
              <div>
                <h3 class="font-serif text-[16px] font-medium text-[var(--ink-primary)]">创建新邮箱</h3>
              </div>
              <button @click="newMailboxDomain = null" class="text-[var(--ink-muted)] hover:text-[var(--ink-primary)]">
                <X class="w-4 h-4" />
              </button>
            </div>

            <div class="space-y-2.5">
              <div class="flex items-center bg-[var(--bg-input)] border border-[var(--rule-medium)] focus-within:border-[var(--rule-strong)] rounded-[2px] overflow-hidden transition">
                <input
                  v-model="newMailboxPrefix"
                  @keydown.enter.prevent="submitAddMailbox"
                  type="text"
                  placeholder="前缀 (如 hello)"
                  autofocus
                  class="flex-1 min-w-0 bg-transparent px-3 py-2 text-[12.5px] font-mono text-[var(--ink-primary)] placeholder-[var(--ink-faint)] focus:outline-none"
                />
                <span class="px-3 py-2 text-[12px] font-mono text-[var(--ink-secondary)] border-l border-[var(--rule-faint)] bg-[var(--bg-subtle)]">
                  @{{ newMailboxDomain.name }}
                </span>
              </div>

              <input
                v-model="newMailboxNote"
                @keydown.enter.prevent="submitAddMailbox"
                type="text"
                placeholder="备注名称（选填）"
                class="w-full bg-[var(--bg-input)] border border-[var(--rule-medium)] focus:border-[var(--rule-strong)] rounded-[2px] px-3 py-2 text-[12.5px] text-[var(--ink-primary)] placeholder-[var(--ink-faint)] focus:outline-none transition"
              />
            </div>

            <div class="flex items-center justify-end gap-2 pt-2 border-t border-[var(--rule-faint)]">
              <button
                @click="newMailboxDomain = null"
                class="ed-btn-outline px-3 py-1.5 text-[12px]"
              >
                取消
              </button>
              <button
                @click="submitAddMailbox"
                :disabled="!newMailboxPrefix.trim()"
                class="ed-btn-ink px-4 py-1.5 text-[12px] font-medium disabled:opacity-40"
              >
                创建
              </button>
            </div>
          </div>
        </div>
      </Transition>

      <!-- MICRO MODAL 3: Drag & Drop Move vs Co-exist -->
      <Transition name="folio-fade">
        <div
          v-if="pendingDropAction"
          class="fixed inset-0 ed-backdrop z-[60] flex items-center justify-center p-4"
          @click.self="pendingDropAction = null"
        >
          <div class="ed-folio-modal w-full max-w-xs p-5 space-y-4">
            <div class="flex items-start justify-between border-b border-[var(--rule-faint)] pb-2.5">
              <div>
                <h3 class="font-serif text-[16px] font-medium text-[var(--ink-primary)]">调整邮箱分组</h3>
              </div>
              <button @click="pendingDropAction = null" class="text-[var(--ink-muted)] hover:text-[var(--ink-primary)]">
                <X class="w-4 h-4" />
              </button>
            </div>

            <p class="text-[12.5px] text-[var(--ink-secondary)] leading-relaxed">
              将邮箱 <span class="font-mono text-[var(--ink-primary)] font-medium">{{ pendingDropAction.mailbox.address }}</span>
              归入分组 <span class="text-[var(--ink-primary)] font-semibold">「{{ pendingDropAction.targetGroup.name }}」</span>：
            </p>

            <div class="flex items-center justify-end gap-2 pt-2 border-t border-[var(--rule-faint)]">
              <button
                @click="pendingDropAction = null"
                class="px-2.5 py-1.5 text-[12px] text-[var(--ink-muted)] hover:text-[var(--ink-primary)] transition"
              >
                取消
              </button>
              <button
                @click="executeDropAction('move')"
                class="ed-btn-outline px-3 py-1.5 text-[12px] font-medium"
              >
                移动至此组
              </button>
              <button
                @click="executeDropAction('copy')"
                class="ed-btn-ink px-3.5 py-1.5 text-[12px] font-medium"
              >
                多组共存
              </button>
            </div>
          </div>
        </div>
      </Transition>

      <!-- MICRO MODAL 4: Mailbox Multi-Group & VIP Settings -->
      <Transition name="folio-fade">
        <div
          v-if="editingMailbox"
          class="fixed inset-0 ed-backdrop z-[60] flex items-center justify-center p-4"
          @click.self="editingMailbox = null"
        >
          <div class="ed-folio-modal w-full max-w-sm p-5 space-y-4">
            <div class="flex items-start justify-between border-b border-[var(--rule-faint)] pb-2.5">
              <div class="min-w-0 pr-2">
                <span class="ed-rubric block">邮箱设置</span>
                <p class="font-mono text-[13px] font-semibold text-[var(--ink-primary)] truncate mt-0.5">
                  {{ editingMailbox.address }}
                </p>
              </div>
              <button @click="editingMailbox = null" class="text-[var(--ink-muted)] hover:text-[var(--ink-primary)] flex-shrink-0">
                <X class="w-4 h-4" />
              </button>
            </div>

            <div class="space-y-3.5">
              <div>
                <div class="flex items-center justify-between mb-2">
                  <span class="ed-rubric">所属分组</span>
                  <button
                    @click="openNewLabelModal(true)"
                    class="text-[11px] font-mono text-[var(--accent-vermilion)] hover:underline flex items-center gap-0.5"
                  >
                    <Plus class="w-3 h-3" />
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
                      'px-2.5 py-1 rounded-[2px] text-[12px] flex items-center gap-1.5 transition border',
                      editForm.label_ids.includes(lbl.id)
                        ? 'bg-[var(--bg-active)] border-[var(--rule-strong)] text-[var(--ink-primary)] font-medium'
                        : 'bg-[var(--bg-input)] border-[var(--rule-faint)] text-[var(--ink-secondary)] hover:border-[var(--rule-medium)]'
                    ]"
                  >
                    <span>{{ lbl.name }}</span>
                    <Check v-if="editForm.label_ids.includes(lbl.id)" class="w-3 h-3 text-[var(--accent-vermilion)]" />
                  </button>
                </div>
              </div>

              <label class="flex items-center justify-between px-3 py-2.5 rounded-[2px] bg-[var(--bg-subtle)] border border-[var(--rule-faint)] cursor-pointer">
                <span class="text-[12.5px] text-[var(--ink-primary)]">
                  设为重点邮箱 (VIP)
                </span>
                <input
                  type="checkbox"
                  v-model="editForm.is_vip"
                  class="w-4 h-4 accent-[#C84B31] cursor-pointer"
                />
              </label>
            </div>

            <div class="flex items-center justify-end gap-2 pt-2 border-t border-[var(--rule-faint)]">
              <button
                @click="editingMailbox = null"
                class="ed-btn-outline px-3 py-1.5 text-[12px]"
              >
                取消
              </button>
              <button
                @click="saveMailboxSettings"
                class="ed-btn-ink px-4 py-1.5 text-[12px] font-medium"
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
