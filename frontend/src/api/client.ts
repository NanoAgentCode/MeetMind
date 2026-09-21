import axios from 'axios'

export const api = axios.create({ baseURL: '/api', timeout: 120_000 })

api.interceptors.response.use(undefined, (error) => {
  if (error.response?.status === 401 && error.config?.url !== '/auth/login') {
    window.dispatchEvent(new Event('meetmind:unauthorized'))
  }
  return Promise.reject(error)
})
