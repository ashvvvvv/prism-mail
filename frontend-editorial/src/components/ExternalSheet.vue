<script setup>
import { ref, computed, watch } from 'vue'
import { useMailStore } from '../stores/mail'
import { X, Check, ChevronDown, Loader2 } from 'lucide-vue-next'

const store = useMailStore()

const PROVIDERS = [
  {
    id: 'gmail',
    name: 'Gmail',
    domains: ['gmail.com', 'googlemail.com'],
    imap_host: 'imap.gmail.com',
    imap_port: 993,
    smtp_host: 'smtp.gmail.com',
    smtp_port: 465,
    placeholder: 'editor@gmail.com',
    guide: '请使用 Google 账户 16 位「应用专用密码 (App Password)」'
  },
  {
    id: 'qq',
    name: 'QQ 邮箱',
    domains: ['qq.com', 'foxmail.com', 'vip.qq.com'],
    imap_host: 'imap.qq.com',
    imap_port: 993,
    smtp_host: 'smtp.qq.com',
    smtp_port: 465,
    placeholder: '10001@qq.com',
    guide: '请在 QQ 邮箱「设置 → 账户」开启 IMAP/SMTP 服务并生成授权码'
  },
  {
    id: '163',
    name: '网易 163',
    domains: ['163.com', '126.com', 'yeah.net'],
    imap_host: 'imap.163.com',
    imap_port: 993,
    smtp_host: 'smtp.163.com',
    smtp_port: 465,
    placeholder: 'name@163.com',
    guide: '请在网易邮箱开启 IMAP/SMTP 服务并填写客户端授权密码'
  },
  {
    id: 'outlook',
    name: 'Outlook',
    domains: ['outlook.com', 'hotmail.com', 'live.com', 'msn.com'],
    imap_host: 'outlook.office365.com',
    imap_port: 993,
    smtp_host: 'smtp.office365.com',
    smtp_port: 587,
    placeholder: 'desk@outlook.com',
    guide: '请填写 Microsoft 账户应用专用密码并确保已启用 IMAP'
  },
  {
    id: 'icloud',
    name: 'iCloud',
    domains: ['icloud.com', 'me.com', 'mac.com'],
    imap_host: 'imap.mail.me.com',
    imap_port: 993,
    smtp_host: 'smtp.mail.me.com',
    smtp_port: 587,
    placeholder: 'reader@icloud.com',
    guide: '请前往 appleid.apple.com 生成 App 专用密码'
  },
  {
    id: 'custom',
    name: '自定义 IMAP',
    domains: [],
    imap_host: '',
    imap_port: 993,
    smtp_host: '',
    smtp_port: 465,
    placeholder: 'name@press-agency.com',
    guide: '手动配置任意标准 IMAP 与 SMTP 邮局服务器主机及端口'
  }
]

const selectedProvider = ref('gmail')
const address = ref('')
const authPassword = ref('')
const remarkName = ref('')
const imapHost = ref('imap.gmail.com')
const imapPort = ref(993)
const smtpHost = ref('smtp.gmail.com')
const smtpPort = ref(465)
const selectedLabelIds = ref([])
const isVip = ref(false)
const showAdvanced = ref(false)

const isTesting = ref(false)
const isSaving = ref(false)
const statusMsg = ref(null)

const currentProviderCfg = computed(() => {
  return PROVIDERS.find(p => p.id === selectedProvider.value) || PROVIDERS[0]
})

const availableLabels = computed(() => {
  return store.mailboxLabels || []
})

const selectProvider = (provId) => {
  selectedProvider.value = provId
  const cfg = PROVIDERS.find(p => p.id === provId)
  if (cfg) {
    imapHost.value = cfg.imap_host
    imapPort.value = cfg.imap_port
    smtpHost.value = cfg.smtp_host
    smtpPort.value = cfg.smtp_port
    showAdvanced.value = provId === 'custom'
  }
  statusMsg.value = null
}

