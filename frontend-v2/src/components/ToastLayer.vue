<script setup>
import { useMailStore } from '../stores/mail'
import { Check, AlertCircle, Info } from 'lucide-vue-next'

const store = useMailStore()
</script>

<template>
  <!-- Sonner-style Toast Stack -->
  <div class="fixed bottom-4 sm:bottom-5 left-4 right-4 sm:left-auto sm:right-5 z-[70] flex flex-col items-center sm:items-end gap-2 pointer-events-none">
    <TransitionGroup name="toast-slide">
      <div
        v-for="t in store.toasts"
        :key="t.id"
        class="pointer-events-auto pm-modal px-3.5 py-2.5 rounded-xl flex items-center gap-2.5 text-[12.5px] text-[var(--text-primary)] min-w-[200px] max-w-full sm:max-w-sm"
      >
        <Check v-if="t.type === 'success'" class="w-3.5 h-3.5 text-[var(--accent-emerald)] flex-shrink-0" />
        <AlertCircle v-else-if="t.type === 'error'" class="w-3.5 h-3.5 text-[var(--accent-rose)] flex-shrink-0" />
        <Info v-else class="w-3.5 h-3.5 text-[var(--text-secondary)] flex-shrink-0" />
        <span class="truncate">{{ t.message }}</span>
      </div>
    </TransitionGroup>
  </div>

  <!-- Custom Confirm Modal -->
  <Transition name="fade-scale">
    <div
      v-if="store.confirmState"
      class="fixed inset-0 pm-backdrop z-[65] flex items-center justify-center p-4 select-none"
      @click.self="store.confirmState.onCancel()"
    >
      <div class="pm-modal rounded-2xl w-full max-w-xs p-5 space-y-4">
        <div class="space-y-1.5">
          <h3 class="text-[13.5px] font-semibold text-[var(--text-primary)]">
            {{ store.confirmState.title }}
          </h3>
          <p class="text-[12.5px] text-[var(--text-secondary)] leading-relaxed">
            {{ store.confirmState.message }}
          </p>
        </div>

        <div class="flex items-center justify-end gap-2 pt-1">
          <button
            @click="store.confirmState.onCancel()"
            class="px-3.5 py-1.5 rounded-lg text-[12px] text-[var(--text-secondary)] hover:bg-[var(--bg-hover)] transition"
          >
            取消
          </button>
          <button
            @click="store.confirmState.onConfirm()"
            :class="[
              'px-4 py-1.5 rounded-lg text-[12px] font-medium transition',
              store.confirmState.danger
                ? 'bg-[var(--accent-rose)] hover:opacity-90 text-white'
                : 'pm-btn-primary'
            ]"
          >
            {{ store.confirmState.confirmText }}
          </button>
        </div>
      </div>
    </div>
  </Transition>
</template>
