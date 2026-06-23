<template>
  <header class="top-nav">
    <div class="top-nav-inner">
      <div class="brand" @click="goTo('/dashboard')">
        <div class="brand-mark">
          <span class="brand-mark-core">GD</span>
        </div>
        <div class="brand-copy">
          <strong>基因数据仓库系统</strong>
          <span>Gene Data Warehouse</span>
        </div>
      </div>

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
  padding: 0 18px;
  background: linear-gradient(180deg, rgba(4, 28, 70, 0.985), rgba(7, 34, 82, 0.965));
  box-shadow: 0 12px 28px rgba(7, 24, 58, 0.26);
}

.top-nav::after {
  content: '';
  position: absolute;
  inset: auto 0 0;
  height: 1px;
  background: rgba(255, 255, 255, 0.08);
}

.top-nav-inner {
  width: min(1680px, 100%);
  margin: 0 auto;
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  align-items: center;
  gap: 24px;
  min-height: 78px;
}

.brand {
  display: inline-flex;
  align-items: center;
  gap: 14px;
  min-width: 0;
  cursor: pointer;
}

.brand-mark {
  display: grid;
  place-items: center;
  width: 44px;
  height: 44px;
  border-radius: 14px;
  background: linear-gradient(135deg, #2f7cf6 0%, #1e40af 100%);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.18);
}

.brand-mark-core {
  color: #ffffff;
  font-size: 17px;
  font-weight: 800;
  letter-spacing: 0.08em;
}

.brand-copy {
  display: flex;
  flex-direction: column;
  min-width: 0;
  color: #ffffff;
}

.brand-copy strong {
  font-size: 15px;
  line-height: 1.2;
  letter-spacing: 0.04em;
}

.brand-copy span {
  margin-top: 3px;
  font-size: 11px;
  color: rgba(226, 232, 240, 0.76);
  letter-spacing: 0.08em;
}

.nav-links {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
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
  padding: 11px 14px;
  border: none;
  border-radius: 14px;
  background: transparent;
  color: rgba(226, 232, 240, 0.9);
  font-size: 14px;
  font-weight: 700;
  cursor: pointer;
  white-space: nowrap;
  transition: background-color 0.2s ease, color 0.2s ease, transform 0.2s ease;
}

.nav-link:hover {
  color: #ffffff;
  background: rgba(255, 255, 255, 0.08);
}

.nav-link.is-active {
  color: #ffffff;
  background: linear-gradient(135deg, #2d68e3 0%, #1d4ed8 100%);
  box-shadow: 0 10px 20px rgba(15, 76, 197, 0.28);
}

.nav-dropdown,
.nav-group-trigger {
  display: inline-flex;
  align-items: stretch;
}

.nav-group-trigger {
  border-radius: 14px;
  transition: background-color 0.2s ease, box-shadow 0.2s ease;
}

.nav-group-trigger.is-active,
.nav-link-tools.is-active {
  background: linear-gradient(135deg, #2d68e3 0%, #1d4ed8 100%);
  box-shadow: 0 10px 20px rgba(15, 76, 197, 0.28);
}

.nav-group-trigger.is-active .nav-link,
.nav-link-tools.is-active {
  color: #ffffff;
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
  padding: 9px 14px;
  border-radius: 12px;
  font-size: 13px;
  font-weight: 700;
}

.action-button,
.logout-button {
  border: none;
  cursor: pointer;
}

.action-button {
  background: rgba(255, 255, 255, 0.08);
  color: #ffffff;
}

.action-language {
  min-width: 92px;
  justify-content: center;
}

.user-chip {
  background: rgba(255, 255, 255, 0.08);
  color: rgba(241, 245, 249, 0.92);
  white-space: nowrap;
}

.logout-button {
  background: rgba(187, 247, 208, 0.16);
  color: #f8fafc;
  border: 1px solid rgba(255, 255, 255, 0.12);
}

@media (max-width: 1360px) {
  .top-nav-inner {
    grid-template-columns: 1fr;
    padding: 12px 0;
    gap: 14px;
  }

  .nav-links {
    justify-content: flex-start;
  }

  .nav-actions {
    justify-content: flex-start;
    flex-wrap: wrap;
  }
}

@media (max-width: 720px) {
  .top-nav {
    padding: 0 12px;
  }

  .top-nav-inner {
    min-height: 72px;
  }

  .brand-copy strong {
    font-size: 14px;
  }

  .nav-link {
    padding: 10px 13px;
    font-size: 13px;
  }
}
</style>
