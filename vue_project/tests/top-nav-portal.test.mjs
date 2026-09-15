import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import test from 'node:test'
import assert from 'node:assert/strict'

const source = readFileSync(join(process.cwd(), 'src', 'components', 'TopNavBar.vue'), 'utf8')

test('top navigation uses the GeneData portal brand', () => {
  assert.match(source, /:aria-label="\$t\('common\.goHome'\)"/)
  assert.match(source, /<strong>GeneData<\/strong>/)
  assert.match(source, /\$t\('page\.home\.subtitle'\)/)
  assert.match(source, /id="top-nav-leaf-gradient"/)
})

test('top navigation renders from one configuration source and keeps account actions', () => {
  assert.match(source, /v-for="item in topNavItems"/)
  assert.doesNotMatch(source, /primaryNavItems|topNavGroups/)
  assert.match(source, /@language-change|emitLanguageChange/)
  assert.match(source, /\$emit\('logout'\)/)
})

test('dropdown navigation supports click, keyboard semantics, and menu state', () => {
  assert.match(source, /trigger="click"/)
  assert.match(source, /aria-haspopup="menu"/)
  assert.match(source, /:aria-expanded="String\(isMenuOpen\(item\.key\)\)"/)
  assert.match(source, /@visible-change="setMenuOpen\(item\.key, \$event\)"/)
  assert.match(source, /\.nav-link:focus-visible/)
  assert.doesNotMatch(source, /trigger="hover"/)
})

test('top navigation uses the white portal visual treatment', () => {
  assert.match(source, /background: rgba\(255, 255, 255, 0\.97\);/)
  assert.match(source, /border-bottom: 1px solid #e2ebf4;/)
  assert.match(source, /\.nav-link\.is-active::after/)
  assert.doesNotMatch(source, /rgba\(4, 28, 70/)
})

test('top navigation retains compact mobile actions', () => {
  assert.match(source, /@media \(max-width: 720px\)/)
  assert.match(source, /\.user-chip,[\s\S]*?display: none;/)
  assert.match(source, /\.action-language[\s\S]*?min-width: 40px;/)
})
