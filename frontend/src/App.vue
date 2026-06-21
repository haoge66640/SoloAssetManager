<template>
  <n-config-provider :theme="darkTheme" :theme-overrides="themeOverrides">
    <n-message-provider>
      <HomeView />
    </n-message-provider>
  </n-config-provider>
</template>

<script setup lang="ts">
import { NConfigProvider, NMessageProvider, darkTheme, type GlobalThemeOverrides } from 'naive-ui'
import HomeView from '@/views/HomeView.vue'

const themeOverrides: GlobalThemeOverrides = {
  common: {
    primaryColor: '#F5A524',
    primaryColorHover: '#FBBF24',
    primaryColorPressed: '#D97706',
    primaryColorSuppl: '#F5A524',
    infoColor: '#2DD4BF',
    infoColorHover: '#5EEAD4',
    infoColorPressed: '#14B8A6',
    successColor: '#34D399',
    warningColor: '#FBBF24',
    errorColor: '#F87171',
    errorColorHover: '#FCA5A5',
    errorColorPressed: '#EF4444',
    bodyColor: '#0E1014',
    cardColor: '#1B1F27',
    modalColor: '#1B1F27',
    popoverColor: '#232833',
    tableColor: '#1B1F27',
    inputColor: '#14171D',
    inputColorDisabled: '#1B1F27',
    actionColor: '#1B1F27',
    hoverColor: 'rgba(255,255,255,0.05)',
    borderColor: '#2A2F3A',
    dividerColor: 'rgba(255,255,255,0.08)',
    textColorBase: '#E8EAED',
    textColor1: '#E8EAED',
    textColor2: '#A1A8B3',
    textColor3: '#6B7280',
    placeholderColor: '#5B6270',
    fontWeightStrong: '700',
    borderRadius: '8px',
    borderRadiusSmall: '6px',
  },
}
</script>

<style>
#app {
  min-height: 100vh;
}
</style>
