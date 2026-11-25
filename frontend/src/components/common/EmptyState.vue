<template>
  <div class="fm-empty" :class="{ 'fm-empty--large': large }">
    <div v-if="code" class="fm-empty__code fm-mono">{{ code }}</div>
    <div v-if="icon || $slots.icon" class="fm-empty__icon">
      <slot name="icon">
        <el-icon :size="large ? 40 : 32">
          <component :is="icon" />
        </el-icon>
      </slot>
    </div>
    <h3 class="fm-empty__title">{{ title }}</h3>
    <p v-if="description" class="fm-empty__desc">{{ description }}</p>
    <div v-if="$slots.actions" class="fm-empty__actions">
      <slot name="actions" />
    </div>
  </div>
</template>

<script setup>
defineProps({
  icon: { type: [Object, Function], default: null },
  code: { type: String, default: '' },
  title: { type: String, required: true },
  description: { type: String, default: '' },
  large: { type: Boolean, default: false }
})
</script>

<style scoped>
.fm-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  max-width: 360px;
  margin: 0 auto;
  padding: var(--fm-space-8) var(--fm-space-4);
}

.fm-empty--large {
  max-width: 440px;
  padding: var(--fm-space-10) var(--fm-space-5);
}

.fm-empty__code {
  font-size: 64px;
  font-weight: 600;
  line-height: 1;
  letter-spacing: -0.04em;
  color: var(--fm-text-3);
  margin-bottom: var(--fm-space-4);
}

.fm-empty__icon {
  color: var(--fm-text-3);
  margin-bottom: var(--fm-space-3);
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.fm-empty__title {
  margin: 0;
  font-size: var(--fm-fs-lg);
  font-weight: 600;
  color: var(--fm-text);
}

.fm-empty__desc {
  margin: var(--fm-space-2) 0 0;
  font-size: var(--fm-fs-sm);
  color: var(--fm-text-2);
  line-height: var(--fm-lh-base);
}

.fm-empty__actions {
  margin-top: var(--fm-space-5);
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--fm-space-2);
  flex-wrap: wrap;
}
</style>
