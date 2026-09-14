<template>
  <header class="top-nav">
    <div class="top-nav-inner">
      <button class="brand" type="button" aria-label="GeneData home" @click="goTo('/dashboard')">
        <span class="brand-mark" aria-hidden="true">
          <svg viewBox="0 0 64 64">
            <defs>
              <linearGradient id="top-nav-leaf-gradient" x1="0" y1="0" x2="1" y2="1">
                <stop offset="0" stop-color="#0c9b73" />
                <stop offset="1" stop-color="#1e6fe0" />
              </linearGradient>
            </defs>
            <path d="M51 7C33 8 17 16 11 31c-5 12-1 22 7 27 8-22 20-34 33-51Z" fill="url(#top-nav-leaf-gradient)" />
            <path d="M16 52C24 35 34 24 48 14" fill="none" stroke="#fff" stroke-width="3" stroke-linecap="round" />
          </svg>
        </span>
        <div class="brand-copy">
          <strong>GeneData</strong>
          <span>Genomic Data Warehouse</span>
        </div>
      </button>

      <nav class="nav-links" aria-label="Primary navigation">
        <button
          v-for="item in primaryNavItems"
          :key="item.path"
          :class="['nav-link', { 'is-active': isGroupActive(item.groupKey) }]"
          @click="goTo(item.path)"
        >
          <span class="nav-icon">
            <el-icon><component :is="item.icon" /></el-icon>
          </span>
          <span>{{ $t(item.labelKey) }}</span>
        </button>

        <el-dropdown trigger="hover" class="nav-dropdown" popper-class="top-nav-dropdown">
          <div :class="['nav-group-trigger', { 'is-active': isGroupActive('dataOverview') }]">
            <button class="nav-link nav-link-main" @click.stop="goTo(topNavGroups.dataOverview.path)">
              <span class="nav-icon">
                <el-icon><DataAnalysis /></el-icon>
              </span>
              <span>{{ $t(topNavGroups.dataOverview.labelKey) }}</span>
            </button>
            <button class="nav-link nav-link-caret" @click.stop>
              <span class="nav-caret">
                <el-icon><ArrowDown /></el-icon>
              </span>
            </button>
          </div>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item
                v-for="item in topNavGroups.dataOverview.children"
                :key="item.path"
                @click="goTo(item.path)"
              >
                {{ $t(item.labelKey) }}
              </el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>

        <el-dropdown trigger="hover" class="nav-dropdown" popper-class="top-nav-dropdown">
          <button :class="['nav-link', 'nav-link-tools', { 'is-active': isGroupActive('tools') }]" @click.stop>
            <span class="nav-icon">
              <el-icon><Tools /></el-icon>
            </span>
            <span>{{ $t(topNavGroups.tools.labelKey) }}</span>
            <span class="nav-caret">
              <el-icon><ArrowDown /></el-icon>
            </span>
          </button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item
                v-for="item in topNavGroups.tools.children"
                :key="item.path"
                @click="goTo(item.path)"
              >
                {{ $t(item.labelKey) }}
              </el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </nav>

      <div class="nav-actions">
        <el-dropdown @command="emitLanguageChange">
          <button class="action-button action-language">
            <el-icon><Platform /></el-icon>
            <span>{{ currentLanguageLabel }}</span>
          </button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="zh">中文</el-dropdown-item>
              <el-dropdown-item command="en">English</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>

        <span class="user-chip">
          <el-icon><User /></el-icon>
          <span>{{ $t('common.currentUser') }}: root</span>
        </span>

        <button class="logout-button" @click="$emit('logout')">
          <el-icon><SwitchButton /></el-icon>
          <span>{{ $t('common.logout') }}</span>
        </button>
      </div>
    </div>
  </header>
</template>

<script>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  ArrowDown,
  CollectionTag,
  DataAnalysis,
  House,
  Platform,
  SwitchButton,
  Tools,
  User
} from '@element-plus/icons-vue'
import { getTopNavActiveGroup, topNavGroups } from '../config/topNavConfig.mjs'

