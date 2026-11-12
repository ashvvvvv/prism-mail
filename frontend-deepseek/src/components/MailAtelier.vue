<script setup>
import { ref, computed, watch } from 'vue'
import { useMailStore } from '../stores/mail'
import {
  Reply, ZoomIn, ZoomOut, Star, Trash2, FileText,
  Download, Copy, Check, Sun, Moon, ChevronDown,
  Sparkles, RotateCw, MailPlus, Search, MailOpen,
  Maximize2, Minimize2, Image as ImageIcon
} from 'lucide-vue-next'

const store = useMailStore()

const heroDayUrl = `${import.meta.env.BASE_URL}deepseek-hero-day.jpg`
const heroNightUrl = `${import.meta.env.BASE_URL}deepseek-hero-night.jpg`
const portraitLetterUrl = `${import.meta.env.BASE_URL}deepseek-portrait-letter.jpg`
const chibiThinkUrl = `${import.meta.env.BASE_URL}deepseek-chibi-think.png`
const chibiHugUrl = `${import.meta.env.BASE_URL}deepseek-chibi-hug.png`

const zoom = ref(1)
const copiedCode = ref(false)
const htmlPaperMode = ref(true)
const thinkExpanded = ref(true)
const vnLineIdx = ref(0)
const stageSparklePop = ref(false)
let sparkleTimer = null

const DAY_LINES = [
  '欢迎回到棱镜邮局呀！海底阳光正好，怀里的大肥鱼也软乎乎的，随时准备潜入深海帮你捞取最新信件哦~ ☀️🐋',
  '看见桌角那封金鲸火漆信了吗？不管是自定义域名还是 Gmail / QQ 邮箱，本女仆都能帮你打理得井井有条 ✨',
  '趴在圆滚滚的蓝色大肥鱼背上处理邮件，效率会提升 200% 哦！要不要按 C 写封信试试看？💙',
  '收到包含验证码的信件时，我会立刻戴上小眼镜开启 R1 深度思考，把验证码叼到最显眼的位置等你复制哒！👓🫧'
]

const NIGHT_LINES = [
  '夜深啦…窗外的荧光水母都游过来陪我们值班了呢。先喝口热红茶暖暖身子，剩下的信件交给我吧 🌙🍵',
  '嘘——怀里的大肥鱼已经睡得冒鼻涕泡啦 🫧 但我的 R1 夜间声呐还在全速运转，一有验证码就会轻声提醒你哦~',
  '深海的夜晚很安静吧？点一下右上角「全景大厅」，可以让整个屏幕变成我们的海底玻璃书房哦 ✨',
  '熬夜处理邮件辛苦啦！等忙完手头这一封，要不要一起去厨房偷吃三碗热腾腾的大白米饭？🍚💙'
]

const PORTRAIT_LINES = [
  '海风好舒服呀——给！这是刚刚大肥鱼从远洋航道为你护送回来的金鲸火漆专递，请查收！✉️🐋',
  '按一下键盘上的 C 键打开写信台，我也会在信纸旁边陪你一起封存每一封重要来信哦~ ✨',
  '头箍差点被海风吹跑啦！不过放心，你的每一封邮件和验证码都被我牢牢守护着呢 💙'
]

const activeVnLines = computed(() => {
  if (store.stageArtMode === 'portrait') return PORTRAIT_LINES
  return store.theme === 'abyss-dark' ? NIGHT_LINES : DAY_LINES
})

const currentVnLine = computed(() => {
  const list = activeVnLines.value
  return list[vnLineIdx.value % list.length]
})

const nextVnLine = () => {
  vnLineIdx.value = (vnLineIdx.value + 1) % activeVnLines.value.length
  stageSparklePop.value = false
  requestAnimationFrame(() => {
    stageSparklePop.value = true
  })
  clearTimeout(sparkleTimer)
  sparkleTimer = setTimeout(() => {
    stageSparklePop.value = false
  }, 620)
}

watch(
  () => [store.theme, store.stageArtMode],
  () => {
    vnLineIdx.value = 0
  }
)

watch(
  () => store.selectedMailDetail?.id,
  () => {
    thinkExpanded.value = true
    copiedCode.value = false
  }
)

const zoomIn = () => {
  if (zoom.value < 1.4) zoom.value = Math.round((zoom.value + 0.1) * 10) / 10
}

