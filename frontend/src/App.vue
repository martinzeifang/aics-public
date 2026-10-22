<template>
  <AppLayout v-if="showLayout" />
  <router-view v-else />
</template>

<script setup lang="ts">
import { onMounted, computed } from 'vue'
import { useRoute } from 'vue-router'
import { useAuthStore } from './stores/auth'
import AppLayout from './components/AppLayout.vue'

const authStore = useAuthStore()
const route = useRoute()

// #1049: Auf der Login-Route NIE die App-Shell (Menü/Sidebar) zeigen — auch nicht,
// falls isAuthenticated kurzzeitig noch true ist. Sonst rahmt AppLayout via seines
// eigenen <router-view> die Anmeldemaske mit Menü oben/links ein.
const showLayout = computed(() => authStore.isAuthenticated && route.name !== 'Login')

onMounted(() => {
  authStore.loadProfile()
})
</script>

<style>
@import './styles/globals.css';
</style>
