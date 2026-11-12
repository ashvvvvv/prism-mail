<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { useMailStore } from './stores/mail'
import HudHeader from './components/HudHeader.vue'
import NavRail from './components/NavRail.vue'
import MailStream from './components/MailStream.vue'
import MailAtelier from './components/MailAtelier.vue'
import CommandPalette from './components/CommandPalette.vue'
import ComposeSheet from './components/ComposeSheet.vue'
import DomainSheet from './components/DomainSheet.vue'
import ExternalSheet from './components/ExternalSheet.vue'
import ToastLayer from './components/ToastLayer.vue'

const store = useMailStore()
const streamRef = ref(null)
const atelierRef = ref(null)

const heroDayBg = `${import.meta.env.BASE_URL}deepseek-hero-day.jpg`
const heroNightBg = `${import.meta.env.BASE_URL}deepseek-hero-night.jpg`

const DEFAULT_SIDEBAR_WIDTH = 268
const DEFAULT_STREAM_WIDTH = 352

const sidebarWidth = ref(Number(localStorage.getItem('prism_deepseek_sidebar_w')) || DEFAULT_SIDEBAR_WIDTH)
const streamWidth = ref(Number(localStorage.getItem('prism_deepseek_stream_w')) || DEFAULT_STREAM_WIDTH)

const activeResizer = ref(null) // 'sidebar' | 'stream' | null
let startX = 0
let startWidth = 0

// Subtle Floating Ocean Bubbles Config
const BUBBLES = [
  { id: 1, left: '6%', size: 12, duration: '15s', delay: '0s' },
  { id: 2, left: '19%', size: 18, duration: '21s', delay: '3s' },
  { id: 3, left: '34%', size: 10, duration: '17s', delay: '6s' },
  { id: 4, left: '49%', size: 22, duration: '24s', delay: '1.5s' },
  { id: 5, left: '64%', size: 14, duration: '18s', delay: '8s' },
  { id: 6, left: '78%', size: 16, duration: '20s', delay: '4.5s' },
  { id: 7, left: '91%', size: 11, duration: '16s', delay: '9s' }
]

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
  const maxTotal = window.innerWidth - 330
  if (activeResizer.value === 'sidebar') {
    sidebarWidth.value = Math.min(Math.max(220, startWidth + delta), Math.min(440, maxTotal - streamWidth.value))
  } else if (activeResizer.value === 'stream') {
    streamWidth.value = Math.min(Math.max(270, startWidth + delta), Math.min(680, maxTotal - sidebarWidth.value))
  }
}

const stopResize = () => {
  if (!activeResizer.value) return
  localStorage.setItem('prism_deepseek_sidebar_w', String(sidebarWidth.value))
  localStorage.setItem('prism_deepseek_stream_w', String(streamWidth.value))
  activeResizer.value = null
  document.body.style.cursor = ''
  document.body.style.userSelect = ''
  window.removeEventListener('mousemove', onMouseMove)
  window.removeEventListener('mouseup', stopResize)
}

const resetWidth = (which) => {
  if (which === 'sidebar') {
    sidebarWidth.value = DEFAULT_SIDEBAR_WIDTH
    localStorage.setItem('prism_deepseek_sidebar_w', String(DEFAULT_SIDEBAR_WIDTH))
  } else {
    streamWidth.value = DEFAULT_STREAM_WIDTH
    localStorage.setItem('prism_deepseek_stream_w', String(DEFAULT_STREAM_WIDTH))
  }
}

const handleGlobalKeydown = (e) => {
  if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
    e.preventDefault()
    store.isCommandOpen = !store.isCommandOpen
    return
  }

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
    store.confirmState
  ) {
    return
  }
  if (e.key === 'Escape' && store.lobbyFullScreen) {
    e.preventDefault()
    store.lobbyFullScreen = false
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
  } else if (key === 'r' && store.selectedMailDetail && !store.showMascotStage) {
    e.preventDefault()
    atelierRef.value?.triggerReply()
  } else if (key === '/') {
    e.preventDefault()
    streamRef.value?.focusSearch()
  }
}

onMounted(() => {
  store.init()
  window.addEventListener('keydown', handleGlobalKeydown)
})

