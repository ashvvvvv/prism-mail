<script setup>
import { ref, computed, watch } from 'vue'
import { useMailStore } from '../stores/mail'
import { X, Copy, Check, Globe, ShieldCheck, Trash2 } from 'lucide-vue-next'

const store = useMailStore()

const domainName = ref('')
const domainDesc = ref('')
const copiedKey = ref('')

const customDomains = computed(() => {
  return (store.domains || []).filter(d => !d.is_external)
})

watch(
  () => store.isDomainModalOpen,
  (isOpen) => {
    if (isOpen) {
      domainName.value = ''
      domainDesc.value = ''
    }
  }
)

const closeAdd = () => {
  store.isDomainModalOpen = false
}

const closeDns = () => {
  store.activeDomainDns = null
}

const openDnsFromList = (dom) => {
  store.isDomainModalOpen = false
  store.activeDomainDns = dom
}

const copyValue = async (key, text) => {
  if (!text) return
  try {
    await navigator.clipboard.writeText(text)
    copiedKey.value = key
    store.notify(`已拷贝 ${key.toUpperCase()} 记录`, 'success')
    setTimeout(() => {
      if (copiedKey.value === key) copiedKey.value = ''
    }, 1600)
  } catch {}
}

const handleCreateDomain = async () => {
  const clean = domainName.value.trim().replace(/^@/, '')
  if (!clean) return
  try {
    const created = await store.createDomain(clean, domainDesc.value.trim())
    domainName.value = ''
    domainDesc.value = ''
    if (created && created.dns_records) {
      store.isDomainModalOpen = false
      store.activeDomainDns = created
    }
  } catch {}
}

const handleDeleteDomain = async (domain) => {
  const ok = await store.askConfirm({
    title: `移除域名 @${domain.name}？`,
    message: `移除域名将同时清理 @${domain.name} 下的关联邮箱地址，确定继续吗？`,
    confirmText: '移除域名',
    danger: true
  })
  if (ok) {
    try {
      await store.deleteDomain(domain.id)
      if (store.activeDomainDns?.id === domain.id) {
        closeDns()
      }
    } catch {}
  }
}

const dnsRows = computed(() => {
  const recs = store.activeDomainDns?.dns_records || {}
  return [
    { key: 'mx', label: 'MX', host: '@ · 优先级 10', val: recs.mx || '' },
    { key: 'spf', label: 'SPF', host: 'TXT · @', val: recs.spf || '' },
    { key: 'dkim', label: 'DKIM', host: 'TXT · default._domainkey', val: recs.dkim_value || '' },
    { key: 'dmarc', label: 'DMARC', host: 'TXT · _dmarc', val: recs.dmarc || '' }
  ]
})
</script>

