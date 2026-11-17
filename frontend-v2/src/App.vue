<script setup>
import { ref, watch, onMounted, onBeforeUnmount } from 'vue'
import { useMailStore } from './stores/mail'
import NavRail from './components/NavRail.vue'
import MailStream from './components/MailStream.vue'
import MailAtelier from './components/MailAtelier.vue'
import CommandPalette from './components/CommandPalette.vue'
import ComposeSheet from './components/ComposeSheet.vue'
import DomainSheet from './components/DomainSheet.vue'
import ExternalSheet from './components/ExternalSheet.vue'
import SettingsSheet from './components/SettingsSheet.vue'
import ToastLayer from './components/ToastLayer.vue'

const store = useMailStore()
const streamRef = ref(null)
const atelierRef = ref(null)

const isMobile = ref(typeof window !== 'undefined' ? window.innerWidth < 1024 : false)

const handleViewportResize = () => {
  const mobile = window.innerWidth < 1024
  isMobile.value = mobile
  if (!mobile && store.isMobileNavOpen) {
    store.isMobileNavOpen = false
  }
}

watch(
  () => store.selectedMail,
  (mail, prev) => {
    if (isMobile.value && mail && !prev && !window.history.state?.prismReader) {
      window.history.pushState({ prismReader: 1 }, '')
    }
  }
)

const handlePopState = () => {
  if (store.isMobileNavOpen) {
    store.isMobileNavOpen = false
    return
  }
  if (isMobile.value && store.selectedMail) {
    store.closeMail()
  }
}

const DEFAULT_SIDEBAR_WIDTH = 252
const DEFAULT_STREAM_WIDTH = 348

const sidebarWidth = ref(Number(localStorage.getItem('prism_v2_sidebar_w')) || DEFAULT_SIDEBAR_WIDTH)
const streamWidth = ref(Number(localStorage.getItem('prism_v2_stream_w')) || DEFAULT_STREAM_WIDTH)

const activeResizer = ref(null) // 'sidebar' | 'stream' | null
let startX = 0
let startWidth = 0

const startResize = (which, evt) => {
  evt.preventDefault()
  activeResizer.value = which
  startX = evt.clientX
  startWidth = which === 'sidebar' ? sidebarWidth.value : streamWidth.value
  document.body.style.cursor = 'col-resize'
  document.body.style.userSelect = 'none'
  window.addEventListener('mousemove', onMouseMove)
  window.addEventListener('mouseup', stopResize)
}

const onMouseMove = (evt) => {
  if (!activeResizer.value) return
  const delta = evt.clientX - startX
  const maxTotal = window.innerWidth - 320
  if (activeResizer.value === 'sidebar') {
    sidebarWidth.value = Math.min(Math.max(200, startWidth + delta), Math.min(440, maxTotal - streamWidth.value))
  } else if (activeResizer.value === 'stream') {
    streamWidth.value = Math.min(Math.max(260, startWidth + delta), Math.min(680, maxTotal - sidebarWidth.value))
  }
}

const stopResize = () => {
  if (!activeResizer.value) return
  localStorage.setItem('prism_v2_sidebar_w', String(sidebarWidth.value))
  localStorage.setItem('prism_v2_stream_w', String(streamWidth.value))
  activeResizer.value = null
  document.body.style.cursor = ''
  document.body.style.userSelect = ''
  window.removeEventListener('mousemove', onMouseMove)
  window.removeEventListener('mouseup', stopResize)
}

const resetWidth = (which) => {
  if (which === 'sidebar') {
    sidebarWidth.value = DEFAULT_SIDEBAR_WIDTH
    localStorage.setItem('prism_v2_sidebar_w', String(DEFAULT_SIDEBAR_WIDTH))
  } else {
    streamWidth.value = DEFAULT_STREAM_WIDTH
    localStorage.setItem('prism_v2_stream_w', String(DEFAULT_STREAM_WIDTH))
  }
}

