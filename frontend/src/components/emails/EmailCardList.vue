<template>
  <div v-loading="loading" class="fm-card-list">
    <div v-if="rows.length > 0" class="fm-card-list__toolbar">
      <el-checkbox
        :model-value="allPageSelected"
        :indeterminate="somePageSelected"
        @change="toggleAllPage"
      >
        全选本页
      </el-checkbox>

      <div class="fm-card-list__sort">
        <el-select
          :model-value="sortProp"
          size="small"
          style="width: 120px"
          @update:model-value="handleSortPropChange"
        >
          <el-option value="default" label="默认排序" />
          <el-option value="email" label="按邮箱" />
          <el-option value="last_check_time" label="最后检查" />
          <el-option value="rt_days" label="RT 剩余" />
        </el-select>
        <el-button
          v-if="sortProp !== 'default'"
          size="small"
          @click="toggleSortOrder"
        >
          {{ sortOrder === 'descending' ? '降序' : '升序' }}
        </el-button>
      </div>
    </div>

    <div v-if="rows.length === 0 && !loading" class="fm-card fm-card-list__empty">
      <EmptyState title="暂无邮箱" description="添加或导入您的邮箱账户开始统一管理。">
        <template #actions>
          <el-button type="primary" @click="$emit('add')">添加邮箱</el-button>
        </template>
      </EmptyState>
    </div>

    <div v-else class="fm-card-list__items">
      <article
        v-for="row in rows"
        :key="row.id"
        class="fm-card fm-email-card"
        :class="{ 'is-selected': selectedSet.has(row.id) }"
      >
        <div class="fm-email-card__head">
          <el-checkbox
            :model-value="selectedSet.has(row.id)"
            :aria-label="`选择 ${row.email}`"
            @change="toggleRow(row.id, $event)"
          />
          <BrandIcon :type="row.mail_type" :size="18" />
          <div class="fm-email-card__title">
            <CopyText :text="row.email" label="邮箱地址" />
            <span class="fm-email-card__type">{{ getMailTypeLabel(row.mail_type) }}</span>
          </div>
        </div>

        <div v-if="row.mail_type === 'outlook'" class="fm-email-card__auth">
          <AuthStatusCell :row="row" compact />
        </div>

        <div class="fm-email-card__meta">
          <span class="fm-email-card__time fm-mono">
            <template v-if="processing[row.id]">
              收信中 {{ processing[row.id].progress ? `${Math.round(processing[row.id].progress)}%` : '' }}
            </template>
            <template v-else-if="row.last_check_time">
              检查：{{ formatRelative(row.last_check_time) }}
            </template>
            <template v-else>从未检查</template>
          </span>

          <label class="fm-email-card__realtime">
            <span>实时</span>
            <el-switch
              size="small"
              :model-value="Boolean(row.enable_realtime_check)"
              @change="$emit('toggle-realtime', row, $event)"
            />
          </label>
        </div>

        <div class="fm-email-card__foot">
          <EmailRowActions
            :row="row"
            :processing="processing[row.id] || null"
            :refreshing="Boolean(refreshingIds[row.id])"
            compact
            @check="$emit('check', $event)"
            @view="$emit('view', $event)"
            @keepalive="$emit('keepalive', $event)"
            @edit="$emit('edit', $event)"
            @reauth="$emit('reauth', $event)"
            @credentials="$emit('credentials', $event)"
            @delete="$emit('delete', $event)"
          />
        </div>
      </article>
    </div>

    <div v-if="totalCount > pageSize" class="fm-card-list__pager">
      <el-pagination
        :current-page="page"
        :page-size="pageSize"
        :total="totalCount"
        layout="prev, pager, next"
        small
        @update:current-page="$emit('update:page', $event)"
      />
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { getMailTypeLabel } from '@/utils/mailTypes'
import { formatRelative } from '@/utils/time'
import BrandIcon from '@/components/common/BrandIcon.vue'
import CopyText from '@/components/common/CopyText.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import AuthStatusCell from './AuthStatusCell.vue'
import EmailRowActions from './EmailRowActions.vue'

const props = defineProps({
  rows: { type: Array, default: () => [] },
  totalCount: { type: Number, default: 0 },
  loading: { type: Boolean, default: false },
  selectedIds: { type: Array, default: () => [] },
  processing: { type: Object, default: () => ({}) },
  refreshingIds: { type: Object, default: () => ({}) },
  sort: { type: Object, default: () => ({ prop: '', order: null }) },
  page: { type: Number, default: 1 },
  pageSize: { type: Number, default: 50 }
})

const emit = defineEmits([
  'update:selectedIds',
  'update:page',
  'sort-change',
  'add',
  'check',
  'view',
  'keepalive',
  'edit',
  'reauth',
  'credentials',
  'delete',
  'toggle-realtime'
])

const selectedSet = computed(() => new Set(props.selectedIds))
const pageIds = computed(() => props.rows.map((r) => r.id))
const sortProp = computed(() => props.sort?.prop || 'default')
const sortOrder = computed(() => props.sort?.order || 'ascending')

const allPageSelected = computed(
  () => pageIds.value.length > 0 && pageIds.value.every((id) => selectedSet.value.has(id))
)

const somePageSelected = computed(() => {
  const c = pageIds.value.filter((id) => selectedSet.value.has(id)).length
  return c > 0 && c < pageIds.value.length
})

function toggleAllPage(checked) {
  const next = new Set(props.selectedIds)
  if (checked) pageIds.value.forEach((id) => next.add(id))
  else pageIds.value.forEach((id) => next.delete(id))
  emit('update:selectedIds', Array.from(next))
}

function toggleRow(id, checked) {
  const next = new Set(props.selectedIds)
  if (checked) next.add(id)
  else next.delete(id)
  emit('update:selectedIds', Array.from(next))
}

function handleSortPropChange(prop) {
  const actual = prop === 'default' ? '' : prop
  emit('sort-change', { prop: actual, order: actual ? 'ascending' : null })
}

function toggleSortOrder() {
  if (sortProp.value === 'default') return
  const nextOrder = sortOrder.value === 'descending' ? 'ascending' : 'descending'
  emit('sort-change', { prop: sortProp.value, order: nextOrder })
}
</script>

<style scoped>
.fm-card-list {
  display: flex;
  flex-direction: column;
  gap: var(--fm-space-3);
}

.fm-card-list__toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--fm-space-2);
}

.fm-card-list__sort {
  display: flex;
  align-items: center;
  gap: 6px;
}

.fm-card-list__items {
  display: flex;
  flex-direction: column;
  gap: var(--fm-space-3);
}

.fm-email-card {
  padding: var(--fm-space-4);
  display: flex;
  flex-direction: column;
  gap: var(--fm-space-3);
}

.fm-email-card.is-selected {
  border-color: var(--fm-accent-border);
  background: var(--fm-surface-2);
}

.fm-email-card__head {
  display: flex;
  align-items: flex-start;
  gap: 10px;
}

.fm-email-card__title {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.fm-email-card__type {
  font-size: var(--fm-fs-xs);
  color: var(--fm-text-3);
}

.fm-email-card__meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: var(--fm-fs-xs);
  color: var(--fm-text-2);
}

.fm-email-card__realtime {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: var(--fm-text-3);
}

.fm-email-card__foot {
  padding-top: var(--fm-space-2);
  border-top: 1px solid var(--fm-border);
}

.fm-card-list__pager {
  display: flex;
  justify-content: center;
  margin-top: var(--fm-space-2);
}
</style>
