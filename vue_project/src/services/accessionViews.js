import axios from 'axios'

const STORAGE_KEY = 'genedata:accession-view-cooldowns:v1'
export const ACCESSION_VIEW_COOLDOWN_MS = 30 * 60 * 1000

const normalizeAccession = value => String(value || '').trim()
const browserSessionStorage = () => (
  typeof window === 'undefined' ? null : window.sessionStorage
)

const loadCooldowns = (storage) => {
  try {
    const parsed = JSON.parse(storage?.getItem(STORAGE_KEY) || '{}')
    return parsed && typeof parsed === 'object' && !Array.isArray(parsed) ? parsed : {}
  } catch (_) {
    return {}
  }
}

export const shouldRecordAccessionView = (
  accession,
  now = Date.now(),
  storage = browserSessionStorage()
) => {
  const normalized = normalizeAccession(accession)
  if (!normalized) return false
  const lastRecordedAt = Number(loadCooldowns(storage)[normalized])
  return !Number.isFinite(lastRecordedAt) || now - lastRecordedAt >= ACCESSION_VIEW_COOLDOWN_MS
}

const saveRecordedView = (accession, now, storage) => {
  if (!storage) return
  try {
    const cooldowns = loadCooldowns(storage)
    cooldowns[accession] = now
    storage.setItem(STORAGE_KEY, JSON.stringify(cooldowns))
  } catch (_) { /* analytics must not block the detail page */ }
}

export const recordAccessionView = async (
  accession,
  { now = Date.now(), storage = browserSessionStorage() } = {}
) => {
  const normalized = normalizeAccession(accession)
  if (!shouldRecordAccessionView(normalized, now, storage)) {
    return { recorded: false, reason: 'cooldown' }
  }
  const response = await axios.post(`/files/accessions/${encodeURIComponent(normalized)}/views/`)
  saveRecordedView(normalized, now, storage)
  return { recorded: true, data: response.data }
}
