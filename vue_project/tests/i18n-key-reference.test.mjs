import assert from 'node:assert/strict'
import { readdirSync, readFileSync } from 'node:fs'
import { extname, join, relative } from 'node:path'
import { runInNewContext } from 'node:vm'
import test from 'node:test'

const readLocale = () => {
  const source = readFileSync(join(process.cwd(), 'src', 'i18n', 'locales', 'zh-CN.js'), 'utf8')
  const start = source.indexOf('const zhCN =') + 'const zhCN ='.length
  const end = source.lastIndexOf('export default zhCN')
  return runInNewContext(`(${source.slice(start, end).trim()})`)
}

const walk = (directory) => readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
  const path = join(directory, entry.name)
  return entry.isDirectory() ? walk(path) : [path]
})

const hasKey = (locale, key) => key.split('.').every((part) => {
  if (!locale || !Object.prototype.hasOwnProperty.call(locale, part)) return false
  locale = locale[part]
  return true
})

test('all static vue-i18n references resolve to locale keys', () => {
  const locale = readLocale()
  const sourceRoot = join(process.cwd(), 'src')
  const files = walk(sourceRoot).filter((file) => ['.vue', '.js'].includes(extname(file)) && !file.includes(`${join('i18n', 'locales')}`))
  const missing = []

  for (const file of files) {
    const source = readFileSync(file, 'utf8')
    for (const match of source.matchAll(/(?:\$t|\bt)\(\s*['"]([^'"]+)['"]/g)) {
      if (!hasKey(locale, match[1])) missing.push(`${relative(sourceRoot, file)}: ${match[1]}`)
    }
  }

  assert.deepEqual(missing, [])
})
