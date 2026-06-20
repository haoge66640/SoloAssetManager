<template>
  <n-config-provider>
    <n-message-provider>
      <HomeView />
    </n-message-provider>
  </n-config-provider>
</template>

<script setup lang="ts">
import { NConfigProvider, NMessageProvider } from 'naive-ui'
import HomeView from '@/views/HomeView.vue'
</script>

<style scoped>
:deep(#app) {
  min-height: 100vh;
}
</style>