const handleAddressInput = () => {
  statusMsg.value = null
  const val = address.value.trim().toLowerCase()
  if (!val.includes('@')) return
  const dom = val.split('@')[1]
  if (!dom) return

  if (dom === '126.com') {
    selectedProvider.value = '163'
    imapHost.value = 'imap.126.com'
    imapPort.value = 993
    smtpHost.value = 'smtp.126.com'
    smtpPort.value = 465
    return
  }
  if (dom === 'yeah.net') {
    selectedProvider.value = '163'
    imapHost.value = 'imap.yeah.net'
    imapPort.value = 993
    smtpHost.value = 'smtp.yeah.net'
    smtpPort.value = 465
    return
  }

  for (const p of PROVIDERS) {
    if (p.domains.includes(dom)) {
      selectedProvider.value = p.id
      imapHost.value = p.imap_host
      imapPort.value = p.imap_port
      smtpHost.value = p.smtp_host
      smtpPort.value = p.smtp_port
      return
    }
  }
}

const toggleLabel = (id) => {
  const idx = selectedLabelIds.value.indexOf(id)
  if (idx > -1) {
    selectedLabelIds.value.splice(idx, 1)
  } else {
    selectedLabelIds.value.push(id)
  }
}

watch(
  () => store.isExternalModalOpen,
  (isOpen) => {
    if (isOpen) {
      statusMsg.value = null
      const editing = store.editingExternalMailbox
      if (editing) {
        selectedProvider.value = editing.provider && editing.provider !== 'local' ? editing.provider : 'custom'
        address.value = editing.address || ''
        authPassword.value = ''
        remarkName.value = editing.name && editing.name !== editing.prefix ? editing.name : ''
        imapHost.value = editing.imap_host || ''
        imapPort.value = editing.imap_port || 993
        smtpHost.value = editing.smtp_host || ''
        smtpPort.value = editing.smtp_port || 465
        selectedLabelIds.value = [...(editing.label_ids || (editing.labels ? editing.labels.map(l => l.id) : []))]
        isVip.value = Boolean(editing.is_vip)
        showAdvanced.value = selectedProvider.value === 'custom'
      } else {
        selectProvider('gmail')
        address.value = ''
        authPassword.value = ''
        remarkName.value = ''
        const defaultLbl = availableLabels.value.find(l => l.name === '核心日常与管理') || availableLabels.value[0]
        selectedLabelIds.value = defaultLbl ? [defaultLbl.id] : []
        isVip.value = false
        showAdvanced.value = false
      }
    } else {
      store.editingExternalMailbox = null
    }
  }
)

const closeModal = () => {
  store.isExternalModalOpen = false
}

const buildPayload = () => ({
  address: address.value.trim(),
  auth_password: authPassword.value.trim(),
  name: remarkName.value.trim(),
  provider: selectedProvider.value,
  imap_host: imapHost.value.trim(),
  imap_port: Number(imapPort.value) || 993,
  smtp_host: smtpHost.value.trim(),
  smtp_port: Number(smtpPort.value) || 465,
  label_ids: selectedLabelIds.value,
  is_vip: isVip.value,
  test_smtp: true
})

const handleTestConnection = async () => {
  if (!address.value.trim() || !authPassword.value.trim()) {
    statusMsg.value = { type: 'error', text: '请填写完整的外部邮箱地址与授权密码' }
    return
  }
  isTesting.value = true
  statusMsg.value = null
  try {
    const res = await store.testExternalMailbox(buildPayload())
    statusMsg.value = { type: 'success', text: res.message }
  } catch (err) {
    statusMsg.value = { type: 'error', text: err.message || '服务器握手验证失败' }
  } finally {
    isTesting.value = false
  }
}

const handleSaveAndSync = async () => {
  if (!address.value.trim() || !authPassword.value.trim()) {
    statusMsg.value = { type: 'error', text: '请填写完整的外部邮箱地址与授权密码' }
    return
  }
  isSaving.value = true
  statusMsg.value = null
  try {
    await store.saveExternalMailbox(buildPayload())
    closeModal()
  } catch (err) {
    statusMsg.value = { type: 'error', text: err.message || '外部信箱接入失败' }
  } finally {
    isSaving.value = false
  }
}
</script>

