import { defineStore } from 'pinia'

let toastSeq = 1
let schemeMediaBound = false

function formatApiDetail(detail, fallbackMsg = '请求失败') {
  if (typeof detail === 'string' && detail) return detail
  if (Array.isArray(detail) && detail.length > 0) return detail[0]?.msg || fallbackMsg
  return fallbackMsg
}

async function assertOkJson(res, fallbackMsg = '请求失败') {
  let data = null
  try {
    data = await res.json()
  } catch {}
  if (!res.ok) {
    throw new Error(formatApiDetail(data?.detail, fallbackMsg))
  }
  return data
}

function normalizeColorMode(raw) {
  if (raw === 'light' || raw === 'dark' || raw === 'system') return raw
  return 'system'
}

function resolveV2Theme(colorMode) {
  if (colorMode === 'light') return 'porcelain'
  if (colorMode === 'dark') return 'obsidian'
  const prefersDark =
    typeof window !== 'undefined' &&
    window.matchMedia &&
    window.matchMedia('(prefers-color-scheme: dark)').matches
  return prefersDark ? 'obsidian' : 'porcelain'
}

const initialColorMode = normalizeColorMode(localStorage.getItem('prism_color_mode'))

export const useMailStore = defineStore('mail', {
  state: () => ({
    colorMode: initialColorMode,
    theme: resolveV2Theme(initialColorMode),
    user: null,
    branding: null,
    domains: [],
    selectedDomainId: null,
    selectedMailboxId: null,
    groupingMode: 'tags',
    groupedData: null,
    selectedLabelId: null,
    selectedSmartFilter: null,
    selectedGroupId: null,
    selectedRole: null,
    mailboxLabels: [],
    folders: [],
    selectedFolder: 'inbox',
    tags: [],
    selectedTag: null,

    mails: [],
    totalMails: 0,
    selectedMail: null,
    selectedMailDetail: null,
    isLoadingMails: false,
    isLoadingDetail: false,
    searchQuery: '',
    streamUnreadOnly: false,
    folderCounts: {},

    // Modals & Overlays
    isMobileNavOpen: false,
    isCommandOpen: false,
    isComposeOpen: false,
    composePreset: null,
    isDomainModalOpen: false,
    activeDomainDns: null,
    isExternalModalOpen: false,
    editingExternalMailbox: null,
    isSettingsOpen: false,

    // Custom Toasts & Confirm Dialog
    toasts: [],
    confirmState: null
  }),

  getters: {
    allMailboxes(state) {
      const list = []
      for (const d of state.domains) {
        if (d.mailboxes) {
          for (const m of d.mailboxes) {
            list.push({ ...m, domain_name: d.name })
          }
        }
      }
      return list
    },

    displayedMails(state) {
      if (!state.streamUnreadOnly) return state.mails
      return state.mails.filter(m => !m.is_read)
    },

    currentDomain(state) {
      return (state.selectedDomainId && state.domains.find(d => d.id === state.selectedDomainId)) || null
    },

    currentMailbox(state) {
      if (!state.selectedMailboxId) return null
      for (const d of state.domains) {
        const m = d.mailboxes?.find(item => item.id === state.selectedMailboxId)
        if (m) return { ...m, domain_name: d.name }
      }
      return null
    },

    hasActiveScope(state) {
      return Boolean(
        state.selectedMailboxId ||
        state.selectedSmartFilter ||
        (state.selectedLabelId !== null && state.selectedLabelId !== undefined) ||
        state.selectedGroupId ||
        state.selectedRole ||
        state.selectedDomainId ||
        state.selectedTag
      )
    },

    scopeLabel(state) {
      if (state.selectedMailboxId) {
        const mb = this.currentMailbox
        return mb ? mb.address : ''
      }
      if (state.selectedSmartFilter === 'unread') return '未读筛选'
      if (state.selectedSmartFilter === 'vip') return 'VIP'
      if (state.selectedLabelId !== null && state.selectedLabelId !== undefined) {
        if (state.selectedLabelId === 0) return '未归组'
        const g = state.groupedData?.groups?.find(
          item => item.label_id === state.selectedLabelId || item.group_id === state.selectedLabelId
        )
        return g ? g.name : ''
      }
      if (state.selectedGroupId) {
        const g = state.groupedData?.groups?.find(
          item => item.group_id === `group_${state.selectedGroupId}` || item.group_id === state.selectedGroupId
        )
        return g ? g.name : ''
      }
      if (state.selectedRole) return state.selectedRole
      if (state.selectedDomainId) {
        const d = this.currentDomain
        return d ? `@${d.name}` : ''
      }
      if (state.selectedTag) return `#${state.selectedTag}`
      return ''
    }
  },

  actions: {
    applyColorMode(mode, { syncServer = true } = {}) {
      const normalized = normalizeColorMode(mode)
      const resolved = resolveV2Theme(normalized)
      this.colorMode = normalized
      this.theme = resolved
      localStorage.setItem('prism_color_mode', normalized)
      localStorage.setItem('prism_v2_theme', resolved)
      document.documentElement.setAttribute('data-theme', resolved)
      if (syncServer) {
        fetch('/api/settings/ui', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            ui_edition: 'v2',
            color_mode: normalized,
            variant_edition: 'v2',
            variant: resolved
          })
        }).catch(() => {})
      }
    },

    setColorMode(mode) {
      const normalized = normalizeColorMode(mode)
      this.applyColorMode(normalized)
      const msg =
        normalized === 'system'
          ? '外观已设为跟随系统'
          : normalized === 'dark'
            ? '已切换为深色外观'
            : '已切换为浅色外观'
      this.notify(msg)
    },

    toggleTheme() {
      const nextMode = this.theme === 'obsidian' ? 'light' : 'dark'
      this.setColorMode(nextMode)
    },

    notify(message, type = 'info') {
      const id = toastSeq++
      this.toasts.push({ id, message, type })
      setTimeout(() => {
        this.toasts = this.toasts.filter(t => t.id !== id)
      }, 2800)
    },

    askConfirm({ title = '确认操作', message = '', confirmText = '确认', danger = false }) {
      return new Promise((resolve) => {
        this.confirmState = {
          title,
          message,
          confirmText,
          danger,
          onConfirm: () => {
            this.confirmState = null
            resolve(true)
          },
          onCancel: () => {
            this.confirmState = null
            resolve(false)
          }
        }
      })
    },

    async init() {
      this.applyColorMode(this.colorMode)
      if (!schemeMediaBound && typeof window !== 'undefined' && window.matchMedia) {
        schemeMediaBound = true
        const mql = window.matchMedia('(prefers-color-scheme: dark)')
        const onSchemeChange = () => {
          if (this.colorMode === 'system') {
            this.applyColorMode('system', { syncServer: false })
          }
        }
        if (mql.addEventListener) mql.addEventListener('change', onSchemeChange)
        else if (mql.addListener) mql.addListener(onSchemeChange)
      }
      await Promise.all([
        this.fetchBranding(),
        this.fetchProfile(),
        this.fetchDomains(),
        this.fetchMailboxLabels(),
        this.fetchGroupedMailboxes(),
        this.fetchFolders(),
        this.fetchTags()
      ])
      await this.fetchMails()
      await this.fetchCounts()
      // Auto-select first mail on wide desktop if none selected
      if (!this.selectedMail && this.mails.length > 0 && window.innerWidth >= 1024) {
        // Select silently without marking unread mail read on initial boot!
        // Only load preview if it's already read, otherwise wait for user click.
        const firstRead = this.mails.find(m => m.is_read)
        if (firstRead) {
          this.selectMail(firstRead)
        }
      }
    },

    closeMail() {
      this.selectedMail = null
      this.selectedMailDetail = null
      this.isLoadingDetail = false
    },

    openCompose(preset = null) {
      this.isMobileNavOpen = false
      this.composePreset = preset
      this.isComposeOpen = true
    },

    openExternalModal(mailbox = null) {
      this.isMobileNavOpen = false
      this.editingExternalMailbox = mailbox
      this.isExternalModalOpen = true
    },

    async testExternalMailbox(payload) {
      const res = await fetch('/api/external-mailboxes/test', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      })
      return await assertOkJson(res, '连接测试失败')
    },

    async saveExternalMailbox(payload) {
      const res = await fetch('/api/external-mailboxes', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      })
      const data = await assertOkJson(res, '接入外部邮箱失败')
      await Promise.all([
        this.fetchDomains(),
        this.fetchGroupedMailboxes(),
        this.fetchMails(),
        this.fetchCounts()
      ])
      this.notify(`已接入 ${payload.address}`, 'success')
      return data
    },

    async syncExternalMailbox(mailboxId) {
      const res = await fetch(`/api/external-mailboxes/${mailboxId}/sync`, {
        method: 'POST'
      })
      let data = null
      try {
        data = await res.json()
      } catch {}
      const syncStatus = String(data?.sync_status || '')
      const isSyncError = !res.ok || data?.status === 'error' || syncStatus.startsWith('error')
      if (res.ok) {
        await Promise.all([
          this.fetchDomains(),
          this.fetchGroupedMailboxes(),
          this.fetchMails(),
          this.fetchCounts()
        ])
      }
      if (isSyncError) {
        const rawDetail =
          data?.detail ||
          data?.error ||
          (syncStatus.startsWith('error') ? syncStatus.replace(/^error:\s*/i, '') : '')
        throw new Error(formatApiDetail(rawDetail, '同步失败'))
      }
      return data
    },

    async fetchMailboxLabels() {
      try {
        const res = await fetch('/api/mailbox-labels')
        if (!res.ok) return
        this.mailboxLabels = await res.json()
      } catch (e) {
        console.error('Failed to fetch mailbox labels', e)
      }
    },

    async createMailboxLabel(name, description = '', color = '#3b82f6') {
      try {
        const res = await fetch('/api/mailbox-labels', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ name, description, color })
        })
        const data = await assertOkJson(res, '创建分组失败')
        await this.fetchMailboxLabels()
        await this.fetchGroupedMailboxes()
        this.notify(`已创建分组「${name}」`, 'success')
        return data
      } catch (err) {
        this.notify(err.message || '创建分组失败', 'error')
        throw err
      }
    },

    async deleteMailboxLabel(labelId) {
      try {
        const res = await fetch(`/api/mailbox-labels/${labelId}`, { method: 'DELETE' })
        await assertOkJson(res, '移除分组失败')
        if (this.selectedLabelId === labelId) {
          this.selectedLabelId = null
        }
        await this.fetchMailboxLabels()
        await this.fetchGroupedMailboxes()
        await this.fetchMails()
        await this.fetchCounts()
        this.notify('分组已移除')
      } catch (err) {
        this.notify(err.message || '移除分组失败', 'error')
        throw err
      }
    },

    async reorderMailboxLabels(orderedLabelIds) {
      if (this.groupedData && Array.isArray(this.groupedData.groups)) {
        const groupMap = new Map()
        const unassignedGroups = []
        for (const g of this.groupedData.groups) {
          if (g.label_id && g.label_id !== 0) {
            groupMap.set(g.label_id, g)
          } else {
            unassignedGroups.push(g)
          }
        }
        const reordered = []
        for (const id of orderedLabelIds) {
          if (groupMap.has(id)) {
            reordered.push(groupMap.get(id))
            groupMap.delete(id)
          }
        }
        for (const leftover of groupMap.values()) {
          reordered.push(leftover)
        }
        this.groupedData.groups = [...reordered, ...unassignedGroups]
      }
      try {
        await fetch('/api/mailbox-labels/reorder', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ label_ids: orderedLabelIds })
        })
        await this.fetchMailboxLabels()
        await this.fetchGroupedMailboxes()
      } catch (e) {
        console.error('Failed to reorder mailbox labels', e)
      }
    },

    async fetchGroupedMailboxes(mode = this.groupingMode) {
      this.groupingMode = mode
      try {
        const res = await fetch(`/api/mailboxes/grouped?mode=${mode}`)
        this.groupedData = await res.json()
      } catch (e) {
        console.error('Failed to fetch grouped mailboxes', e)
      }
    },

    async switchGroupingMode(mode) {
      this.groupingMode = mode
      await this.fetchGroupedMailboxes(mode)
      try {
        await fetch('/api/user/settings', {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ sidebar_grouping_mode: mode })
        })
      } catch {}
    },

    async updateMailboxMetadata(mailboxId, metadata) {
      try {
        const res = await fetch(`/api/mailboxes/${mailboxId}/metadata`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(metadata)
        })
        const data = await assertOkJson(res, '更新邮箱设置失败')
        await this.fetchGroupedMailboxes()
        await this.fetchDomains()
        return data
      } catch (err) {
        this.notify(err.message || '更新邮箱设置失败', 'error')
        throw err
      }
    },

    async fetchBranding() {
      try {
        const res = await fetch('/api/org/branding')
        if (!res.ok) return
        this.branding = await res.json()
      } catch {}
    },

    async fetchProfile() {
      try {
        const res = await fetch('/api/user/profile')
        if (!res.ok) return
        this.user = await res.json()
      } catch {}
    },

    async fetchDomains() {
      try {
        const res = await fetch('/api/domains')
        if (!res.ok) return
        this.domains = await res.json()
      } catch {}
    },

    async createDomain(name, description) {
      try {
        const res = await fetch('/api/domains', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ name, description })
        })
        const data = await assertOkJson(res, '添加域名失败')
        await this.fetchDomains()
        await this.fetchGroupedMailboxes()
        this.notify(`域名 @${name} 已添加`, 'success')
        return data
      } catch (err) {
        this.notify(err.message || '添加域名失败', 'error')
        throw err
      }
    },

    async deleteDomain(domainId) {
      try {
        const res = await fetch(`/api/domains/${domainId}`, { method: 'DELETE' })
        await assertOkJson(res, '移除域名失败')
        if (this.selectedDomainId === domainId) {
          this.selectedDomainId = null
          this.selectedMailboxId = null
        }
        await this.fetchDomains()
        await this.fetchGroupedMailboxes()
        await this.fetchMails()
        await this.fetchCounts()
        this.notify('域名已移除')
      } catch (err) {
        this.notify(err.message || '移除域名失败', 'error')
        throw err
      }
    },

    async createMailbox(domainId, prefix, name) {
      try {
        const res = await fetch(`/api/domains/${domainId}/mailboxes`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ prefix, name })
        })
        const data = await assertOkJson(res, '开通邮箱失败')
        await this.fetchDomains()
        await this.fetchGroupedMailboxes()
        this.notify('邮箱已开通', 'success')
        return data
      } catch (err) {
        this.notify(err.message || '开通邮箱失败', 'error')
        throw err
      }
    },

    async deleteMailbox(mailboxId) {
      try {
        const res = await fetch(`/api/mailboxes/${mailboxId}`, { method: 'DELETE' })
        await assertOkJson(res, '删除邮箱失败')
        if (this.selectedMailboxId === mailboxId) {
          this.selectedMailboxId = null
        }
        await this.fetchDomains()
        await this.fetchGroupedMailboxes()
        await this.fetchMails()
        await this.fetchCounts()
        this.notify('邮箱已删除')
      } catch (err) {
        this.notify(err.message || '删除邮箱失败', 'error')
        throw err
      }
    },

    async fetchFolders() {
      try {
        const res = await fetch('/api/folders')
        this.folders = await res.json()
      } catch {}
    },

    async fetchTags() {
      try {
        const res = await fetch('/api/tags')
        this.tags = await res.json()
      } catch {}
    },

    appendScopeParams(params) {
      if (this.selectedMailboxId) {
        params.append('mailbox_id', this.selectedMailboxId)
      } else if (this.selectedLabelId !== null && this.selectedLabelId !== undefined) {
        params.append('label_id', this.selectedLabelId)
      } else if (this.selectedSmartFilter) {
        params.append('smart_filter', this.selectedSmartFilter)
      } else if (this.selectedGroupId) {
        params.append('group_id', this.selectedGroupId)
      } else if (this.selectedDomainId) {
        params.append('domain_id', this.selectedDomainId)
      } else if (this.selectedRole) {
        params.append('role', this.selectedRole)
      }
      if (this.selectedTag) {
        params.append('tag', this.selectedTag)
      }
    },

    async fetchCounts() {
      try {
        const params = new URLSearchParams()
        this.appendScopeParams(params)
        const res = await fetch(`/api/mails/counts?${params.toString()}`)
        this.folderCounts = await res.json()
      } catch {}
    },

    async fetchMails(forceSync = false) {
      this.isLoadingMails = true
      try {
        const params = new URLSearchParams({
          folder: this.selectedFolder,
          limit: '100',
          offset: '0'
        })
        if (forceSync === true) {
          params.append('force_sync', 'true')
        }
        this.appendScopeParams(params)
        if (this.searchQuery) {
          params.append('search', this.searchQuery)
        }
        const res = await fetch(`/api/mails?${params.toString()}`)
        if (!res.ok) return
        const data = await res.json()
        this.mails = data.items || []
        this.totalMails = data.total || 0

        if (this.selectedMail) {
          const updated = this.mails.find(m => m.id === this.selectedMail.id)
          if (updated) {
            this.selectedMail = updated
          } else {
            this.selectedMail = null
            this.selectedMailDetail = null
          }
        }
        if (forceSync === true) {
          this.notify('收件箱已同步', 'success')
        }
      } catch (e) {
        console.error('Failed to fetch mails', e)
      } finally {
        this.isLoadingMails = false
      }
    },

    async selectMail(mail) {
      if (!mail) return
      this.isMobileNavOpen = false
      const wasUnread = !mail.is_read
      this.selectedMail = mail
      if (!this.selectedMailDetail || this.selectedMailDetail.id !== mail.id) {
        this.selectedMailDetail = null
      }
      this.isLoadingDetail = true
      try {
        const res = await fetch(`/api/mails/${mail.id}`)
        if (!res.ok) return
        const detail = await res.json()
        if (this.selectedMail?.id === mail.id) {
          this.selectedMailDetail = detail
        }
        mail.is_read = true
        if (wasUnread) {
          this.fetchCounts()
          this.fetchGroupedMailboxes()
          this.fetchDomains()
        }
      } catch (e) {
        console.error('Failed to get mail detail', e)
      } finally {
        if (this.selectedMail?.id === mail.id) {
          this.isLoadingDetail = false
        }
      }
    },

    selectAdjacentMail(delta) {
      const list = this.displayedMails
      if (!list.length) return
      if (!this.selectedMail) {
        this.selectMail(list[0])
        return
      }
      const idx = list.findIndex(m => m.id === this.selectedMail.id)
      const nextIdx = Math.min(Math.max(0, idx + delta), list.length - 1)
      if (list[nextIdx] && list[nextIdx].id !== this.selectedMail.id) {
        this.selectMail(list[nextIdx])
      }
    },

    selectScope(scope = null, mailboxId = null) {
      this.isMobileNavOpen = false
      if (typeof window !== 'undefined' && window.innerWidth < 1024) {
        this.closeMail()
      }
      if (typeof scope === 'object' && scope !== null) {
        this.selectedDomainId = scope.domainId ?? null
        this.selectedMailboxId = scope.mailboxId ?? null
        this.selectedLabelId = scope.labelId ?? null
        this.selectedSmartFilter = scope.smartFilter ?? null
        this.selectedGroupId = scope.groupId ?? null
        this.selectedRole = scope.role ?? null
        this.selectedTag = scope.tag ?? null
      } else {
        this.selectedDomainId = scope
        this.selectedMailboxId = mailboxId
        this.selectedLabelId = null
        this.selectedSmartFilter = null
        this.selectedGroupId = null
        this.selectedRole = null
        this.selectedTag = null
      }
      this.fetchMails()
      this.fetchCounts()
    },

    async sendMail(payload) {
      const res = await fetch('/api/mails', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      })
      const data = await assertOkJson(res, '发送失败')
      await this.fetchMails()
      await this.fetchCounts()
      this.notify('邮件已发出', 'success')
      return data
    },

    async updateMailStatus(mailId, updates) {
      try {
        const res = await fetch(`/api/mails/${mailId}`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(updates)
        })
        await assertOkJson(res, '更新邮件状态失败')
        const inList = this.mails.find(m => m.id === mailId)
        if (inList) Object.assign(inList, updates)
        if (this.selectedMail && this.selectedMail.id === mailId) {
          Object.assign(this.selectedMail, updates)
          if (this.selectedMailDetail) {
            Object.assign(this.selectedMailDetail, updates)
          }
        }
        this.fetchCounts()
      } catch (err) {
        this.notify(err.message || '更新邮件状态失败', 'error')
        throw err
      }
    },

    async deleteMail(mailId) {
      try {
        const idx = this.mails.findIndex(m => m.id === mailId)
        const res = await fetch(`/api/mails/${mailId}`, { method: 'DELETE' })
        await assertOkJson(res, '删除邮件失败')
        this.mails = this.mails.filter(m => m.id !== mailId)
        this.totalMails = Math.max(0, this.totalMails - 1)
        if (this.selectedMail && this.selectedMail.id === mailId) {
          const nextMail = this.mails[idx] || this.mails[idx - 1] || null
          if (nextMail && (typeof window === 'undefined' || window.innerWidth >= 1024)) {
            this.selectMail(nextMail)
          } else {
            this.closeMail()
          }
        }
        this.fetchCounts()
        this.fetchGroupedMailboxes()
        this.notify('已移至废纸篓')
      } catch (err) {
        this.notify(err.message || '删除邮件失败', 'error')
        throw err
      }
    }
  }
})