<template>
  <!-- Sheet 1: Custom Domains Manager & Bind New Domain -->
  <Transition name="mac-sheet-fade">
    <div
      v-if="store.isDomainModalOpen"
      class="fixed inset-0 mac-backdrop z-50 flex items-end sm:items-center justify-center p-0 sm:p-4 select-none"
      @click.self="closeAdd"
    >
      <div class="mac-sheet rounded-t-[18px] sm:rounded-[16px] w-full max-w-[430px] max-h-[90dvh] overflow-y-auto p-4 sm:p-5 pb-safe space-y-4">
        <div class="flex items-center justify-between pb-2 mac-hairline-b">
          <div class="flex items-center gap-2">
            <Globe class="w-4 h-4 text-[var(--apple-blue)]" />
            <h3 class="text-[14px] font-semibold text-[var(--label-primary)]">自定义域名管理</h3>
          </div>
          <button
            type="button"
            @click="closeAdd"
            class="w-6 h-6 rounded-full bg-[var(--fill-tertiary)] hover:bg-[var(--fill-secondary)] flex items-center justify-center text-[var(--label-secondary)] transition"
          >
            <X class="w-3.5 h-3.5" />
          </button>
        </div>

        <!-- Existing Custom Domains List -->
        <div v-if="customDomains.length > 0" class="space-y-1.5 max-h-[168px] overflow-y-auto pr-0.5">
          <span class="text-[11.5px] font-medium text-[var(--label-secondary)] px-0.5">已绑定域名</span>
          <div
            v-for="dom in customDomains"
            :key="dom.id"
            class="px-3 py-2 rounded-[10px] bg-[var(--fill-quaternary)] border border-[var(--separator)] flex items-center justify-between gap-2"
          >
            <div class="min-w-0">
              <p class="text-[12.5px] font-mono font-semibold text-[var(--label-primary)] truncate">
                @{{ dom.name }}
              </p>
              <p class="text-[11px] text-[var(--label-secondary)] truncate">
                {{ dom.mailboxes?.length || 0 }} 个邮箱 {{ dom.description ? `· ${dom.description}` : '' }}
              </p>
            </div>
            <div class="flex items-center gap-1.5 flex-shrink-0">
              <button
                type="button"
                @click="openDnsFromList(dom)"
                class="px-2 py-1 rounded-[7px] bg-[var(--fill-active-subtle)] text-[var(--apple-blue)] text-[11.5px] font-medium flex items-center gap-1 hover:opacity-85 transition"
              >
                <ShieldCheck class="w-3 h-3" />
                <span>DNS 记录</span>
              </button>
              <button
                type="button"
                @click="handleDeleteDomain(dom)"
                class="p-1.5 rounded-[7px] text-[var(--label-secondary)] hover:text-[var(--apple-red)] hover:bg-[var(--fill-hover)] transition"
                title="移除域名"
              >
                <Trash2 class="w-3.5 h-3.5" />
              </button>
            </div>
          </div>
        </div>

        <!-- Add New Domain Form -->
        <div class="space-y-2.5 pt-1">
          <span class="text-[11.5px] font-medium text-[var(--label-secondary)] px-0.5 block">添加新域名</span>
          <input
            v-model="domainName"
            @keydown.enter.prevent="handleCreateDomain"
            type="text"
            placeholder="输入域名（例如 example.com）"
            autofocus
            class="w-full h-9 px-3 rounded-[9px] bg-[var(--bg-input-solid)] border border-[var(--separator-strong)] focus:border-[var(--apple-blue)] focus:ring-2 focus:ring-[var(--apple-blue)]/20 text-[13px] font-mono text-[var(--label-primary)] placeholder-[var(--label-secondary)] focus:outline-none transition"
          />
          <input
            v-model="domainDesc"
            @keydown.enter.prevent="handleCreateDomain"
            type="text"
            placeholder="用途备注（选填）"
            class="w-full h-9 px-3 rounded-[9px] bg-[var(--bg-input-solid)] border border-[var(--separator-strong)] focus:border-[var(--apple-blue)] focus:ring-2 focus:ring-[var(--apple-blue)]/20 text-[13px] text-[var(--label-primary)] placeholder-[var(--label-secondary)] focus:outline-none transition"
          />
        </div>

        <div class="flex items-center justify-end gap-2 pt-1">
          <button
            type="button"
            @click="closeAdd"
            class="mac-btn-secondary h-[30px] px-3.5 rounded-[8px] text-[12.5px] font-medium"
          >
            关闭
          </button>
          <button
            type="button"
            @click="handleCreateDomain"
            :disabled="!domainName.trim()"
            class="mac-btn-blue h-[30px] px-4 rounded-[8px] text-[12.5px] font-medium disabled:opacity-40"
          >
            添加并查看 DNS
          </button>
        </div>
      </div>
    </div>
  </Transition>

  <!-- Sheet 2: 1-Click Copy DNS Records (MX, SPF, DKIM, DMARC) -->
  <Transition name="mac-sheet-fade">
    <div
      v-if="store.activeDomainDns"
      class="fixed inset-0 mac-backdrop z-50 flex items-end sm:items-center justify-center p-0 sm:p-4 select-none"
      @click.self="closeDns"
    >
      <div class="mac-sheet rounded-t-[18px] sm:rounded-[16px] w-full max-w-[520px] max-h-[90dvh] overflow-y-auto p-4 sm:p-5 pb-safe space-y-4">
        <div class="flex items-center justify-between pb-2.5 mac-hairline-b">
          <div class="flex items-center gap-2">
            <ShieldCheck class="w-4 h-4 text-[var(--apple-green)]" />
            <span class="text-[14px] font-semibold text-[var(--label-primary)]">
              DNS 解析配置 · <span class="font-mono text-[var(--apple-blue)]">@{{ store.activeDomainDns.name }}</span>
            </span>
          </div>
          <button
            type="button"
            @click="closeDns"
            class="w-6 h-6 rounded-full bg-[var(--fill-tertiary)] hover:bg-[var(--fill-secondary)] flex items-center justify-center text-[var(--label-secondary)] transition"
          >
            <X class="w-3.5 h-3.5" />
          </button>
        </div>

        <div class="space-y-2.5 max-h-[340px] overflow-y-auto pr-0.5">
          <div
            v-for="rec in dnsRows"
            :key="rec.key"
            class="p-3 rounded-[10px] bg-[var(--fill-quaternary)] border border-[var(--separator)] space-y-1.5"
          >
            <div class="flex items-center justify-between text-[12px]">
              <div class="flex items-center gap-2">
                <span class="px-1.5 py-[1px] rounded-[5px] bg-[var(--fill-active-subtle)] text-[var(--apple-blue)] font-mono text-[11px] font-semibold">
                  {{ rec.label }}
                </span>
                <span class="font-mono text-[11.5px] text-[var(--label-secondary)]">{{ rec.host }}</span>
              </div>

              <button
                type="button"
                @click="copyValue(rec.key, rec.val)"
                class="px-2 py-0.5 rounded-[6px] bg-[var(--bg-input-solid)] hover:bg-[var(--fill-hover)] border border-[var(--separator)] text-[var(--apple-blue)] text-[11.5px] font-medium flex items-center gap-1 transition"
              >
                <Check v-if="copiedKey === rec.key" class="w-3 h-3 text-[var(--apple-green)]" />
                <Copy v-else class="w-3 h-3" />
                <span>{{ copiedKey === rec.key ? '已拷贝' : '一键拷贝' }}</span>
              </button>
            </div>

            <div class="font-mono text-[11.5px] text-[var(--label-primary)] break-all leading-relaxed select-all bg-[var(--bg-input-solid)]/60 rounded-[6px] px-2.5 py-1.5 border border-[var(--separator-subtle)]">
              {{ rec.val || '暂无记录值' }}
            </div>
          </div>
        </div>

        <div class="flex items-center justify-between pt-2 mac-hairline-t">
          <button
            type="button"
            @click="handleDeleteDomain(store.activeDomainDns)"
            class="text-[12.5px] text-[var(--apple-red)] hover:opacity-80 font-medium transition"
          >
            移除此域名...
          </button>

          <button
            type="button"
            @click="closeDns"
            class="mac-btn-blue h-[30px] px-4 rounded-[8px] text-[12.5px] font-medium"
          >
            完成
          </button>
        </div>
      </div>
    </div>
  </Transition>
</template>
