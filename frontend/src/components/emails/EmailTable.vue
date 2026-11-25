<template>
  <div class="fm-email-table-wrap">
    <div class="fm-email-table-card">
      <el-table
        v-loading="loading"
        :data="rows"
        row-key="id"
        class="fm-email-table"
        @sort-change="handleSortChange"
      >
        <el-table-column width="44" align="center">
          <template #header>
            <el-checkbox
              :model-value="allPageSelected"
              :indeterminate="somePageSelected"
              aria-label="全选当前页"
              @change="toggleAllPage"
            />
          </template>
          <template #default="{ row }">
            <el-checkbox
              :model-value="selectedSet.has(row.id)"
              :aria-label="`选择 ${row.email}`"
              @change="toggleRow(row.id, $event)"
            />
          </template>
        </el-table-column>

        <el-table-column
          prop="email"
          label="邮箱"
          min-width="260"
          sortable="custom"
        >
          <template #default="{ row }">
            <div class="fm-email-cell">
              <BrandIcon :type="row.mail_type" :size="18" />
              <div class="fm-email-cell__info">
                <CopyText :text="row.email" label="邮箱地址" truncate class="fm-email-cell__addr" />
                <span class="fm-email-cell__type">{{ getMailTypeLabel(row.mail_type) }}</span>
              </div>
            </div>
          </template>
        </el-table-column>

        <el-table-column
          prop="rt_days"
          label="授权 / RT 寿命"
          width="204"
          sortable="custom"
        >
          <template #default="{ row }">
            <AuthStatusCell :row="row" />
          </template>
        </el-table-column>

        <el-table-column label="密码" width="136">
          <template #default="{ row }">
            <div class="fm-pwd-cell">
              <template v-if="revealedPasswords[row.id] !== undefined">
                <CopyText
                  :text="revealedPasswords[row.id]"
                  label="密码"
                  truncate
                  class="fm-pwd-cell__plain"
                />
              </template>
              <span v-else class="fm-pwd-cell__mask fm-mono">••••••••</span>

              <el-tooltip
                :content="revealedPasswords[row.id] !== undefined ? '隐藏密码' : '查看密码'"
                placement="top"
              >
                <button
                  type="button"
                  class="fm-pwd-cell__btn"
                  :disabled="Boolean(passwordLoading[row.id])"
                  :aria-label="revealedPasswords[row.id] !== undefined ? '隐藏密码' : '查看密码'"
                  @click="$emit('reveal-password', row)"
                >
                  <el-icon :size="14" :class="{ 'is-loading': passwordLoading[row.id] }">
                    <Loading v-if="passwordLoading[row.id]" />
                    <Hide v-else-if="revealedPasswords[row.id] !== undefined" />
                    <View v-else />
                  </el-icon>
                </button>
              </el-tooltip>
            </div>
          </template>
        </el-table-column>

        <el-table-column label="实时收信" width="88" align="center">
          <template #default="{ row }">
            <el-switch
              size="small"
              :model-value="Boolean(row.enable_realtime_check)"
              :aria-label="`切换 ${row.email} 实时收信`"
              @change="$emit('toggle-realtime', row, $event)"
            />
          </template>
        </el-table-column>

        <el-table-column
          prop="last_check_time"
          label="最后检查"
          width="132"
          sortable="custom"
        >
          <template #default="{ row }">
            <span v-if="processing[row.id]" class="fm-check-progress">
              <el-icon class="is-loading" :size="13"><Loading /></el-icon>
              <span class="fm-mono">
                {{ formatProgress(processing[row.id]) }}
              </span>
            </span>

            <el-tooltip
              v-else-if="row.last_check_time"
              :content="formatAbs(row.last_check_time)"
              placement="top"
            >
              <span class="fm-mono fm-check-time">
                {{ formatRelative(row.last_check_time) }}
              </span>
            </el-tooltip>

            <span v-else class="fm-check-never">从未</span>
          </template>
        </el-table-column>

        <el-table-column label="操作" width="156" fixed="right" align="right">
          <template #default="{ row }">
            <EmailRowActions
              :row="row"
              :processing="processing[row.id] || null"
              :refreshing="Boolean(refreshingIds[row.id])"
              @check="$emit('check', $event)"
              @view="$emit('view', $event)"
              @keepalive="$emit('keepalive', $event)"
              @edit="$emit('edit', $event)"
              @reauth="$emit('reauth', $event)"
              @credentials="$emit('credentials', $event)"
              @delete="$emit('delete', $event)"
            />
          </template>
        </el-table-column>

        <template #empty>
          <EmptyState
            title="暂无符合条件的邮箱"
            description="尝试调整筛选条件，或添加新的邮箱账户。"
          />
        </template>
      </el-table>
    </div>

    <div v-if="totalCount > 0" class="fm-email-table-footer">
      <span class="fm-email-table-footer__total">
        共 <strong class="fm-mono">{{ totalCount }}</strong> 条（筛选后）
      </span>
      <el-pagination
        :current-page="page"
        :page-size="pageSize"
        :page-sizes="[20, 50, 100]"
        :total="totalCount"
        layout="sizes, prev, pager, next"
        small
        @update:current-page="$emit('update:page', $event)"
        @update:page-size="$emit('update:pageSize', $event)"
      />
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { View, Hide, Loading } from '@element-plus/icons-vue'
import { getMailTypeLabel } from '@/utils/mailTypes'
import { formatAbs, formatRelative } from '@/utils/time'
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
  revealedPasswords: { type: Object, default: () => ({}) },
  passwordLoading: { type: Object, default: () => ({}) },
  page: { type: Number, default: 1 },
  pageSize: { type: Number, default: 50 }
})

