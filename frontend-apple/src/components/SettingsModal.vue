<script setup>
import { ref, computed, watch, nextTick } from 'vue'
import { useMailStore } from '../stores/mail'
import {
  X, Check, Copy, Eye, RotateCw, LogOut, ArrowUpRight, Sun, Moon, Monitor
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
const showRevealPrompt = ref(false)
const revealPassword = ref('')
const revealingKey = ref(false)
const revealInputRef = ref(null)
const statusMsg = ref('')
const statusError = ref(false)
const switchingEdition = ref('')

const isApiKeyMasked = computed(() => Boolean(apiKey.value && apiKey.value.includes('•')))

const extractDetailMsg = (detail, fallback) => {
  if (typeof detail === 'string' && detail) return detail
  if (Array.isArray(detail) && detail.length > 0) return detail[0]?.msg || fallback
  return fallback
}

const flash = (msg, isErr = false) => {
  statusMsg.value = msg
  statusError.value = isErr
}

const loadAccount = async () => {
  statusMsg.value = ''
  showRevealPrompt.value = false
  revealPassword.value = ''
  revealingKey.value = false
  try {
    const res = await fetch('/api/auth/me')
    if (!res.ok) return
    const data = await res.json()
    username.value = data.username || 'admin'
    apiKey.value = data.api_key || data.api_key_masked || ''
  } catch {}
}

watch(
  () => store.isSettingsOpen,
  (open) => {
    if (open) loadAccount()
  }
)

const switchEdition = async (edId) => {
  if (edId === 'apple') return
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
      const errMsg = typeof data.detail === 'string' ? data.detail : (Array.isArray(data.detail) ? (data.detail[0]?.msg || '修改失败') : '修改失败')
      flash(errMsg, true)
      return
    }
    currentPassword.value = ''
    newPassword.value = ''
    flash('密码已更新')
  } catch (e) {
    flash(e.message || '网络请求失败', true)
  }
}

const toggleRevealPrompt = async () => {
  showRevealPrompt.value = !showRevealPrompt.value
  revealPassword.value = ''
  if (showRevealPrompt.value) {
    await nextTick()
    revealInputRef.value?.focus()
  }
}

const revealKey = async () => {
  if (!revealPassword.value || revealingKey.value) return
  revealingKey.value = true
  try {
    const res = await fetch('/api/auth/reveal-api-key', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ current_password: revealPassword.value })
    })
    let data = null
    try {
      data = await res.json()
    } catch {}
    if (!res.ok) {
      store.notify(extractDetailMsg(data?.detail, '密码验证未通过'), 'error')
      return
    }
    if (data?.api_key) {
      apiKey.value = data.api_key
      revealPassword.value = ''
      showRevealPrompt.value = false
      store.notify('已解锁完整密钥', 'success')
    }
  } catch (e) {
    store.notify(e.message || '解锁密钥失败', 'error')
  } finally {
    revealingKey.value = false
  }
}

const copyKey = async () => {
  if (!apiKey.value) return
  if (isApiKeyMasked.value) {
    showRevealPrompt.value = true
    await nextTick()
    revealInputRef.value?.focus()
    store.notify('请先输入当前密码解锁完整密钥后再复制')
    return
  }
  try {
    await navigator.clipboard.writeText(apiKey.value)
    store.notify('已复制密钥', 'success')
  } catch {
    store.notify('复制失败，请手动选中复制', 'error')
  }
}

const logout = async () => {
  try {
    await fetch('/api/auth/logout', { method: 'POST' })
  } catch {}
  window.location.href = '/login'
}

const rotateKey = async () => {
  const ok = await store.askConfirm({
    title: '重置 API 密钥',
    message: '重置后原密钥将立即失效，确定继续吗？',
    confirmText: '重置',
    danger: true
  })
  if (!ok) return
  try {
    const res = await fetch('/api/auth/rotate-api-key', { method: 'POST' })
    let data = null
    try {
      data = await res.json()
    } catch {}
    if (!res.ok) {
      store.notify(extractDetailMsg(data?.detail, '重置密钥失败'), 'error')
      return
    }
    if (data?.api_key) {
      apiKey.value = data.api_key
      showRevealPrompt.value = false
      revealPassword.value = ''
      store.notify('API 密钥已更新', 'success')
    }
  } catch (e) {
    store.notify(e.message || '重置密钥失败', 'error')
  }
}

const close = () => {
  store.isSettingsOpen = false
}
</script>

