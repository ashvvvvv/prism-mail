<script setup>
import { ref, watch } from 'vue'
import { useMailStore } from '../stores/mail'
import { X, Copy, Check } from 'lucide-vue-next'

const store = useMailStore()

const domainName = ref('')
const domainDesc = ref('')
const copiedKey = ref('')

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

const copyValue = async (key, text) => {
  if (!text) return
  try {
    await navigator.clipboard.writeText(text)
    copiedKey.value = key
    store.notify(`已复制 ${key.toUpperCase()} 记录`, 'success')
    setTimeout(() => {
      if (copiedKey.value === key) copiedKey.value = ''
    }, 1500)
  } catch {}
}

const handleCreateDomain = async () => {
  const cleaned = domainName.value.trim().replace(/^@/, '')
  if (cleaned) {
    try {
      await store.createDomain(cleaned, domainDesc.value.trim())
      closeAdd()
    } catch {}
  }
}

const handleDeleteDomain = async (domain) => {
  const ok = await store.askConfirm({
    title: '移除域名',
    message: `确定移除 @${domain.name} 及其下属所有邮箱吗？`,
    confirmText: '移除',
    danger: true
  })
  if (ok) {
    try {
      await store.deleteDomain(domain.id)
      closeDns()
    } catch {}
  }
}
</script>

<template>
  <!-- Add Domain Modal -->
  <Transition name="fade-scale">
    <div
      v-if="store.isDomainModalOpen"
      class="fixed inset-0 pm-backdrop z-50 flex items-end sm:items-center justify-center p-0 sm:p-4"
      @click.self="closeAdd"
    >
      <div class="pm-modal rounded-t-2xl sm:rounded-2xl w-full max-w-sm p-5 pb-safe space-y-4">
        <div class="flex items-center justify-between">
          <h3 class="text-[13.5px] font-semibold text-[var(--text-primary)]">绑定自定义域名</h3>
          <button @click="closeAdd" class="text-[var(--text-muted)] hover:text-[var(--text-primary)]">
            <X class="w-4 h-4" />
          </button>
        </div>

        <div class="space-y-2.5">
          <input
            v-model="domainName"
            @keydown.enter.prevent="handleCreateDomain"
            type="text"
            placeholder="域名 (如 example.com)"
            autofocus
            class="w-full bg-[var(--bg-input)] border border-[var(--border-hairline)] focus:border-[var(--border-focus)] rounded-xl px-3 py-2 text-[12.5px] font-mono text-[var(--text-primary)] placeholder-[var(--text-muted)] focus:outline-none transition"
          />
          <input
            v-model="domainDesc"
            @keydown.enter.prevent="handleCreateDomain"
            type="text"
            placeholder="备注 (选填)"
            class="w-full bg-[var(--bg-input)] border border-[var(--border-hairline)] focus:border-[var(--border-focus)] rounded-xl px-3 py-2 text-[12.5px] text-[var(--text-primary)] placeholder-[var(--text-muted)] focus:outline-none transition"
          />
        </div>

        <div class="flex items-center justify-end gap-2 pt-1">
          <button
            @click="closeAdd"
            class="px-3.5 py-1.5 rounded-lg text-[12px] text-[var(--text-secondary)] hover:bg-[var(--bg-hover)] transition"
          >
            取消
          </button>
          <button
            @click="handleCreateDomain"
            :disabled="!domainName.trim()"
            class="pm-btn-primary px-4 py-1.5 rounded-lg text-[12px] font-medium disabled:opacity-40"
          >
            绑定
          </button>
        </div>
      </div>
    </div>
  </Transition>

  <!-- DNS Records Sheet -->
  <Transition name="fade-scale">
    <div
      v-if="store.activeDomainDns"
      class="fixed inset-0 pm-backdrop z-50 flex items-end sm:items-center justify-center p-0 sm:p-4"
      @click.self="closeDns"
    >
      <div class="pm-modal rounded-t-2xl sm:rounded-2xl w-full max-w-lg max-h-[90dvh] flex flex-col p-4 sm:p-5 pb-safe space-y-4">
        <div class="flex items-center justify-between pb-2 border-b border-[var(--border-hairline)] flex-shrink-0">
          <span class="text-[13.5px] font-mono font-semibold text-[var(--text-primary)] truncate pr-2">
            DNS · @{{ store.activeDomainDns.name }}
          </span>
          <button @click="closeDns" class="text-[var(--text-muted)] hover:text-[var(--text-primary)] flex-shrink-0">
            <X class="w-4 h-4" />
          </button>
        </div>

        <div class="space-y-2.5 flex-1 max-h-[60dvh] sm:max-h-80 overflow-y-auto pr-0.5">
          <div
            v-for="rec in [
              { key: 'mx', label: 'MX', host: '@ · Priority 10', val: store.activeDomainDns.dns_records.mx },
              { key: 'spf', label: 'SPF', host: 'TXT · @', val: store.activeDomainDns.dns_records.spf },
              { key: 'dkim', label: 'DKIM', host: 'TXT · default._domainkey', val: store.activeDomainDns.dns_records.dkim_value },
              { key: 'dmarc', label: 'DMARC', host: 'TXT · _dmarc', val: store.activeDomainDns.dns_records.dmarc }
            ]"
            :key="rec.key"
            class="p-3 rounded-xl bg-[var(--bg-subtle)] border border-[var(--border-hairline)] space-y-1.5"
          >
            <div class="flex items-center justify-between text-[11.5px]">
              <div class="flex items-center gap-2">
                <span class="font-semibold text-[var(--text-primary)]">{{ rec.label }}</span>
                <span class="font-mono text-[var(--text-muted)]">{{ rec.host }}</span>
              </div>
              <button
                @click="copyValue(rec.key, rec.val)"
                class="text-[var(--text-secondary)] hover:text-[var(--text-primary)] flex items-center gap-1 transition"
              >
                <Check v-if="copiedKey === rec.key" class="w-3 h-3 text-[var(--accent-emerald)]" />
                <Copy v-else class="w-3 h-3" />
                <span>{{ copiedKey === rec.key ? '已复制' : '复制' }}</span>
              </button>
            </div>
            <div class="font-mono text-[11px] text-[var(--text-secondary)] break-all leading-relaxed select-all">
              {{ rec.val }}
            </div>
          </div>
        </div>

        <div class="flex items-center justify-between pt-2 border-t border-[var(--border-hairline)]">
          <button
            @click="handleDeleteDomain(store.activeDomainDns)"
            class="text-[12px] text-[var(--accent-rose)] hover:opacity-80 transition"
          >
            移除域名
          </button>
          <button
            @click="closeDns"
            class="pm-btn-primary px-4 py-1.5 rounded-lg text-[12px] font-medium"
          >
            完成
          </button>
        </div>
      </div>
    </div>
  </Transition>
</template>
