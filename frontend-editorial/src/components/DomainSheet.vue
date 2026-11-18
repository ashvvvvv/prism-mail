<script setup>
import { ref, computed, watch } from 'vue'
import { useMailStore } from '../stores/mail'
import { X, Copy, Check, ShieldCheck, Trash2, Plus } from 'lucide-vue-next'

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

const closeRegistry = () => {
  store.isDomainModalOpen = false
}

const closeDns = () => {
  store.activeDomainDns = null
}

const inspectDnsFromRegistry = (dom) => {
  store.isDomainModalOpen = false
  store.activeDomainDns = dom
}

const copyValue = async (key, text) => {
  if (!text) return
  try {
    await navigator.clipboard.writeText(text)
    copiedKey.value = key
    store.notify(`已复制 ${key.toUpperCase()} 解析记录`, 'success')
    setTimeout(() => {
      if (copiedKey.value === key) copiedKey.value = ''
    }, 1500)
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
    title: '移除域名',
    message: `确定移除 @${domain.name} 及其关联邮箱吗？此操作不可撤销。`,
    confirmText: '移除',
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
</script>

<template>
  <!-- MODAL A: Domain Ledger & New Custom Domain Registration -->
  <Transition name="folio-fade">
    <div
      v-if="store.isDomainModalOpen"
      class="fixed inset-0 ed-backdrop z-50 flex items-end sm:items-center justify-center p-0 sm:p-4"
      @click.self="closeRegistry"
    >
      <div class="ed-folio-modal w-full max-w-md max-h-[90dvh] overflow-y-auto pb-safe">
        <!-- Header -->
        <div class="px-4 sm:px-5 py-3.5 border-b border-[var(--rule-medium)] bg-[var(--bg-linen)] flex items-center justify-between">
          <h3 class="font-serif text-[17px] font-medium text-[var(--ink-primary)]">
            域名管理
          </h3>
          <button @click="closeRegistry" class="text-[var(--ink-muted)] hover:text-[var(--ink-primary)]">
            <X class="w-4 h-4" />
          </button>
        </div>

        <div class="p-4 sm:p-5 space-y-5">
          <!-- Existing Domains Table -->
          <div v-if="customDomains.length > 0" class="space-y-2">
            <span class="ed-rubric block">已绑定域名 ({{ customDomains.length }})</span>
            <div class="border border-[var(--rule-medium)] divide-y divide-[var(--rule-faint)] rounded-[2px] max-h-48 overflow-y-auto bg-[var(--bg-salon)]">
              <div
                v-for="dom in customDomains"
                :key="dom.id"
                class="px-3 py-2 flex items-center justify-between gap-2 text-[12px]"
              >
                <div class="min-w-0">
                  <p class="font-mono font-semibold text-[var(--ink-primary)] truncate">@{{ dom.name }}</p>
                  <p class="text-[11px] text-[var(--ink-muted)] truncate">
                    {{ dom.description || `${dom.mailboxes?.length || 0} 个邮箱` }}
                  </p>
                </div>

                <div class="flex items-center gap-1.5 flex-shrink-0">
                  <button
                    @click="inspectDnsFromRegistry(dom)"
                    class="ed-btn-outline px-2 py-1 text-[11px] font-mono flex items-center gap-1"
                    title="查看 MX / SPF / DKIM / DMARC 记录"
                  >
                    <ShieldCheck class="w-3 h-3 text-[var(--accent-forest)]" />
                    <span>DNS 记录</span>
                  </button>
                  <button
                    @click="handleDeleteDomain(dom)"
                    class="p-1 text-[var(--ink-muted)] hover:text-[var(--accent-vermilion)] transition"
                    title="移除域名"
                  >
                    <Trash2 class="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>
            </div>
          </div>

          <!-- Bind New Custom Domain Form -->
          <div class="space-y-2.5 pt-1">
            <span class="ed-rubric block">添加新域名</span>
            <input
              v-model="domainName"
              @keydown.enter.prevent="handleCreateDomain"
              type="text"
              placeholder="输入域名 (如 example.com)"
              autofocus
              class="w-full bg-[var(--bg-input)] border border-[var(--rule-medium)] focus:border-[var(--rule-strong)] rounded-[2px] px-3 py-2 text-[12.5px] font-mono text-[var(--ink-primary)] placeholder-[var(--ink-faint)] focus:outline-none transition"
            />
            <input
              v-model="domainDesc"
              @keydown.enter.prevent="handleCreateDomain"
              type="text"
              placeholder="用途备注（选填）"
              class="w-full bg-[var(--bg-input)] border border-[var(--rule-medium)] focus:border-[var(--rule-strong)] rounded-[2px] px-3 py-2 text-[12.5px] text-[var(--ink-primary)] placeholder-[var(--ink-faint)] focus:outline-none transition"
            />
          </div>

          <div class="flex items-center justify-end gap-2 pt-3 border-t border-[var(--rule-faint)]">
            <button
              @click="closeRegistry"
              class="ed-btn-outline px-3.5 py-1.5 text-[12px]"
            >
              关闭
            </button>
            <button
              @click="handleCreateDomain"
              :disabled="!domainName.trim()"
              class="ed-btn-ink px-4 py-1.5 text-[12px] font-medium disabled:opacity-40 flex items-center gap-1.5"
            >
              <Plus class="w-3.5 h-3.5" />
              <span>添加域名</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  </Transition>

  <!-- MODAL B: DNS Specification Certificate (MX / SPF / DKIM / DMARC) -->
  <Transition name="folio-fade">
    <div
      v-if="store.activeDomainDns"
      class="fixed inset-0 ed-backdrop z-50 flex items-end sm:items-center justify-center p-0 sm:p-4"
      @click.self="closeDns"
    >
      <div class="ed-folio-modal w-full max-w-lg max-h-[90dvh] flex flex-col overflow-hidden">
        <div class="px-4 sm:px-5 py-3.5 border-b border-[var(--rule-medium)] bg-[var(--bg-linen)] flex items-start justify-between flex-shrink-0">
          <div>
            <span class="ed-rubric text-[var(--accent-forest)] block">DNS 解析记录</span>
            <h3 class="font-mono text-[16px] font-semibold text-[var(--ink-primary)] mt-0.5">
              @{{ store.activeDomainDns.name }}
            </h3>
          </div>
          <button @click="closeDns" class="text-[var(--ink-muted)] hover:text-[var(--ink-primary)]">
            <X class="w-4 h-4" />
          </button>
        </div>

        <div class="p-4 sm:p-5 space-y-3 overflow-y-auto">
          <div
            v-for="rec in [
              { key: 'mx', label: 'MX', host: '@ · 优先级 10', val: store.activeDomainDns.dns_records?.mx },
              { key: 'spf', label: 'SPF', host: 'TXT · @', val: store.activeDomainDns.dns_records?.spf },
              { key: 'dkim', label: 'DKIM', host: 'TXT · default._domainkey', val: store.activeDomainDns.dns_records?.dkim_value },
              { key: 'dmarc', label: 'DMARC', host: 'TXT · _dmarc', val: store.activeDomainDns.dns_records?.dmarc }
            ]"
            :key="rec.key"
            class="p-3 rounded-[2px] bg-[var(--bg-salon)] border border-[var(--rule-medium)] space-y-1.5"
          >
            <div class="flex items-center justify-between text-[11.5px] pb-1 border-b border-[var(--rule-faint)]">
              <div class="flex items-center gap-2">
                <span class="px-1.5 py-[1px] bg-[var(--ink-primary)] text-[var(--bg-salon)] font-mono text-[10px] font-semibold">
                  {{ rec.label }}
                </span>
                <span class="font-mono text-[11px] text-[var(--ink-muted)]">{{ rec.host }}</span>
              </div>
              <button
                @click="copyValue(rec.key, rec.val)"
                class="font-mono text-[11px] text-[var(--ink-secondary)] hover:text-[var(--accent-forest)] flex items-center gap-1 transition"
              >
                <Check v-if="copiedKey === rec.key" class="w-3 h-3 text-[var(--accent-forest)]" />
                <Copy v-else class="w-3 h-3" />
                <span>{{ copiedKey === rec.key ? '已复制' : '一键复制' }}</span>
              </button>
            </div>
            <div class="font-mono text-[11px] text-[var(--ink-secondary)] break-all leading-relaxed select-all">
              {{ rec.val || '—' }}
            </div>
          </div>
        </div>

        <div class="px-4 sm:px-5 py-3 pb-safe border-t border-[var(--rule-medium)] bg-[var(--bg-linen)] flex items-center justify-between flex-shrink-0">
          <button
            @click="handleDeleteDomain(store.activeDomainDns)"
            class="text-[12px] text-[var(--accent-vermilion)] hover:underline transition"
          >
            移除此域名
          </button>
          <button
            @click="closeDns"
            class="ed-btn-ink px-4 py-1.5 text-[12px] font-medium"
          >
            完成
          </button>
        </div>
      </div>
    </div>
  </Transition>
</template>
