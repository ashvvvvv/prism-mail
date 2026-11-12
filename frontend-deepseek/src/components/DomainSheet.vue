<script setup>
import { ref, watch } from 'vue'
import { useMailStore } from '../stores/mail'
import { X, Copy, Check, Globe } from 'lucide-vue-next'

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
    store.notify(`已复制 ${key.toUpperCase()} 解析记录 ✨`, 'success')
    setTimeout(() => {
      if (copiedKey.value === key) copiedKey.value = ''
    }, 1500)
  } catch {}
}

const handleCreateDomain = async () => {
  if (domainName.value.trim()) {
    await store.createDomain(domainName.value.trim(), domainDesc.value.trim())
    closeAdd()
  }
}

const handleDeleteDomain = async (domain) => {
  const ok = await store.askConfirm({
    title: '移除自定义域名',
    message: `确定移除域名 @${domain.name} 及其下属所有信箱吗？此操作不可撤销哦。`,
    confirmText: '确认移除',
    danger: true
  })
  if (ok) {
    await store.deleteDomain(domain.id)
    closeDns()
  }
}
</script>

<template>
  <!-- Add Domain Modal -->
  <Transition name="fade-scale">
    <div
      v-if="store.isDomainModalOpen"
      class="fixed inset-0 ds-backdrop z-50 flex items-center justify-center p-4"
      @click.self="closeAdd"
    >
      <div class="ds-modal w-full max-w-md p-5 space-y-4">
        <div class="flex items-center justify-between">
          <h3 class="text-[14.5px] font-extrabold text-[var(--text-primary)] flex items-center gap-2">
            <Globe class="w-4 h-4 text-[#4D6BFE]" />
            <span>绑定自定义域名</span>
          </h3>
          <button @click="closeAdd" class="text-[var(--text-muted)] hover:text-[var(--text-primary)]">
            <X class="w-4 h-4" />
          </button>
        </div>

        <!-- Existing Domains Quick List (if any non-external) -->
        <div
          v-if="store.domains.filter(d => !d.is_external).length > 0"
          class="space-y-1.5 max-h-36 overflow-y-auto p-2 rounded-2xl bg-[var(--bg-subtle)] border border-[var(--border-hairline)]"
        >
          <div class="px-1.5 text-[10.5px] font-bold text-[var(--text-muted)]">已接入域名（点击查看 DNS 解析）</div>
          <div
            v-for="dom in store.domains.filter(d => !d.is_external)"
            :key="dom.id"
            @click="closeAdd(); store.activeDomainDns = dom"
            class="px-2.5 py-1.5 rounded-xl hover:bg-[var(--bg-hover)] flex items-center justify-between cursor-pointer transition text-[12px]"
          >
            <span class="font-mono font-bold text-[#4D6BFE] dark:text-[#7DD3FC]">@{{ dom.name }}</span>
            <span class="text-[11px] font-semibold text-[var(--text-muted)]">查看 DNS →</span>
          </div>
        </div>

        <div class="space-y-2.5">
          <input
            v-model="domainName"
            @keydown.enter.prevent="handleCreateDomain"
            type="text"
            placeholder="输入新域名 (如 example.com)"
            autofocus
            class="w-full bg-[var(--bg-input)] border border-[var(--border-hairline)] focus:border-[var(--border-focus)] rounded-xl px-3.5 py-2 text-[12.5px] font-mono text-[var(--text-primary)] placeholder-[var(--text-muted)] focus:outline-none transition"
          />
          <input
            v-model="domainDesc"
            @keydown.enter.prevent="handleCreateDomain"
            type="text"
            placeholder="用途备注 (选填)"
            class="w-full bg-[var(--bg-input)] border border-[var(--border-hairline)] focus:border-[var(--border-focus)] rounded-xl px-3.5 py-2 text-[12.5px] text-[var(--text-primary)] placeholder-[var(--text-muted)] focus:outline-none transition"
          />
        </div>

        <div class="flex items-center justify-end gap-2 pt-1">
          <button
            @click="closeAdd"
            class="px-3.5 py-1.5 rounded-xl text-[12px] font-semibold text-[var(--text-secondary)] hover:bg-[var(--bg-hover)] transition"
          >
            关闭
          </button>
          <button
            @click="handleCreateDomain"
            :disabled="!domainName.trim()"
            class="ds-btn-primary px-4 py-1.5 rounded-xl text-[12px] font-bold disabled:opacity-40"
          >
            立即绑定
          </button>
        </div>
      </div>
    </div>
  </Transition>

  <!-- DNS Records Sheet -->
  <Transition name="fade-scale">
    <div
      v-if="store.activeDomainDns"
      class="fixed inset-0 ds-backdrop z-50 flex items-center justify-center p-4"
      @click.self="closeDns"
    >
      <div class="ds-modal w-full max-w-lg p-5 space-y-4">
        <div class="flex items-center justify-between pb-2.5 border-b border-[var(--border-hairline)]">
          <div class="flex items-center gap-2">
            <span class="px-2 py-0.5 rounded-md bg-[#4D6BFE] text-white text-[10.5px] font-mono font-bold">DNS</span>
            <span class="text-[14px] font-mono font-extrabold text-[var(--text-primary)]">
              @{{ store.activeDomainDns.name }}
            </span>
          </div>
          <button @click="closeDns" class="text-[var(--text-muted)] hover:text-[var(--text-primary)]">
            <X class="w-4 h-4" />
          </button>
        </div>

        <div class="space-y-2.5 max-h-80 overflow-y-auto pr-0.5">
          <div
            v-for="rec in [
              { key: 'mx', label: 'MX', host: '@ · Priority 10', val: store.activeDomainDns.dns_records?.mx },
              { key: 'spf', label: 'SPF', host: 'TXT · @', val: store.activeDomainDns.dns_records?.spf },
              { key: 'dkim', label: 'DKIM', host: 'TXT · default._domainkey', val: store.activeDomainDns.dns_records?.dkim_value },
              { key: 'dmarc', label: 'DMARC', host: 'TXT · _dmarc', val: store.activeDomainDns.dns_records?.dmarc }
            ]"
            :key="rec.key"
            class="p-3.5 rounded-2xl bg-[var(--bg-subtle)] border border-[var(--border-hairline)] space-y-1.5"
          >
            <div class="flex items-center justify-between text-[11.5px]">
              <div class="flex items-center gap-2">
                <span class="px-2 py-0.5 rounded-md bg-[#4D6BFE]/14 text-[#4D6BFE] dark:text-[#7DD3FC] font-mono font-bold">
                  {{ rec.label }}
                </span>
                <span class="font-mono text-[var(--text-muted)]">{{ rec.host }}</span>
              </div>
              <button
                @click="copyValue(rec.key, rec.val)"
                class="px-2.5 py-0.5 rounded-lg bg-[var(--bg-elevated)] hover:bg-[#4D6BFE] text-[var(--text-secondary)] hover:text-white border border-[var(--border-hairline)] font-bold flex items-center gap-1 transition"
              >
                <Check v-if="copiedKey === rec.key" class="w-3 h-3 text-[var(--accent-emerald)]" />
                <Copy v-else class="w-3 h-3" />
                <span>{{ copiedKey === rec.key ? '已复制' : '一键复制' }}</span>
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
            class="text-[12px] font-bold text-[var(--accent-rose)] hover:opacity-80 transition"
          >
            移除此域名
          </button>
          <button
            @click="closeDns"
            class="ds-btn-primary px-4 py-1.5 rounded-xl text-[12px] font-bold"
          >
            完成配置
          </button>
        </div>
      </div>
    </div>
  </Transition>
</template>
