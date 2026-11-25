<template>
  <div class="fm-search-view">
    <PageHeader
      title="邮件搜索"
      subtitle="跨邮箱全文检索标题、发件人、收件人与正文内容"
    />

    <SearchBar
      :initial-query="currentQuery"
      :initial-in="currentScopes"
      :loading="loading"
      @search="handleSearchSubmit"
    />

    <div v-if="!hasSearched" class="fm-card fm-search-empty">
      <EmptyState
        :icon="Search"
        title="请在上方输入关键词开始搜索"
        description="支持按标题、发件人、收件人与正文多维组合检索。"
      />
    </div>

    <div v-else-if="!loading && results.length === 0" class="fm-card fm-search-empty">
      <EmptyState
        :icon="Search"
        title="未找到符合条件的邮件"
        description="尝试更换关键词或扩大搜索范围。"
      />
    </div>

    <div v-else class="fm-search-pane" :class="{ 'is-narrow': isNarrow }">
      <div v-if="!isMobile || !selectedMail" class="fm-search-pane__list">
        <MailList
          :records="results"
          :selected-id="selectedMail?.id"
          :loading="loading"
          hide-search
          show-email-badge
          :highlight-query="currentQuery"
          :show-empty-action="false"
          empty-title="未找到符合条件的邮件"
          empty-description="请尝试其他搜索词。"
          @select="selectedId = $event.id"
          @click-sender="searchBySender"
          @click-email="goToEmail"
        />
      </div>

      <div v-if="!isMobile" class="fm-search-pane__reader">
        <MailReader
          :mail="selectedMail"
          :email-id="selectedMail?.email_id"
          show-search-links
          @click-sender="searchBySender"
          @click-email="goToEmail"
        />
      </div>
    </div>

    <div v-if="isMobile && selectedMail" class="fm-mobile-reader-overlay">
      <MailReader
        :mail="selectedMail"
        :email-id="selectedMail?.email_id"
        show-back
        show-search-links
        @back="selectedId = null"
        @click-sender="searchBySender"
        @click-email="goToEmail"
      />
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Search } from '@element-plus/icons-vue'
import api from '@/services/api'
import { useBreakpoint } from '@/composables/useBreakpoint'
import PageHeader from '@/components/common/PageHeader.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import SearchBar from '@/components/mail/SearchBar.vue'
import MailList from '@/components/mail/MailList.vue'
import MailReader from '@/components/mail/MailReader.vue'

const DEFAULT_SCOPES = ['subject', 'sender', 'content']

const route = useRoute()
const router = useRouter()
const { isMobile, isNarrow } = useBreakpoint()

const loading = ref(false)
const hasSearched = ref(false)
const results = ref([])
const selectedId = ref(null)

const currentQuery = computed(() => String(route.query.q || '').trim())
const currentScopes = computed(() => {
  const raw = route.query.in
  if (!raw) return DEFAULT_SCOPES
  const arr = String(raw)
    .split(',')
    .map((s) => s.trim())
    .filter((s) => ['subject', 'sender', 'recipient', 'content'].includes(s))
  return arr.length > 0 ? arr : DEFAULT_SCOPES
})

const selectedMail = computed(() => {
  if (!selectedId.value) return null
  return results.value.find((m) => Number(m.id) === Number(selectedId.value)) || null
})

async function executeSearch(q, scopes) {
  if (!q) {
    hasSearched.value = false
    results.value = []
    selectedId.value = null
    return
  }
  loading.value = true
  hasSearched.value = true
  selectedId.value = null
  try {
    const res = await api.search(q, scopes)
    const list = Array.isArray(res?.data?.results) ? res.data.results : []
    results.value = list
    if (list.length === 0) {
      ElMessage.info('未找到符合条件的邮件')
    } else if (!isMobile.value) {
      selectedId.value = list[0].id
    }
  } catch (err) {
    results.value = []
    ElMessage.error(err?.response?.data?.error || '搜索失败，请稍后重试')
  } finally {
    loading.value = false
  }
}

watch(
  () => [route.query.q, route.query.in],
  () => {
    executeSearch(currentQuery.value, currentScopes.value)
  },
  { immediate: true }
)

function handleSearchSubmit({ q, in: scopes }) {
  router.push({
    name: 'search',
    query: { q, in: scopes.join(',') }
  })
}

function searchBySender(senderAddress) {
  if (!senderAddress) return
  router.push({
    name: 'search',
    query: { q: senderAddress, in: 'sender' }
  })
}

function goToEmail(mail) {
  if (!mail?.email_id) return
  router.push({
    name: 'email-detail',
    params: { id: mail.email_id },
    query: { mail: String(mail.id) }
  })
}
</script>

<style scoped>
.fm-search-empty {
  padding: var(--fm-space-6);
}

.fm-search-pane {
  display: grid;
  grid-template-columns: 360px minmax(0, 1fr);
  height: calc(100vh - 280px);
  min-height: 480px;
  border: 1px solid var(--fm-border);
  border-radius: var(--fm-radius-lg);
  overflow: hidden;
  background: var(--fm-surface);
  box-shadow: var(--fm-shadow-xs);
}

.fm-search-pane.is-narrow {
  grid-template-columns: 300px minmax(0, 1fr);
}

.fm-search-pane__list {
  border-right: 1px solid var(--fm-border);
  min-height: 0;
  overflow: hidden;
}

.fm-search-pane__reader {
  min-width: 0;
  min-height: 0;
  overflow: hidden;
}

.fm-mobile-reader-overlay {
  position: fixed;
  inset: 0;
  z-index: 300;
  background: var(--fm-surface);
  display: flex;
  flex-direction: column;
}

@media (max-width: 767.98px) {
  .fm-search-pane {
    grid-template-columns: 1fr;
    height: calc(100vh - 300px);
    min-height: 400px;
  }

  .fm-search-pane__list {
    border-right: none;
  }
}
</style>
