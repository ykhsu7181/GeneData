import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { runInNewContext } from 'node:vm'
import test from 'node:test'
import assert from 'node:assert/strict'

const readLocale = (filename, identifier) => {
  const source = readFileSync(join(process.cwd(), 'src', 'i18n', 'locales', filename), 'utf8')
  const assignment = `const ${identifier} =`
  const start = source.indexOf(assignment) + assignment.length
  const end = source.lastIndexOf(`export default ${identifier}`)
  return runInNewContext(`(${source.slice(start, end).trim()})`)
}

const zhCN = readLocale('zh-CN.js', 'zhCN')
const enUS = readLocale('en-US.js', 'enUS')

const flattenKeys = (value, prefix = '') => Object.entries(value).flatMap(([key, child]) => {
  const path = prefix ? `${prefix}.${key}` : key
  if (child && typeof child === 'object' && !Array.isArray(child)) return flattenKeys(child, path)
  return [path]
})

test('Chinese and English locale files expose identical keys', () => {
  assert.deepEqual(flattenKeys(zhCN).sort(), flattenKeys(enUS).sort())
})

test('approved portal labels stay stable in both locales', () => {
  assert.deepEqual(Object.values(zhCN.page.home.stats).slice(0, 4), ['基因组', '物种', '注释', '品种'])
  assert.deepEqual(Object.values(enUS.page.home.stats).slice(0, 4), ['Assemblies', 'Species', 'Annotations', 'Accessions'])
  assert.equal(zhCN.page.home.stats.slogan, '开放数据 • 开放科学 • 共创未来')
  assert.deepEqual(
    [zhCN.nav.home, zhCN.nav.accession, zhCN.nav.assembly, zhCN.nav.data, zhCN.nav.more],
    ['首页', '品种信息', '基因组', '数据资源', '更多']
  )
  assert.deepEqual(
    [enUS.nav.home, enUS.nav.accession, enUS.nav.assembly, enUS.nav.data, enUS.nav.more],
    ['Home', 'Accession', 'Assembly', 'Data', 'More']
  )
  assert.equal(zhCN.page.accessionDetail.breadcrumb, '首页 / 品种信息 / {accession}')
  assert.equal(zhCN.page.accessionSearch.placeholder, '搜索品种编号 / 物种 / 亚群，例如 IR64')
})

test('i18n bootstrap preserves locale ids and uses split locale modules', () => {
  const source = readFileSync(join(process.cwd(), 'src', 'i18n', 'index.js'), 'utf8')
  assert.match(source, /import zhCN from '\.\/locales\/zh-CN\.js'/)
  assert.match(source, /import enUS from '\.\/locales\/en-US\.js'/)
  assert.match(source, /locale: localStorage\.getItem\('language'\) \|\| 'zh'/)
  assert.match(source, /zh: zhCN[\s\S]*?en: enUS/)
})

test('application synchronizes vue-i18n, Element Plus, and document language', () => {
  const source = readFileSync(join(process.cwd(), 'src', 'App.vue'), 'utf8')
  assert.match(source, /<el-config-provider :locale="elementLocale">/)
  assert.match(source, /element-plus\/es\/locale\/lang\/zh-cn/)
  assert.match(source, /element-plus\/es\/locale\/lang\/en/)
  assert.match(source, /document\.documentElement\.lang/)
  assert.match(source, /t\('messages\.languageChanged'\)/)
  assert.doesNotMatch(source, /t\('messages\.logoutSuccess'\)/)
  assert.doesNotMatch(source, /layout-footer|footer\.version/)
  assert.match(source, /\.layout-main-dashboard\s*\{[^}]*padding: 0;/)
})
