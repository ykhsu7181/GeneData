import axios from 'axios'

export const fetchPublicFiles = (params, config = {}) =>
  axios.get('/v1/files/', { ...config, params })

export const fetchPublicFileDetail = (fileCode, config = {}) =>
  axios.get(`/v1/files/${encodeURIComponent(fileCode)}/`, config)

export const publicFileManifestUrl = '/gd/api/v1/files/manifest.tsv'
