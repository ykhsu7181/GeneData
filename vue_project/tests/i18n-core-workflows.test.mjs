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

const hasPath = (object, path) => path.split('.').every((segment) => {
  if (!object || !Object.prototype.hasOwnProperty.call(object, segment)) return false
  object = object[segment]
  return true
})

const zhCN = readLocale('zh-CN.js', 'zhCN')
const enUS = readLocale('en-US.js', 'enUS')
const viewNames = ['AccessionCard.vue', 'AccessionDetailTableView.vue', 'DataOverviewView.vue', 'RawDataView.vue']
const sources = Object.fromEntries(viewNames.map((name) => [
  name,
  readFileSync(join(process.cwd(), 'src', 'views', name), 'utf8')
]))

test('stage two static translation references exist in both locales', () => {
  const keyPattern = /(?:\$t|\bt)\(\s*'([^']+)'/g
  for (const [name, source] of Object.entries(sources)) {
    const keys = new Set(Array.from(source.matchAll(keyPattern), (match) => match[1]))
    for (const key of keys) {
      assert.equal(hasPath(zhCN, key), true, `${name} references missing Chinese key ${key}`)
      assert.equal(hasPath(enUS, key), true, `${name} references missing English key ${key}`)
    }
  }
})

test('core workflows no longer render known bilingual or hardcoded UI copy', () => {
  assert.doesNotMatch(sources['RawDataView.vue'], /课题组原始数据 Research Group Raw Data/)
  assert.doesNotMatch(sources['DataOverviewView.vue'], /数据集 \(Dataset\)|组装版本 \(Assembly\)|注释版本 \(Annotation\)/)
  assert.doesNotMatch(sources['DataOverviewView.vue'], /{{\s*category\.en_label\s*}}/)
  assert.doesNotMatch(sources['AccessionDetailTableView.vue'], /label:\s*'基本信息'/)
  for (const source of Object.values(sources)) {
    assert.doesNotMatch(source, /ElMessage\.(?:error|warning|success)\(\s*['"][\u3400-\u9fff]/)
  }
})

test('dynamic labels and messages react through vue-i18n without changing API endpoints', () => {
  assert.match(sources['AccessionDetailTableView.vue'], /labelKey:\s*'page\.accessionDetail\.tabs\./)
  assert.match(sources['AccessionDetailTableView.vue'], /page\.accessionDetail\.assemblyInformation/)
  assert.match(sources['AccessionDetailTableView.vue'], /const submitSearch = async/)
  assert.match(sources['DataOverviewView.vue'], /categoryLabel\(row\.category\)/)
  assert.match(sources['RawDataView.vue'], /t\(`status\.\$\{key\}`\)/)
  assert.match(sources['AccessionCard.vue'], /\/files\/query\/organisms\//)
  assert.match(sources['AccessionDetailTableView.vue'], /\/files\/accessions\//)
  assert.match(sources['DataOverviewView.vue'], /\/files\/query\/data-overview\//)
  assert.match(sources['RawDataView.vue'], /\/files\/query\/raw-data\//)
})
