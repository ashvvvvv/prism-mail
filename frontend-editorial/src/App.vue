<script setup>
import { ref, watch, onMounted, onBeforeUnmount } from 'vue'
import { useMailStore } from './stores/mail'
import MastheadBar from './components/MastheadBar.vue'
import IndexDirectory from './components/IndexDirectory.vue'
import DispatchLedger from './components/DispatchLedger.vue'
import ReadingSalon from './components/ReadingSalon.vue'
import CommandPalette from './components/CommandPalette.vue'
import ComposeSheet from './components/ComposeSheet.vue'
import DomainSheet from './components/DomainSheet.vue'
import ExternalSheet from './components/ExternalSheet.vue'
import SettingsSheet from './components/SettingsSheet.vue'
import ToastLayer from './components/ToastLayer.vue'

const store = useMailStore()
const ledgerRef = ref(null)
const salonRef = ref(null)

const isMobile = ref(typeof window !== 'undefined' ? window.innerWidth < 1024 : false)
const handleViewportResize = () => {
  const mobile = window.innerWidth < 1024
  isMobile.value = mobile
  if (!mobile) {
    store.isMobileNavOpen = false
  }
}

const handlePopState = () => {
  if (isMobile.value && store.selectedMail) {
    store.closeMail()
  }
}

watch(
  () => store.selectedMail,
  (mail, prev) => {
    if (isMobile.value && mail && !prev) {
      if (!window.history.state?.prismReader) {
        window.history.pushState({ prismReader: 1 }, '')
      }
    }
  }
)

const DEFAULT_INDEX_WIDTH = 264
const DEFAULT_LEDGER_WIDTH = 364

const indexWidth = ref(Number(localStorage.getItem('prism_editorial_index_w')) || DEFAULT_INDEX_WIDTH)
const ledgerWidth = ref(Number(localStorage.getItem('prism_editorial_ledger_w')) || DEFAULT_LEDGER_WIDTH)

const activeResizer = ref(null) // 'index' | 'ledger' | null
let startX = 0
let startWidth = 0

const startResize = (which, evt) => {
  evt.preventDefault()
  activeResizer.value = which
  startX = evt.clientX
  startWidth = which === 'index' ? indexWidth.value : ledgerWidth.value
  document.body.style.cursor = 'col-resize'
  document.body.style.userSelect = 'none'
  window.addEventListener('mousemove', onMouseMove)
  window.addEventListener('mouseup', stopResize)
}

const onMouseMove = (evt) => {
  if (!activeResizer.value) return
  const delta = evt.clientX - startX
  const maxTotal = window.innerWidth - 320
  if (activeResizer.value === 'index') {
    indexWidth.value = Math.min(Math.max(204, startWidth + delta), Math.min(440, maxTotal - ledgerWidth.value))
  } else if (activeResizer.value === 'ledger') {
    ledgerWidth.value = Math.min(Math.max(268, startWidth + delta), Math.min(680, maxTotal - indexWidth.value))
  }
}

const stopResize = () => {
  if (!activeResizer.value) return
  localStorage.setItem('prism_editorial_index_w', String(indexWidth.value))
  localStorage.setItem('prism_editorial_ledger_w', String(ledgerWidth.value))
  activeResizer.value = null
  document.body.style.cursor = ''
  document.body.style.userSelect = ''
  window.removeEventListener('mousemove', onMouseMove)
  window.removeEventListener('mouseup', stopResize)
}

const resetWidth = (which) => {
  if (which === 'index') {
    indexWidth.value = DEFAULT_INDEX_WIDTH
    localStorage.setItem('prism_editorial_index_w', String(DEFAULT_INDEX_WIDTH))
  } else {
    ledgerWidth.value = DEFAULT_LEDGER_WIDTH
    localStorage.setItem('prism_editorial_ledger_w', String(DEFAULT_LEDGER_WIDTH))
  }
}

