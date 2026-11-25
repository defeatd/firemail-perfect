<template>
  <header class="fm-page-header">
    <div class="fm-page-header__main">
      <div v-if="backTo" class="fm-page-header__back-row">
        <router-link :to="backTo" class="fm-page-header__back">
          <el-icon><ArrowLeft /></el-icon>
          <span>{{ backLabel }}</span>
        </router-link>
      </div>
      <div class="fm-page-header__title-row">
        <h1 class="fm-page-header__title">
          <slot name="title">{{ title }}</slot>
        </h1>
        <span
          v-if="count !== null && count !== undefined && count !== ''"
          class="fm-page-header__count fm-mono"
        >
          {{ count }}
        </span>
      </div>
      <p v-if="subtitle" class="fm-page-header__subtitle">{{ subtitle }}</p>
      <div v-if="$slots.meta" class="fm-page-header__meta">
        <slot name="meta" />
      </div>
    </div>
    <div v-if="$slots.actions" class="fm-page-header__actions">
      <slot name="actions" />
    </div>
  </header>
</template>

<script setup>
import { ArrowLeft } from '@element-plus/icons-vue'

defineProps({
  title: { type: String, default: '' },
  subtitle: { type: String, default: '' },
  count: { type: [Number, String], default: null },
  backTo: { type: [String, Object], default: null },
  backLabel: { type: String, default: '返回' }
})
</script>

<style scoped>
.fm-page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--fm-space-4);
  margin-bottom: var(--fm-space-6);
}

.fm-page-header__main {
  min-width: 0;
  flex: 1;
}

.fm-page-header__back-row {
  margin-bottom: var(--fm-space-2);
}

.fm-page-header__back {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: var(--fm-fs-sm);
  color: var(--fm-text-2);
  text-decoration: none;
  transition: color var(--fm-dur-fast) var(--fm-ease);
}

.fm-page-header__back:hover {
  color: var(--fm-text);
}

.fm-page-header__title-row {
  display: flex;
  align-items: center;
  gap: var(--fm-space-2);
  flex-wrap: wrap;
}

.fm-page-header__title {
  margin: 0;
  font-size: var(--fm-fs-xl);
  font-weight: 600;
  line-height: var(--fm-lh-tight);
  letter-spacing: -0.02em;
  color: var(--fm-text);
  display: inline-flex;
  align-items: center;
  gap: var(--fm-space-2);
  min-width: 0;
}

.fm-page-header__count {
  display: inline-flex;
  align-items: center;
  height: 22px;
  padding: 0 8px;
  border-radius: var(--fm-radius-pill);
  background: var(--fm-muted-soft);
  color: var(--fm-text-2);
  font-size: var(--fm-fs-xs);
  font-weight: 500;
}

.fm-page-header__subtitle {
  margin: 4px 0 0;
  font-size: var(--fm-fs-sm);
  color: var(--fm-text-2);
}

.fm-page-header__meta {
  margin-top: var(--fm-space-2);
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--fm-space-3);
  font-size: var(--fm-fs-xs);
  color: var(--fm-text-3);
}

.fm-page-header__actions {
  display: flex;
  align-items: center;
  gap: var(--fm-space-2);
  flex-shrink: 0;
  flex-wrap: wrap;
}

@media (max-width: 767.98px) {
  .fm-page-header {
    flex-direction: column;
    align-items: stretch;
    gap: var(--fm-space-3);
    margin-bottom: var(--fm-space-5);
  }

  .fm-page-header__actions {
    width: 100%;
  }
}
</style>
