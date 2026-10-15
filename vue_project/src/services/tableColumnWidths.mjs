const normalizeWidth = (value, fallback, minimum = 72, maximum = 640) => {
  const number = Number(value)
  if (!Number.isFinite(number)) return fallback
  return Math.min(maximum, Math.max(minimum, Math.round(number)))
}

export const loadColumnWidths = (storageKey, defaults, storage = globalThis.localStorage) => {
  if (!storage) return { ...defaults }
  try {
    const stored = JSON.parse(storage.getItem(storageKey))
    if (!stored || typeof stored !== 'object' || Array.isArray(stored)) return { ...defaults }
    return Object.fromEntries(Object.entries(defaults).map(([key, fallback]) => [
      key,
      normalizeWidth(stored[key], fallback)
    ]))
  } catch (_) {
    return { ...defaults }
  }
}

export const saveColumnWidths = (storageKey, widths, storage = globalThis.localStorage) => {
  if (!storage) return false
  try {
    storage.setItem(storageKey, JSON.stringify(widths))
    return true
  } catch (_) {
    return false
  }
}

export const resizeColumn = (widths, key, width, defaults) => ({
  ...widths,
  [key]: normalizeWidth(width, defaults[key] || 120)
})

export const resetColumnWidths = defaults => ({ ...defaults })