const handleGlobalKeydown = (e) => {
  if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
    e.preventDefault()
    store.isCommandOpen = !store.isCommandOpen
    return
  }

  if ((e.metaKey || e.ctrlKey) && e.key === ',') {
    e.preventDefault()
    store.isSettingsOpen = !store.isSettingsOpen
    return
  }

  const tag = (e.target?.tagName || '').toLowerCase()
  if (tag === 'input' || tag === 'textarea' || tag === 'select' || e.target?.isContentEditable) {
    return
  }
  if (e.key === 'Escape') {
    if (store.isMobileNavOpen) {
      store.isMobileNavOpen = false
      return
    }
    if (isMobile.value && store.selectedMail) {
      store.closeMail()
      return
    }
  }
  if (
    store.isCommandOpen ||
    store.isSettingsOpen ||
    store.isComposeOpen ||
    store.isDomainModalOpen ||
    store.activeDomainDns ||
    store.isExternalModalOpen ||
    store.confirmState
  ) {
    return
  }
  if (e.metaKey || e.ctrlKey || e.altKey) return

  const key = e.key.toLowerCase()
  if (key === 'c') {
    e.preventDefault()
    store.openCompose()
  } else if (key === 'j' || e.key === 'ArrowDown') {
    e.preventDefault()
    store.selectAdjacentMail(1)
  } else if (key === 'k' || e.key === 'ArrowUp') {
    e.preventDefault()
    store.selectAdjacentMail(-1)
  } else if (key === 'r' && store.selectedMailDetail) {
    e.preventDefault()
    salonRef.value?.triggerReply()
  } else if (key === '/') {
    e.preventDefault()
    ledgerRef.value?.focusSearch()
  }
}

onMounted(() => {
  handleViewportResize()
  store.init()
  window.addEventListener('keydown', handleGlobalKeydown)
  window.addEventListener('resize', handleViewportResize)
  window.addEventListener('popstate', handlePopState)
})

onBeforeUnmount(() => {
  stopResize()
  window.removeEventListener('keydown', handleGlobalKeydown)
  window.removeEventListener('resize', handleViewportResize)
  window.removeEventListener('popstate', handlePopState)
})
</script>

<template>
  <div class="app-viewport flex flex-col overflow-hidden bg-[var(--bg-linen)] text-[var(--ink-primary)]">
    <!-- Top Architectural Masthead Bar -->
    <MastheadBar />

    <!-- Mobile Slide-Over Directory Drawer -->
    <Transition name="backdrop-fade">
      <div
        v-if="isMobile && store.isMobileNavOpen"
        class="fixed inset-0 ed-backdrop z-40"
        @click="store.isMobileNavOpen = false"
      />
    </Transition>
    <Transition name="drawer-slide">
      <IndexDirectory
        v-if="isMobile && store.isMobileNavOpen"
        class="fixed inset-y-0 left-0 z-50 w-[284px] max-w-[85vw] shadow-2xl"
      />
    </Transition>

    <!-- 3 Resizable Architectural Columns (Desktop) / Single Active Pane (Mobile) -->
    <div class="flex-1 flex overflow-hidden min-h-0">
      <!-- Column 1: Index Directory (Desktop) -->
      <IndexDirectory
        v-if="!isMobile"
        :style="{ width: `${indexWidth}px` }"
      />

      <!-- Resizer 1: Index <-> Ledger -->
      <div
        v-if="!isMobile"
        @mousedown="startResize('index', $event)"
        @dblclick="resetWidth('index')"
        class="w-2 -mx-1 z-20 cursor-col-resize group flex items-center justify-center select-none flex-shrink-0"
        title="拖动调整目录栏宽（双击还原默认）"
      >
        <div
          :class="[
            'w-[1.5px] h-full transition-colors duration-150',
            activeResizer === 'index'
              ? 'bg-[var(--accent-vermilion)]'
              : 'bg-transparent group-hover:bg-[var(--accent-vermilion)]'
          ]"
        />
      </div>

      <!-- Column 2: Dispatch Ledger -->
      <DispatchLedger
        v-show="!isMobile || !store.selectedMail"
        ref="ledgerRef"
        :class="isMobile ? 'flex-1 w-full !border-r-0' : ''"
        :style="isMobile ? {} : { width: `${ledgerWidth}px` }"
      />

      <!-- Resizer 2: Ledger <-> Reading Salon -->
      <div
        v-if="!isMobile"
        @mousedown="startResize('ledger', $event)"
        @dblclick="resetWidth('ledger')"
        class="w-2 -mx-1 z-20 cursor-col-resize group flex items-center justify-center select-none flex-shrink-0"
        title="拖动调整列表栏宽（双击还原默认）"
      >
        <div
          :class="[
            'w-[1.5px] h-full transition-colors duration-150',
            activeResizer === 'ledger'
              ? 'bg-[var(--accent-vermilion)]'
              : 'bg-transparent group-hover:bg-[var(--accent-vermilion)]'
          ]"
        />
      </div>

      <!-- Column 3: Reading Salon -->
      <ReadingSalon
        v-show="!isMobile || Boolean(store.selectedMail)"
        ref="salonRef"
        :class="isMobile ? 'flex-1 w-full min-w-0' : 'flex-1 min-w-[300px]'"
      />
    </div>

    <!-- Editorial Overlays & Folio Modals -->
    <CommandPalette />
    <ComposeSheet />
    <DomainSheet />
    <ExternalSheet />
    <SettingsSheet />
    <ToastLayer />
  </div>
</template>
