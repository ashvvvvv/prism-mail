<script setup>
import { ref, onMounted, watch } from 'vue'
import DOMPurify from 'dompurify'

const props = defineProps({
  html: {
    type: String,
    default: ''
  }
})

const hostRef = ref(null)
let shadowRoot = null

const FORBID_TAGS = [
  'script', 'iframe', 'frame', 'frameset', 'object', 'embed', 'applet',
  'form', 'input', 'button', 'textarea', 'select', 'option', 'meta',
  'base', 'link', 'noscript', 'template', 'svg', 'math'
]
const FORBID_ATTR = ['srcdoc', 'formaction', 'xlink:href']
const SAFE_URI_RE = /^(?:https?:|mailto:|tel:|#)/i

const decodeAndStripCssComments = (rawCss) => {
  return String(rawCss || '')
    .replace(/\/\*[\s\S]*?(?:\*\/|$)/g, '')
    .replace(/\\(?:\r\n|[\r\n\f])/g, '')
    .replace(/\\([0-9a-fA-F]{1,6})(?:\r\n|[ \t\r\n\f])?/g, (_, hex) => {
      const cp = parseInt(hex, 16)
      if (
        Number.isNaN(cp) ||
        cp <= 0x1f ||
        cp === 0x7f ||
        cp > 0x10ffff ||
        (cp >= 0xd800 && cp <= 0xdfff)
      ) {
        return ' '
      }
      const ch = String.fromCodePoint(cp)
      if (ch === '"') return '\\000022 '
      if (ch === "'") return '\\000027 '
      if (ch === '\\') return '\\00005c '
      return ch
    })
    .replace(/\\([^\r\n\f0-9a-fA-F])/g, (_, ch) => {
      if (ch === '"') return '\\000022 '
      if (ch === "'") return '\\000027 '
      if (ch === '\\') return '\\00005c '
      return ch
    })
    .replace(/\\$/g, '')
}

const sanitizeCssText = (rawCss, isStylesheet = false) => {
  let css = decodeAndStripCssComments(rawCss)
  if (isStylesheet) {
    css = css
      .replace(/<!--|-->/g, '')
      .replace(/@(?:import|charset|namespace)\b[^;{}]*(?:;|$)/gi, '')
      .replace(/:host(?:-context)?\b/gi, ':not(*)')
  } else {
    css = css.replace(/@import\b[^;{}]*(?:;|$)/gi, '')
  }
  return css
    .replace(
      /url\s*\(\s*(?:\\00002[27]\s*|['"])?\s*(?:javascript|vbscript|data\s*:\s*text\/html)\b[^)]*\)/gi,
      'none'
    )
    .replace(/position\s*:\s*(?:fixed|sticky)\b/gi, 'position: static')
    .replace(/(?:expression\s*\(|javascript\s*:|vbscript\s*:|-moz-binding\s*:?|behavior\s*:)/gi, '')
}

const sanitizeEmailFragment = (rawHtml) => {
  const emptyFrag = document.createDocumentFragment()
  if (!rawHtml) return emptyFrag
  try {
    const clean = DOMPurify.sanitize(rawHtml, {
      FORBID_TAGS,
      FORBID_ATTR,
      ALLOW_UNKNOWN_PROTOCOLS: false,
      FORCE_BODY: true
    })
    const tpl = document.createElement('template')
    tpl.innerHTML = clean

    tpl.content.querySelectorAll('a, area').forEach((node) => {
      const href = (node.getAttribute('href') || '').trim()
      if (href && !SAFE_URI_RE.test(href)) {
        node.removeAttribute('href')
      } else if (href) {
        node.setAttribute('target', '_blank')
        node.setAttribute('rel', 'noopener noreferrer')
      } else {
        node.removeAttribute('href')
      }
    })

    tpl.content.querySelectorAll('[style]').forEach((node) => {
      const cleaned = sanitizeCssText(node.getAttribute('style') || '', false).trim()
      if (cleaned) {
        node.setAttribute('style', cleaned)
      } else {
        node.removeAttribute('style')
      }
    })

    tpl.content.querySelectorAll('style').forEach((styleNode) => {
      styleNode.textContent = sanitizeCssText(styleNode.textContent || '', true)
    })

    return tpl.content
  } catch {
    return emptyFrag
  }
}

const BASE_SHADOW_CSS = `
:host {
  display: block !important;
  contain: content !important;
  position: relative !important;
  overflow-x: auto !important;
  word-break: break-word !important;
}
img {
  max-width: 100%;
  height: auto;
}
table {
  max-width: 100% !important;
}
a {
  color: var(--accent-blue, var(--apple-blue, var(--accent-vermilion, #2563eb)));
  text-decoration: underline;
  text-underline-offset: 2px;
}
:host(.pm-mail-paper) a {
  color: #2563eb;
}
:host(.apple-mail-paper) a {
  color: #007aff;
}
:host(.ed-mail-paper) a {
  color: #C84B31;
}
pre {
  white-space: pre-wrap;
  overflow-x: auto;
}
`

const renderShadow = () => {
  if (!hostRef.value) return
  if (!shadowRoot) {
    shadowRoot = hostRef.value.attachShadow({ mode: 'open' })
  }
  const bodyWrap = document.createElement('div')
  bodyWrap.className = 'pm-shadow-body'
  bodyWrap.appendChild(sanitizeEmailFragment(props.html))

  const baseStyle = document.createElement('style')
  baseStyle.textContent = BASE_SHADOW_CSS

  shadowRoot.replaceChildren(bodyWrap, baseStyle)
}

onMounted(renderShadow)
watch(() => props.html, renderShadow)
</script>

<template>
  <div ref="hostRef" />
</template>
