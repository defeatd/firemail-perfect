<template>
  <div class="fm-import-view">
    <PageHeader
      title="批量导入"
      subtitle="毫秒级快速入库，后台限速自动首验并识别 IMAP / Graph 收信通道"
    />

    <div class="fm-import-grid">
      <div class="fm-import-main">
        <section class="fm-card fm-import-card">
          <ImportPanel
            ref="panelRef"
            @imported="handleImported"
          />
        </section>

        <section v-if="importResult" class="fm-card fm-import-card">
          <ImportResult
            :result="importResult"
            :job-summary="job.summary.value"
            :cancelling="job.cancelling.value"
            :raw-text="importRawText"
            @cancel-job="job.cancelAll()"
            @view-emails="router.push('/emails')"
            @continue="handleContinue"
          />
        </section>
      </div>

      <aside class="fm-card fm-import-guide">
        <h3 class="fm-import-guide__title">导入格式说明</h3>
        <p class="fm-import-guide__desc">
          每行一条记录，默认自动识别 <code class="fm-mono">----</code>、Tab、
          <code class="fm-mono">|</code>，也可在左侧手动指定 <code class="fm-mono">:</code>。按 GUID 自动定位
          <code class="fm-mono">client_id</code>，兼容 3/4/5/6 段及 Token 含分隔符：
        </p>

        <div class="fm-import-guide__code fm-mono">
          邮箱----密码----client_id----refresh_token
        </div>

        <div class="fm-import-guide__section">
          <div class="fm-import-guide__sub">示例行（点击可复制）</div>
          <div class="fm-import-guide__example">
            <CopyText :text="EXAMPLE_LINE" label="示例行" />
          </div>
        </div>

        <el-alert
          type="info"
          :closable="false"
          show-icon
          title="先入库，后台限速首验"
          description="有效格式行会立即写入并标记「首验中」，由后台任务依次校验 IMAP 与 Graph 通道。即使微软提示失效，账号行也会保留以便重试或设备码重授。"
        />

        <div class="fm-import-guide__section">
          <div class="fm-import-guide__sub">推荐：使用 Device Code 直接授权</div>
          <p class="fm-import-guide__desc">
            无需手动提取 Refresh Token，直接在浏览器完成微软设备码授权并自动建立 90 天保活基线。
          </p>
          <div class="fm-import-guide__links">
            <router-link to="/emails?action=add&tab=device" class="fm-import-guide__cta">
              前往使用 Device Code 授权添加 →
            </router-link>
            <a
              href="https://learn.microsoft.com/en-us/entra/identity-platform/v2-oauth2-device-code"
              target="_blank"
              rel="noopener noreferrer"
              class="fm-import-guide__ext"
            >
              查看 Microsoft OAuth 文档 ↗
            </a>
          </div>
        </div>
      </aside>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import PageHeader from '@/components/common/PageHeader.vue'
import CopyText from '@/components/common/CopyText.vue'
import ImportPanel from '@/components/import/ImportPanel.vue'
import ImportResult from '@/components/import/ImportResult.vue'
import { useEmailsStore } from '@/stores/emails'
import { useImportJob } from '@/composables/useImportJob'

const EXAMPLE_LINE =
  'example@outlook.com----YourPassword123----9e5f94bc-e8a4-4e73-b8be-63364c29d753----M.C512_BAY.0.U.-ExampleRefreshTokenWithAtLeastFiftyChars0123456789'

const router = useRouter()
const emails = useEmailsStore()
const job = useImportJob()

const panelRef = ref(null)
const importResult = ref(null)
const importRawText = ref('')

function handleImported(result) {
  importResult.value = result
  importRawText.value = result?.rawText || ''
  const ids = Array.isArray(result?.job_ids)
    ? result.job_ids
    : result?.job_id
      ? [result.job_id]
      : []
  if (ids.length > 0) {
    job.track(ids, {
      onFinish: () => {
        emails.refreshAll().catch(() => {})
      }
    })
  } else {
    job.reset()
  }
}

function handleContinue() {
  job.reset()
  importResult.value = null
  importRawText.value = ''
  panelRef.value?.reset()
}
</script>

<style scoped>
.fm-import-grid {
  display: grid;
  grid-template-columns: minmax(0, 8fr) minmax(280px, 4fr);
  gap: var(--fm-space-5);
  align-items: start;
}

.fm-import-main {
  display: flex;
  flex-direction: column;
  gap: var(--fm-space-5);
}

.fm-import-card {
  padding: var(--fm-space-5);
}

.fm-import-guide {
  padding: var(--fm-space-5);
  display: flex;
  flex-direction: column;
  gap: var(--fm-space-4);
}

.fm-import-guide__title {
  margin: 0;
  font-size: var(--fm-fs-md);
  font-weight: 600;
  color: var(--fm-text);
}

.fm-import-guide__sub {
  font-size: var(--fm-fs-xs);
  font-weight: 600;
  color: var(--fm-text-2);
  margin-bottom: 6px;
}

.fm-import-guide__desc {
  margin: 0;
  font-size: var(--fm-fs-sm);
  color: var(--fm-text-2);
  line-height: var(--fm-lh-base);
}

.fm-import-guide__code {
  padding: 10px 12px;
  border-radius: var(--fm-radius-md);
  background: var(--fm-bg-subtle);
  border: 1px solid var(--fm-border);
  font-size: var(--fm-fs-xs);
  color: var(--fm-text);
  word-break: break-all;
}

.fm-import-guide__example {
  padding: 8px 10px;
  border-radius: var(--fm-radius-md);
  background: var(--fm-bg-subtle);
  border: 1px solid var(--fm-border);
  font-size: 11px;
}

.fm-import-guide__section {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.fm-import-guide__links {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-top: 4px;
}

.fm-import-guide__cta {
  font-size: var(--fm-fs-sm);
  font-weight: 500;
  color: var(--fm-accent);
  text-decoration: none;
}

.fm-import-guide__cta:hover {
  text-decoration: underline;
}

.fm-import-guide__ext {
  font-size: var(--fm-fs-xs);
  color: var(--fm-text-2);
  text-decoration: none;
}

.fm-import-guide__ext:hover {
  color: var(--fm-text);
}

@media (max-width: 1023.98px) {
  .fm-import-grid {
    grid-template-columns: 1fr;
  }
}
</style>
