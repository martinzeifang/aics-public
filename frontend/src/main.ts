import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'
import { i18n, getLocale } from './i18n'
import apiClient from './api/client'
import { install401Interceptor } from './api/install-401-interceptor'
import { usePortalStore } from './stores/portal'
import './styles/globals.css'

document.documentElement.setAttribute('lang', getLocale())

const app = createApp(App)

app.use(createPinia())  // Store-Setup vor Interceptor — sonst useAuthStore() crasht
app.use(router)
app.use(i18n)

// #414: global 401 → logout + router.push('/login') (kein hard reload)
install401Interceptor(router, apiClient)

// #1410: Portal-Modus (SOC-Portal) vor dem Mount laden, damit Router-Guards +
// AppLayout das Gating synchron kennen. Best-effort — blockiert den Start nicht hart.
const portalStore = usePortalStore()
portalStore.load().finally(() => {
  if (portalStore.isSoc) document.title = portalStore.portalName  // #1414: Tab-Titel
  app.mount('#app')
})
