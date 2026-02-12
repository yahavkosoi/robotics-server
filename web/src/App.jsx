import { Navigate, Route, Routes } from 'react-router-dom'

import { UploadPage } from './pages/UploadPage'
import { AdminLoginPage } from './pages/AdminLoginPage'
import { AdminUploadsPage } from './pages/AdminUploadsPage'
import { AdminSettingsPage } from './pages/AdminSettingsPage'

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<UploadPage />} />
      <Route path="/admin/login" element={<AdminLoginPage />} />
      <Route path="/admin/uploads" element={<AdminUploadsPage />} />
      <Route path="/admin/settings" element={<AdminSettingsPage />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
