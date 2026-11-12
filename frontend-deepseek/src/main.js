import { createApp } from 'vue'
import { createPinia } from 'pinia'
import './style.css'
import App from './App.vue'

// Auto-redirect to /login if session cookie expires during active use
const rawFetch = window.fetch.bind(window)
window.fetch = async (...args) => {
  const res = await rawFetch(...args)
  if (res.status === 401 && !window.location.pathname.startsWith('/login')) {
    const next = encodeURIComponent(window.location.pathname + window.location.search)
    window.location.href = `/login?next=${next}`
  }
  return res
}

const app = createApp(App)
app.use(createPinia())
app.mount('#app')
