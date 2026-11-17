<script setup>
import { ref, computed, watch } from 'vue'
import { useMailStore } from '../stores/mail'
import { X, Check, ChevronDown, Loader2, MailPlus } from 'lucide-vue-next'

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
    placeholder: 'name@gmail.com',
    guide: '需填入 Google 账号 16 位「应用专用密码 (App Password)」'
  },
  {
    id: 'qq',
    name: 'QQ 邮箱',
    domains: ['qq.com', 'foxmail.com', 'vip.qq.com'],
    imap_host: 'imap.qq.com',
    imap_port: 993,
    smtp_host: 'smtp.qq.com',
    smtp_port: 465,
    placeholder: '123456@qq.com',
    guide: '需在 QQ 邮箱「设置 → 账户」开启 IMAP/SMTP 并生成授权码'
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
    guide: '需在网易邮箱开启 IMAP/SMTP 并填入客户端授权密码'
  },
  {
    id: 'outlook',
    name: 'Outlook',
    domains: ['outlook.com', 'hotmail.com', 'live.com', 'msn.com'],
    imap_host: 'outlook.office365.com',
    imap_port: 993,
    smtp_host: 'smtp.office365.com',
    smtp_port: 587,
    placeholder: 'name@outlook.com',
    guide: '需填入 Microsoft 账户应用专用密码并开启 IMAP'
  },
  {
    id: 'icloud',
    name: 'iCloud',
    domains: ['icloud.com', 'me.com', 'mac.com'],
    imap_host: 'imap.mail.me.com',
    imap_port: 993,
    smtp_host: 'smtp.mail.me.com',
    smtp_port: 587,
    placeholder: 'name@icloud.com',
    guide: '需在 appleid.apple.com 生成 Apple 账户「App 专用密码」'
  },
  {
    id: 'custom',
    name: '自定义',
    domains: [],
    imap_host: '',
    imap_port: 993,
    smtp_host: '',
    smtp_port: 465,
    placeholder: 'user@company.com',
    guide: '手动配置自定义 IMAP 收信与 SMTP 发信服务器地址'
  }
]

const selectedProvider = ref('icloud')
const address = ref('')
const authPassword = ref('')
const remarkName = ref('')
const imapHost = ref('imap.mail.me.com')
const imapPort = ref(993)
const smtpHost = ref('smtp.mail.me.com')
const smtpPort = ref(587)
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
    statusMsg.value = { type: 'error', text: '请填写完整的邮箱地址与授权码 / 应用专用密码' }
    return
  }
  isTesting.value = true
  statusMsg.value = null
  try {
    const res = await store.testExternalMailbox(buildPayload())
    statusMsg.value = { type: 'success', text: res.message || '连接验证成功' }
  } catch (err) {
    statusMsg.value = { type: 'error', text: err.message || '连接验证失败' }
  } finally {
    isTesting.value = false
  }
}

const handleSaveAndSync = async () => {
  if (!address.value.trim() || !authPassword.value.trim()) {
    statusMsg.value = { type: 'error', text: '请填写完整的邮箱地址与授权码 / 应用专用密码' }
    return
  }
  isSaving.value = true
  statusMsg.value = null
  try {
    await store.saveExternalMailbox(buildPayload())
    closeModal()
  } catch (err) {
    statusMsg.value = { type: 'error', text: err.message || '接入失败' }
  } finally {
    isSaving.value = false
  }
}
</script>

