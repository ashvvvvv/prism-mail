<script setup>
import { ref, watch } from 'vue'
import { useMailStore } from '../stores/mail'
import {
  X, Check, Copy, RotateCw, LogOut, ArrowUpRight, Sun, Moon, Monitor
} from 'lucide-vue-next'

const store = useMailStore()

const editions = [
  { id: 'v2', name: '曜石', sub: '现代紧凑' },
  { id: 'apple', name: '清透', sub: '轻盈通透' },
  { id: 'editorial', name: '纸墨', sub: '书页排版' }
]

const modeOptions = [
  { id: 'light', label: '浅色', icon: Sun },
  { id: 'dark', label: '深色', icon: Moon },
  { id: 'system', label: '跟随系统', icon: Monitor }
]

const username = ref('admin')
const currentPassword = ref('')
const newPassword = ref('')
const apiKey = ref('')
const statusMsg = ref('')
const statusError = ref(false)
const switchingEdition = ref('')

const flash = (msg, isErr = false) => {
  statusMsg.value = msg
  statusError.value = isErr
}

const loadAccount = async () => {
  statusMsg.value = ''
  try {
    const res = await fetch('/api/auth/me')
    if (!res.ok) return
    const data = await res.json()
    username.value = data.username || 'admin'
    apiKey.value = data.api_key || ''
  } catch {}
}

watch(
  () => store.isSettingsOpen,
  (open) => {
    if (open) loadAccount()
  }
)

const switchEdition = async (edId) => {
  if (edId === 'editorial') return
  switchingEdition.value = edId
  try {
    await fetch('/api/settings/ui', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ui_edition: edId, color_mode: store.colorMode })
    })
  } catch {}
  window.location.href = `/${edId}/`
}

const savePassword = async () => {
  if (!currentPassword.value || !newPassword.value) return
  try {
    const res = await fetch('/api/auth/password', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        new_username: username.value.trim(),
        current_password: currentPassword.value,
        new_password: newPassword.value
      })
    })
    const data = await res.json()
    if (!res.ok) {
      flash(data.detail || '修改失败', true)
      return
    }
    currentPassword.value = ''
    newPassword.value = ''
    flash('密码已更新')
  } catch (e) {
    flash(e.message || '网络请求失败', true)
  }
}

const copyKey = async () => {
  if (!apiKey.value) return
  await navigator.clipboard.writeText(apiKey.value)
  store.notify('已复制密钥', 'success')
}

const rotateKey = async () => {
  const ok = await store.askConfirm({
    title: '重置 API 密钥',
    message: '重置后原密钥将立即失效，确定继续吗？',
    confirmText: '重置',
    danger: true
  })
  if (!ok) return
  const res = await fetch('/api/auth/rotate-api-key', { method: 'POST' })
  if (res.ok) {
    const data = await res.json()
    apiKey.value = data.api_key
    store.notify('API 密钥已更新', 'success')
  }
}

const close = () => {
  store.isSettingsOpen = false
}
</script>

