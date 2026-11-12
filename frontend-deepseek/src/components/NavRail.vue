<script setup>
import { ref, computed } from 'vue'
import { useMailStore } from '../stores/mail'
import {
  Plus, X, Inbox, Star, Send, FileText, Trash2,
  ChevronRight, ShieldCheck, SlidersHorizontal,
  Check, Sparkles, RefreshCw, KeyRound
} from 'lucide-vue-next'

const store = useMailStore()
const chibiImgUrl = `${import.meta.env.BASE_URL}deepseek-chibi-hug.png`

const LABEL_COLORS = [
  '#4D6BFE', '#38BDF8', '#10B981', '#F59E0B', '#EC4899', '#8B5CF6', '#F43F5E'
]

const collapsedGroups = ref(new Set())
const syncingMailboxIds = ref(new Set())

// Chibi Companion Poke Animation State
const isPoking = ref(false)
const showBubblePop = ref(false)
let pokeTimer = null

const pokeWhale = () => {
  store.pokeWhale()
  isPoking.value = false
  showBubblePop.value = false
  requestAnimationFrame(() => {
    isPoking.value = true
    showBubblePop.value = true
  })
  clearTimeout(pokeTimer)
  pokeTimer = setTimeout(() => {
    isPoking.value = false
    showBubblePop.value = false
  }, 560)
}

// Custom Micro-Modals
const showNewLabelModal = ref(false)
const newLabelName = ref('')
const newLabelColor = ref('#4D6BFE')
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
    color: '#4D6BFE',
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
      .map(g => ({ id: g.label_id, name: g.name, color: g.color }))
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
      store.notify(`${mb.address} 潜航同步完成 🫧`, 'success')
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
    store.fetchMails()
  }
}

const toggleVipScope = () => {
  if (store.selectedSmartFilter === 'vip') {
    store.selectScope(null)
  } else {
    store.selectedFolder = 'inbox'
    store.selectScope({ smartFilter: 'vip' })
  }
}

const openDomainDns = (domainId) => {
  const dom = store.domains.find(d => d.id === domainId)
  if (dom) store.activeDomainDns = dom
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
  newLabelColor.value = LABEL_COLORS[availableLabels.value.length % LABEL_COLORS.length]
  showNewLabelModal.value = true
}

const submitCreateLabel = async () => {
  const name = newLabelName.value.trim()
  if (!name) return
  const created = await store.createMailboxLabel(name, '', newLabelColor.value)
  if (assignNewLabelToEdit.value && created?.id && editingMailbox.value) {
    editForm.value.label_ids.push(created.id)
  }
  showNewLabelModal.value = false
}

const handleDeleteLabel = async (grp) => {
  const ok = await store.askConfirm({
    title: '移除分组确认',
    message: `确定要移除分组「${grp.name}」吗？组内的邮箱本体会安全保留哦~`,
    confirmText: '移除分组',
    danger: true
  })
  if (ok) {
    await store.deleteMailboxLabel(grp.label_id)
  }
}

const handleDeleteMailbox = async (mb) => {
  const ok = await store.askConfirm({
    title: '删除信箱确认',
    message: `确定要删除信箱 ${mb.address} 吗？删除后将无法恢复哦。`,
    confirmText: '确认删除',
    danger: true
  })
  if (ok) {
    await store.deleteMailbox(mb.id)
  }
}

// Drag & Drop Handlers
const canReorderGroup = (grp) => {
  return store.groupingMode === 'tags' && Boolean(grp.label_id && grp.label_id !== 0)
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
  store.notify(`已更新 ${mailbox.address} 归属分组 ✨`, 'success')
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
    store.notify('信箱分组与 VIP 设置已保存 🐋', 'success')
    editingMailbox.value = null
  }
}
</script>

