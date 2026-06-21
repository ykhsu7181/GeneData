<template>
  <div class="app-shell">
    <router-view v-if="isStandaloneRoute" />

    <div v-else :class="['layout-shell', { 'is-dashboard-route': isDashboardRoute }]">
      <TopNavBar
        :current-language="currentLanguage"
        @language-change="handleLanguageChange"
        @logout="handleLogout"
      />

      <main :class="['layout-main', { 'layout-main-dashboard': isDashboardRoute }]">
        <router-view />
      </main>

      <footer class="layout-footer">
        {{ $t('footer.version') }}
      </footer>
    </div>
  </div>
</template>

<script>
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'

import TopNavBar from '@/components/TopNavBar.vue'

export default {
  name: 'App',
  components: {
    TopNavBar
  },
  setup() {
    const route = useRoute()
    const router = useRouter()
    const { locale } = useI18n()

    const currentLanguage = ref(locale.value)

    watch(locale, (newLocale) => {
      currentLanguage.value = newLocale
    })

    const isStandaloneRoute = computed(() => route.path === '/login' || route.path.startsWith('/admin'))
    const isDashboardRoute = computed(() => route.path === '/' || route.path === '/dashboard')

    const handleLanguageChange = (language) => {
      locale.value = language
      currentLanguage.value = language
      localStorage.setItem('language', language)

      ElMessage({
        message: language === 'zh' ? '已切换到中文' : 'Switched to English',
        type: 'success'
      })
    }

    const handleLogout = () => {
      localStorage.removeItem('isLoggedIn')
      ElMessage({
        message: currentLanguage.value === 'zh' ? '已退出登录' : 'Logged out successfully',
        type: 'success'
      })
      router.push('/login')
    }

    return {
      currentLanguage,
      isStandaloneRoute,
      isDashboardRoute,
      handleLanguageChange,
      handleLogout
    }
  }
}
</script>

<style>
:root {
  --app-bg: #f3f7fb;
  --panel-bg: #ffffff;
  --text-primary: #0f172a;
  --text-secondary: #475569;
  --shell-font: "Source Han Sans SC", "Noto Sans SC", "PingFang SC", "Microsoft YaHei", sans-serif;
}

* {
  box-sizing: border-box;
}

html,
body,
#app {
  width: 100%;
  min-height: 100%;
  margin: 0;
}

body {
  font-family: var(--shell-font);
  color: var(--text-primary);
  background:
    radial-gradient(circle at top, rgba(59, 130, 246, 0.08), transparent 28%),
    linear-gradient(180deg, #f8fbff, var(--app-bg));
}

a {
  text-decoration: none;
}

.app-shell,
.layout-shell {
  min-height: 100vh;
}

.layout-shell {
  display: flex;
  flex-direction: column;
}

.layout-main {
  flex: 1;
  width: min(1480px, calc(100% - 40px));
  margin: 0 auto;
  padding: 28px 0 36px;
}

.layout-main-dashboard {
  width: min(1680px, calc(100% - 32px));
  padding: 0 0 48px;
}

.layout-footer {
  padding: 14px 20px 24px;
  text-align: center;
  color: #64748b;
  font-size: 13px;
}

.empty-page {
  display: grid;
  place-items: center;
  min-height: 320px;
  border-radius: 24px;
  background: var(--panel-bg);
  box-shadow: 0 16px 36px rgba(15, 23, 42, 0.08);
}

.empty-page h2 {
  color: #64748b;
  font-size: 24px;
}

@media (max-width: 720px) {
  .layout-main {
    width: min(100%, calc(100% - 24px));
    padding: 18px 0 28px;
  }

  .layout-main-dashboard {
    width: min(100%, calc(100% - 20px));
    padding: 0 0 36px;
  }
}
</style>