<template>
  <Transition name="folio-fade">
    <div
      v-if="store.isExternalModalOpen"
      class="fixed inset-0 ed-backdrop z-50 flex items-end sm:items-center justify-center p-0 sm:p-4"
      @click.self="closeModal"
    >
      <div class="ed-folio-modal w-full max-w-lg max-h-[90dvh] flex flex-col overflow-hidden">
        <!-- Header -->
        <div class="px-4 sm:px-5 py-3.5 border-b border-[var(--rule-medium)] bg-[var(--bg-linen)] flex items-center justify-between flex-shrink-0">
          <h3 class="font-serif text-[17px] font-medium text-[var(--ink-primary)]">
            {{ store.editingExternalMailbox ? '更新外部邮箱凭据' : '添加外部邮箱' }}
          </h3>
          <button @click="closeModal" class="text-[var(--ink-muted)] hover:text-[var(--ink-primary)]">
            <X class="w-4 h-4" />
          </button>
        </div>

        <div class="p-4 sm:p-5 space-y-4 overflow-y-auto">
          <!-- Provider Segmented Matrix -->
          <div class="grid grid-cols-3 sm:grid-cols-6 border border-[var(--rule-medium)] rounded-[2px] bg-[var(--bg-subtle)] p-[1px] gap-[1px]">
            <button
              v-for="p in PROVIDERS"
              :key="p.id"
              type="button"
              @click="selectProvider(p.id)"
              :class="[
                'py-1.5 px-1 text-[11px] transition text-center truncate rounded-[1px]',
                selectedProvider === p.id
                  ? 'bg-[var(--ink-primary)] text-[var(--bg-salon)] font-medium'
                  : 'text-[var(--ink-muted)] hover:text-[var(--ink-primary)] hover:bg-[var(--bg-hover)]'
              ]"
            >
              {{ p.name }}
            </button>
          </div>

          <!-- Credentials Inputs -->
          <div class="space-y-3">
            <div class="grid grid-cols-1 sm:grid-cols-3 gap-2.5">
              <input
                v-model="address"
                @input="handleAddressInput"
                type="email"
                :placeholder="currentProviderCfg.placeholder"
                class="sm:col-span-2 bg-[var(--bg-input)] border border-[var(--rule-medium)] focus:border-[var(--rule-strong)] rounded-[2px] px-3 py-2 text-[12.5px] font-mono text-[var(--ink-primary)] placeholder-[var(--ink-faint)] focus:outline-none transition"
              />
              <input
                v-model="remarkName"
                type="text"
                placeholder="备注名称 (选填)"
                class="bg-[var(--bg-input)] border border-[var(--rule-medium)] focus:border-[var(--rule-strong)] rounded-[2px] px-3 py-2 text-[12.5px] text-[var(--ink-primary)] placeholder-[var(--ink-faint)] focus:outline-none transition"
              />
            </div>

            <div class="space-y-1">
              <input
                v-model="authPassword"
                type="password"
                placeholder="输入授权码 / 应用专用密码"
                class="w-full bg-[var(--bg-input)] border border-[var(--rule-medium)] focus:border-[var(--rule-strong)] rounded-[2px] px-3 py-2 text-[12.5px] font-mono text-[var(--ink-primary)] placeholder-[var(--ink-faint)] focus:outline-none transition"
              />
              <p class="text-[11px] text-[var(--ink-muted)]">{{ currentProviderCfg.guide }}</p>
            </div>

            <!-- Group Assignment & VIP -->
            <div class="space-y-2 pt-0.5">
              <div v-if="availableLabels.length > 0" class="flex flex-wrap gap-1.5">
                <button
                  v-for="lbl in availableLabels"
                  :key="lbl.id"
                  type="button"
                  @click="toggleLabel(lbl.id)"
                  :class="[
                    'px-2.5 py-1 rounded-[2px] text-[11.5px] flex items-center gap-1.5 transition border',
                    selectedLabelIds.includes(lbl.id)
                      ? 'bg-[var(--bg-active)] border-[var(--rule-strong)] text-[var(--ink-primary)] font-medium'
                      : 'bg-[var(--bg-input)] border-[var(--rule-faint)] text-[var(--ink-secondary)] hover:border-[var(--rule-medium)]'
                  ]"
                >
                  <span>{{ lbl.name }}</span>
                  <Check v-if="selectedLabelIds.includes(lbl.id)" class="w-3 h-3 text-[var(--accent-vermilion)]" />
                </button>
              </div>

              <label class="inline-flex items-center gap-2 text-[12px] text-[var(--ink-secondary)] cursor-pointer select-none">
                <input type="checkbox" v-model="isVip" class="w-3.5 h-3.5 accent-[#C84B31]" />
                <span>标记为重点关注信箱 (VIP)</span>
              </label>
            </div>

            <!-- Advanced IMAP / SMTP Server Parameters -->
            <div class="rounded-[2px] border border-[var(--rule-medium)] bg-[var(--bg-subtle)] overflow-hidden">
              <button
                type="button"
                @click="showAdvanced = !showAdvanced"
                class="w-full px-3 py-1.5 flex items-center justify-between text-[11px] font-mono text-[var(--ink-muted)] hover:text-[var(--ink-primary)] transition"
              >
                <span class="truncate pr-2">IMAP {{ imapHost || '未配置' }}:{{ imapPort }} · SMTP {{ smtpHost || '未配置' }}:{{ smtpPort }}</span>
                <ChevronDown :class="['w-3.5 h-3.5 flex-shrink-0 transition-transform', { 'rotate-180': showAdvanced }]" />
              </button>

              <div v-if="showAdvanced" class="p-2.5 border-t border-[var(--rule-faint)] grid grid-cols-3 gap-2 bg-[var(--bg-ledger)]">
                <input
                  v-model="imapHost"
                  type="text"
                  placeholder="IMAP 主机 (如 imap.domain.com)"
                  class="col-span-2 bg-[var(--bg-input)] border border-[var(--rule-medium)] rounded-[2px] px-2.5 py-1.5 text-[12px] font-mono text-[var(--ink-primary)] focus:outline-none"
                />
                <input
                  v-model.number="imapPort"
                  type="number"
                  placeholder="993"
                  class="bg-[var(--bg-input)] border border-[var(--rule-medium)] rounded-[2px] px-2.5 py-1.5 text-[12px] font-mono text-[var(--ink-primary)] focus:outline-none"
                />
                <input
                  v-model="smtpHost"
                  type="text"
                  placeholder="SMTP 主机 (如 smtp.domain.com)"
                  class="col-span-2 bg-[var(--bg-input)] border border-[var(--rule-medium)] rounded-[2px] px-2.5 py-1.5 text-[12px] font-mono text-[var(--ink-primary)] focus:outline-none"
                />
                <input
                  v-model.number="smtpPort"
                  type="number"
                  placeholder="465"
                  class="bg-[var(--bg-input)] border border-[var(--rule-medium)] rounded-[2px] px-2.5 py-1.5 text-[12px] font-mono text-[var(--ink-primary)] focus:outline-none"
                />
              </div>
            </div>
          </div>

          <!-- Status Banner -->
          <div
            v-if="statusMsg"
            :class="[
              'px-3 py-2 rounded-[2px] border text-[12px] font-mono',
              statusMsg.type === 'success'
                ? 'bg-[var(--accent-forest-soft)] border-[var(--accent-forest-border)] text-[var(--accent-forest)]'
                : 'bg-[var(--accent-vermilion-soft)] border-[var(--accent-vermilion-border)] text-[var(--accent-vermilion)]'
            ]"
          >
            {{ statusMsg.text }}
          </div>
        </div>

        <!-- Footer -->
        <div class="px-4 sm:px-5 py-3 pb-safe border-t border-[var(--rule-medium)] bg-[var(--bg-linen)] flex items-center justify-between flex-shrink-0">
          <button
            type="button"
            @click="handleTestConnection"
            :disabled="isTesting || isSaving"
            class="ed-btn-outline px-3 py-1.5 text-[12px] disabled:opacity-40 flex items-center gap-1.5"
          >
            <Loader2 v-if="isTesting" class="w-3.5 h-3.5 animate-spin" />
            <span>{{ isTesting ? '验证中...' : '测试连接' }}</span>
          </button>

          <div class="flex items-center gap-2">
            <button
              type="button"
              @click="closeModal"
              class="ed-btn-outline px-3.5 py-1.5 text-[12px]"
            >
              取消
            </button>
            <button
              type="button"
              @click="handleSaveAndSync"
              :disabled="isSaving || isTesting"
              class="ed-btn-ink px-4 py-1.5 text-[12px] font-medium disabled:opacity-40 flex items-center gap-1.5"
            >
              <Loader2 v-if="isSaving" class="w-3.5 h-3.5 animate-spin" />
              <span>{{ isSaving ? '同步中...' : '保存并同步' }}</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  </Transition>
</template>
