import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import test from 'node:test'
import {
  loadColumnWidths,
  resetColumnWidths,
  resizeColumn,
  saveColumnWidths
} from '../src/services/tableColumnWidths.mjs'

const source = relativePath => readFileSync(resolve('src', relativePath), 'utf8')

test('column width preferences load, clamp, save, and reset safely', () => {
  const values = new Map([['widths', JSON.stringify({ accession: 40, assembly: 900 })]])
  const storage = {
    getItem: key => values.get(key) || null,
    setItem: (key, value) => values.set(key, value)
  }
  const defaults = { accession: 130, assembly: 220 }

  assert.deepEqual(loadColumnWidths('widths', defaults, storage), { accession: 72, assembly: 640 })
  const resized = resizeColumn(defaults, 'accession', 175.6, defaults)
  assert.equal(resized.accession, 176)
  assert.equal(saveColumnWidths('saved', resized, storage), true)
  assert.deepEqual(JSON.parse(values.get('saved')), resized)
  assert.deepEqual(resetColumnWidths(defaults), defaults)
})

test('Assembly List keeps Accession and Assembly fixed while other columns are selectable and resizable', () => {
  const view = source('views/AssemblyPortalView.vue')
  assert.match(view, /requiredColumnKeys = \['accession', 'assembly'\]/)
  assert.match(view, /requiredColumnKeys, 'species', 'assembly_level'/)
  assert.match(view, /:disabled="column\.required"/)
  assert.match(view, /@header-dragend="handleHeaderDragEnd"/)
  assert.match(view, /ASSEMBLY_COLUMN_WIDTHS_STORAGE_KEY/)
  assert.match(view, /resetColumnWidths/)
})

test('Data List exposes pointer and keyboard column resizing with persisted widths', () => {
  const view = source('views/DataOverviewView.vue')
  const settings = source('components/data-overview/DataOverviewColumnSettings.vue')
  assert.match(view, /class="column-resizer"/)
  assert.match(view, /@pointerdown="startColumnResize/)
  assert.match(view, /@keydown\.left\.prevent="resizeColumnByKeyboard/)
  assert.match(view, /WIDTH_STORAGE_KEY/)
  assert.match(view, /stopColumnResize\(\)/)
  assert.match(settings, /\$emit\('reset-widths'\)/)
})

test('map cluster panel stays inside the map and scrolls overflowing content', () => {
  const drawer = source('components/accession/AccessionClusterPanel.vue')
  for (const field of ['scientific_name', 'longitude', 'latitude', 'country', 'region']) {
    assert.match(drawer, new RegExp(`item\\.${field}`))
  }
  assert.match(drawer, /formatCoordinate/)
  assert.match(drawer, /position:absolute/)
  assert.match(drawer, /width:min\(560px, 33\.333%\)/)
  assert.match(drawer, /max-height:calc\(100% - 24px\)/)
  assert.match(drawer, /overflow-x:hidden/)
  assert.match(drawer, /overflow-y:auto/)
  assert.match(drawer, /scrollbar-width:none/)
  assert.match(drawer, /min-width:0/)
  assert.match(drawer, /th:nth-child\(6\) \{ width:16%; \}/)
})
