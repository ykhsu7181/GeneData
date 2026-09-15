import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import test from 'node:test'
import assert from 'node:assert/strict'

const routerSource = readFileSync(join(process.cwd(), 'src', 'router', 'index.js'), 'utf8')
const viewSource = readFileSync(join(process.cwd(), 'src', 'views', 'AssemblyView.vue'), 'utf8')

test('Assembly has an authenticated standalone route', () => {
  assert.match(
    routerSource,
    /path:\s*'\/assembly'[\s\S]*?component:\s*\(\)\s*=>\s*import\('\.\.\/views\/AssemblyView\.vue'\)[\s\S]*?requiresAuth:\s*true/
  )
})

test('Assembly page is an honest placeholder without data requests or fake records', () => {
  assert.match(viewSource, /\$t\('page\.assembly\.title'\)/)
  assert.match(viewSource, /\$t\('page\.assembly\.description'\)/)
  assert.match(viewSource, /\$t\('page\.assembly\.comingSoon'\)/)
  assert.doesNotMatch(viewSource, /axios|fetch\(|\.get\(|\.post\(|mock|fake|genome-card/i)
})

test('hidden Tools routes remain registered', () => {
  for (const path of ['/core-variable-blocks', '/codon-card', '/tools/codonw']) {
    assert.match(routerSource, new RegExp(`path:\\s*'${path}'`))
  }
})
