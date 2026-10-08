import axios from 'axios'

export const fetchDataOverview = (params, config = {}) => axios.get('/files/query/data-overview/', { ...config, params })

export const fetchDataFileDetail = (fileId, config = {}) => axios.get(`/files/data-files/${fileId}/detail/`, config)
