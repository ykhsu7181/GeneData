const firstValue = value => (Array.isArray(value) ? value[0] : value)
const LOCATION_PATTERN = /^([A-Za-z0-9][A-Za-z0-9._|+~-]{0,254}):([1-9]\d*)-([1-9]\d*)$/
const SAFE_JBROWSE_ID = /^[A-Za-z0-9][A-Za-z0-9._-]{0,254}$/

export const normalizePositiveId = (value) => {
  const normalized = String(firstValue(value) || '').trim()
  return /^[1-9]\d*$/.test(normalized) ? normalized : ''
}

export const normalizeJBrowseLocation = (value) => {
  const normalized = String(firstValue(value) || '').trim()
  if (!normalized || normalized.length > 512) return ''
  const match = normalized.match(LOCATION_PATTERN)
  if (!match) return ''
  const start = Number(match[2])
  const end = Number(match[3])
  if (!Number.isSafeInteger(start) || !Number.isSafeInteger(end) || end < start) return ''
  return `${match[1]}:${start}-${end}`
}

export const buildJBrowseUrl = ({ configUrl, assemblyName = '', loc = '', trackIds = [] }) => {
  const params = new URLSearchParams({ config: configUrl })
  if (loc) {
    if (!SAFE_JBROWSE_ID.test(assemblyName)) return ''
    const safeTracks = trackIds.filter(trackId => SAFE_JBROWSE_ID.test(trackId))
    if (!safeTracks.length || safeTracks.length !== trackIds.length) return ''
    params.set('assembly', assemblyName)
    params.set('loc', loc)
    params.set('tracks', safeTracks.join(','))
  }
  return `/jbrowse2/?${params.toString()}`
}
