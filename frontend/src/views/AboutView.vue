<template>
  <div class="fm-about-view">
    <PageHeader
      title="关于 FireMail"
      subtitle="Outlook 邮箱池 · 精准取件 · 90 天令牌自动保活工作台"
    >
      <template v-if="!auth.isAuthenticated" #actions>
        <el-button type="primary" @click="router.push('/login')">前往登录</el-button>
      </template>
    </PageHeader>

    <div class="fm-about-grid">
      <section class="fm-card fm-about-card">
        <h2 class="fm-about-card__title">项目概览</h2>
        <p class="fm-about-card__desc">
          FireMail（花火邮箱助手）是一套面向多邮箱资产集中管理、实时收信、验证码快速提取与 Microsoft Outlook OAuth2 Refresh Token 90 天生命周期自动保活的现代 Web 工作台。
        </p>
        <KeyValueList :items="projectInfo" />
      </section>

      <section class="fm-card fm-about-card">
        <h2 class="fm-about-card__title">技术栈</h2>
        <p class="fm-about-card__desc">
          前后端分离架构，结合 WebSocket 实时推送与本地零外链字体加载，兼顾响应速度与安全隔离。
        </p>
        <div class="fm-about-tags">
          <span v-for="tech in TECH_STACK" :key="tech" class="fm-about-tag fm-mono">
            {{ tech }}
          </span>
        </div>
      </section>

      <section class="fm-card fm-about-card fm-about-card--full">
        <h2 class="fm-about-card__title">核心能力</h2>
        <div class="fm-about-features">
          <article v-for="feat in FEATURES" :key="feat.title" class="fm-about-feat">
            <h3 class="fm-about-feat__title">{{ feat.title }}</h3>
            <p class="fm-about-feat__desc">{{ feat.desc }}</p>
          </article>
        </div>
      </section>

      <section class="fm-card fm-about-card fm-about-card--full">
        <h2 class="fm-about-card__title">使用注意事项</h2>
        <ul class="fm-about-notices">
          <li v-for="note in NOTICES" :key="note">{{ note }}</li>
        </ul>
      </section>
    </div>
  </div>
</template>

<script setup>
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import PageHeader from '@/components/common/PageHeader.vue'
import KeyValueList from '@/components/common/KeyValueList.vue'

const appVersion =
  import.meta.env.VITE_APP_VERSION || (typeof __APP_VERSION__ !== 'undefined' ? __APP_VERSION__ : '1.0.0')

const router = useRouter()
const auth = useAuthStore()

const projectInfo = [
  { label: '应用名称', value: 'FireMail（花火邮箱助手）' },
  { label: '当前版本', value: `v${appVersion}`, mono: true },
  { label: '支持协议', value: 'Microsoft OAuth2 / IMAP / WebSocket', mono: true },
  { label: '安全隔离', value: 'DOMPurify + 无脚本 Sandboxed Iframe' }
]

const TECH_STACK = [
  'Vue 3',
  'Pinia',
  'Vue Router',
  'Element Plus',
  'Vite',
  'DOMPurify',
  'Flask',
  'SQLite',
  'WebSockets'
]

const FEATURES = [
  {
    title: '多协议邮箱资产统一纳管',
    desc: '同时支持 Outlook / Hotmail、通用 IMAP、Gmail 与 QQ 邮箱，提供批量校验导入与标准四段格式导出。'
  },
  {
    title: '90 天 Refresh Token 自动保活',
    desc: '后台按到期优先级自动轮换续期，结合 AADSTS 错误分类、健康态势条与寿命进度条实现到期前主动预警。'
  },
  {
    title: 'Device Code 免提取快捷授权',
    desc: '内置微软设备码引导流程，无需手动抓取 Refresh Token 即可一键完成新增或重新授权。'
  },
  {
    title: '沉浸式收件箱与验证码快取',
    desc: '双栏桌面阅读器与全屏移动抽屉，自动打分识别主流中英文验证码并支持列表级一键复制。'
  },
  {
    title: 'WebSocket 实时同步推送',
    desc: '收信进度、导入结果与批量变更实时回传前端，支持按邮箱独立开启实时收信轮询。'
  },
  {
    title: '多用户权限与安全正文沙箱',
    desc: '细粒度用户与管理员权限控制；所有 HTML 邮件均经 DOMPurify 清洗并运行在禁用脚本的沙箱框架中。'
  }
]

const NOTICES = [
  '敏感凭据（密码、Client ID、Refresh Token）仅在明确请求时按需下发并暂存于当前页面内存，请妥善保管导出文件。',
  'Outlook 长期未活动账号的 Refresh Token 超过 90 天不续期将失效，建议保持后台 Token 保活调度处于运行状态。',
  '遇到 AADSTS 强交互或风控告警（需重授）时，请通过「Device Code 重新授权」流程及时恢复令牌。'
]
</script>

<style scoped>
.fm-about-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--fm-space-5);
}

.fm-about-card {
  padding: var(--fm-space-5);
  display: flex;
  flex-direction: column;
  gap: var(--fm-space-4);
}

.fm-about-card--full {
  grid-column: 1 / -1;
}

.fm-about-card__title {
  margin: 0;
  font-size: var(--fm-fs-md);
  font-weight: 600;
  color: var(--fm-text);
}

.fm-about-card__desc {
  margin: 0;
  font-size: var(--fm-fs-sm);
  color: var(--fm-text-2);
  line-height: var(--fm-lh-base);
}

.fm-about-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.fm-about-tag {
  padding: 4px 10px;
  border-radius: var(--fm-radius-pill);
  background: var(--fm-bg-subtle);
  border: 1px solid var(--fm-border);
  font-size: var(--fm-fs-xs);
  color: var(--fm-text-2);
}

.fm-about-features {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--fm-space-4);
}

.fm-about-feat {
  padding: var(--fm-space-4);
  border-radius: var(--fm-radius-md);
  background: var(--fm-surface-2);
  border: 1px solid var(--fm-border);
}

.fm-about-feat__title {
  margin: 0 0 6px;
  font-size: var(--fm-fs-sm);
  font-weight: 600;
  color: var(--fm-text);
}

.fm-about-feat__desc {
  margin: 0;
  font-size: var(--fm-fs-xs);
  color: var(--fm-text-2);
  line-height: var(--fm-lh-base);
}

.fm-about-notices {
  margin: 0;
  padding-left: 18px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  font-size: var(--fm-fs-sm);
  color: var(--fm-text-2);
  line-height: var(--fm-lh-base);
}

@media (max-width: 1023.98px) {
  .fm-about-grid,
  .fm-about-features {
    grid-template-columns: 1fr;
  }
}
</style>