const zoomOut = () => {
  if (zoom.value > 0.8) zoom.value = Math.round((zoom.value - 0.1) * 10) / 10
}

const toggleStar = () => {
  if (store.selectedMailDetail) {
    store.updateMailStatus(store.selectedMailDetail.id, {
      is_starred: !store.selectedMailDetail.is_starred
    })
  }
}

const handleDelete = () => {
  if (store.selectedMailDetail) {
    store.deleteMail(store.selectedMailDetail.id)
  }
}

const parseSender = (raw) => {
  if (!raw) return { name: '神秘发件人', email: '' }
  const match = raw.match(/^([^<]+)<([^>]+)>$/)
  if (match) {
    return {
      name: match[1].trim().replace(/^["']|["']$/g, '') || match[2].trim(),
      email: match[2].trim()
    }
  }
  return { name: raw.trim(), email: raw.trim() }
}

const senderInfo = computed(() => parseSender(store.selectedMailDetail?.sender))

const stripHtmlText = (html) => {
  if (!html) return ''
  return html.replace(/<style[\s\S]*?<\/style>/gi, ' ').replace(/<[^>]+>/g, ' ')
}

const extractedCode = computed(() => {
  const detail = store.selectedMailDetail
  if (!detail) return null
  const text = `${detail.subject || ''} ${detail.body_text || ''} ${stripHtmlText(detail.body_html)}`
  const kwMatch = text.match(/(?:验证码|校验码|动态码|确认码|安全码|代码|code|verification|passcode|otp|pin)[^0-9A-Za-z]{0,24}\b([0-9]{4,8})\b/i)
  if (kwMatch) return kwMatch[1]
  const subjMatch = (detail.subject || '').match(/\b([0-9]{6})\b/)
  if (subjMatch) return subjMatch[1]
  return null
})

const copyCode = async (code) => {
  try {
    await navigator.clipboard.writeText(code)
    copiedCode.value = true
    store.notify(`鲸鱼娘已叼来验证码 ${code}，快去粘贴吧 ✨`, 'success')
    setTimeout(() => {
      copiedCode.value = false
    }, 2000)
  } catch {}
}

const copyAddress = async (addr) => {
  if (!addr) return
  try {
    await navigator.clipboard.writeText(addr)
    store.notify(`已复制邮箱地址 ${addr} 🫧`)
  } catch {}
}

const handleReply = () => {
  const detail = store.selectedMailDetail
  if (!detail) return
  const replyTo = senderInfo.value.email
  const subj = detail.subject && detail.subject.toLowerCase().startsWith('re:')
    ? detail.subject
    : `Re: ${detail.subject || ''}`
  store.openCompose({
    mailboxId: detail.mailbox_id,
    recipient: replyTo,
    subject: subj,
    body: ''
  })
}

const formatFullDate = (iso) => {
  if (!iso) return ''
  return new Date(iso).toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false
  })
}

defineExpose({
  triggerReply: handleReply
})
</script>

