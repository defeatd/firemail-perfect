<template>
  <div class="fm-blank-layout">
    <div class="fm-blank-layout__theme">
      <ThemeToggle />
    </div>
    <main class="fm-blank-layout__content">
      <slot />
    </main>
  </div>
</template>

<script setup>
import ThemeToggle from '@/components/shell/ThemeToggle.vue'
</script>

<style scoped>
.fm-blank-layout {
  position: relative;
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--fm-space-6) var(--fm-space-4);
  background: var(--fm-bg);
}

.fm-blank-layout__theme {
  position: fixed;
  top: var(--fm-space-4);
  right: var(--fm-space-4);
  z-index: 20;
}

.fm-blank-layout__content {
  width: 100%;
  max-width: 960px;
}
</style>