<template>
  <Transition name="mac-sheet-fade">
    <div
      v-if="store.isSettingsOpen"
      class="fixed inset-0 mac-backdrop z-50 flex items-end sm:items-center justify-center p-0 sm:p-4 select-none"
      @click.self="close"
    >
      <div class="mac-sheet rounded-t-[18px] sm:rounded-[16px] w-full max-w-[520px] max-h-[90dvh] flex flex-col overflow-hidden">
        <!-- Header -->
        <div class="px-4 sm:px-5 py-3.5 mac-hairline-b flex items-center justify-between flex-shrink-0">
          <h2 class="text-[14.5px] font-semibold text-[var(--label-primary)]">设置</h2>
          <button
            type="button"
            @click="close"
            class="w-6 h-6 rounded-full bg-[var(--fill-tertiary)] hover:bg-[var(--fill-secondary)] flex items-center justify-center text-[var(--label-secondary)] transition"
          >
            <X class="w-3.5 h-3.5" />
          </button>
        </div>

        <!-- Scrollable Body -->
        <div class="p-4 sm:p-5 overflow-y-auto space-y-5">
          <!-- Section 1: Theme & Appearance -->
          <section class="space-y-3">
            <div class="flex items-center justify-between">
              <span class="text-[12px] font-semibold text-[var(--label-primary)]">界面主题</span>
              <a
                href="/ui"
                class="inline-flex items-center gap-1 text-[12px] font-medium text-[var(--apple-blue)] hover:opacity-80 transition"
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
                  'p-2.5 sm:p-3 rounded-[11px] border text-left transition flex flex-col justify-between min-h-[70px]',
                  ed.id === 'apple'
                    ? 'bg-[var(--fill-active-subtle)] border-[var(--apple-blue)]'
                    : 'bg-[var(--fill-quaternary)] border-[var(--separator)] hover:bg-[var(--fill-hover)]'
                ]"
              >
                <div class="flex items-center justify-between gap-1">
                  <span
                    :class="[
                      'text-[13px] font-semibold',
                      ed.id === 'apple' ? 'text-[var(--apple-blue)]' : 'text-[var(--label-primary)]'
                    ]"
                  >
                    {{ ed.name }}
                  </span>
                  <Check v-if="ed.id === 'apple'" class="w-3.5 h-3.5 text-[var(--apple-blue)] flex-shrink-0" />
                </div>
                <span class="text-[11px] text-[var(--label-secondary)]">
                  {{ switchingEdition === ed.id ? '切换中…' : ed.sub }}
                </span>
              </button>
            </div>

            <!-- 3-Segment Appearance Control: Light | Dark | System -->
            <div class="flex items-center justify-between flex-wrap gap-2 px-3.5 py-2.5 rounded-[10px] bg-[var(--fill-quaternary)] border border-[var(--separator)]">
              <span class="text-[12px] font-medium text-[var(--label-primary)]">外观模式</span>
              <div class="inline-flex items-center p-[2px] rounded-[8px] bg-[var(--fill-tertiary)]">
                <button
                  v-for="opt in modeOptions"
                  :key="opt.id"
                  type="button"
                  @click="store.setColorMode(opt.id)"
                  :class="[
                    'px-2.5 py-1 rounded-[6px] text-[11.5px] flex items-center gap-1.5 transition',
                    store.colorMode === opt.id
                      ? 'bg-[var(--bg-input-solid)] text-[var(--label-primary)] font-medium shadow-sm'
                      : 'text-[var(--label-secondary)] hover:text-[var(--label-primary)]'
                  ]"
                >
                  <component :is="opt.icon" class="w-3.5 h-3.5" />
                  <span>{{ opt.label }}</span>
                </button>
              </div>
            </div>
          </section>

          <!-- Section 2: Account Security -->
          <section class="space-y-3 pt-4 mac-hairline-t">
            <div class="flex items-center justify-between">
              <span class="text-[12px] font-semibold text-[var(--label-primary)]">账户安全</span>
              <a
                href="/account"
                class="inline-flex items-center gap-1 text-[11.5px] font-medium text-[var(--apple-blue)] hover:opacity-80 transition"
              >
                <span>账户中心</span>
                <ArrowUpRight class="w-3.5 h-3.5" />
              </a>
            </div>
            <form @submit.prevent="savePassword" class="space-y-2.5">
              <div class="grid grid-cols-1 sm:grid-cols-3 gap-2">
                <input
                  v-model="username"
                  type="text"
                  placeholder="用户名"
                  required
                  class="h-10 sm:h-9 px-3 rounded-[9px] bg-[var(--bg-input-solid)] border border-[var(--separator-strong)] focus:border-[var(--apple-blue)] focus:ring-2 focus:ring-[var(--apple-blue)]/20 text-[12.5px] text-[var(--label-primary)] focus:outline-none transition"
                />
                <input
                  v-model="currentPassword"
                  type="password"
                  placeholder="当前密码"
                  required
                  class="h-10 sm:h-9 px-3 rounded-[9px] bg-[var(--bg-input-solid)] border border-[var(--separator-strong)] focus:border-[var(--apple-blue)] focus:ring-2 focus:ring-[var(--apple-blue)]/20 text-[12.5px] text-[var(--label-primary)] focus:outline-none transition"
                />
                <input
                  v-model="newPassword"
                  type="password"
                  placeholder="新密码（至少 10 位）"
                  minlength="10"
                  required
                  class="h-10 sm:h-9 px-3 rounded-[9px] bg-[var(--bg-input-solid)] border border-[var(--separator-strong)] focus:border-[var(--apple-blue)] focus:ring-2 focus:ring-[var(--apple-blue)]/20 text-[12.5px] text-[var(--label-primary)] focus:outline-none transition"
                />
              </div>
              <div class="flex items-center justify-between min-h-[30px]">
                <span
                  v-if="statusMsg"
                  :class="['text-[11.5px] font-medium', statusError ? 'text-[var(--apple-red)]' : 'text-[var(--apple-green)]']"
                >
                  {{ statusMsg }}
                </span>
                <span v-else />
                <button
                  type="submit"
                  class="mac-btn-blue h-[30px] px-3.5 rounded-[8px] text-[12px] font-medium"
                >
                  保存修改
                </button>
              </div>
            </form>
          </section>

          <!-- Section 3: API Key -->
          <section class="space-y-3 pt-4 mac-hairline-t">
            <div class="flex items-center justify-between">
              <span class="text-[12px] font-semibold text-[var(--label-primary)]">API 密钥</span>
              <a
                href="/docs"
                target="_blank"
                rel="noopener"
                class="inline-flex items-center gap-1 text-[11.5px] text-[var(--label-secondary)] hover:text-[var(--apple-blue)] transition"
              >
                <span>接口文档</span>
                <ArrowUpRight class="w-3.5 h-3.5" />
              </a>
            </div>

            <div class="flex items-center gap-2 flex-wrap sm:flex-nowrap">
              <input
                :value="apiKey"
                readonly
                type="text"
                class="flex-1 min-w-[160px] h-10 sm:h-9 px-3 rounded-[9px] bg-[var(--bg-input-solid)] border border-[var(--separator-strong)] text-[11.5px] font-mono text-[var(--label-secondary)] focus:outline-none"
              />
              <button
                v-if="isApiKeyMasked"
                type="button"
                @click="toggleRevealPrompt"
                class="mac-btn-secondary h-10 sm:h-9 px-3 rounded-[9px] text-[12px] font-medium flex items-center gap-1.5"
              >
                <Eye class="w-3.5 h-3.5" />
                <span>查看</span>
              </button>
              <button
                type="button"
                @click="copyKey"
                class="mac-btn-secondary h-10 sm:h-9 px-3 rounded-[9px] text-[12px] font-medium flex items-center gap-1.5"
              >
                <Copy class="w-3.5 h-3.5" />
                <span>复制</span>
              </button>
              <button
                type="button"
                @click="rotateKey"
                class="mac-btn-secondary h-10 sm:h-9 px-3 rounded-[9px] text-[12px] text-[var(--label-secondary)] flex items-center gap-1.5"
                title="重置密钥"
              >
                <RotateCw class="w-3.5 h-3.5" />
                <span>重置</span>
              </button>
            </div>

            <form
              v-if="showRevealPrompt && isApiKeyMasked"
              @submit.prevent="revealKey"
              class="flex items-center gap-2 pt-1"
            >
              <input
                ref="revealInputRef"
                v-model="revealPassword"
                type="password"
                placeholder="输入当前登录密码以查看完整密钥"
                required
                class="flex-1 min-w-0 h-9 px-3 rounded-[9px] bg-[var(--bg-input-solid)] border border-[var(--separator-strong)] focus:border-[var(--apple-blue)] focus:ring-2 focus:ring-[var(--apple-blue)]/20 text-[12px] text-[var(--label-primary)] focus:outline-none transition"
              />
              <button
                type="submit"
                :disabled="!revealPassword || revealingKey"
                class="mac-btn-blue h-9 px-3 rounded-[8px] text-[12px] font-medium disabled:opacity-40 flex-shrink-0"
              >
                {{ revealingKey ? '验证中…' : '确认查看' }}
              </button>
              <button
                type="button"
                @click="showRevealPrompt = false"
                class="h-9 px-2.5 rounded-[8px] text-[12px] text-[var(--label-secondary)] hover:text-[var(--label-primary)] transition flex-shrink-0"
              >
                取消
              </button>
            </form>
          </section>
        </div>

        <!-- Footer -->
        <div class="px-4 sm:px-5 py-3 pb-safe mac-hairline-t bg-[var(--fill-quaternary)] flex items-center justify-between flex-shrink-0">
          <button
            type="button"
            @click="logout"
            class="inline-flex items-center gap-1.5 text-[12px] text-[var(--apple-red)] hover:opacity-80 transition font-medium"
          >
            <LogOut class="w-3.5 h-3.5" />
            <span>退出登录</span>
          </button>
          <button
            type="button"
            @click="close"
            class="mac-btn-secondary h-[30px] px-4 rounded-[8px] text-[12.5px] font-medium"
          >
            完成
          </button>
        </div>
      </div>
    </div>
  </Transition>
</template>