<template>
  <main class="flex-1 ds-card bg-[var(--bg-reader)] flex flex-col overflow-hidden relative">
    <!-- =====================================================================
         MODE A: Active Email Reader + DeepSeek Iconic <think> OTP Block
         ===================================================================== -->
    <div v-if="store.selectedMailDetail && !store.showMascotStage" class="h-full flex flex-col">
      <!-- Sticky ACG Reader Toolbar -->
      <header class="h-12 px-5 border-b border-[var(--border-hairline)] flex items-center justify-between gap-3 flex-shrink-0">
        <div class="flex items-center gap-1.5 flex-wrap">
          <button
            @click="handleReply"
            class="h-8 px-3 rounded-xl bg-[#4D6BFE]/12 hover:bg-[#4D6BFE] text-[#4D6BFE] dark:text-[#7DD3FC] hover:text-white border border-[#4D6BFE]/25 text-[12px] font-bold flex items-center gap-1.5 ds-spring"
          >
            <Reply class="w-3.5 h-3.5" />
            <span>回复</span>
            <kbd class="text-[10px] font-mono opacity-75 ml-0.5">R</kbd>
          </button>

          <button
            @click="toggleStar"
            :class="[
              'h-8 w-8 rounded-xl flex items-center justify-center border transition ds-spring',
              store.selectedMailDetail.is_starred
                ? 'bg-amber-400/15 border-amber-400/35 text-[var(--accent-amber)]'
                : 'bg-[var(--bg-subtle)] border-[var(--border-hairline)] text-[var(--text-muted)] hover:text-[var(--accent-amber)]'
            ]"
            title="星标信件"
          >
            <Star class="w-3.5 h-3.5" :fill="store.selectedMailDetail.is_starred ? 'currentColor' : 'none'" />
          </button>

          <button
            @click="handleDelete"
            class="h-8 w-8 rounded-xl bg-[var(--bg-subtle)] border border-[var(--border-hairline)] flex items-center justify-center text-[var(--text-muted)] hover:text-[var(--accent-rose)] hover:border-rose-400/35 ds-spring"
            title="移至废纸篓"
          >
            <Trash2 class="w-3.5 h-3.5" />
          </button>

          <!-- Summon Memorial Lobby Anytime Button -->
          <button
            @click="store.summonMascot()"
            class="h-8 px-3 rounded-xl bg-gradient-to-r from-[#4D6BFE]/12 to-[#38BDF8]/16 hover:from-[#4D6BFE]/22 hover:to-[#38BDF8]/28 border border-[var(--border-strong)] text-[12px] font-bold text-[var(--text-primary)] flex items-center gap-1.5 ds-spring ml-1"
            title="返回记忆大厅欣赏 DeepSeek 鲸鱼娘"
          >
            <img :src="chibiHugUrl" alt="" class="w-4 h-4 object-contain" />
            <span>记忆大厅</span>
          </button>
        </div>

        <div class="flex items-center gap-2 text-[var(--text-muted)] flex-shrink-0">
          <!-- HTML Paper vs Abyss Adaptive Toggle -->
          <button
            v-if="store.selectedMailDetail.body_html && store.theme === 'abyss-dark'"
            @click="htmlPaperMode = !htmlPaperMode"
            class="h-8 px-2.5 rounded-xl bg-[var(--bg-subtle)] hover:bg-[var(--bg-hover)] border border-[var(--border-hairline)] text-[11px] font-bold flex items-center gap-1.5 transition text-[var(--text-secondary)]"
            title="切换 HTML 信纸背景模式"
          >
            <Sun v-if="htmlPaperMode" class="w-3.5 h-3.5 text-amber-400" />
            <Moon v-else class="w-3.5 h-3.5 text-[#38BDF8]" />
            <span>{{ htmlPaperMode ? '纯白信纸' : '深海暗底' }}</span>
          </button>

          <div class="flex items-center h-8 bg-[var(--bg-subtle)] rounded-xl border border-[var(--border-hairline)] px-1">
            <button @click="zoomOut" class="p-1 hover:text-[#4D6BFE] transition" title="缩小正文">
              <ZoomOut class="w-3.5 h-3.5" />
            </button>
            <span class="px-1.5 text-[11px] font-mono font-bold tabular-nums text-[var(--text-secondary)]">
              {{ Math.round(zoom * 100) }}%
            </span>
            <button @click="zoomIn" class="p-1 hover:text-[#4D6BFE] transition" title="放大正文">
              <ZoomIn class="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      </header>

      <!-- Scrollable Reading Canvas -->
      <div class="flex-1 overflow-y-auto px-6 md:px-9 py-6">
        <div class="max-w-3xl mx-auto space-y-5">
          <!-- ===============================================================
               DeepSeek Iconic <think> Reasoning Card + Chibi Glasses Whale!
               =============================================================== -->
          <div v-if="extractedCode" class="ds-think-card p-4 space-y-3 relative overflow-hidden">
            <!-- Collapsible <think> Header -->
            <button
              type="button"
              @click="thinkExpanded = !thinkExpanded"
              class="w-full flex items-center justify-between gap-2 text-left group"
            >
              <div class="flex items-center gap-2 min-w-0">
                <span class="px-2 py-0.5 rounded-md bg-[#4D6BFE] text-white text-[10px] font-mono font-bold tracking-wider uppercase flex-shrink-0">
                  &lt;think&gt;
                </span>
                <span class="text-[12.5px] font-extrabold text-[#4D6BFE] dark:text-[#7DD3FC] truncate">
                  👓 已深度思考（用时 0.02 秒）· 鲸鱼娘已为你叼来验证码
                </span>
              </div>
              <ChevronDown
                :class="[
                  'w-4 h-4 text-[#4D6BFE] transition-transform duration-200 flex-shrink-0',
                  thinkExpanded ? 'rotate-180' : ''
                ]"
              />
            </button>

            <!-- Collapsible Monologue Quote -->
            <div
              v-if="thinkExpanded"
              class="pl-3 border-l-[3px] border-[#4D6BFE]/40 text-[12px] text-[var(--text-secondary)] leading-relaxed italic"
            >
              “推一下小眼镜…排除邮件里的日期与干扰数字，锁定核心动态验证码为
              <span class="font-mono font-bold not-italic text-[#4D6BFE] dark:text-[#7DD3FC]">{{ extractedCode }}</span>，大肥鱼已经叼在嘴里啦！”
            </div>

            <!-- Crystal-Blue #4D6BFE OTP Capsule + Chibi Think Sticker + 1-Click Copy -->
            <div class="pt-0.5 flex items-center justify-between gap-3 flex-wrap p-3 rounded-2xl bg-[var(--bg-elevated)] border border-[#4D6BFE]/25 shadow-sm">
              <div class="flex items-center gap-3.5">
                <img
                  :src="chibiThinkUrl"
                  alt="R1 深度思考叼信"
                  class="w-14 h-14 object-contain ds-chibi-sticker animate-whale-bob flex-shrink-0 select-none pointer-events-none"
                  draggable="false"
                />
                <div>
                  <span class="text-[10.5px] font-bold text-[var(--text-muted)] block">核心动态验证码 · R1 精准提取</span>
                  <span class="text-[22px] font-mono font-extrabold tracking-[0.26em] text-[#4D6BFE] dark:text-[#7DD3FC] tabular-nums select-all">
                    {{ extractedCode }}
                  </span>
                </div>
              </div>

              <button
                type="button"
                @click="copyCode(extractedCode)"
                class="ds-btn-primary px-4 py-2.5 rounded-xl text-[12.5px] font-bold flex items-center gap-1.5"
              >
                <Check v-if="copiedCode" class="w-4 h-4" />
                <Copy v-else class="w-4 h-4" />
                <span>{{ copiedCode ? '已复制验证码' : '复制验证码' }}</span>
              </button>
            </div>
          </div>

          <!-- Subject & Sender Header -->
          <div class="space-y-4 pb-5 border-b border-[var(--border-hairline)]">
            <h1 class="text-[19px] md:text-[21px] font-extrabold tracking-[-0.015em] text-[var(--text-primary)] leading-snug">
              {{ store.selectedMailDetail.subject || '(无主题信件)' }}
            </h1>

            <div class="flex items-center justify-between gap-4 flex-wrap">
              <div class="flex items-center gap-3 min-w-0">
                <div class="w-10 h-10 rounded-2xl bg-gradient-to-br from-[#4D6BFE]/16 to-[#38BDF8]/22 border border-[#4D6BFE]/30 flex items-center justify-center text-[14px] font-extrabold text-[#4D6BFE] dark:text-[#7DD3FC] flex-shrink-0">
                  {{ senderInfo.name.charAt(0).toUpperCase() }}
                </div>
                <div class="min-w-0 space-y-0.5">
                  <div class="flex items-center gap-2 text-[13px] truncate">
                    <span class="font-extrabold text-[var(--text-primary)]">{{ senderInfo.name }}</span>
                    <button
                      v-if="senderInfo.email && senderInfo.email !== senderInfo.name"
                      @click="copyAddress(senderInfo.email)"
                      class="px-2 py-0.5 rounded-md bg-[var(--bg-subtle)] hover:bg-[var(--bg-hover)] text-[11px] font-mono text-[var(--text-secondary)] truncate transition"
                      title="点击复制发件人邮箱"
                    >
                      {{ senderInfo.email }}
                    </button>
                  </div>
                  <div class="flex items-center gap-1.5 text-[11.5px] text-[var(--text-muted)] font-mono truncate">
                    <span>投递至</span>
                    <button
                      @click="copyAddress(store.selectedMailDetail.recipient)"
                      class="text-[#4D6BFE] dark:text-[#7DD3FC] font-semibold hover:underline transition"
                      title="点击复制收件邮箱"
                    >
                      {{ store.selectedMailDetail.recipient }}
                    </button>
                  </div>
                </div>
              </div>

              <time class="px-2.5 py-1 rounded-full bg-[var(--bg-subtle)] border border-[var(--border-hairline)] text-[11px] font-mono font-semibold tabular-nums text-[var(--text-muted)] flex-shrink-0">
                {{ formatFullDate(store.selectedMailDetail.created_at) }}
              </time>
            </div>
          </div>

          <!-- Mail Body -->
          <div
            class="transition-transform origin-top"
            :style="{ transform: `scale(${zoom})` }"
          >
            <div
              v-if="store.selectedMailDetail.body_html"
              v-html="store.selectedMailDetail.body_html"
              :class="[
                'text-[14px] leading-relaxed',
                htmlPaperMode || store.theme === 'ocean-light' ? 'ds-mail-paper' : 'ds-mail-adaptive'
              ]"
            />
            <div
              v-else
              class="ds-mail-adaptive text-[var(--text-primary)] text-[14px] whitespace-pre-wrap leading-[1.8] font-sans"
            >{{ store.selectedMailDetail.body_text }}</div>

            <!-- Attachments -->
            <div
              v-if="store.selectedMailDetail.has_attachments && store.selectedMailDetail.attachments?.length"
              class="mt-8 pt-6 border-t border-[var(--border-hairline)]"
            >
              <h4 class="text-[12px] font-extrabold text-[var(--text-secondary)] mb-3 flex items-center gap-1.5">
                <span>📎 随信附件 · {{ store.selectedMailDetail.attachments.length }}</span>
              </h4>
              <div class="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                <div
                  v-for="att in store.selectedMailDetail.attachments"
                  :key="att.name"
                  class="p-3 rounded-2xl bg-[var(--bg-subtle)] hover:bg-[var(--bg-hover)] border border-[var(--border-hairline)] flex items-center justify-between transition cursor-pointer"
                >
                  <div class="flex items-center gap-2.5 truncate">
                    <FileText class="w-4 h-4 text-[#4D6BFE] flex-shrink-0" />
                    <div class="truncate">
                      <p class="text-[12.5px] font-bold text-[var(--text-primary)] truncate">{{ att.name }}</p>
                      <p class="text-[10.5px] font-mono text-[var(--text-muted)]">{{ att.size }}</p>
                    </div>
                  </div>
                  <Download class="w-4 h-4 text-[#4D6BFE]" />
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- =====================================================================
         MODE B: Blue Archive Memorial Lobby Dual-CG Stage (Day <-> Night + Portrait)
         ===================================================================== -->
    <div v-else class="h-full w-full relative overflow-hidden select-none flex flex-col justify-between">
      <!-- Layer 1: Ambient Blurred Dual-CG Background Fill (Never leaves awkward blank margins) -->
      <div class="absolute inset-0 overflow-hidden pointer-events-none z-0">
        <img
          :src="store.stageArtMode === 'portrait' ? portraitLetterUrl : heroDayUrl"
          alt=""
          :class="[
            'absolute inset-0 w-full h-full object-cover scale-110 blur-2xl transition-opacity duration-700',
            store.stageArtMode === 'portrait' || store.theme === 'ocean-light' ? 'opacity-45' : 'opacity-0'
          ]"
        />
        <img
          :src="heroNightUrl"
          alt=""
          :class="[
            'absolute inset-0 w-full h-full object-cover scale-110 blur-2xl transition-opacity duration-700',
            store.stageArtMode === 'cg' && store.theme === 'abyss-dark' ? 'opacity-55' : 'opacity-0'
          ]"
        />
        <!-- Soft vignette overlay for crystal readability -->
        <div
          :class="[
            'absolute inset-0 transition-colors duration-700',
            store.lobbyFullScreen
              ? 'bg-gradient-to-t from-[#081126]/65 via-transparent to-[#081126]/20'
              : store.theme === 'ocean-light'
                ? 'bg-gradient-to-b from-white/45 via-white/20 to-[#E8F3FF]/75'
                : 'bg-gradient-to-b from-[#091226]/45 via-[#091226]/25 to-[#081022]/82'
          ]"
        />
      </div>

      <!-- Full-Screen Edge-to-Edge Artwork when in Panoramic Lobby Mode -->
      <div
        v-if="store.lobbyFullScreen"
        @click="nextVnLine"
        class="absolute inset-0 z-[1] cursor-pointer overflow-hidden flex items-center justify-center"
        title="点击看板娘互动切换台词"
      >
        <template v-if="store.stageArtMode === 'cg'">
          <img
            :src="heroDayUrl"
            alt="晴海阳光海底温室记忆大厅"
            :class="[
              'absolute inset-0 w-full h-full object-cover object-center animate-lobby-breathe transition-opacity duration-700',
              store.theme === 'ocean-light' ? 'opacity-100' : 'opacity-0'
            ]"
            draggable="false"
          />
          <img
            :src="heroNightUrl"
            alt="深海星夜荧光水母记忆大厅"
            :class="[
              'absolute inset-0 w-full h-full object-cover object-center animate-lobby-breathe transition-opacity duration-700',
              store.theme === 'abyss-dark' ? 'opacity-100' : 'opacity-0'
            ]"
            draggable="false"
          />
        </template>
        <img
          v-else
          :src="portraitLetterUrl"
          alt="海风递送金鲸火漆信立绘"
          class="h-full max-h-full w-auto object-contain animate-lobby-breathe drop-shadow-2xl"
          draggable="false"
        />
        <div class="absolute inset-x-0 bottom-0 h-52 bg-gradient-to-t from-[#071024]/80 via-[#071024]/30 to-transparent pointer-events-none" />
      </div>

      <!-- Top Floating Memorial Lobby Control Strip -->
      <div class="relative z-20 px-4 sm:px-6 pt-4 flex items-center justify-between gap-2 flex-wrap">
        <!-- Left Status Pill -->
        <div class="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-[var(--bg-elevated)]/88 backdrop-blur-xl border border-[var(--border-strong)] shadow-sm text-[11px] font-mono font-bold text-[#4D6BFE] dark:text-[#7DD3FC]">
          <Sparkles class="w-3.5 h-3.5 text-[#D4AF6A]" />
          <span>{{ store.theme === 'ocean-light' ? 'SUNLIT CONSERVATORY // 晴海记忆大厅' : 'BIOLUMINESCENT ABYSS // 深海星夜大厅' }}</span>
          <span class="opacity-40">·</span>
          <span>{{ store.folderCounts.inbox || 0 }} UNREAD</span>
        </div>

        <!-- Right Gallery & Day/Night Switcher Pills -->
        <div class="flex items-center gap-1.5">
          <!-- Switch CG vs Letter Portrait -->
          <div class="inline-flex p-0.5 rounded-full bg-[var(--bg-elevated)]/88 backdrop-blur-xl border border-[var(--border-strong)] shadow-sm text-[11px]">
            <button
              @click="store.stageArtMode = 'cg'"
              :class="[
                'px-2.5 py-1 rounded-full font-bold transition flex items-center gap-1',
                store.stageArtMode === 'cg'
                  ? 'bg-[#4D6BFE] text-white shadow-sm'
                  : 'text-[var(--text-secondary)] hover:text-[var(--text-primary)]'
              ]"
            >
              <ImageIcon class="w-3 h-3" />
              <span>记忆大厅 CG</span>
            </button>
            <button
              @click="store.stageArtMode = 'portrait'"
              :class="[
                'px-2.5 py-1 rounded-full font-bold transition flex items-center gap-1',
                store.stageArtMode === 'portrait'
                  ? 'bg-[#4D6BFE] text-white shadow-sm'
                  : 'text-[var(--text-secondary)] hover:text-[var(--text-primary)]'
              ]"
            >
              <span>✉️ 海风递信</span>
            </button>
          </div>

          <!-- Instant Day/Night CG Switch on Stage -->
          <button
            v-if="store.stageArtMode === 'cg'"
            @click="store.toggleTheme()"
            class="h-7 px-2.5 rounded-full bg-[var(--bg-elevated)]/88 backdrop-blur-xl hover:bg-[var(--bg-elevated)] border border-[var(--border-strong)] shadow-sm text-[11px] font-bold text-[var(--text-primary)] flex items-center gap-1 ds-spring"
            title="一键切换晴海阳光 / 深海荧光水母 CG"
          >
            <Sun v-if="store.theme === 'ocean-light'" class="w-3 h-3 text-amber-500" />
            <Moon v-else class="w-3 h-3 text-[#38BDF8]" />
            <span>{{ store.theme === 'ocean-light' ? '切至深海夜景' : '切至晴海午后' }}</span>
          </button>

          <!-- Fullscreen Lobby Expand / Collapse -->
          <button
            @click="store.toggleLobbyFullScreen()"
            class="h-7 px-2.5 rounded-full bg-[var(--bg-elevated)]/88 backdrop-blur-xl hover:bg-[#4D6BFE] hover:text-white border border-[var(--border-strong)] shadow-sm text-[11px] font-bold text-[var(--text-primary)] flex items-center gap-1 ds-spring"
            :title="store.lobbyFullScreen ? '退出全景大厅 (ESC)' : '展开全屏沉浸式记忆大厅'"
          >
            <Minimize2 v-if="store.lobbyFullScreen" class="w-3 h-3" />
            <Maximize2 v-else class="w-3 h-3" />
            <span>{{ store.lobbyFullScreen ? '退出全景' : '全景展开' }}</span>
          </button>
        </div>
      </div>

      <!-- Center Uncropped Masterpiece Frame (in 3-Column Mode so 100% of 16:9 / 3:4 art is visible!) -->
      <div
        v-if="!store.lobbyFullScreen"
        class="relative z-10 flex-1 min-h-0 px-4 sm:px-6 py-3 flex items-center justify-center overflow-hidden"
      >
        <!-- 16:9 Dual-CG Framed Window -->
        <div
          v-if="store.stageArtMode === 'cg'"
          @click="nextVnLine"
          class="relative w-full max-w-[780px] aspect-video max-h-full rounded-[24px] overflow-hidden cursor-pointer group border-[1.5px] border-white/75 dark:border-[#60A5FA]/35 shadow-[0_22px_54px_-12px_rgba(30,64,175,0.28)] dark:shadow-[0_24px_60px_-12px_rgba(2,6,23,0.85)]"
          title="点击画面与 DeepSeek 鲸鱼娘互动"
        >
          <img
            :src="heroDayUrl"
            alt="DeepSeek娘 · 晴海阳光海底温室记忆大厅"
            :class="[
              'absolute inset-0 w-full h-full object-cover animate-lobby-breathe transition-opacity duration-700',
              store.theme === 'ocean-light' ? 'opacity-100' : 'opacity-0'
            ]"
            draggable="false"
          />
          <img
            :src="heroNightUrl"
            alt="DeepSeek娘 · 深海星夜荧光水母记忆大厅"
            :class="[
              'absolute inset-0 w-full h-full object-cover animate-lobby-breathe transition-opacity duration-700',
              store.theme === 'abyss-dark' ? 'opacity-100' : 'opacity-0'
            ]"
            draggable="false"
          />

          <!-- Subtle Interactive Heart/Bubble Pop on Click -->
          <Transition name="fade-scale">
            <div
              v-if="stageSparklePop"
              class="absolute top-3.5 right-3.5 px-3 py-1 rounded-full bg-[#4D6BFE]/90 backdrop-blur-md text-white text-[11.5px] font-extrabold shadow-lg flex items-center gap-1"
            >
              <span>💙 噗噜~ 好感度 +1</span>
            </div>
          </Transition>
        </div>

        <!-- 3:4 Sea-Breeze Gold-Whale Letter Portrait Showcase -->
        <div
          v-else
          @click="nextVnLine"
          class="relative h-full max-h-[460px] aspect-[3/4] rounded-[24px] overflow-hidden cursor-pointer group border-[1.5px] border-white/80 dark:border-[#60A5FA]/35 shadow-[0_22px_54px_-12px_rgba(30,64,175,0.30)]"
          title="点击画面与 DeepSeek 鲸鱼娘互动"
        >
          <img
            :src="portraitLetterUrl"
            alt="DeepSeek娘 · 海风递送金鲸火漆信"
            class="w-full h-full object-cover animate-lobby-breathe"
            draggable="false"
          />
          <Transition name="fade-scale">
            <div
              v-if="stageSparklePop"
              class="absolute top-3 right-3 px-2.5 py-1 rounded-full bg-[#4D6BFE]/90 text-white text-[11px] font-extrabold shadow-lg"
            >
              <span>✉️ 专递送达!</span>
            </div>
          </Transition>
        </div>
      </div>

      <!-- Bottom Visual-Novel / Momotalk Translucent Glass Dialogue Dock -->
      <div class="relative z-20 px-4 sm:px-6 pb-4 pt-1 flex flex-col items-center">
        <div class="w-full max-w-2xl space-y-2.5">
          <!-- VN Dialogue Card -->
          <div
            @click="nextVnLine"
            class="w-full rounded-[22px] px-4 py-3.5 bg-[var(--bg-elevated)]/90 backdrop-blur-2xl border-[1.5px] border-[var(--border-strong)] shadow-xl cursor-pointer hover:border-[#4D6BFE]/65 transition relative"
          >
            <div class="flex items-center justify-between gap-2 mb-1.5">
              <div class="inline-flex items-center gap-2">
                <span class="px-2.5 py-0.5 rounded-full bg-gradient-to-r from-[#4D6BFE] to-[#38BDF8] text-white text-[11px] font-extrabold shadow-sm flex items-center gap-1">
                  <span>★ DeepSeek娘 · 皇家蓝鲸女仆</span>
                </span>
                <span class="text-[10.5px] font-mono font-semibold text-[var(--text-muted)]">
                  {{ store.stageArtMode === 'portrait' ? '海风专递形态' : store.theme === 'ocean-light' ? '晴海午后形态' : '深海夜读形态' }}
                </span>
              </div>
              <span class="text-[10.5px] font-bold text-[#4D6BFE] dark:text-[#7DD3FC] animate-pulse">
                点击继续对话 ▾
              </span>
            </div>

            <Transition name="quote-pop" mode="out-in">
              <p
                :key="`${store.theme}_${store.stageArtMode}_${vnLineIdx}`"
                class="text-[13px] leading-[1.65] font-semibold text-[var(--text-primary)]"
              >
                {{ currentVnLine }}
              </p>
            </Transition>
          </div>

          <!-- Quick Action Capsule Row -->
          <div class="flex items-center justify-center gap-2 flex-wrap">
            <button
              v-if="store.selectedMailDetail"
              @click="store.lobbyFullScreen = false; store.showMascotStage = false"
              class="h-8 px-3.5 rounded-full bg-[var(--bg-elevated)]/92 backdrop-blur-xl hover:bg-[#4D6BFE] text-[#4D6BFE] dark:text-[#7DD3FC] hover:text-white border border-[#4D6BFE]/40 text-[12px] font-bold flex items-center gap-1.5 ds-spring shadow-sm"
            >
              <MailOpen class="w-3.5 h-3.5" />
              <span>返回刚看的信件</span>
            </button>

            <button
              @click="store.openCompose()"
              class="ds-btn-primary h-8 px-4 rounded-full text-[12px] font-bold flex items-center gap-1.5"
            >
              <Sparkles class="w-3.5 h-3.5" />
              <span>撰写新信件</span>
              <kbd class="px-1.5 py-[1px] rounded bg-white/20 text-[10px] font-mono">C</kbd>
            </button>

            <button
              @click="store.fetchMails(true)"
              :disabled="store.isLoadingMails"
              class="h-8 px-3.5 rounded-full bg-[var(--bg-elevated)]/90 backdrop-blur-xl hover:bg-[var(--bg-hover)] border border-[var(--border-strong)] text-[12px] font-bold text-[var(--text-primary)] flex items-center gap-1.5 ds-spring shadow-sm"
            >
              <RotateCw :class="['w-3.5 h-3.5 text-[#4D6BFE]', { 'animate-spin': store.isLoadingMails }]" />
              <span>{{ store.isLoadingMails ? '潜航捞信中...' : '潜航捞信' }}</span>
            </button>

            <button
              @click="store.openExternalModal()"
              class="h-8 px-3.5 rounded-full bg-[var(--bg-elevated)]/90 backdrop-blur-xl hover:bg-[var(--bg-hover)] border border-[var(--border-hairline)] text-[12px] font-bold text-[var(--text-secondary)] hover:text-[var(--text-primary)] flex items-center gap-1.5 ds-spring shadow-sm"
            >
              <MailPlus class="w-3.5 h-3.5 text-[#38BDF8]" />
              <span>接入外部邮箱</span>
            </button>

            <button
              @click="store.isCommandOpen = true"
              class="h-8 px-3.5 rounded-full bg-[var(--bg-elevated)]/90 backdrop-blur-xl hover:bg-[var(--bg-hover)] border border-[var(--border-hairline)] text-[12px] font-bold text-[var(--text-secondary)] hover:text-[var(--text-primary)] flex items-center gap-1.5 ds-spring shadow-sm"
            >
              <Search class="w-3.5 h-3.5 text-[#4D6BFE]" />
              <span>指令面板</span>
              <kbd class="ds-kbd">⌘K</kbd>
            </button>
          </div>
        </div>
      </div>
    </div>
  </main>
</template>
