import { defineStore } from 'pinia'
import { ref, watch } from 'vue'

export type Theme = 'light' | 'dark'

const STORAGE_KEY = 'aics_theme'

export const useThemeStore = defineStore('theme', () => {
  const initial: Theme = (localStorage.getItem(STORAGE_KEY) as Theme) || 'light'
  const theme = ref<Theme>(initial)

  const apply = (t: Theme) => {
    document.documentElement.setAttribute('data-theme', t)
  }

  apply(theme.value)

  watch(theme, (t) => {
    localStorage.setItem(STORAGE_KEY, t)
    apply(t)
  })

  const toggle = () => {
    theme.value = theme.value === 'light' ? 'dark' : 'light'
  }

  const setTheme = (t: Theme) => {
    theme.value = t
  }

  return { theme, toggle, setTheme }
})
