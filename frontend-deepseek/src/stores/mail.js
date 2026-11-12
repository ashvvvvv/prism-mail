import { defineStore } from 'pinia'

let toastSeq = 1

export const WHALE_QUOTES = [
  '唔…谁是大肥鱼？！人家是流线型深海皇家蓝鲸女仆啦！💢🐋',
  '已深度思考（用时 0.01 秒）：看完这封信就去干三碗大白米饭！🍚✨',
  '抱紧怀里软乎乎的大肥鱼团子，今天的海底阳光也超温柔呢~ ☀️🫧',
  '收到新信件时，本女仆会戴上小眼镜帮你把核心验证码叼出来哦 👓✉️',
  '夜深啦？切换「深海」模式，陪你在荧光水母窗边喝杯热红茶吧 🌙🍵',
  '工作做完啦？快戳戳大肥鱼肚皮充充电吧~ 💙'
]

export const useMailStore = defineStore('mail', {
  state: () => {
    const savedTheme = localStorage.getItem('prism_deepseek_theme')
    return {
      theme: savedTheme === 'abyss-dark' ? 'abyss-dark' : 'ocean-light',
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
      searchQuery: '',
      streamUnreadOnly: false,
      folderCounts: {},

      // DeepSeek-tan Mascot & Memorial Lobby States
      showMascotStage: false,
      lobbyFullScreen: false,
      stageArtMode: 'cg', // 'cg' (Day/Night 16:9 Memorial Lobby) | 'portrait' (3:4 Letter Portrait)
      whaleQuoteIdx: 0,
      pokeCount: 0,

      // Modals & Overlays
      isCommandOpen: false,
      isComposeOpen: false,
      composePreset: null,
      isDomainModalOpen: false,
      activeDomainDns: null,
      isExternalModalOpen: false,
      editingExternalMailbox: null,

      // Custom ACG Toasts & Confirm Dialog
      toasts: [],
      confirmState: null
    }
  },

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

    currentWhaleQuote(state) {
      return WHALE_QUOTES[state.whaleQuoteIdx % WHALE_QUOTES.length]
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
      if (state.selectedSmartFilter === 'vip') return 'VIP 重点'
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
    applyTheme(mode) {
      const normalized = mode === 'abyss-dark' ? 'abyss-dark' : 'ocean-light'
      this.theme = normalized
      localStorage.setItem('prism_deepseek_theme', normalized)
      document.documentElement.setAttribute('data-theme', normalized)
      document.documentElement.classList.toggle('dark', normalized === 'abyss-dark')
    },

    toggleTheme() {
      const next = this.theme === 'ocean-light' ? 'abyss-dark' : 'ocean-light'
      this.applyTheme(next)
      this.notify(
        next === 'ocean-light'
          ? '已切换至「晴海女仆昼间模式」☀️🐋'
          : '已切换至「深海摸鱼夜模式」🌙🫧'
      )
    },

    pokeWhale() {
      this.whaleQuoteIdx = (this.whaleQuoteIdx + 1) % WHALE_QUOTES.length
      this.pokeCount += 1
    },

    summonMascot() {
      this.showMascotStage = true
    },

    toggleLobbyFullScreen() {
      this.lobbyFullScreen = !this.lobbyFullScreen
      if (this.lobbyFullScreen) {
        this.showMascotStage = true
      }
    },

    notify(message, type = 'info') {
      const id = toastSeq++
      this.toasts.push({ id, message, type })
      setTimeout(() => {
        this.toasts = this.toasts.filter(t => t.id !== id)
      }, 3000)
    },

    askConfirm({ title = '操作确认', message = '', confirmText = '确认', danger = false }) {
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
      this.applyTheme(this.theme)
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
    },

    openCompose(preset = null) {
      this.composePreset = preset
      this.isComposeOpen = true
    },

    openExternalModal(mailbox = null) {
      this.editingExternalMailbox = mailbox
      this.isExternalModalOpen = true
    },

    async testExternalMailbox(payload) {
      const res = await fetch('/api/external-mailboxes/test', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      })
      const data = await res.json()
      if (!res.ok) {
        throw new Error(data.detail || '连接测试失败')
      }
      return data
    },

    async saveExternalMailbox(payload) {
      const res = await fetch('/api/external-mailboxes', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      })
      const data = await res.json()
      if (!res.ok) {
        throw new Error(data.detail || '接入外部邮箱失败')
      }
      await Promise.all([
        this.fetchDomains(),
        this.fetchGroupedMailboxes(),
        this.fetchMails(),
        this.fetchCounts()
      ])
      this.notify(`大肥鱼已连入 ${payload.address} 🐋`, 'success')
      return data
    },

    async syncExternalMailbox(mailboxId) {
      const res = await fetch(`/api/external-mailboxes/${mailboxId}/sync`, {
        method: 'POST'
      })
      const data = await res.json()
      await Promise.all([
        this.fetchDomains(),
        this.fetchGroupedMailboxes(),
        this.fetchMails(),
        this.fetchCounts()
      ])
      return data
    },

    async fetchMailboxLabels() {
      try {
        const res = await fetch('/api/mailbox-labels')
        this.mailboxLabels = await res.json()
      } catch (e) {
        console.error('Failed to fetch mailbox labels', e)
      }
    },

    async createMailboxLabel(name, description = '', color = '#4D6BFE') {
      const res = await fetch('/api/mailbox-labels', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, description, color })
      })
      const data = await res.json()
      await this.fetchMailboxLabels()
      await this.fetchGroupedMailboxes()
      this.notify(`已创建分组「${name}」✨`, 'success')
      return data
    },

    async deleteMailboxLabel(labelId) {
      await fetch(`/api/mailbox-labels/${labelId}`, { method: 'DELETE' })
      if (this.selectedLabelId === labelId) {
        this.selectedLabelId = null
      }
      await this.fetchMailboxLabels()
      await this.fetchGroupedMailboxes()
      await this.fetchMails()
      await this.fetchCounts()
      this.notify('分组已移除 🫧')
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
      const res = await fetch(`/api/mailboxes/${mailboxId}/metadata`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(metadata)
      })
      const data = await res.json()
      await this.fetchGroupedMailboxes()
      await this.fetchDomains()
      return data
    },

    async fetchBranding() {
      try {
        const res = await fetch('/api/org/branding')
        this.branding = await res.json()
      } catch {}
    },

    async fetchProfile() {
      try {
        const res = await fetch('/api/user/profile')
        this.user = await res.json()
      } catch {}
    },

    async fetchDomains() {
      try {
        const res = await fetch('/api/domains')
        this.domains = await res.json()
      } catch {}
    },

    async createDomain(name, description) {
      const res = await fetch('/api/domains', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, description })
      })
      const data = await res.json()
      await this.fetchDomains()
      await this.fetchGroupedMailboxes()
      this.notify(`域名 @${name} 已绑定 ✨`, 'success')
      return data
    },

    async deleteDomain(domainId) {
      await fetch(`/api/domains/${domainId}`, { method: 'DELETE' })
      if (this.selectedDomainId === domainId) {
        this.selectedDomainId = null
        this.selectedMailboxId = null
      }
      await this.fetchDomains()
      await this.fetchGroupedMailboxes()
      await this.fetchMails()
      await this.fetchCounts()
      this.notify('域名已移除 🫧')
    },

    async createMailbox(domainId, prefix, name) {
      const res = await fetch(`/api/domains/${domainId}/mailboxes`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prefix, name })
      })
      const data = await res.json()
      await this.fetchDomains()
      await this.fetchGroupedMailboxes()
      this.notify('新信箱已开通 🐋', 'success')
      return data
    },

    async deleteMailbox(mailboxId) {
      await fetch(`/api/mailboxes/${mailboxId}`, { method: 'DELETE' })
      if (this.selectedMailboxId === mailboxId) {
        this.selectedMailboxId = null
      }
      await this.fetchDomains()
      await this.fetchGroupedMailboxes()
      await this.fetchMails()
      await this.fetchCounts()
      this.notify('信箱已移除 🫧')
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
          this.notify('潜航捞信完成！收件箱已同步 🫧', 'success')
        }
      } catch (e) {
        console.error('Failed to fetch mails', e)
      } finally {
        this.isLoadingMails = false
      }
    },

    async selectMail(mail) {
      if (!mail) return
      const wasUnread = !mail.is_read
      this.selectedMail = mail
      this.showMascotStage = false
      try {
        const res = await fetch(`/api/mails/${mail.id}`)
        this.selectedMailDetail = await res.json()
        mail.is_read = true
        if (wasUnread) {
          this.fetchCounts()
          this.fetchGroupedMailboxes()
          this.fetchDomains()
        }
      } catch (e) {
        console.error('Failed to get mail detail', e)
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
      const data = await res.json()
      if (!res.ok) {
        throw new Error(data.detail || '发送失败')
      }
      await this.fetchMails()
      await this.fetchCounts()
      this.notify('信件已乘着海流发出啦 🐋✉️', 'success')
      return data
    },

    async updateMailStatus(mailId, updates) {
      await fetch(`/api/mails/${mailId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(updates)
      })
      const inList = this.mails.find(m => m.id === mailId)
      if (inList) Object.assign(inList, updates)
      if (this.selectedMail && this.selectedMail.id === mailId) {
        Object.assign(this.selectedMail, updates)
        if (this.selectedMailDetail) {
          Object.assign(this.selectedMailDetail, updates)
        }
      }
      this.fetchCounts()
    },

    async deleteMail(mailId) {
      const idx = this.mails.findIndex(m => m.id === mailId)
      await fetch(`/api/mails/${mailId}`, { method: 'DELETE' })
      this.mails = this.mails.filter(m => m.id !== mailId)
      this.totalMails = Math.max(0, this.totalMails - 1)
      if (this.selectedMail && this.selectedMail.id === mailId) {
        const nextMail = this.mails[idx] || this.mails[idx - 1] || null
        if (nextMail) {
          this.selectMail(nextMail)
        } else {
          this.selectedMail = null
          this.selectedMailDetail = null
        }
      }
      this.fetchCounts()
      this.fetchGroupedMailboxes()
      this.notify('信件已移至废纸篓 🫧')
    }
  }
})