onBeforeUnmount(() => {
  stopResize()
  window.removeEventListener('keydown', handleGlobalKeydown)
})
</script>

<template>
  <div class="h-screen w-screen flex flex-col overflow-hidden ds-ocean-canvas text-[var(--text-primary)] relative">
    <!-- Immersive Blurred Dual-CG Ambient Backdrop (Day <-> Night Crossfade) -->
    <div class="absolute inset-0 overflow-hidden pointer-events-none z-0 select-none" aria-hidden="true">
      <img
        :src="heroDayBg"
        alt=""
        :class="[
          'absolute inset-0 w-full h-full object-cover scale-110 blur-[34px] transition-opacity duration-700',
          store.theme === 'ocean-light' ? 'opacity-[0.34]' : 'opacity-0'
        ]"
      />
      <img
        :src="heroNightBg"
        alt=""
        :class="[
          'absolute inset-0 w-full h-full object-cover scale-110 blur-[34px] transition-opacity duration-700',
          store.theme === 'abyss-dark' ? 'opacity-[0.42]' : 'opacity-0'
        ]"
      />
    </div>

    <!-- Subtle Schale OS Dot-Grid Pattern -->
    <div class="absolute inset-0 ds-dot-grid pointer-events-none z-0" />

    <!-- Subtle Animated Floating Ocean Bubbles -->
    <div class="absolute inset-0 overflow-hidden pointer-events-none z-0" aria-hidden="true">
      <span
        v-for="b in BUBBLES"
        :key="b.id"
        class="ds-bubble"
        :style="{
          left: b.left,
          width: `${b.size}px`,
          height: `${b.size}px`,
          animationDuration: b.duration,
          animationDelay: b.delay
        }"
      />
    </div>

    <!-- Top ACG HUD Header Bar -->
    <HudHeader />

    <!-- 3-Column Draggable Split-Pane ACG Workspace (or Full-Screen Memorial Lobby Mode) -->
    <div class="flex-1 px-3 pt-2.5 pb-3 flex overflow-hidden min-h-0 min-w-0 z-10">
      <template v-if="!store.lobbyFullScreen">
        <!-- Column 1: DeepSeek-tan Sidebar Rail + Chibi Companion -->
        <NavRail :style="{ width: `${sidebarWidth}px` }" />

        <!-- Resizer 1: Sidebar <-> MailStream -->
        <div
          @mousedown="startResize('sidebar', $event)"
          @dblclick="resetWidth('sidebar')"
          class="w-2.5 z-30 cursor-col-resize group flex items-center justify-center select-none flex-shrink-0"
          title="拖动调整侧栏宽度（双击还原默认）"
        >
          <div
            :class="[
              'w-[3px] rounded-full transition-all duration-150',
              activeResizer === 'sidebar'
                ? 'h-24 bg-[#4D6BFE]'
                : 'h-10 bg-transparent group-hover:bg-[#4D6BFE]/45'
            ]"
          />
        </div>

        <!-- Column 2: Momotalk Mail Stream -->
        <MailStream ref="streamRef" :style="{ width: `${streamWidth}px` }" />

        <!-- Resizer 2: MailStream <-> MailAtelier -->
        <div
          @mousedown="startResize('stream', $event)"
          @dblclick="resetWidth('stream')"
          class="w-2.5 z-30 cursor-col-resize group flex items-center justify-center select-none flex-shrink-0"
          title="拖动调整列表宽度（双击还原默认）"
        >
          <div
            :class="[
              'w-[3px] rounded-full transition-all duration-150',
              activeResizer === 'stream'
                ? 'h-24 bg-[#4D6BFE]'
                : 'h-10 bg-transparent group-hover:bg-[#4D6BFE]/45'
            ]"
          />
        </div>
      </template>

      <!-- Column 3: DeepSeek-tan Memorial Lobby Stage & <think> Mail Reader -->
      <MailAtelier ref="atelierRef" class="flex-1 min-w-[300px]" />
    </div>

    <!-- Modals & Overlays -->
    <CommandPalette />
    <ComposeSheet />
    <DomainSheet />
    <ExternalSheet />
    <ToastLayer />
  </div>
</template>
