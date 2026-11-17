<script setup>
import { ref, watch, onMounted, onBeforeUnmount } from 'vue'
import { useMailStore } from './stores/mail'
import MacToolbar from './components/MacToolbar.vue'
import SidebarVibrancy from './components/SidebarVibrancy.vue'
import MailListPane from './components/MailListPane.vue'
import MailReaderPane from './components/MailReaderPane.vue'
import SpotlightModal from './components/SpotlightModal.vue'
import ComposeModal from './components/ComposeModal.vue'
import DomainModal from './components/DomainModal.vue'
import ExternalModal from './components/ExternalModal.vue'
import SettingsModal from './components/SettingsModal.vue'
import MacToastAndAlert from './components/MacToastAndAlert.vue'

const store = useMailStore()
const toolbarRef = ref(null)
const readerRef = ref(null)

const isMobile = ref(typeof window !== 'undefined' ? window.innerWidth < 1024 : false)

const updateViewport = () => {
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
    if (isMobile.value && mail && !prev && !window.history.state?.prismReader) {
      window.history.pushState({ prismReader: 1 }, '')
    }
  }
)

const DEFAULT_SIDEBAR_WIDTH = 246
const DEFAULT_STREAM_WIDTH = 342

const sidebarWidth = ref(Number(localStorage.getItem('prism_apple_sidebar_w')) || DEFAULT_SIDEBAR_WIDTH)
const streamWidth = ref(Number(localStorage.getItem('prism_apple_stream_w')) || DEFAULT_STREAM_WIDTH)

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
  const effectiveSidebar = store.isSidebarCollapsed ? 0 : sidebarWidth.value
  if (activeResizer.value === 'sidebar') {
    sidebarWidth.value = Math.min(Math.max(196, startWidth + delta), Math.min(420, maxTotal - streamWidth.value))
  } else if (activeResizer.value === 'stream') {
    streamWidth.value = Math.min(Math.max(264, startWidth + delta), Math.min(640, maxTotal - effectiveSidebar))
  }
}

const stopResize = () => {
  if (!activeResizer.value) return
  localStorage.setItem('prism_apple_sidebar_w', String(sidebarWidth.value))
  localStorage.setItem('prism_apple_stream_w', String(streamWidth.value))
  activeResizer.value = null
  document.body.style.cursor = ''
  document.body.style.userSelect = ''
  window.removeEventListener('mousemove', onMouseMove)
  window.removeEventListener('mouseup', stopResize)
}

const resetWidth = (which) => {
  if (which === 'sidebar') {
    sidebarWidth.value = DEFAULT_SIDEBAR_WIDTH
    localStorage.setItem('prism_apple_sidebar_w', String(DEFAULT_SIDEBAR_WIDTH))
  } else {
    streamWidth.value = DEFAULT_STREAM_WIDTH
    localStorage.setItem('prism_apple_stream_w', String(DEFAULT_STREAM_WIDTH))
  }
}

const handleToolbarReply = () => {
  readerRef.value?.triggerReply()
}

const handleGlobalKeydown = (e) => {
  // Cmd/Ctrl + K always toggles Spotlight Command Palette
  if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
    e.preventDefault()
    store.isCommandOpen = !store.isCommandOpen
    return
  }

  // Cmd/Ctrl + , toggles macOS System Settings
  if ((e.metaKey || e.ctrlKey) && e.key === ',') {
    e.preventDefault()
    store.isSettingsOpen = !store.isSettingsOpen
    return
  }

  // Skip single-key shortcuts if user is typing or any sheet is open
  const tag = (e.target?.tagName || '').toLowerCase()
  if (tag === 'input' || tag === 'textarea' || tag === 'select' || e.target?.isContentEditable) {
    return
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
    readerRef.value?.triggerReply()
  } else if (key === '/') {
    e.preventDefault()
    toolbarRef.value?.focusSearch()
  }
}

onMounted(() => {
  store.init()
  updateViewport()
  window.addEventListener('keydown', handleGlobalKeydown)
  window.addEventListener('resize', updateViewport)
  window.addEventListener('popstate', handlePopState)
})

