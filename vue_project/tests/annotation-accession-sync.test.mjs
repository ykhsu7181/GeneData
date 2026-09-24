import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const source = readFileSync(resolve(process.cwd(), 'src/views/AnnotationView.vue'), 'utf8')

assert.match(
  source,
  /await pushRouteQuery\(buildNormalizedQuery\(\{ accession: value \}\)\);\s*await handleRouteParams\(\);/,
  'Annotation accession selection should immediately resolve hierarchy and load annotation data'
)

assert.match(
  source,
  /requestedAssemblyId[\s\S]*?page\.annotation\.assemblyNotFound/,
  'An invalid Assembly ID should produce an explicit context error'
)

assert.match(
  source,
  /requestedAnnotationId[\s\S]*?page\.annotation\.annotationNotFound/,
  'An invalid Annotation ID should produce an explicit context error'
)

assert.match(
  source,
  /const normalizeAssemblyReturnPath[\s\S]*?const returnToAssembly/,
  'Annotation context should validate and restore its Assembly return path'
)

assert.match(
  source,
  /const useDefaultAnnotation[\s\S]*?buildNormalizedQuery/,
  'Invalid context should offer a default-annotation recovery path'
)

console.log('annotation accession context sync source checks passed')
