import { createApp } from 'vue'
import { createPinia } from 'pinia'
import './style.css'
import App from './App.vue'

const origFetch = window.fetch.bind(window)
window.fetch = async (input, init = {}) => {
  const urlStr = typeof input === 'string' ? input : (input?.url || '')
  const isSameOriginApi =
    urlStr.startsWith('/api/') ||
    (typeof window !== 'undefined' && urlStr.startsWith(`${window.location.origin}/api/`))
  let nextInit = init
  if (isSameOriginApi) {
    const headers = new Headers(init?.headers || (typeof input !== 'string' ? input?.headers : undefined) || {})
    if (!headers.has('X-Requested-With')) {
      headers.set('X-Requested-With', 'PrismMail')
    }
    nextInit = { ...init, headers }
  }
  const res = await origFetch(input, nextInit)
  if (res.status === 401 && urlStr.includes('/api/') && !urlStr.includes('/api/auth/login')) {
    window.location.href = `/login?next=${encodeURIComponent(window.location.pathname + window.location.search)}`
  }
  return res
}

const app = createApp(App)
app.use(createPinia())
app.mount('#app')