onBeforeUnmount(() => {
  stopResize()
  window.removeEventListener('keydown', handleGlobalKeydown)
  window.removeEventListener('resize', updateViewport)
  window.removeEventListener('popstate', handlePopState)
})
</script>

<template>
  <div class="app-viewport flex flex-col overflow-hidden text-[var(--label-primary)]">
    <!-- Unified macOS Sequoia Window Toolbar -->
    <MacToolbar ref="toolbarRef" @reply="handleToolbarReply" />

    <!-- 3-Column Split View Workspace -->
    <div class="flex-1 flex overflow-hidden min-h-0 relative">
      <!-- Mobile Drawer Backdrop -->
      <Transition name="backdrop-fade">
        <div
          v-if="isMobile && store.isMobileNavOpen"
          class="fixed inset-0 bg-black/40 backdrop-blur-[2px] z-40"
          @click="store.isMobileNavOpen = false"
        />
      </Transition>

      <!-- Mobile Slide-Over Sidebar -->
      <Transition name="drawer-slide">
        <SidebarVibrancy
          v-if="isMobile && store.isMobileNavOpen"
          class="fixed inset-y-0 left-0 z-50 w-[284px] max-w-[85vw] shadow-2xl !bg-[var(--bg-sheet)]"
        />
      </Transition>

      <!-- Column 1: Frosted Translucent macOS Sidebar (Desktop) -->
      <SidebarVibrancy
        v-if="!isMobile"
        v-show="!store.isSidebarCollapsed"
        :style="{ width: `${sidebarWidth}px` }"
      />

      <!-- Split-Pane Resizer 1 (Sidebar <-> Mail List) -->
      <div
        v-if="!isMobile"
        v-show="!store.isSidebarCollapsed"
        @mousedown="startResize('sidebar', $event)"
        @dblclick="resetWidth('sidebar')"
        class="w-[7px] -mx-[3.5px] z-20 cursor-col-resize group flex items-center justify-center select-none flex-shrink-0"
        title="拖动调整边栏宽度（双击还原默认宽度）"
      >
        <div
          :class="[
            'w-[2px] h-full transition-colors duration-150',
            activeResizer === 'sidebar'
              ? 'bg-[var(--apple-blue)]'
              : 'bg-transparent group-hover:bg-[var(--apple-blue)]/45'
          ]"
        />
      </div>

      <!-- Column 2: Crisp Apple Mail List -->
      <MailListPane
        v-show="!isMobile || !store.selectedMail"
        :style="isMobile ? {} : { width: `${streamWidth}px` }"
        :class="isMobile ? 'flex-1 w-full !border-r-0' : ''"
      />

      <!-- Split-Pane Resizer 2 (Mail List <-> Reading Pane) -->
      <div
        v-if="!isMobile"
        @mousedown="startResize('stream', $event)"
        @dblclick="resetWidth('stream')"
        class="w-[7px] -mx-[3.5px] z-20 cursor-col-resize group flex items-center justify-center select-none flex-shrink-0"
        title="拖动调整邮件列表宽度（双击还原默认宽度）"
      >
        <div
          :class="[
            'w-[2px] h-full transition-colors duration-150',
            activeResizer === 'stream'
              ? 'bg-[var(--apple-blue)]'
              : 'bg-transparent group-hover:bg-[var(--apple-blue)]/45'
          ]"
        />
      </div>

      <!-- Column 3: Crisp Apple Mail Reading Pane -->
      <MailReaderPane
        v-show="!isMobile || Boolean(store.selectedMail)"
        ref="readerRef"
        :class="isMobile ? 'flex-1 w-full min-w-0' : 'flex-1 min-w-[280px]'"
      />
    </div>

    <!-- macOS Sheets, Spotlight & Notification Banners -->
    <SpotlightModal />
    <ComposeModal />
    <DomainModal />
    <ExternalModal />
    <SettingsModal />
    <MacToastAndAlert />
  </div>
</template>