const handleGlobalKeydown = (e) => {
  // Cmd/Ctrl + K always toggles Command Palette; Cmd/Ctrl + , opens Settings
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

  // Skip single-key shortcuts if user is typing or a modal is open
  const tag = (e.target?.tagName || '').toLowerCase()
  if (tag === 'input' || tag === 'textarea' || tag === 'select' || e.target?.isContentEditable) {
    return
  }
  if (
    store.isCommandOpen ||
    store.isComposeOpen ||
    store.isDomainModalOpen ||
    store.activeDomainDns ||
    store.isExternalModalOpen ||
    store.isSettingsOpen ||
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
    atelierRef.value?.triggerReply()
  } else if (key === '/') {
    e.preventDefault()
    streamRef.value?.focusSearch()
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
  <div class="app-viewport flex overflow-hidden bg-[var(--bg-canvas)] text-[var(--text-primary)] relative">
    <!-- Desktop Column 1: Borderless Architectural Sidebar Rail -->
    <NavRail v-if="!isMobile" :style="{ width: `${sidebarWidth}px` }" />

    <!-- Mobile Slide-Over Navigation Drawer -->
    <template v-else>
      <Transition name="backdrop-fade">
        <div
          v-if="store.isMobileNavOpen"
          class="fixed inset-0 pm-backdrop z-40"
          @click="store.isMobileNavOpen = false"
        />
      </Transition>
      <Transition name="drawer-slide">
        <NavRail
          v-if="store.isMobileNavOpen"
          class="fixed inset-y-0 left-0 z-50 w-[284px] max-w-[85vw] bg-[var(--bg-canvas)] border-r border-[var(--border-strong)] shadow-2xl"
        />
      </Transition>
    </template>

    <!-- Resizer 1: Sidebar <-> Floating Sheet (Desktop Only) -->
    <div
      v-if="!isMobile"
      @mousedown="startResize('sidebar', $event)"
      @dblclick="resetWidth('sidebar')"
      class="w-2 -mx-1 z-30 cursor-col-resize group flex items-center justify-center select-none flex-shrink-0"
      title="拖动调整宽度（双击还原）"
    >
      <div
        :class="[
          'w-[2px] h-12 rounded-full transition-all duration-150',
          activeResizer === 'sidebar'
            ? 'h-full bg-[var(--text-secondary)]'
            : 'bg-transparent group-hover:bg-[var(--border-strong)]'
        ]"
      />
    </div>

    <!-- Floating Architectural Workspace Sheet (Full-Bleed on Mobile) -->
    <div
      :class="[
        'flex-1 flex overflow-hidden min-w-0',
        isMobile ? 'bg-[var(--bg-sheet)]' : 'my-2 mr-2 rounded-2xl pm-sheet'
      ]"
    >
      <!-- Column 2: Mail Stream -->
      <MailStream
        v-show="!isMobile || !store.selectedMail"
        ref="streamRef"
        :style="isMobile ? undefined : { width: `${streamWidth}px` }"
        :class="isMobile ? 'w-full flex-1 border-r-0' : ''"
      />

      <!-- Resizer 2: Stream <-> Atelier (Desktop Only) -->
      <div
        v-if="!isMobile"
        @mousedown="startResize('stream', $event)"
        @dblclick="resetWidth('stream')"
        class="w-1.5 -mx-[3px] z-30 cursor-col-resize group flex items-center justify-center select-none flex-shrink-0"
        title="拖动调整宽度（双击还原）"
      >
        <div
          :class="[
            'w-[1.5px] h-full transition-colors duration-150',
            activeResizer === 'stream'
              ? 'bg-[var(--text-secondary)]'
              : 'bg-transparent group-hover:bg-[var(--border-strong)]'
          ]"
        />
      </div>

      <!-- Column 3: Editorial Reading Atelier -->
      <MailAtelier
        v-show="!isMobile || Boolean(store.selectedMail)"
        ref="atelierRef"
        :class="isMobile ? 'w-full flex-1 min-w-0' : 'flex-1 min-w-[280px]'"
      />
    </div>

    <!-- Overlays & Sheets -->
    <CommandPalette />
    <ComposeSheet />
    <DomainSheet />
    <ExternalSheet />
    <SettingsSheet />
    <ToastLayer />
  </div>
</template>
