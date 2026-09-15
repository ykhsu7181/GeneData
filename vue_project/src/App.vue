<template>
  <el-config-provider :locale="elementLocale">
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
  </el-config-provider>
</template>

<script>
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import en from 'element-plus/es/locale/lang/en'

import TopNavBar from '@/components/TopNavBar.vue'

export default {
  name: 'App',
  components: {
    TopNavBar
  },
  setup() {
    const route = useRoute()
    const router = useRouter()
    const { locale, t } = useI18n()

    const currentLanguage = ref(locale.value)
    const elementLocale = computed(() => (currentLanguage.value === 'zh' ? zhCn : en))

    watch(locale, (newLocale) => {
      currentLanguage.value = newLocale
      document.documentElement.lang = newLocale === 'zh' ? 'zh-CN' : 'en'
    }, { immediate: true })

    const isStandaloneRoute = computed(() => route.path === '/login' || route.path.startsWith('/admin'))
    const isDashboardRoute = computed(() => route.path === '/' || route.path === '/dashboard')

    const handleLanguageChange = (language) => {
      locale.value = language
      currentLanguage.value = language
      localStorage.setItem('language', language)

      ElMessage({
        message: t('messages.languageChanged'),
        type: 'success'
      })
    }

    const handleLogout = () => {
      localStorage.removeItem('isLoggedIn')
      ElMessage({
        message: t('messages.logoutSuccess'),
        type: 'success'
      })
      router.push('/login')
    }

    return {
      currentLanguage,
      elementLocale,
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
  --app-bg: #eef4fb;
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
    radial-gradient(circle at top, rgba(28, 86, 197, 0.12), transparent 30%),
    linear-gradient(180deg, #f7fbff 0%, #f4f8fd 30%, var(--app-bg) 100%);
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
  padding: 30px 0 42px;
}

.layout-main-dashboard {
  width: 100%;
  max-width: none;
  padding: 0 0 56px;
}

.layout-footer {
  padding: 18px 20px 28px;
  text-align: center;
  color: #5f6f85;
  font-size: 13px;
  letter-spacing: 0.03em;
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
    padding: 0 0 36px;
  }
}
</style>
