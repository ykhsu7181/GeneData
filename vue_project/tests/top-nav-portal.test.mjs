import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import test from 'node:test'
import assert from 'node:assert/strict'

const source = readFileSync(join(process.cwd(), 'src', 'components', 'TopNavBar.vue'), 'utf8')
const appSource = readFileSync(join(process.cwd(), 'src', 'App.vue'), 'utf8')

test('top navigation uses the GeneData portal brand', () => {
  assert.match(source, /:aria-label="\$t\('common\.goHome'\)"/)
  assert.match(source, /<strong>GeneData<\/strong>/)
  assert.match(source, /\$t\('page\.home\.subtitle'\)/)
  assert.match(source, /id="top-nav-leaf-gradient"/)
})

test('top navigation renders from one configuration source and only keeps language switching', () => {
  assert.match(source, /v-for="item in topNavItems"/)
  assert.doesNotMatch(source, /primaryNavItems|topNavGroups/)
  assert.match(source, /@language-change|emitLanguageChange/)
  assert.doesNotMatch(source, /user-chip|logout-button|\$emit\('logout'\)/)
  assert.match(source, /\.nav-links\s*\{[^}]*justify-content: flex-end;/)
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
  assert.match(source, /\.action-language[\s\S]*?min-width: 40px;/)
})

test('top navigation remains one-row and prevents vertical inner scrolling', () => {
  assert.match(source, /\.top-nav\s*\{[\s\S]*?position: fixed;[\s\S]*?top: 0;[\s\S]*?left: 0;[\s\S]*?right: 0;/)
  assert.match(source, /\.top-nav\s*\{[\s\S]*?height: 76px;/)
  assert.match(source, /\.top-nav-inner\s*\{[\s\S]*?height: 76px;/)
  assert.match(source, /\.nav-links\s*\{[\s\S]*?overflow-x: auto;[\s\S]*?overflow-y: hidden;/)
  assert.match(source, /@media \(max-width: 1280px\)[\s\S]*?grid-template-columns: auto minmax\(0, 1fr\) auto;/)
  assert.doesNotMatch(source, /grid-row:\s*2;/)
})

test('fixed top navigation reserves layout space for page content', () => {
  assert.match(appSource, /\.layout-shell\s*\{[\s\S]*?padding-top: 76px;/)
  assert.match(appSource, /@media \(max-width: 720px\)[\s\S]*?\.layout-shell\s*\{[\s\S]*?padding-top: 68px;/)
})
