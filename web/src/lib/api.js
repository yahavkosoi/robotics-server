const JSON_HEADERS = {
  'Content-Type': 'application/json'
}

async function request(path, options = {}) {
  const response = await fetch(path, {
    credentials: 'include',
    ...options,
    headers: {
      ...(options.body instanceof FormData ? {} : JSON_HEADERS),
      ...(options.headers || {})
    }
  })

  if (!response.ok) {
    let detail = 'Request failed'
    try {
      const payload = await response.json()
      detail = payload.detail || payload.message || detail
    } catch {
      // ignore JSON parsing failure
    }
    throw new Error(detail)
  }

  if (response.status === 204) {
    return null
  }

  const contentType = response.headers.get('content-type') || ''
  if (contentType.includes('application/json')) {
    return response.json()
  }
  return response.text()
}

export const api = {
  request,
  getUploaders: () => request('/api/uploaders'),
  createUploader: (payload) => request('/api/uploaders', { method: 'POST', body: JSON.stringify(payload) }),
  uploadBatch: (formData) => request('/api/upload-batches', { method: 'POST', body: formData }),

  loginAdmin: (payload) => request('/api/admin/login', { method: 'POST', body: JSON.stringify(payload) }),
  logoutAdmin: () => request('/api/admin/logout', { method: 'POST' }),
  getAdminMe: () => request('/api/admin/me'),

  getAdminUploads: () => request('/api/admin/uploads'),
  getDownloadLinks: (payload) => request('/api/admin/files/download-many', { method: 'POST', body: JSON.stringify(payload) }),
  deleteFiles: (payload) => request('/api/admin/files/delete-many', { method: 'POST', body: JSON.stringify(payload) }),
  buildCopyString: (payload) => request('/api/admin/copy-string', { method: 'POST', body: JSON.stringify(payload) }),

  getSettings: () => request('/api/admin/settings'),
  updateSettings: (payload) => request('/api/admin/settings', { method: 'PUT', body: JSON.stringify(payload) }),

  getAdmins: () => request('/api/admin/users'),
  createAdmin: (payload) => request('/api/admin/users', { method: 'POST', body: JSON.stringify(payload) }),
  updateAdmin: (adminId, payload) => request(`/api/admin/users/${adminId}`, { method: 'PATCH', body: JSON.stringify(payload) }),
  deleteAdmin: (adminId) => request(`/api/admin/users/${adminId}`, { method: 'DELETE' }),

  getManagedUploaders: () => request('/api/admin/uploaders'),
  updateManagedUploader: (uploaderId, payload) => request(`/api/admin/uploaders/${uploaderId}`, { method: 'PATCH', body: JSON.stringify(payload) }),
  disableManagedUploader: (uploaderId) => request(`/api/admin/uploaders/${uploaderId}`, { method: 'DELETE' }),

  runLegacyImport: (payload) => request('/api/admin/migrate/import-legacy', { method: 'POST', body: JSON.stringify(payload) })
}
