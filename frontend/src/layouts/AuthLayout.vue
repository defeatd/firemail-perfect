<template>
  <div class="fm-auth-layout">
    <div class="fm-auth-layout__theme">
      <ThemeToggle />
    </div>

    <aside class="fm-auth-layout__brand">
      <div class="fm-auth-layout__brand-inner">
        <div class="fm-auth-layout__logo">
          <span class="fm-auth-layout__spark" aria-hidden="true">
            <svg viewBox="0 0 24 24" width="28" height="28" fill="none">
              <path
                d="M12.6 2.5C12.9 6.2 16 7.8 16.5 12.2C17.6 11.2 18.2 9.9 18.4 8.6C20.2 10.7 20.8 13.7 19.6 16.6C18.4 19.6 15.5 21.5 12 21.5C7.6 21.5 4.2 18.1 4.2 13.6C4.2 9.5 7.4 6.6 10.6 3.9C11.3 3.3 12 2.8 12.6 2.5Z"
                fill="currentColor"
              />
            </svg>
          </span>
          <span class="fm-auth-layout__name">FireMail</span>
        </div>

        <h1 class="fm-auth-layout__tagline">
          Outlook 邮箱池 · 精准取件 · 90 天令牌自动保活
        </h1>

        <ul class="fm-auth-layout__points">
          <li>
            <span class="fm-auth-layout__dot" />
            <span>集中纳管 Outlook、IMAP、Gmail 与 QQ 多类型邮箱资产</span>
          </li>
          <li>
            <span class="fm-auth-layout__dot" />
            <span>90 天 Refresh Token 到期优先自动轮换与健康态势预警</span>
          </li>
          <li>
            <span class="fm-auth-layout__dot" />
            <span>沉浸式安全阅读器，智能识别验证码并一键复制</span>
          </li>
        </ul>

        <footer class="fm-auth-layout__version fm-mono">v{{ appVersion }}</footer>
      </div>
    </aside>

    <main class="fm-auth-layout__main">
      <div class="fm-auth-layout__card">
        <div class="fm-auth-layout__compact-brand">
          <span class="fm-auth-layout__spark" aria-hidden="true">
            <svg viewBox="0 0 24 24" width="20" height="20" fill="none">
              <path
                d="M12.6 2.5C12.9 6.2 16 7.8 16.5 12.2C17.6 11.2 18.2 9.9 18.4 8.6C20.2 10.7 20.8 13.7 19.6 16.6C18.4 19.6 15.5 21.5 12 21.5C7.6 21.5 4.2 18.1 4.2 13.6C4.2 9.5 7.4 6.6 10.6 3.9C11.3 3.3 12 2.8 12.6 2.5Z"
                fill="currentColor"
              />
            </svg>
          </span>
          <span class="fm-auth-layout__compact-name">FireMail</span>
        </div>

        <slot />
      </div>
    </main>
  </div>
</template>

<script setup>
import ThemeToggle from '@/components/shell/ThemeToggle.vue'

const appVersion =
  import.meta.env.VITE_APP_VERSION || (typeof __APP_VERSION__ !== 'undefined' ? __APP_VERSION__ : '1.0.0')
</script>

<style scoped>
.fm-auth-layout {
  position: relative;
  min-height: 100vh;
  display: grid;
  grid-template-columns: 5fr 7fr;
  background: var(--fm-bg);
}

.fm-auth-layout__theme {
  position: fixed;
  top: var(--fm-space-4);
  right: var(--fm-space-4);
  z-index: 20;
}

.fm-auth-layout__brand {
  background: var(--fm-bg-subtle);
  border-right: 1px solid var(--fm-border);
  padding: var(--fm-space-9) var(--fm-space-8);
  display: flex;
  flex-direction: column;
  justify-content: center;
}

.fm-auth-layout__brand-inner {
  max-width: 400px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: var(--fm-space-6);
}

.fm-auth-layout__logo {
  display: inline-flex;
  align-items: center;
  gap: 10px;
}

.fm-auth-layout__spark {
  display: inline-flex;
  color: var(--fm-accent);
}

.fm-auth-layout__name {
  font-size: 20px;
  font-weight: 600;
  letter-spacing: -0.02em;
  color: var(--fm-text);
}

.fm-auth-layout__tagline {
  margin: 0;
  font-size: var(--fm-fs-2xl);
  font-weight: 600;
  line-height: 1.35;
  letter-spacing: -0.025em;
  color: var(--fm-text);
}

.fm-auth-layout__points {
  margin: 0;
  padding: 0;
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: var(--fm-space-3);
  font-size: var(--fm-fs-sm);
  color: var(--fm-text-2);
}

.fm-auth-layout__points li {
  display: flex;
  align-items: flex-start;
  gap: 10px;
}

.fm-auth-layout__dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--fm-accent);
  margin-top: 8px;
  flex-shrink: 0;
}

.fm-auth-layout__version {
  font-size: var(--fm-fs-xs);
  color: var(--fm-text-3);
  padding-top: var(--fm-space-4);
  border-top: 1px solid var(--fm-border);
}

.fm-auth-layout__main {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--fm-space-6) var(--fm-space-4);
}

.fm-auth-layout__card {
  width: 100%;
  max-width: 380px;
  background: var(--fm-surface);
  border: 1px solid var(--fm-border);
  border-radius: var(--fm-radius-xl);
  box-shadow: var(--fm-shadow-md);
  padding: var(--fm-space-7);
}

.fm-auth-layout__compact-brand {
  display: none;
  align-items: center;
  gap: 8px;
  margin-bottom: var(--fm-space-5);
}

.fm-auth-layout__compact-name {
  font-size: 16px;
  font-weight: 600;
  letter-spacing: -0.02em;
  color: var(--fm-text);
}

@media (max-width: 1023.98px) {
  .fm-auth-layout {
    grid-template-columns: 1fr;
  }

  .fm-auth-layout__brand {
    display: none;
  }

  .fm-auth-layout__compact-brand {
    display: inline-flex;
  }
}
</style>