const emit = defineEmits([
  'update:selectedIds',
  'update:page',
  'update:pageSize',
  'sort-change',
  'check',
  'view',
  'keepalive',
  'edit',
  'reauth',
  'credentials',
  'delete',
  'toggle-realtime',
  'reveal-password'
])

const selectedSet = computed(() => new Set(props.selectedIds))

const pageIds = computed(() => props.rows.map((r) => r.id))

const allPageSelected = computed(
  () => pageIds.value.length > 0 && pageIds.value.every((id) => selectedSet.value.has(id))
)

const somePageSelected = computed(() => {
  const count = pageIds.value.filter((id) => selectedSet.value.has(id)).length
  return count > 0 && count < pageIds.value.length
})

function toggleAllPage(checked) {
  const next = new Set(props.selectedIds)
  if (checked) {
    pageIds.value.forEach((id) => next.add(id))
  } else {
    pageIds.value.forEach((id) => next.delete(id))
  }
  emit('update:selectedIds', Array.from(next))
}

function toggleRow(id, checked) {
  const next = new Set(props.selectedIds)
  if (checked) {
    next.add(id)
  } else {
    next.delete(id)
  }
  emit('update:selectedIds', Array.from(next))
}

function handleSortChange({ prop, order }) {
  emit('sort-change', { prop: prop || '', order: order || null })
}

function formatProgress(status) {
  if (!status) return '收信中'
  const pct = Number(status.progress)
  return Number.isFinite(pct) && pct > 0 ? `收信中 ${Math.round(pct)}%` : '收信中'
}
</script>

<style scoped>
.fm-email-table-card {
  background: var(--fm-surface);
  border: 1px solid var(--fm-border);
  border-radius: var(--fm-radius-lg);
  overflow: hidden;
  box-shadow: var(--fm-shadow-xs);
}

.fm-email-table :deep(.el-table__row) {
  height: 52px;
}

.fm-email-cell {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.fm-email-cell__info {
  display: flex;
  flex-direction: column;
  min-width: 0;
  line-height: 1.3;
}

.fm-email-cell__addr {
  font-size: var(--fm-fs-sm);
  font-weight: 500;
}

.fm-email-cell__type {
  font-size: var(--fm-fs-xs);
  color: var(--fm-text-3);
}

.fm-pwd-cell {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 6px;
}

.fm-pwd-cell__mask {
  color: var(--fm-text-3);
  letter-spacing: 0.08em;
  font-size: var(--fm-fs-xs);
}

.fm-pwd-cell__plain {
  font-size: var(--fm-fs-xs);
  min-width: 0;
}

.fm-pwd-cell__btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border: none;
  border-radius: var(--fm-radius-xs);
  background: transparent;
  color: var(--fm-text-3);
  cursor: pointer;
  flex-shrink: 0;
}

.fm-pwd-cell__btn:hover:not(:disabled) {
  background: var(--fm-surface-hover);
  color: var(--fm-text);
}

.fm-check-progress {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  color: var(--fm-info);
  font-size: var(--fm-fs-xs);
}

.fm-check-time {
  font-size: var(--fm-fs-xs);
  color: var(--fm-text-2);
}

.fm-check-never {
  font-size: var(--fm-fs-xs);
  color: var(--fm-text-3);
}

.fm-email-table-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: var(--fm-space-3);
  margin-top: var(--fm-space-4);
}

.fm-email-table-footer__total {
  font-size: var(--fm-fs-xs);
  color: var(--fm-text-3);
}
</style>