export default {
  name: 'TopNavBar',
  components: {
    ArrowDown,
    DataAnalysis,
    Platform,
    SwitchButton,
    Tools,
    User
  },
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

    const primaryNavItems = [
      { groupKey: 'home', labelKey: 'nav.home', path: '/dashboard', icon: House },
      { groupKey: 'accession', labelKey: 'nav.accession', path: '/accession-card', icon: CollectionTag }
    ]

    const currentLanguageLabel = computed(() => (props.currentLanguage === 'zh' ? '中文' : 'English'))
    const activeGroupKey = computed(() => getTopNavActiveGroup(route.path))

    const isGroupActive = (groupKey) => activeGroupKey.value === groupKey
    const goTo = (path) => {
      if (route.path !== path) {
        router.push(path)
      }
    }
    const emitLanguageChange = (language) => emit('language-change', language)

    return {
      primaryNavItems,
      topNavGroups,
      currentLanguageLabel,
      isGroupActive,
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
  z-index: 120;
  padding: 0 22px;
  background: rgba(255, 255, 255, 0.97);
  border-bottom: 1px solid #e2ebf4;
  box-shadow: 0 8px 24px rgba(22, 55, 94, 0.06);
  backdrop-filter: blur(14px);
}

.top-nav::after {
  content: '';
  position: absolute;
  inset: auto 0 0;
  height: 1px;
  background: rgba(22, 119, 232, 0.08);
}

.top-nav-inner {
  width: min(1400px, 100%);
  margin: 0 auto;
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  align-items: center;
  gap: 24px;
  min-height: 76px;
}

.brand {
  display: inline-flex;
  align-items: center;
  gap: 14px;
  min-width: 0;
  padding: 0;
  border: 0;
  background: transparent;
  color: inherit;
  font: inherit;
  text-align: left;
  cursor: pointer;
}

.brand-mark {
  width: 40px;
  height: 40px;
  flex: 0 0 40px;
}

.brand-mark svg {
  display: block;
  width: 100%;
  height: 100%;
}

.brand-copy {
  display: flex;
  flex-direction: column;
  min-width: 0;
  color: #0c2346;
}

.brand-copy strong {
  font-size: 24px;
  line-height: 1;
  letter-spacing: -0.035em;
}

.brand-copy span {
  margin-top: 3px;
  font-size: 11px;
  color: #506887;
  letter-spacing: 0.01em;
}

.nav-links {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  min-width: 0;
  overflow-x: auto;
  scrollbar-width: none;
}

.nav-links::-webkit-scrollbar {
  display: none;
}

.nav-link {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  position: relative;
  min-height: 44px;
  padding: 11px 13px;
  border: none;
  border-radius: 8px;
  background: transparent;
  color: #29415f;
  font-size: 14px;
  font-weight: 700;
  cursor: pointer;
  white-space: nowrap;
  transition: background-color 0.2s ease, color 0.2s ease, transform 0.2s ease;
}

.nav-link:hover {
  color: #1268cc;
  background: #f2f7fd;
}

.nav-link.is-active {
  color: #0d65d1;
  background: transparent;
  box-shadow: none;
}

.nav-link.is-active::after {
  content: '';
  position: absolute;
  left: 13px;
  right: 13px;
  bottom: -16px;
  height: 2px;
  border-radius: 2px;
  background: #1677e8;
}

.nav-dropdown,
.nav-group-trigger {
  display: inline-flex;
  align-items: stretch;
}

.nav-group-trigger {
  border-radius: 8px;
  transition: background-color 0.2s ease, box-shadow 0.2s ease;
}

.nav-group-trigger.is-active,
.nav-link-tools.is-active {
  background: transparent;
  box-shadow: none;
}

.nav-group-trigger.is-active .nav-link,
.nav-link-tools.is-active {
  color: #0d65d1;
}

.nav-link-main {
  border-top-right-radius: 0;
  border-bottom-right-radius: 0;
}

.nav-link-caret {
  padding-left: 10px;
  padding-right: 10px;
  border-top-left-radius: 0;
  border-bottom-left-radius: 0;
}

.nav-link-caret,
.nav-link-tools {
  gap: 10px;
}

.nav-link-tools {
  min-width: 106px;
  justify-content: center;
}

.nav-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 18px;
  font-size: 16px;
}

.nav-caret {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
}

.nav-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 10px;
}

.action-button,
.logout-button,
.user-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-height: 40px;
  padding: 9px 12px;
  border-radius: 9px;
  font-size: 13px;
  font-weight: 700;
}

.action-button,
.logout-button {
  border: none;
  cursor: pointer;
}

.action-button {
  border: 1px solid #d3e0ed;
  background: #ffffff;
  color: #29415f;
}

.action-language {
  min-width: 92px;
  justify-content: center;
}

.user-chip {
  background: #f4f8fc;
  color: #526b87;
  white-space: nowrap;
}

.logout-button {
  background: #ffffff;
  color: #315170;
  border: 1px solid #d3e0ed;
}

@media (max-width: 1280px) {
  .top-nav-inner {
    grid-template-columns: auto 1fr;
    padding: 12px 0;
    gap: 10px 20px;
  }

  .nav-links {
    grid-column: 1 / -1;
    grid-row: 2;
    justify-content: flex-start;
  }

  .nav-actions {
    justify-content: flex-end;
  }

  .nav-link.is-active::after {
    bottom: -8px;
  }
}

@media (max-width: 720px) {
  .top-nav {
    padding: 0 12px;
  }

  .top-nav-inner {
    grid-template-columns: 1fr auto;
    min-height: 68px;
  }

  .brand-copy strong {
    font-size: 21px;
  }

  .brand-copy span,
  .user-chip,
  .action-button span,
  .logout-button span {
    display: none;
  }

  .action-language {
    min-width: 40px;
  }

  .nav-link {
    padding: 10px 13px;
    font-size: 13px;
  }
}
</style>
