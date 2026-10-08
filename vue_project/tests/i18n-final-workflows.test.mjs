import assert from 'node:assert/strict'
import { readdirSync, readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import test from 'node:test'

const read = (path) => readFileSync(resolve(process.cwd(), path), 'utf8')

const walkVueFiles = (directory) => readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
  const path = resolve(directory, entry.name)
  return entry.isDirectory() ? walkVueFiles(path) : path.endsWith('.vue') ? [path] : []
})

const phaseThreeFiles = [
  'src/views/AnnotationView.vue',
  'src/views/TranscriptomeOverviewView.vue',
  'src/views/LoginView.vue',
  'src/views/AdminLogin.vue',
  'src/views/AdminDashboard.vue',
  'src/views/AdminDataManager.vue',
  'src/views/AdminFileManager.vue',
  'src/views/CoreVariableBlocks.vue',
  'src/views/CodonCard.vue',
  'src/views/CodonWTool.vue'
]

test('phase three pages use vue-i18n for user-facing copy', () => {
  for (const file of phaseThreeFiles) {
    const source = read(file)
    assert.match(source, /\$t\(|\bt\(/, `${file} should reference localized copy`)
  }
})

test('site templates contain no hardcoded Chinese interface copy', () => {
  for (const file of walkVueFiles(resolve(process.cwd(), 'src'))) {
    const source = readFileSync(file, 'utf8')
    const template = (source.match(/<template>([\s\S]*?)<\/template>/) || [])[1] || ''
    const withoutComments = template
      .replace(/<!--[\s\S]*?-->/g, '')
      .replace(/<el-dropdown-item command="zh">中文<\/el-dropdown-item>/g, '')
      .replace(/value="中国"/g, '')
    assert.doesNotMatch(withoutComments, /[\u3400-\u9fff]/, `${file} should not hardcode Chinese template text`)
  }
})

test('phase three keeps routes and API contracts stable', () => {
  const router = read('src/router/index.js')
  for (const route of ['/genome-card', '/annotation', '/transcriptome-overview', '/login', '/admin/login', '/admin/dashboard', '/core-variable-blocks', '/codon-card', '/tools/codonw']) {
    assert.match(router, new RegExp(route.replaceAll('/', '\\/')), `route ${route} should remain registered`)
  }

  const combined = phaseThreeFiles.map(read).join('\n')
  for (const endpoint of ['/files/query/transcriptome-list/', '/admin/session/', '/admin/files/', '/admin/data-management/list/']) {
    assert.match(combined, new RegExp(endpoint.replaceAll('/', '\\/')), `endpoint ${endpoint} should remain unchanged`)
  }
})

test('admin and tool pages do not expose backend message text directly', () => {
  const sources = [
    read('src/views/AdminLogin.vue'),
    read('src/views/AdminDataManager.vue'),
    read('src/views/AdminFileManager.vue'),
    read('src/views/CodonCard.vue')
  ].join('\n')

  assert.doesNotMatch(sources, /ElMessage\.(?:success|error|warning)\(response(?:\.data)?\.message/, 'backend messages should remain in logs, not localized UI')
})
