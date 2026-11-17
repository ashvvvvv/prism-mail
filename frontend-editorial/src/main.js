import { createApp } from 'vue'
import { createPinia } from 'pinia'
import './style.css'
import App from './App.vue'

const origFetch = window.fetch.bind(window)
window.fetch = async (input, init) => {
  const res = await origFetch(input, init)
  const urlStr = typeof input === 'string' ? input : (input?.url || '')
  if (res.status === 401 && urlStr.includes('/api/') && !urlStr.includes('/api/auth/login')) {
    window.location.href = `/login?next=${encodeURIComponent(window.location.pathname + window.location.search)}`
  }
  return res
}

const app = createApp(App)
app.use(createPinia())
app.mount('#app')
