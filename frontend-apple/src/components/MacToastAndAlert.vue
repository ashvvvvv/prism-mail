<script setup>
import { useMailStore } from '../stores/mail'
import { Check, AlertCircle, Info, Trash2 } from 'lucide-vue-next'

const store = useMailStore()
</script>

<template>
  <!-- macOS Notification Center Frosted Banners (Top-Right below Toolbar) -->
  <div class="fixed top-[58px] sm:top-[62px] left-3 right-3 sm:left-auto sm:right-4 z-[80] flex flex-col items-center sm:items-end gap-2 pointer-events-none select-none">
    <TransitionGroup name="mac-banner">
      <div
        v-for="t in store.toasts"
        :key="t.id"
        class="pointer-events-auto mac-toast px-3.5 py-2.5 rounded-[13px] flex items-center gap-2.5 text-[12.5px] font-medium text-[var(--label-primary)] min-w-[210px] max-w-full sm:max-w-[340px]"
      >
        <div
          :class="[
            'w-6 h-6 rounded-[7px] flex items-center justify-center flex-shrink-0 text-white shadow-sm',
            t.type === 'success'
              ? 'bg-[var(--apple-green)]'
              : t.type === 'error'
                ? 'bg-[var(--apple-red)]'
                : 'bg-[var(--apple-blue)]'
          ]"
        >
          <Check v-if="t.type === 'success'" class="w-3.5 h-3.5 stroke-[2.5]" />
          <AlertCircle v-else-if="t.type === 'error'" class="w-3.5 h-3.5 stroke-[2.2]" />
          <Info v-else class="w-3.5 h-3.5 stroke-[2.2]" />
        </div>
        <span class="truncate">{{ t.message }}</span>
      </div>
    </TransitionGroup>
  </div>

  <!-- Authentic macOS Sequoia Alert / Confirm Sheet -->
  <Transition name="mac-sheet-fade">
    <div
      v-if="store.confirmState"
      class="fixed inset-0 mac-backdrop z-[75] flex items-center justify-center p-4 select-none"
      @click.self="store.confirmState.onCancel()"
    >
      <div class="mac-sheet rounded-[18px] w-full max-w-[290px] p-5 text-center space-y-4">
        <div class="mx-auto w-12 h-12 rounded-[14px] flex items-center justify-center shadow-sm"
          :class="store.confirmState.danger ? 'bg-[#FF3B30]/14 text-[var(--apple-red)]' : 'bg-[#007AFF]/14 text-[var(--apple-blue)]'"
        >
          <Trash2 v-if="store.confirmState.danger" class="w-6 h-6 stroke-[1.8]" />
          <Info v-else class="w-6 h-6 stroke-[1.8]" />
        </div>

        <div class="space-y-1.5">
          <h3 class="text-[14px] font-semibold text-[var(--label-primary)] leading-snug">
            {{ store.confirmState.title }}
          </h3>
          <p class="text-[12px] text-[var(--label-secondary)] leading-relaxed">
            {{ store.confirmState.message }}
          </p>
        </div>

        <div class="grid grid-cols-2 gap-2 pt-1">
          <button
            type="button"
            @click="store.confirmState.onCancel()"
            class="mac-btn-secondary h-[32px] rounded-[9px] text-[13px] font-medium"
          >
            取消
          </button>
          <button
            type="button"
            @click="store.confirmState.onConfirm()"
            :class="[
              'h-[32px] rounded-[9px] text-[13px] font-semibold text-white transition active:scale-[0.985]',
              store.confirmState.danger
                ? 'bg-[var(--apple-red)] hover:brightness-95 shadow-[0_1px_2px_rgba(255,59,48,0.28)]'
                : 'mac-btn-blue'
            ]"
          >
            {{ store.confirmState.confirmText }}
          </button>
        </div>
      </div>
    </div>
  </Transition>
</template>
