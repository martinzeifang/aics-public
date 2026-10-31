import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'
import { i18n, getLocale } from './i18n'
import apiClient from './api/client'
import { install401Interceptor } from './api/install-401-interceptor'
import './styles/globals.css'

document.documentElement.setAttribute('lang', getLocale())

const app = createApp(App)

app.use(createPinia())  // Store-Setup vor Interceptor — sonst useAuthStore() crasht
app.use(router)
app.use(i18n)

// #414: global 401 → logout + router.push('/login') (kein hard reload)
install401Interceptor(router, apiClient)

app.mount('#app')
