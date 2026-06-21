<template>
  <header class="top-nav">
    <div class="brand" @click="goTo('/dashboard')">
      <div class="brand-mark">GD</div>
      <div class="brand-copy">
        <strong>基因数据仓库系统</strong>
        <span>Gene Data Warehouse</span>
      </div>
    </div>

    <nav class="nav-links">
      <button
        v-for="item in navItems"
        :key="item.path"
        :class="['nav-link', { 'is-active': isActive(item.path) }]"
        @click="goTo(item.path)">
        {{ $t(item.labelKey) }}
      </button>

      <el-dropdown trigger="click" class="tools-dropdown">
        <button :class="['nav-link', { 'is-active': isToolsActive }]">
          {{ $t('nav.tools') }}
        </button>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item @click="goTo('/tools/codonw')">
              {{ $t('nav.codonw') }}
            </el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
    </nav>

    <div class="nav-actions">
      <el-dropdown @command="emitLanguageChange">
        <button class="action-button">
          {{ currentLanguageLabel }}
        </button>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item command="zh">中文</el-dropdown-item>
            <el-dropdown-item command="en">English</el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>

      <span class="user-chip">{{ $t('common.currentUser') }}: root</span>
      <button class="logout-button" @click="$emit('logout')">{{ $t('common.logout') }}</button>
    </div>
  </header>
</template>

<script>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'

export default {
  name: 'TopNavBar',
  props: {
    currentLanguage: {
      type: String,
      default: 'zh'
    }
  },
  emits: ['logout', 'language-change'],
  setup(props, { emit }) {
    const route = useRoute()
    const router = useRouter()

    const navItems = [
      { labelKey: 'nav.home', path: '/dashboard' },
      { labelKey: 'nav.accession', path: '/accession-card' },
      { labelKey: 'nav.dataOverview', path: '/data-overview' },
      { labelKey: 'nav.transcriptomeOverview', path: '/transcriptome-overview' },
      { labelKey: 'nav.genome', path: '/genome-card' },
      { labelKey: 'nav.annotation', path: '/annotation' },
      { labelKey: 'nav.coreVariableBlocks', path: '/core-variable-blocks' },
      { labelKey: 'nav.codon', path: '/codon-card' }
    ]

    const activePathMap = {
      '/': '/dashboard',
      '/dashboard': '/dashboard',
      '/annotation-card': '/annotation',
      '/core-variable-blocks-card': '/core-variable-blocks',
      '/accession-detail': '/accession-card'
    }

    const currentLanguageLabel = computed(() => (props.currentLanguage === 'zh' ? '中文' : 'English'))
    const normalizedActivePath = computed(() => activePathMap[route.path] || route.path)
    const isToolsActive = computed(() => normalizedActivePath.value.startsWith('/tools/'))

    const isActive = (path) => normalizedActivePath.value === path
    const goTo = (path) => {
      if (route.path !== path) {
        router.push(path)
      }
    }
    const emitLanguageChange = (language) => emit('language-change', language)

    return {
      navItems,
      currentLanguageLabel,
      isToolsActive,
      isActive,
      goTo,
      emitLanguageChange
    }
  }
}
</script>

<style scoped>
.top-nav {
  position: sticky;
  top: 0;
  z-index: 50;
  display: grid;
  grid-template-columns: auto 1fr auto;
  align-items: center;
  gap: 24px;
  padding: 14px 28px;
  background:
    linear-gradient(135deg, rgba(7, 36, 89, 0.98), rgba(9, 24, 56, 0.98)),
    radial-gradient(circle at top left, rgba(26, 108, 255, 0.28), transparent 42%);
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  box-shadow: 0 18px 32px rgba(5, 18, 46, 0.26);
  backdrop-filter: blur(12px);
}

.brand {
  display: flex;
  align-items: center;
  gap: 14px;
  cursor: pointer;
}

.brand-mark {
  display: grid;
  place-items: center;
  width: 44px;
  height: 44px;
  border-radius: 14px;
  background: linear-gradient(135deg, #3b82f6, #16a34a);
  color: #fff;
  font-size: 16px;
  font-weight: 700;
  letter-spacing: 0.06em;
}

.brand-copy {
  display: flex;
  flex-direction: column;
  color: #fff;
}

.brand-copy strong {
  font-size: 20px;
  letter-spacing: 0.04em;
}

.brand-copy span {
  font-size: 12px;
  color: rgba(226, 232, 240, 0.82);
}

.nav-links {
  display: flex;
  align-items: center;
  gap: 8px;
  overflow-x: auto;
}

.nav-link {
  padding: 10px 16px;
  border: 0;
  border-radius: 999px;
  background: transparent;
  color: rgba(226, 232, 240, 0.86);
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
  white-space: nowrap;
}

.nav-link:hover,
.nav-link.is-active {
  background: rgba(59, 130, 246, 0.2);
  color: #fff;
}

.tools-dropdown {
  display: inline-flex;
}

.nav-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.action-button,
.logout-button {
  border: 0;
  border-radius: 999px;
  padding: 9px 14px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
}

.action-button {
  background: rgba(255, 255, 255, 0.1);
  color: #fff;
}

.user-chip {
  padding: 9px 14px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.08);
  color: rgba(226, 232, 240, 0.92);
  font-size: 13px;
}

.logout-button {
  background: linear-gradient(135deg, #f59e0b, #ea580c);
  color: #fff;
}

@media (max-width: 1200px) {
  .top-nav {
    grid-template-columns: 1fr;
    gap: 16px;
  }

  .nav-actions {
    justify-content: flex-end;
  }
}

@media (max-width: 720px) {
  .top-nav {
    padding: 16px 18px;
  }

  .brand-copy strong {
    font-size: 18px;
  }

  .nav-actions {
    flex-wrap: wrap;
    justify-content: flex-start;
  }
}
</style>
