<script setup>
import { useMailStore } from '../stores/mail'
import { Check, AlertCircle, Bookmark } from 'lucide-vue-next'

const store = useMailStore()
</script>

<template>
  <!-- Editorial Postal Slip Toast Notifications -->
  <div class="fixed bottom-4 sm:bottom-5 left-3 right-3 sm:left-auto sm:right-5 z-[70] flex flex-col items-center sm:items-end gap-2 pointer-events-none pb-safe">
    <TransitionGroup name="postal-toast">
      <div
        v-for="t in store.toasts"
        :key="t.id"
        :class="[
          'pointer-events-auto ed-folio-modal px-3.5 py-2.5 flex items-center gap-2.5 text-[12.5px] text-[var(--ink-primary)] min-w-[210px] max-w-full sm:max-w-sm border-l-[3px]',
          t.type === 'success'
            ? 'border-l-[var(--accent-forest)]'
            : t.type === 'error'
              ? 'border-l-[var(--accent-vermilion)]'
              : 'border-l-[var(--ink-primary)]'
        ]"
      >
        <Check v-if="t.type === 'success'" class="w-3.5 h-3.5 text-[var(--accent-forest)] flex-shrink-0" />
        <AlertCircle v-else-if="t.type === 'error'" class="w-3.5 h-3.5 text-[var(--accent-vermilion)] flex-shrink-0" />
        <Bookmark v-else class="w-3.5 h-3.5 text-[var(--ink-secondary)] flex-shrink-0" />
        <span class="truncate">{{ t.message }}</span>
      </div>
    </TransitionGroup>
  </div>

  <!-- Custom Architectural Confirm Dialog -->
  <Transition name="folio-fade">
    <div
      v-if="store.confirmState"
      class="fixed inset-0 ed-backdrop z-[65] flex items-center justify-center p-4 select-none"
      @click.self="store.confirmState.onCancel()"
    >
      <div class="ed-folio-modal w-full max-w-xs overflow-hidden">
        <div class="px-5 py-3 border-b border-[var(--rule-faint)] bg-[var(--bg-linen)]">
          <span class="ed-rubric text-[var(--accent-vermilion)] block">确认操作</span>
          <h3 class="font-serif text-[17px] font-medium text-[var(--ink-primary)] mt-0.5">
            {{ store.confirmState.title }}
          </h3>
        </div>

        <div class="p-5 space-y-4">
          <p class="text-[12.5px] text-[var(--ink-secondary)] leading-relaxed">
            {{ store.confirmState.message }}
          </p>

          <div class="flex items-center justify-end gap-2 pt-2 border-t border-[var(--rule-faint)]">
            <button
              @click="store.confirmState.onCancel()"
              class="ed-btn-outline px-3.5 py-1.5 text-[12px]"
            >
              取消
            </button>
            <button
              @click="store.confirmState.onConfirm()"
              :class="[
                'px-4 py-1.5 rounded-[2px] text-[12px] font-medium transition',
                store.confirmState.danger
                  ? 'bg-[var(--accent-vermilion)] hover:opacity-90 text-[#FAF8F4]'
                  : 'ed-btn-ink'
              ]"
            >
              {{ store.confirmState.confirmText }}
            </button>
          </div>
        </div>
      </div>
    </div>
  </Transition>
</template>
