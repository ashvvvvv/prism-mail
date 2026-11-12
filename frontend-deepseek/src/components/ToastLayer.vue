<script setup>
import { useMailStore } from '../stores/mail'
import { Check, AlertCircle, Sparkles } from 'lucide-vue-next'

const store = useMailStore()
</script>

<template>
  <!-- Momotalk / Schale OS Bouncy ACG Toast Bubbles -->
  <div class="fixed bottom-5 right-5 z-[70] flex flex-col gap-2.5 pointer-events-none">
    <TransitionGroup name="toast-slide">
      <div
        v-for="t in store.toasts"
        :key="t.id"
        class="pointer-events-auto ds-modal px-4 py-2.5 rounded-full flex items-center gap-2.5 text-[12.5px] font-bold text-[var(--text-primary)] min-w-[220px] max-w-sm shadow-lg"
      >
        <div
          v-if="t.type === 'success'"
          class="w-5 h-5 rounded-full bg-emerald-500/15 text-[var(--accent-emerald)] flex items-center justify-center flex-shrink-0"
        >
          <Check class="w-3.5 h-3.5 stroke-[2.5]" />
        </div>
        <div
          v-else-if="t.type === 'error'"
          class="w-5 h-5 rounded-full bg-rose-500/15 text-[var(--accent-rose)] flex items-center justify-center flex-shrink-0"
        >
          <AlertCircle class="w-3.5 h-3.5 stroke-[2.5]" />
        </div>
        <div
          v-else
          class="w-5 h-5 rounded-full bg-[#4D6BFE]/15 text-[#4D6BFE] dark:text-[#7DD3FC] flex items-center justify-center flex-shrink-0"
        >
          <Sparkles class="w-3.5 h-3.5" />
        </div>
        <span class="truncate">{{ t.message }}</span>
      </div>
    </TransitionGroup>
  </div>

  <!-- Custom ACG Confirm Modal -->
  <Transition name="fade-scale">
    <div
      v-if="store.confirmState"
      class="fixed inset-0 ds-backdrop z-[65] flex items-center justify-center p-4 select-none"
      @click.self="store.confirmState.onCancel()"
    >
      <div class="ds-modal w-full max-w-xs p-5 space-y-4">
        <div class="space-y-1.5">
          <div class="flex items-center gap-2">
            <span class="text-[16px]">🐋</span>
            <h3 class="text-[14px] font-extrabold text-[var(--text-primary)]">
              {{ store.confirmState.title }}
            </h3>
          </div>
          <p class="text-[12.5px] text-[var(--text-secondary)] leading-relaxed">
            {{ store.confirmState.message }}
          </p>
        </div>

        <div class="flex items-center justify-end gap-2 pt-1">
          <button
            @click="store.confirmState.onCancel()"
            class="px-3.5 py-1.5 rounded-xl text-[12px] font-semibold text-[var(--text-secondary)] hover:bg-[var(--bg-hover)] transition"
          >
            先不了
          </button>
          <button
            @click="store.confirmState.onConfirm()"
            :class="[
              'px-4 py-1.5 rounded-xl text-[12px] font-bold ds-spring',
              store.confirmState.danger
                ? 'bg-[var(--accent-rose)] hover:opacity-90 text-white shadow-sm'
                : 'ds-btn-primary'
            ]"
          >
            {{ store.confirmState.confirmText }}
          </button>
        </div>
      </div>
    </div>
  </Transition>
</template>
