import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import test from 'node:test'
import assert from 'node:assert/strict'

const heroPath = join(process.cwd(), 'src', 'components', 'DashboardHero.vue')
const source = readFileSync(heroPath, 'utf8')

test('dashboard hero uses compact reference-style title and content', () => {
  assert.match(source, /<h1>\s*基因数据仓库\s*<\/h1>/)
  assert.doesNotMatch(source, /hero-pill-row/)
  assert.doesNotMatch(source, /hero-summary/)
  assert.doesNotMatch(source, /hero-scroll-tip/)
  assert.doesNotMatch(source, /summaryCards/)
})

test('dashboard hero keeps a compact desktop proportion', () => {
  assert.match(source, /\.hero-panel\s*{[\s\S]*?min-height:\s*330px;/)
  assert.match(source, /\.hero-shell\s*{[\s\S]*?padding:\s*32px 0 30px;/)
  assert.match(source, /\.hero-search\s*:deep\(\.el-input__wrapper\)\s*{[\s\S]*?min-height:\s*56px;/)
  assert.match(source, /\.search-button\s*{[\s\S]*?min-height:\s*54px;/)
})