<template>
  <aside class="flex-shrink-0 ds-card flex flex-col select-none p-3 overflow-hidden">
    <!-- Primary Luminous Compose CTA -->
    <div class="mb-3">
      <button
        @click="store.openCompose()"
        class="ds-btn-primary w-full h-10 px-3.5 rounded-2xl text-[13px] font-bold flex items-center justify-between group"
      >
        <span class="flex items-center gap-2">
          <!-- Cute Paper-Plane + Fin Sparkle SVG -->
          <svg class="w-4 h-4 transition-transform duration-300 group-hover:translate-x-0.5 group-hover:-translate-y-0.5" viewBox="0 0 24 24" fill="none">
            <path d="M21.5 3.5L10.5 14.5" stroke="currentColor" stroke-width="2" stroke-linecap="round" />
            <path d="M21.5 3.5L14.5 21L10.5 14.5L3.5 10.5L21.5 3.5Z" stroke="currentColor" stroke-width="2" stroke-linejoin="round" fill="rgba(255,255,255,0.22)" />
            <circle cx="5" cy="5" r="1.2" fill="#FFFFFF" />
          </svg>
          <span>撰写新信件</span>
        </span>
        <kbd class="px-1.5 py-0.5 rounded-md bg-white/20 text-white text-[10.5px] font-mono font-bold">C</kbd>
      </button>
    </div>

    <!-- Scrollable Navigation Matrix -->
    <div class="flex-1 overflow-y-auto pr-0.5 space-y-4 min-h-0">
      <!-- Core Folders -->
      <nav class="space-y-1">
        <div class="flex items-center justify-between px-2 pb-0.5">
          <span class="text-[10.5px] font-bold uppercase tracking-wider text-[var(--text-muted)]">信箱终端</span>
          <button
            @click="toggleVipScope"
            :class="[
              'px-2 py-0.5 rounded-full text-[10.5px] font-bold flex items-center gap-1 transition',
              store.selectedSmartFilter === 'vip'
                ? 'bg-amber-400/20 text-amber-600 dark:text-amber-300 border border-amber-400/40'
                : 'text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-hover)]'
            ]"
            title="只看 VIP 重点信箱"
          >
            <Sparkles class="w-2.5 h-2.5 text-amber-500" />
            <span>VIP</span>
          </button>
        </div>

        <button
          v-for="item in [
            { id: 'inbox', label: '收件箱', icon: Inbox, count: store.folderCounts.inbox, highlight: true },
            { id: 'starred', label: '星标信件', icon: Star, count: store.folderCounts.starred },
            { id: 'sent', label: '已投递', icon: Send, count: store.folderCounts.sent },
            { id: 'drafts', label: '草稿箱', icon: FileText, count: store.folderCounts.drafts },
            { id: 'trash', label: '废纸篓', icon: Trash2, count: store.folderCounts.trash }
          ]"
          :key="item.id"
          @click="handleSelectFolder(item.id)"
          :class="[
            'w-full h-8 px-2.5 rounded-xl text-[12.5px] flex items-center justify-between ds-spring',
            store.selectedFolder === item.id && !store.hasActiveScope
              ? 'bg-[var(--bg-active)] text-[#4D6BFE] dark:text-[#7DD3FC] font-bold border border-[#4D6BFE]/20'
              : store.selectedFolder === item.id
                ? 'bg-[var(--bg-subtle)] text-[var(--text-primary)] font-semibold'
                : 'text-[var(--text-secondary)] hover:bg-[var(--bg-hover)] hover:text-[var(--text-primary)]'
          ]"
        >
          <span class="flex items-center gap-2.5">
            <component
              :is="item.icon"
              :class="[
                'w-3.5 h-3.5 stroke-[2]',
                store.selectedFolder === item.id ? 'text-[#4D6BFE] dark:text-[#60A5FA]' : 'text-[var(--text-muted)]'
              ]"
            />
            <span>{{ item.label }}</span>
          </span>
          <span
            v-if="item.count"
            :class="[
              'px-1.5 py-[1px] rounded-full text-[10.5px] font-mono tabular-nums',
              item.highlight && store.selectedFolder === item.id
                ? 'bg-[#4D6BFE] text-white font-bold'
                : 'bg-[var(--bg-pill)] text-[var(--text-secondary)] font-semibold'
            ]"
          >
            {{ item.count }}
          </span>
        </button>
      </nav>

      <!-- Groups / Domains Tree Matrix -->
      <div class="space-y-1.5">
        <div class="flex items-center justify-between px-1.5">
          <!-- Segmented Switch: 分组 / 域名 -->
          <div class="inline-flex p-0.5 rounded-xl bg-[var(--bg-subtle)] border border-[var(--border-hairline)] text-[11px]">
            <button
              @click="store.switchGroupingMode('tags')"
              :class="[
                'px-2.5 py-0.5 rounded-lg transition font-bold',
                store.groupingMode === 'tags'
                  ? 'bg-[#4D6BFE] text-white shadow-sm'
                  : 'text-[var(--text-muted)] hover:text-[var(--text-primary)]'
              ]"
            >
              分组
            </button>
            <button
              @click="store.switchGroupingMode('domain_first')"
              :class="[
                'px-2.5 py-0.5 rounded-lg transition font-bold',
                store.groupingMode === 'domain_first'
                  ? 'bg-[#4D6BFE] text-white shadow-sm'
                  : 'text-[var(--text-muted)] hover:text-[var(--text-primary)]'
              ]"
            >
              域名
            </button>
          </div>

          <div class="flex items-center gap-1">
            <button
              @click="store.openExternalModal()"
              class="px-1.5 py-0.5 rounded-lg text-[11px] font-semibold text-[#4D6BFE] dark:text-[#7DD3FC] hover:bg-[var(--bg-hover)] transition"
              title="接入外部邮箱"
            >
              + 外部
            </button>
            <button
              @click="store.groupingMode === 'tags' ? openNewLabelModal(false) : (store.isDomainModalOpen = true)"
              class="p-1 rounded-lg text-[var(--text-muted)] hover:text-[#4D6BFE] hover:bg-[var(--bg-hover)] transition"
              :title="store.groupingMode === 'tags' ? '新建分组' : '绑定新域名'"
            >
              <Plus class="w-3.5 h-3.5" />
            </button>
          </div>
        </div>

        <!-- Draggable Groups & Mailboxes -->
        <div class="space-y-0.5">
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
              class="absolute -top-[1.5px] left-2 right-2 h-[2.5px] bg-gradient-to-r from-[#4D6BFE] to-[#38BDF8] rounded-full z-20 pointer-events-none"
            />

            <!-- Group Row -->
            <div
              :draggable="canReorderGroup(grp)"
              @dragstart="handleGroupDragStart($event, grp)"
              @dragend="resetDragState"
              @click="handleSelectGroup(grp)"
              :class="[
                'h-[30px] px-2 rounded-xl flex items-center justify-between cursor-pointer transition group/hdr',
                dragOverGroupId === grp.group_id
                  ? 'bg-[var(--bg-active)] ring-2 ring-[#4D6BFE]'
                  : isGroupSelected(grp)
                    ? 'bg-[var(--bg-active)] text-[#4D6BFE] dark:text-[#7DD3FC] font-bold'
                    : 'text-[var(--text-secondary)] hover:bg-[var(--bg-hover)] hover:text-[var(--text-primary)]',
                draggingGroupId === grp.group_id ? 'opacity-40' : ''
              ]"
            >
              <div class="flex items-center gap-1.5 min-w-0">
                <button
                  @click.stop="toggleGroupCollapse(grp.group_id)"
                  class="p-0.5 text-[var(--text-muted)] hover:text-[#4D6BFE] transition flex-shrink-0"
                >
                  <ChevronRight
                    :class="[
                      'w-3.5 h-3.5 transition-transform duration-150',
                      !isCollapsed(grp.group_id) ? 'rotate-90' : ''
                    ]"
                  />
                </button>
                <span
                  class="w-2.5 h-2.5 rounded-full flex-shrink-0 ring-2 ring-white/60 dark:ring-white/10"
                  :style="{ backgroundColor: grp.color || '#4D6BFE' }"
                />
                <span class="text-[12.5px] truncate">{{ grp.name }}</span>
                <span class="text-[10.5px] text-[var(--text-faint)] font-mono tabular-nums">
                  {{ grp.mailboxes?.length || 0 }}
                </span>
              </div>

              <div class="flex items-center gap-1 flex-shrink-0">
                <button
                  v-if="grp.domain_id && !grp.is_external"
                  @click.stop="openDomainDns(grp.domain_id)"
                  class="p-0.5 text-[var(--text-muted)] hover:text-[var(--accent-emerald)] opacity-0 group-hover/hdr:opacity-100 transition"
                  title="查看并复制 DNS 记录"
                >
                  <ShieldCheck class="w-3.5 h-3.5" />
                </button>
                <button
                  v-if="grp.domain_id"
                  @click.stop="grp.is_external ? store.openExternalModal() : openAddMailboxModal(grp.domain_id)"
                  class="p-0.5 text-[var(--text-muted)] hover:text-[#4D6BFE] opacity-0 group-hover/hdr:opacity-100 transition"
                  :title="grp.is_external ? '接入外部邮箱' : '在此域名下开通邮箱'"
                >
                  <Plus class="w-3.5 h-3.5" />
                </button>
                <button
                  v-if="store.groupingMode === 'tags' && grp.label_id && grp.label_id !== 0"
                  @click.stop="handleDeleteLabel(grp)"
                  class="p-0.5 text-[var(--text-muted)] hover:text-[var(--accent-rose)] opacity-0 group-hover/hdr:opacity-100 transition"
                  title="移除分组"
                >
                  <Trash2 class="w-3 h-3" />
                </button>
                <span
                  v-if="grp.unread_count"
                  class="px-1.5 py-[1px] rounded-full bg-[#4D6BFE]/12 text-[#4D6BFE] dark:text-[#7DD3FC] text-[10.5px] font-mono font-bold tabular-nums"
                >
                  {{ grp.unread_count }}
                </span>
              </div>
            </div>

            <!-- Nested Mailboxes -->
            <div
              v-if="grp.mailboxes && grp.mailboxes.length > 0 && !isCollapsed(grp.group_id)"
              class="ml-[15px] pl-2.5 border-l-[1.5px] border-[var(--border-hairline)] my-0.5 space-y-[2px]"
            >
              <div
                v-for="mb in grp.mailboxes"
                :key="`${grp.group_id}_${mb.id}`"
                draggable="true"
                @dragstart="handleMailboxDragStart($event, mb, grp)"
                @dragend="resetDragState"
                @click.stop="handleSelectMailbox(mb)"
                :class="[
                  'h-7 px-2 rounded-lg flex items-center justify-between text-[12px] cursor-pointer transition group/mb',
                  store.selectedMailboxId === mb.id
                    ? 'bg-[var(--bg-active)] text-[#4D6BFE] dark:text-[#7DD3FC] font-bold'
                    : 'text-[var(--text-muted)] hover:bg-[var(--bg-hover)] hover:text-[var(--text-primary)]'
                ]"
                :title="mb.address"
              >
                <div class="flex items-center gap-1.5 min-w-0">
                  <span
                    v-if="mb.is_external && mb.sync_status && mb.sync_status.startsWith('error')"
                    class="w-1.5 h-1.5 rounded-full bg-[var(--accent-rose)] flex-shrink-0"
                    :title="mb.sync_status"
                  />
                  <span
                    v-else-if="mb.unread_count"
                    class="w-1.5 h-1.5 rounded-full bg-[#38BDF8] flex-shrink-0"
                  />
                  <Sparkles
                    v-if="mb.is_vip"
                    class="w-3 h-3 text-[var(--accent-amber)] flex-shrink-0"
                  />
                  <span class="font-mono text-[11.5px] truncate">{{ formatMailboxLabel(mb) }}</span>
                </div>

                <div class="flex items-center gap-0.5 flex-shrink-0">
                  <button
                    v-if="mb.is_external"
                    @click.stop="handleSyncExternal(mb)"
                    class="p-0.5 text-[var(--text-muted)] hover:text-[#4D6BFE] opacity-0 group-hover/mb:opacity-100 transition"
                    title="手动同步此外部邮箱"
                  >
                    <RefreshCw :class="['w-2.5 h-2.5', { 'animate-spin text-[#4D6BFE]': syncingMailboxIds.has(mb.id) }]" />
                  </button>
                  <button
                    v-if="mb.is_external"
                    @click.stop="store.openExternalModal(mb)"
                    class="p-0.5 text-[var(--text-muted)] hover:text-[#4D6BFE] opacity-0 group-hover/mb:opacity-100 transition"
                    title="修改连接凭据"
                  >
                    <KeyRound class="w-2.5 h-2.5" />
                  </button>
                  <button
                    @click.stop="openMailboxSettings(mb)"
                    class="p-0.5 text-[var(--text-muted)] hover:text-[#4D6BFE] opacity-0 group-hover/mb:opacity-100 transition"
                    title="分组与 VIP 标记"
                  >
                    <SlidersHorizontal class="w-2.5 h-2.5" />
                  </button>
                  <button
                    v-if="!mb.is_default"
                    @click.stop="handleDeleteMailbox(mb)"
                    class="p-0.5 text-[var(--text-muted)] hover:text-[var(--accent-rose)] opacity-0 group-hover/mb:opacity-100 transition"
                    title="删除信箱"
                  >
                    <Trash2 class="w-2.5 h-2.5" />
                  </button>
                  <span
                    v-if="mb.unread_count"
                    class="text-[10.5px] font-mono tabular-nums text-[#4D6BFE] dark:text-[#7DD3FC] font-bold pl-1"
                  >
                    {{ mb.unread_count }}
                  </span>
                </div>
              </div>
            </div>

            <!-- Drop Indicator (After) -->
            <div
              v-if="dragMode === 'group' && groupDropTargetId === grp.group_id && groupDropPosition === 'after'"
              class="absolute -bottom-[1.5px] left-2 right-2 h-[2.5px] bg-gradient-to-r from-[#4D6BFE] to-[#38BDF8] rounded-full z-20 pointer-events-none"
            />
          </div>
        </div>
      </div>

      <!-- Mail Content Tags -->
      <div v-if="store.tags && store.tags.length > 0" class="space-y-0.5 pt-2 border-t border-[var(--border-hairline)]">
        <div class="px-2 pb-1 text-[10.5px] font-bold uppercase tracking-wider text-[var(--text-muted)]">
          内容标签
        </div>
        <button
          v-for="t in store.tags"
          :key="t.id"
          @click="store.selectScope({ tag: store.selectedTag === t.name ? null : t.name })"
          :class="[
            'w-full h-7 px-2.5 rounded-xl text-[12px] flex items-center gap-2 transition',
            store.selectedTag === t.name
              ? 'bg-[var(--bg-active)] text-[#4D6BFE] dark:text-[#7DD3FC] font-bold'
              : 'text-[var(--text-secondary)] hover:bg-[var(--bg-hover)]'
          ]"
        >
          <span class="w-2 h-2 rounded-full" :style="{ backgroundColor: t.color }" />
          <span>{{ t.name }}</span>
        </button>
      </div>
    </div>

    <!-- ===================================================================
         Interactive Chibi DeepSeek娘 & 大肥鱼 Companion Widget
         =================================================================== -->
    <div class="mt-3 pt-2.5 border-t border-[var(--border-hairline)] flex-shrink-0">
      <div
        @click="pokeWhale()"
        class="relative rounded-[18px] p-2.5 bg-gradient-to-br from-[#4D6BFE]/[0.08] via-[#38BDF8]/[0.07] to-transparent border border-[var(--border-strong)] cursor-pointer group hover:border-[#4D6BFE]/50 transition-all"
        title="点击戳一戳大肥鱼！"
      >
        <!-- Speech Bubble (Momotalk Style) -->
        <div class="relative mb-2 px-2.5 py-2 rounded-2xl bg-[var(--bg-elevated)] border border-[var(--border-hairline)] shadow-sm min-h-[48px] flex items-center">
          <Transition name="quote-pop" mode="out-in">
            <p
              :key="store.whaleQuoteIdx"
              class="text-[11.5px] leading-[1.45] font-semibold text-[var(--text-primary)]"
            >
              {{ store.currentWhaleQuote }}
            </p>
          </Transition>
          <!-- Little Speech Pointer -->
          <span class="absolute -bottom-1.5 left-7 w-3 h-3 rotate-45 bg-[var(--bg-elevated)] border-r border-b border-[var(--border-hairline)]" />
        </div>

        <!-- Chibi Illustration + Companion Status -->
        <div class="flex items-center gap-2.5 pt-0.5">
          <div
            :class="[
              'relative w-[74px] h-[74px] flex items-center justify-center flex-shrink-0',
              isPoking ? 'animate-whale-poke' : 'animate-whale-bob'
            ]"
          >
            <img
              :src="chibiImgUrl"
              alt="Q版 DeepSeek娘 与 蓝色大肥鱼"
              class="w-full h-full object-contain ds-chibi-sticker select-none pointer-events-none"
              draggable="false"
            />
            <!-- Poke Bubble Burst -->
            <Transition name="fade-scale">
              <span
                v-if="showBubblePop"
                class="absolute -top-1 -right-1 px-1.5 py-0.5 rounded-full bg-[#4D6BFE] text-white text-[9.5px] font-bold shadow"
              >
                🫧 噗噜!
              </span>
            </Transition>
          </div>

          <div class="min-w-0 flex-1 space-y-1">
            <div class="flex items-center justify-between gap-1">
              <span class="text-[12px] font-extrabold text-[var(--text-primary)] truncate">大肥鱼伴读中</span>
              <button
                @click.stop="store.summonMascot()"
                class="px-1.5 py-0.5 rounded-md bg-[#4D6BFE]/12 hover:bg-[#4D6BFE] text-[#4D6BFE] dark:text-[#7DD3FC] hover:text-white text-[10px] font-bold transition flex-shrink-0"
                title="返回记忆大厅欣赏看板娘"
              >
                大厅 ↗
              </button>
            </div>
            <p class="text-[10.5px] text-[var(--text-muted)] truncate">
              戳一戳大肥鱼 · 吐泡泡互动
            </p>
            <div class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-[#4D6BFE]/12 text-[#4D6BFE] dark:text-[#7DD3FC] text-[10px] font-mono font-bold">
              <span>🐋 摸鱼能量</span>
              <span>{{ 100 + store.pokeCount * 5 }}%</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Micro Modal 1: Create Group -->
    <Transition name="fade-scale">
      <div
        v-if="showNewLabelModal"
        class="fixed inset-0 ds-backdrop z-50 flex items-center justify-center p-4"
        @click.self="showNewLabelModal = false"
      >
        <div class="ds-modal w-full max-w-xs p-5 space-y-4">
          <div class="flex items-center justify-between">
            <h3 class="text-[14px] font-extrabold text-[var(--text-primary)] flex items-center gap-1.5">
              <span>🏷️ 新建邮箱分组</span>
            </h3>
            <button @click="showNewLabelModal = false" class="text-[var(--text-muted)] hover:text-[var(--text-primary)]">
              <X class="w-4 h-4" />
            </button>
          </div>
          <input
            v-model="newLabelName"
            @keydown.enter.prevent="submitCreateLabel"
            type="text"
            placeholder="输入分组名称 (如：核心业务 / 游戏账号)"
            autofocus
            class="w-full bg-[var(--bg-input)] border border-[var(--border-hairline)] focus:border-[var(--border-focus)] rounded-xl px-3.5 py-2 text-[12.5px] text-[var(--text-primary)] placeholder-[var(--text-muted)] focus:outline-none transition"
          />
          <div class="flex items-center gap-2 pt-0.5">
            <button
              v-for="c in LABEL_COLORS"
              :key="c"
              type="button"
              @click="newLabelColor = c"
              :class="[
                'w-5 h-5 rounded-full transition transform',
                newLabelColor === c ? 'scale-125 ring-2 ring-[#4D6BFE] ring-offset-2 ring-offset-[var(--bg-elevated)]' : 'opacity-70 hover:opacity-100'
              ]"
              :style="{ backgroundColor: c }"
            />
          </div>
          <div class="flex items-center justify-end gap-2 pt-1">
            <button
              @click="showNewLabelModal = false"
              class="px-3.5 py-1.5 rounded-xl text-[12px] font-semibold text-[var(--text-secondary)] hover:bg-[var(--bg-hover)] transition"
            >
              取消
            </button>
            <button
              @click="submitCreateLabel"
              :disabled="!newLabelName.trim()"
              class="ds-btn-primary px-4 py-1.5 rounded-xl text-[12px] font-bold disabled:opacity-40"
            >
              创建分组
            </button>
          </div>
        </div>
      </div>
    </Transition>

    <!-- Micro Modal 2: Create Local Mailbox -->
    <Transition name="fade-scale">
      <div
        v-if="newMailboxDomain"
        class="fixed inset-0 ds-backdrop z-50 flex items-center justify-center p-4"
        @click.self="newMailboxDomain = null"
      >
        <div class="ds-modal w-full max-w-sm p-5 space-y-4">
          <div class="flex items-center justify-between">
            <h3 class="text-[14px] font-extrabold text-[var(--text-primary)]">🐋 开通新信箱</h3>
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
                placeholder="前缀 (如 maid)"
                autofocus
                class="flex-1 bg-transparent px-3.5 py-2 text-[12.5px] font-mono text-[var(--text-primary)] placeholder-[var(--text-muted)] focus:outline-none"
              />
              <span class="px-3 py-2 text-[12px] font-mono font-semibold text-[#4D6BFE] dark:text-[#7DD3FC] border-l border-[var(--border-hairline)] bg-[var(--bg-subtle)]">
                @{{ newMailboxDomain.name }}
              </span>
            </div>
            <input
              v-model="newMailboxNote"
              @keydown.enter.prevent="submitAddMailbox"
              type="text"
              placeholder="备注名称 (选填)"
              class="w-full bg-[var(--bg-input)] border border-[var(--border-hairline)] focus:border-[var(--border-focus)] rounded-xl px-3.5 py-2 text-[12.5px] text-[var(--text-primary)] placeholder-[var(--text-muted)] focus:outline-none transition"
            />
          </div>
          <div class="flex items-center justify-end gap-2 pt-1">
            <button
              @click="newMailboxDomain = null"
              class="px-3.5 py-1.5 rounded-xl text-[12px] font-semibold text-[var(--text-secondary)] hover:bg-[var(--bg-hover)] transition"
            >
              取消
            </button>
            <button
              @click="submitAddMailbox"
              :disabled="!newMailboxPrefix.trim()"
              class="ds-btn-primary px-4 py-1.5 rounded-xl text-[12px] font-bold disabled:opacity-40"
            >
              立即开通
            </button>
          </div>
        </div>
      </div>
    </Transition>

    <!-- Micro Modal 3: Drag & Drop Move/Copy -->
    <Transition name="fade-scale">
      <div
        v-if="pendingDropAction"
        class="fixed inset-0 ds-backdrop z-50 flex items-center justify-center p-4"
        @click.self="pendingDropAction = null"
      >
        <div class="ds-modal w-full max-w-xs p-5 space-y-4">
          <div class="flex items-center justify-between">
            <h3 class="text-[14px] font-extrabold text-[var(--text-primary)]">🫧 调整分组归属</h3>
            <button @click="pendingDropAction = null" class="text-[var(--text-muted)] hover:text-[var(--text-primary)]">
              <X class="w-4 h-4" />
            </button>
          </div>
          <p class="text-[12.5px] text-[var(--text-secondary)] leading-relaxed">
            将信箱 <span class="font-mono text-[#4D6BFE] dark:text-[#7DD3FC] font-bold">{{ pendingDropAction.mailbox.address }}</span>
            归入 <span class="text-[var(--text-primary)] font-bold">「{{ pendingDropAction.targetGroup.name }}」</span>：
          </p>
          <div class="flex items-center justify-end gap-2">
            <button
              @click="pendingDropAction = null"
              class="px-3 py-1.5 rounded-xl text-[12px] font-semibold text-[var(--text-muted)] hover:text-[var(--text-primary)] transition"
            >
              取消
            </button>
            <button
              @click="executeDropAction('move')"
              class="px-3.5 py-1.5 rounded-xl text-[12px] bg-[var(--bg-subtle)] hover:bg-[var(--bg-hover)] text-[var(--text-primary)] border border-[var(--border-strong)] font-bold ds-spring"
            >
              移动过去
            </button>
            <button
              @click="executeDropAction('copy')"
              class="ds-btn-primary px-3.5 py-1.5 rounded-xl text-[12px] font-bold"
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
        class="fixed inset-0 ds-backdrop z-50 flex items-center justify-center p-4"
        @click.self="editingMailbox = null"
      >
        <div class="ds-modal w-full max-w-sm p-5 space-y-4">
          <div class="flex items-center justify-between">
            <span class="font-mono text-[13px] font-bold text-[#4D6BFE] dark:text-[#7DD3FC] truncate">
              {{ editingMailbox.address }}
            </span>
            <button @click="editingMailbox = null" class="text-[var(--text-muted)] hover:text-[var(--text-primary)]">
              <X class="w-4 h-4" />
            </button>
          </div>

          <div class="space-y-3.5">
            <div>
              <div class="flex items-center justify-between mb-2">
                <span class="text-[11.5px] font-bold text-[var(--text-muted)]">所属分组 (可多选)</span>
                <button
                  @click="openNewLabelModal(true)"
                  class="text-[11.5px] font-bold text-[#4D6BFE] dark:text-[#7DD3FC] hover:underline flex items-center gap-0.5 transition"
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
                    'px-2.5 py-1 rounded-xl text-[12px] flex items-center gap-1.5 transition border',
                    editForm.label_ids.includes(lbl.id)
                      ? 'bg-[var(--bg-active)] border-[#4D6BFE] text-[#4D6BFE] dark:text-[#7DD3FC] font-bold'
                      : 'bg-[var(--bg-subtle)] border-[var(--border-hairline)] text-[var(--text-secondary)] hover:text-[var(--text-primary)]'
                  ]"
                >
                  <span class="w-2 h-2 rounded-full" :style="{ backgroundColor: lbl.color || '#4D6BFE' }" />
                  <span>{{ lbl.name }}</span>
                  <Check v-if="editForm.label_ids.includes(lbl.id)" class="w-3 h-3" />
                </button>
              </div>
            </div>

            <label class="flex items-center justify-between px-3.5 py-2.5 rounded-2xl bg-[var(--bg-subtle)] border border-[var(--border-hairline)] cursor-pointer hover:border-[var(--border-strong)] transition">
              <span class="text-[12.5px] font-bold text-[var(--text-primary)] flex items-center gap-2">
                <Sparkles class="w-4 h-4 text-[var(--accent-amber)]" />
                <span>设为重点关注 (VIP)</span>
              </span>
              <input
                type="checkbox"
                v-model="editForm.is_vip"
                class="w-4 h-4 rounded accent-[#4D6BFE] cursor-pointer"
              />
            </label>
          </div>

          <div class="flex items-center justify-end gap-2">
            <button
              @click="editingMailbox = null"
              class="px-3.5 py-1.5 rounded-xl text-[12px] font-semibold text-[var(--text-secondary)] hover:bg-[var(--bg-hover)] transition"
            >
              取消
            </button>
            <button
              @click="saveMailboxSettings"
              class="ds-btn-primary px-4 py-1.5 rounded-xl text-[12px] font-bold"
            >
              保存设置
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </aside>
</template>
