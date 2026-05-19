<template>
  <AppLayout v-if="authStore.isAuthenticated" />
  <router-view v-else />
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import { useAuthStore } from './stores/auth'
import AppLayout from './components/AppLayout.vue'

const authStore = useAuthStore()

onMounted(() => {
  authStore.loadProfile()
})
</script>

<style>
@import './styles/globals.css';
</style>