<template>
  <Transition name="mac-sheet-fade">
    <div
      v-if="store.isExternalModalOpen"
      class="fixed inset-0 mac-backdrop z-50 flex items-end sm:items-center justify-center p-0 sm:p-4 select-none"
      @click.self="closeModal"
    >
      <div class="mac-sheet rounded-t-[18px] sm:rounded-[16px] w-full max-w-[470px] max-h-[90dvh] overflow-y-auto p-4 sm:p-5 pb-safe space-y-4">
        <div class="flex items-center justify-between pb-2.5 mac-hairline-b">
          <div class="flex items-center gap-2">
            <MailPlus class="w-4 h-4 text-[var(--apple-blue)]" />
            <h3 class="text-[14px] font-semibold text-[var(--label-primary)]">
              {{ store.editingExternalMailbox ? '更新外部邮箱账户凭据' : '添加外部邮箱账户' }}
            </h3>
          </div>
          <button
            type="button"
            @click="closeModal"
            class="w-6 h-6 rounded-full bg-[var(--fill-tertiary)] hover:bg-[var(--fill-secondary)] flex items-center justify-center text-[var(--label-secondary)] transition"
          >
            <X class="w-3.5 h-3.5" />
          </button>
        </div>

        <!-- macOS Segmented Provider Picker -->
        <div class="grid grid-cols-3 sm:grid-cols-6 gap-1 p-1 rounded-[10px] bg-[var(--seg-track)]">
          <button
            v-for="p in PROVIDERS"
            :key="p.id"
            type="button"
            @click="selectProvider(p.id)"
            :class="[
              'py-1.5 px-1 rounded-[7px] text-[11.5px] transition text-center truncate',
              selectedProvider === p.id
                ? 'bg-[var(--seg-thumb)] text-[var(--label-primary)] font-semibold shadow-[var(--seg-thumb-shadow)]'
                : 'text-[var(--label-secondary)] hover:text-[var(--label-primary)]'
            ]"
          >
            {{ p.name }}
          </button>
        </div>

        <div class="space-y-3">
          <div class="grid grid-cols-1 sm:grid-cols-3 gap-2">
            <input
              v-model="address"
              @input="handleAddressInput"
              type="email"
              :placeholder="currentProviderCfg.placeholder"
              class="sm:col-span-2 h-9 px-3 rounded-[9px] bg-[var(--bg-input-solid)] border border-[var(--separator-strong)] focus:border-[var(--apple-blue)] focus:ring-2 focus:ring-[var(--apple-blue)]/20 text-[12.5px] font-mono text-[var(--label-primary)] placeholder-[var(--label-secondary)] focus:outline-none transition"
            />
            <input
              v-model="remarkName"
              type="text"
              placeholder="备注名称 (选填)"
              class="h-9 px-3 rounded-[9px] bg-[var(--bg-input-solid)] border border-[var(--separator-strong)] focus:border-[var(--apple-blue)] focus:ring-2 focus:ring-[var(--apple-blue)]/20 text-[12.5px] text-[var(--label-primary)] placeholder-[var(--label-secondary)] focus:outline-none transition"
            />
          </div>

          <div class="space-y-1">
            <input
              v-model="authPassword"
              type="password"
              placeholder="输入授权码 / App 专用密码"
              class="w-full h-9 px-3 rounded-[9px] bg-[var(--bg-input-solid)] border border-[var(--separator-strong)] focus:border-[var(--apple-blue)] focus:ring-2 focus:ring-[var(--apple-blue)]/20 text-[12.5px] font-mono text-[var(--label-primary)] placeholder-[var(--label-secondary)] focus:outline-none transition"
            />
            <p class="text-[11px] text-[var(--label-secondary)] px-1">{{ currentProviderCfg.guide }}</p>
          </div>

          <!-- Group Assignment & VIP Row -->
          <div class="space-y-2 pt-0.5">
            <div v-if="availableLabels.length > 0" class="flex flex-wrap gap-1.5">
              <button
                v-for="lbl in availableLabels"
                :key="lbl.id"
                type="button"
                @click="toggleLabel(lbl.id)"
                :class="[
                  'px-2.5 py-1 rounded-[7px] text-[11.5px] flex items-center gap-1.5 transition border',
                  selectedLabelIds.includes(lbl.id)
                    ? 'bg-[var(--fill-active-subtle)] border-[var(--apple-blue)] text-[var(--apple-blue)] font-medium'
                    : 'bg-[var(--fill-quaternary)] border-[var(--separator)] text-[var(--label-primary)] hover:bg-[var(--fill-hover)]'
                ]"
              >
                <span>{{ lbl.name }}</span>
                <Check v-if="selectedLabelIds.includes(lbl.id)" class="w-3 h-3" />
              </button>
            </div>

            <div
              @click="isVip = !isVip"
              class="flex items-center justify-between px-3 py-2 rounded-[9px] bg-[var(--fill-quaternary)] border border-[var(--separator)] cursor-pointer"
            >
              <span class="text-[12.5px] text-[var(--label-primary)] font-medium">
                标记为 VIP 重点邮箱
              </span>
              <button
                type="button"
                role="switch"
                :aria-checked="isVip"
                :class="[
                  'w-[34px] h-[20px] rounded-full p-[2px] transition-colors flex items-center',
                  isVip ? 'bg-[#34C759]' : 'bg-[var(--fill-secondary)]'
                ]"
              >
                <span
                  :class="[
                    'w-[16px] h-[16px] rounded-full bg-white shadow transition-transform',
                    isVip ? 'translate-x-[14px]' : 'translate-x-0'
                  ]"
                />
              </button>
            </div>
          </div>

          <!-- Collapsible IMAP / SMTP Server Settings -->
          <div class="rounded-[10px] border border-[var(--separator)] bg-[var(--fill-quaternary)] overflow-hidden">
            <button
              type="button"
              @click="showAdvanced = !showAdvanced"
              class="w-full px-3 py-2 flex items-center justify-between text-[11px] font-mono text-[var(--label-secondary)] hover:text-[var(--label-primary)] transition"
            >
              <span class="truncate pr-2">IMAP {{ imapHost || '未设置' }}:{{ imapPort }} · SMTP {{ smtpHost || '未设置' }}:{{ smtpPort }}</span>
              <ChevronDown :class="['w-3.5 h-3.5 flex-shrink-0 transition-transform', { 'rotate-180': showAdvanced }]" />
            </button>

            <div v-if="showAdvanced" class="p-2.5 mac-hairline-t grid grid-cols-3 gap-2">
              <input
                v-model="imapHost"
                type="text"
                placeholder="IMAP 服务器"
                class="col-span-2 h-8 px-2.5 rounded-[7px] bg-[var(--bg-input-solid)] border border-[var(--separator-strong)] text-[12px] font-mono text-[var(--label-primary)] focus:outline-none"
              />
              <input
                v-model.number="imapPort"
                type="number"
                placeholder="993"
                class="h-8 px-2.5 rounded-[7px] bg-[var(--bg-input-solid)] border border-[var(--separator-strong)] text-[12px] font-mono text-[var(--label-primary)] focus:outline-none"
              />
              <input
                v-model="smtpHost"
                type="text"
                placeholder="SMTP 服务器"
                class="col-span-2 h-8 px-2.5 rounded-[7px] bg-[var(--bg-input-solid)] border border-[var(--separator-strong)] text-[12px] font-mono text-[var(--label-primary)] focus:outline-none"
              />
              <input
                v-model.number="smtpPort"
                type="number"
                placeholder="465"
                class="h-8 px-2.5 rounded-[7px] bg-[var(--bg-input-solid)] border border-[var(--separator-strong)] text-[12px] font-mono text-[var(--label-primary)] focus:outline-none"
              />
            </div>
          </div>
        </div>

        <!-- Connection Test Status Banner -->
        <div
          v-if="statusMsg"
          :class="[
            'px-3 py-2 rounded-[9px] border text-[12px] font-medium',
            statusMsg.type === 'success'
              ? 'bg-[#34C759]/12 border-[#34C759]/30 text-[var(--apple-green)]'
              : 'bg-[#FF3B30]/12 border-[#FF3B30]/30 text-[var(--apple-red)]'
          ]"
        >
          {{ statusMsg.text }}
        </div>

        <div class="flex items-center justify-between pt-2 mac-hairline-t">
          <button
            type="button"
            @click="handleTestConnection"
            :disabled="isTesting || isSaving"
            class="mac-btn-secondary h-[30px] px-3 rounded-[8px] text-[12px] font-medium disabled:opacity-40 flex items-center gap-1.5"
          >
            <Loader2 v-if="isTesting" class="w-3.5 h-3.5 animate-spin text-[var(--apple-blue)]" />
            <span>{{ isTesting ? '正在验证...' : '测试连接' }}</span>
          </button>

          <div class="flex items-center gap-2">
            <button
              type="button"
              @click="closeModal"
              class="mac-btn-secondary h-[30px] px-3.5 rounded-[8px] text-[12.5px] font-medium"
            >
              取消
            </button>
            <button
              type="button"
              @click="handleSaveAndSync"
              :disabled="isSaving || isTesting"
              class="mac-btn-blue h-[30px] px-4 rounded-[8px] text-[12.5px] font-medium disabled:opacity-40 flex items-center gap-1.5"
            >
              <Loader2 v-if="isSaving" class="w-3.5 h-3.5 animate-spin" />
              <span>{{ isSaving ? '正在同步...' : '存储并同步' }}</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  </Transition>
</template>