<template>
  <Transition name="folio-fade">
    <div
      v-if="store.isSettingsOpen"
      class="fixed inset-0 ed-backdrop z-50 flex items-end sm:items-center justify-center p-0 sm:p-4 select-none"
      @click.self="close"
    >
      <div class="ed-folio-modal w-full max-w-[520px] max-h-[90dvh] flex flex-col overflow-hidden">
        <!-- Header -->
        <div class="px-4 sm:px-5 py-3.5 border-b border-[var(--rule-medium)] bg-[var(--bg-linen)] flex items-center justify-between flex-shrink-0">
          <h2 class="font-serif text-[17px] font-medium text-[var(--ink-primary)]">设置</h2>
          <button
            type="button"
            @click="close"
            class="p-1 text-[var(--ink-muted)] hover:text-[var(--ink-primary)] transition"
          >
            <X class="w-4 h-4" />
          </button>
        </div>

        <!-- Scrollable Body -->
        <div class="p-4 sm:p-5 overflow-y-auto space-y-5 bg-[var(--bg-salon)]">
          <!-- Section 1: Theme & Appearance -->
          <section class="space-y-3">
            <div class="flex items-center justify-between">
              <span class="text-[12px] font-semibold text-[var(--ink-primary)]">界面主题</span>
              <a
                href="/ui"
                class="inline-flex items-center gap-1 text-[11.5px] text-[var(--accent-vermilion)] hover:underline transition"
              >
                <span>主题预览</span>
                <ArrowUpRight class="w-3.5 h-3.5" />
              </a>
            </div>

            <div class="grid grid-cols-3 gap-2 sm:gap-2.5">
              <button
                v-for="ed in editions"
                :key="ed.id"
                type="button"
                @click="switchEdition(ed.id)"
                :class="[
                  'p-2.5 sm:p-3 rounded-[2px] border text-left transition flex flex-col justify-between min-h-[70px] sm:min-h-[72px]',
                  ed.id === 'editorial'
                    ? 'bg-[var(--bg-active)] border-[var(--rule-strong)]'
                    : 'bg-[var(--bg-linen)] border-[var(--rule-faint)] hover:border-[var(--rule-medium)] hover:bg-[var(--bg-hover)]'
                ]"
              >
                <div class="flex items-center justify-between gap-1">
                  <span class="text-[13px] font-serif font-semibold text-[var(--ink-primary)]">{{ ed.name }}</span>
                  <Check v-if="ed.id === 'editorial'" class="w-3.5 h-3.5 text-[var(--accent-vermilion)] flex-shrink-0" />
                </div>
                <span class="text-[11px] text-[var(--ink-muted)]">
                  {{ switchingEdition === ed.id ? '切换中…' : ed.sub }}
                </span>
              </button>
            </div>

            <!-- 3-Segment Appearance Mode: Light | Dark | System -->
            <div class="flex flex-wrap items-center justify-between gap-2 px-3.5 py-2 rounded-[2px] bg-[var(--bg-linen)] border border-[var(--rule-faint)]">
              <span class="text-[12px] font-medium text-[var(--ink-primary)]">外观模式</span>
              <div class="inline-flex items-center border border-[var(--rule-medium)] rounded-[2px] bg-[var(--bg-subtle)] p-[1px]">
                <button
                  v-for="opt in modeOptions"
                  :key="opt.id"
                  type="button"
                  @click="store.setColorMode(opt.id)"
                  :class="[
                    'px-2.5 py-1 rounded-[1px] text-[11.5px] flex items-center gap-1.5 transition',
                    store.colorMode === opt.id
                      ? 'bg-[var(--ink-primary)] text-[var(--bg-salon)] font-medium'
                      : 'text-[var(--ink-muted)] hover:text-[var(--ink-primary)]'
                  ]"
                >
                  <component :is="opt.icon" class="w-3.5 h-3.5" />
                  <span>{{ opt.label }}</span>
                </button>
              </div>
            </div>
          </section>

          <!-- Section 2: Account Security -->
          <section class="space-y-3 pt-4 border-t border-[var(--rule-faint)]">
            <span class="text-[12px] font-semibold text-[var(--ink-primary)] block">账户安全</span>
            <form @submit.prevent="savePassword" class="space-y-2.5">
              <div class="grid grid-cols-1 sm:grid-cols-3 gap-2">
                <input
                  v-model="username"
                  type="text"
                  placeholder="用户名"
                  required
                  class="bg-[var(--bg-input)] border border-[var(--rule-medium)] focus:border-[var(--rule-strong)] rounded-[2px] px-3 py-2 text-[12.5px] text-[var(--ink-primary)] focus:outline-none"
                />
                <input
                  v-model="currentPassword"
                  type="password"
                  placeholder="当前密码"
                  required
                  class="bg-[var(--bg-input)] border border-[var(--rule-medium)] focus:border-[var(--rule-strong)] rounded-[2px] px-3 py-2 text-[12.5px] text-[var(--ink-primary)] focus:outline-none"
                />
                <input
                  v-model="newPassword"
                  type="password"
                  placeholder="新密码"
                  minlength="6"
                  required
                  class="bg-[var(--bg-input)] border border-[var(--rule-medium)] focus:border-[var(--rule-strong)] rounded-[2px] px-3 py-2 text-[12.5px] text-[var(--ink-primary)] focus:outline-none"
                />
              </div>
              <div class="flex items-center justify-between min-h-[28px]">
                <span
                  v-if="statusMsg"
                  :class="['text-[11.5px]', statusError ? 'text-[var(--accent-vermilion)]' : 'text-[var(--accent-forest)]']"
                >
                  {{ statusMsg }}
                </span>
                <span v-else />
                <button
                  type="submit"
                  class="ed-btn-ink px-3.5 py-1.5 text-[12px] font-medium"
                >
                  保存修改
                </button>
              </div>
            </form>
          </section>

          <!-- Section 3: API Key -->
          <section class="space-y-3 pt-4 border-t border-[var(--rule-faint)]">
            <div class="flex items-center justify-between">
              <span class="text-[12px] font-semibold text-[var(--ink-primary)]">API 密钥</span>
              <a
                href="/docs"
                target="_blank"
                rel="noopener"
                class="inline-flex items-center gap-1 text-[11.5px] text-[var(--ink-muted)] hover:text-[var(--ink-primary)] transition"
              >
                <span>接口文档</span>
                <ArrowUpRight class="w-3.5 h-3.5" />
              </a>
            </div>

            <div class="flex items-center gap-2">
              <input
                :value="apiKey"
                readonly
                type="text"
                class="flex-1 min-w-0 bg-[var(--bg-input)] border border-[var(--rule-medium)] rounded-[2px] px-3 py-2 text-[11.5px] font-mono text-[var(--ink-secondary)] focus:outline-none"
              />
              <button
                type="button"
                @click="copyKey"
                class="ed-btn-outline px-2.5 sm:px-3 py-2 text-[12px] flex items-center gap-1.5 flex-shrink-0"
              >
                <Copy class="w-3.5 h-3.5" />
                <span>复制</span>
              </button>
              <button
                type="button"
                @click="rotateKey"
                class="ed-btn-outline px-2.5 sm:px-3 py-2 text-[12px] text-[var(--ink-secondary)] flex items-center gap-1.5 flex-shrink-0"
                title="重置密钥"
              >
                <RotateCw class="w-3.5 h-3.5" />
                <span>重置</span>
              </button>
            </div>
          </section>
        </div>

        <!-- Footer -->
        <div class="px-4 sm:px-5 py-3 pb-safe border-t border-[var(--rule-medium)] bg-[var(--bg-linen)] flex items-center justify-between flex-shrink-0">
          <a
            href="/logout"
            class="inline-flex items-center gap-1.5 text-[12px] text-[var(--accent-vermilion)] hover:opacity-80 transition font-medium"
          >
            <LogOut class="w-3.5 h-3.5" />
            <span>退出登录</span>
          </a>
          <button
            type="button"
            @click="close"
            class="ed-btn-outline px-4 py-1.5 text-[12px] font-medium"
          >
            完成
          </button>
        </div>
      </div>
    </div>
  </Transition>
</template>
