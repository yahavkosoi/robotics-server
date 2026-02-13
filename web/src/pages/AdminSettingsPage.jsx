import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

import { api } from '../lib/api'
import { useAdminGuard } from '../lib/useAdminGuard'
import { Button } from '../components/ui/button'
import { Card, CardDescription, CardTitle } from '../components/ui/card'
import { Checkbox } from '../components/ui/checkbox'
import { Input } from '../components/ui/input'
import { Select } from '../components/ui/select'

function gradeOptions(includeEmpty = false) {
  const values = [7, 8, 9, 10, 11, 12]
  if (includeEmpty) {
    return [<option key="empty" value="">Unset</option>, ...values.map((grade) => <option key={grade} value={grade}>{grade}</option>)]
  }
  return values.map((grade) => (
    <option key={grade} value={grade}>
      {grade}
    </option>
  ))
}

export function AdminSettingsPage() {
  const { admin, loading } = useAdminGuard()

  const [settings, setSettings] = useState(null)
  const [allowedExtensionsText, setAllowedExtensionsText] = useState('')
  const [admins, setAdmins] = useState([])
  const [uploaders, setUploaders] = useState([])

  const [newAdminUsername, setNewAdminUsername] = useState('')
  const [newAdminPassword, setNewAdminPassword] = useState('')

  const [newUploaderName, setNewUploaderName] = useState('')
  const [newUploaderGrade, setNewUploaderGrade] = useState('')

  const [importUsersPath, setImportUsersPath] = useState('/path/to/users.json')
  const [importGroupsPath, setImportGroupsPath] = useState('/path/to/groups.json')

  const [status, setStatus] = useState('')
  const [error, setError] = useState('')

  useEffect(() => {
    if (!loading) {
      loadAll()
    }
  }, [loading])

  async function loadAll() {
    setError('')
    try {
      const [settingsData, adminsData, uploadersData] = await Promise.all([
        api.getSettings(),
        api.getAdmins(),
        api.getManagedUploaders()
      ])
      setSettings(settingsData.settings)
      setAllowedExtensionsText((settingsData.settings.allowed_extensions || []).join(', '))
      setAdmins(adminsData.admins || [])
      setUploaders(uploadersData.uploaders || [])
    } catch (err) {
      setError(err.message)
    }
  }

  async function saveSettings() {
    if (!settings) return
    setError('')
    setStatus('')
    try {
      const payload = {
        ...settings,
        allowed_extensions: allowedExtensionsText
          .split(',')
          .map((value) => value.trim())
          .filter(Boolean)
      }
      const data = await api.updateSettings(payload)
      setSettings(data.settings)
      setAllowedExtensionsText((data.settings.allowed_extensions || []).join(', '))
      setStatus('Settings saved. Restart backend and web dev server to apply changed ports.')
    } catch (err) {
      setError(err.message)
    }
  }

  async function addAdmin() {
    setError('')
    setStatus('')
    try {
      await api.createAdmin({ username: newAdminUsername, password: newAdminPassword })
      setNewAdminUsername('')
      setNewAdminPassword('')
      const data = await api.getAdmins()
      setAdmins(data.admins || [])
      setStatus('Admin created.')
    } catch (err) {
      setError(err.message)
    }
  }

  async function toggleAdminActive(row) {
    setError('')
    setStatus('')
    try {
      await api.updateAdmin(row.id, { is_active: !row.is_active })
      const data = await api.getAdmins()
      setAdmins(data.admins || [])
      setStatus('Admin updated.')
    } catch (err) {
      setError(err.message)
    }
  }

  async function resetAdminPassword(row) {
    const password = window.prompt(`New password for ${row.username}:`)
    if (!password) return

    setError('')
    setStatus('')
    try {
      await api.updateAdmin(row.id, { password })
      setStatus(`Password reset for ${row.username}.`)
    } catch (err) {
      setError(err.message)
    }
  }

  async function removeAdmin(row) {
    if (!window.confirm(`Delete admin ${row.username}?`)) {
      return
    }
    setError('')
    setStatus('')
    try {
      await api.deleteAdmin(row.id)
      const data = await api.getAdmins()
      setAdmins(data.admins || [])
      setStatus('Admin deleted.')
    } catch (err) {
      setError(err.message)
    }
  }

  async function addUploader() {
    setError('')
    setStatus('')
    try {
      await api.createUploader({
        display_name: newUploaderName,
        grade: Number(newUploaderGrade),
        extra_groups: []
      })
      setNewUploaderName('')
      setNewUploaderGrade('')
      const data = await api.getManagedUploaders()
      setUploaders(data.uploaders || [])
      setStatus('Uploader created.')
    } catch (err) {
      setError(err.message)
    }
  }

  function updateUploaderDraft(id, key, value) {
    setUploaders((current) =>
      current.map((row) => {
        if (row.id !== id) return row
        return { ...row, [key]: value }
      })
    )
  }

  async function saveUploader(row) {
    setError('')
    setStatus('')
    try {
      await api.updateManagedUploader(row.id, {
        display_name: row.display_name,
        grade: row.grade === '' ? null : Number(row.grade),
        is_active_for_upload: Boolean(row.is_active_for_upload),
        extra_groups: (row.extra_groups || []).filter(Boolean)
      })
      setStatus(`Updated ${row.display_name}.`)
      const data = await api.getManagedUploaders()
      setUploaders(data.uploaders || [])
    } catch (err) {
      setError(err.message)
    }
  }

  async function disableUploader(row) {
    if (!window.confirm(`Disable uploader ${row.display_name} for future uploads?`)) {
      return
    }
    setError('')
    setStatus('')
    try {
      await api.disableManagedUploader(row.id)
      const data = await api.getManagedUploaders()
      setUploaders(data.uploaders || [])
      setStatus(`${row.display_name} disabled for new uploads.`)
    } catch (err) {
      setError(err.message)
    }
  }

  async function runLegacyImport() {
    setError('')
    setStatus('')
    try {
      const data = await api.runLegacyImport({ users_path: importUsersPath, groups_path: importGroupsPath })
      setStatus(
        `Legacy import complete: imported ${data.report.counts.imported_uploaders}, ` +
          `skipped no-grade ${data.report.counts.skipped_no_grade}, merged groups ${data.report.counts.merged_collision_groups}.`
      )
      await loadAll()
    } catch (err) {
      setError(err.message)
    }
  }

  if (loading || !settings) {
    return <main className="page-shell"><p className="muted">Loading settings...</p></main>
  }

  return (
    <main className="page-shell">
      <Card>
        <div className="page-topbar">
          <div>
            <CardTitle>Admin Settings</CardTitle>
            <CardDescription>Manage server behavior, admins, uploader names, and legacy migration.</CardDescription>
          </div>
          <div className="row-inline">
            <Link to="/admin/uploads"><Button variant="outline">Back to Uploads</Button></Link>
          </div>
        </div>

        {error ? <p className="error-text">{error}</p> : null}
        {status ? <p className="ok-text">{status}</p> : null}

        <section className="section-block">
          <h3>Server Settings</h3>
          <div className="field-row">
            <label className="field">
              <span>Retention days</span>
              <Input
                type="number"
                min={1}
                value={settings.retention_days}
                onChange={(event) => setSettings((current) => ({ ...current, retention_days: Number(event.target.value) }))}
              />
            </label>
            <label className="field">
              <span>Max file size (MB)</span>
              <Input
                type="number"
                min={1}
                value={settings.max_file_size_mb}
                onChange={(event) => setSettings((current) => ({ ...current, max_file_size_mb: Number(event.target.value) }))}
              />
            </label>
          </div>

          <div className="field-row">
            <label className="field">
              <span>Backend port</span>
              <Input
                type="number"
                min={1}
                max={65535}
                value={settings.backend_port ?? 8080}
                onChange={(event) =>
                  setSettings((current) => ({ ...current, backend_port: Number(event.target.value) }))
                }
              />
            </label>
            <label className="field">
              <span>Web port</span>
              <Input
                type="number"
                min={1}
                max={65535}
                value={settings.web_port ?? 5173}
                onChange={(event) =>
                  setSettings((current) => ({ ...current, web_port: Number(event.target.value) }))
                }
              />
            </label>
          </div>

          <label className="field">
            <span>Allowed extensions (comma separated)</span>
            <Input value={allowedExtensionsText} onChange={(event) => setAllowedExtensionsText(event.target.value)} />
          </label>

          <div className="field-row">
            <label className="field">
              <span>Upload access mode</span>
              <Select
                value={settings.upload_access_mode}
                onChange={(event) => setSettings((current) => ({ ...current, upload_access_mode: event.target.value }))}
              >
                <option value="open_lan">Open on LAN</option>
                <option value="shared_password">Shared password</option>
                <option value="disabled">Disabled</option>
              </Select>
            </label>
            <label className="field">
              <span>Shared upload password</span>
              <Input
                value={settings.upload_shared_password || ''}
                onChange={(event) =>
                  setSettings((current) => ({
                    ...current,
                    upload_shared_password: event.target.value
                  }))
                }
              />
            </label>
          </div>

          <Button onClick={saveSettings}>Save Settings</Button>
        </section>

        <section className="section-block">
          <h3>Admin Users</h3>
          <div className="field-row">
            <label className="field">
              <span>Username</span>
              <Input value={newAdminUsername} onChange={(event) => setNewAdminUsername(event.target.value)} />
            </label>
            <label className="field">
              <span>Password</span>
              <Input type="password" value={newAdminPassword} onChange={(event) => setNewAdminPassword(event.target.value)} />
            </label>
            <div className="field fit-end">
              <span>&nbsp;</span>
              <Button onClick={addAdmin}>Add Admin</Button>
            </div>
          </div>

          <div className="table-shell">
            <table>
              <thead>
                <tr>
                  <th>Username</th>
                  <th>Status</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {admins.map((row) => (
                  <tr key={row.id}>
                    <td>{row.username}</td>
                    <td>{row.is_active ? 'Active' : 'Inactive'}</td>
                    <td className="row-inline">
                      <Button variant="outline" onClick={() => toggleAdminActive(row)}>
                        {row.is_active ? 'Deactivate' : 'Activate'}
                      </Button>
                      <Button variant="outline" onClick={() => resetAdminPassword(row)}>Reset Password</Button>
                      <Button variant="outline" onClick={() => removeAdmin(row)}>Delete</Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        <section className="section-block">
          <h3>Uploader Names</h3>
          <div className="field-row">
            <label className="field">
              <span>Display name</span>
              <Input value={newUploaderName} onChange={(event) => setNewUploaderName(event.target.value)} />
            </label>
            <label className="field">
              <span>Grade</span>
              <Select value={newUploaderGrade} onChange={(event) => setNewUploaderGrade(event.target.value)}>
                <option value="">Select</option>
                {gradeOptions(false)}
              </Select>
            </label>
            <div className="field fit-end">
              <span>&nbsp;</span>
              <Button onClick={addUploader}>Add Uploader</Button>
            </div>
          </div>

          <div className="table-shell">
            <table>
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Grade</th>
                  <th>Active</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {uploaders.map((row) => (
                  <tr key={row.id}>
                    <td>
                      <Input
                        value={row.display_name}
                        onChange={(event) => updateUploaderDraft(row.id, 'display_name', event.target.value)}
                      />
                    </td>
                    <td>
                      <Select value={row.grade ?? ''} onChange={(event) => updateUploaderDraft(row.id, 'grade', event.target.value)}>
                        {gradeOptions(true)}
                      </Select>
                    </td>
                    <td>
                      <label className="row-inline">
                        <Checkbox
                          checked={Boolean(row.is_active_for_upload)}
                          onChange={(event) => updateUploaderDraft(row.id, 'is_active_for_upload', event.target.checked)}
                        />
                        <span>{row.is_active_for_upload ? 'Enabled' : 'Disabled'}</span>
                      </label>
                    </td>
                    <td className="row-inline">
                      <Button variant="outline" onClick={() => saveUploader(row)}>Save</Button>
                      <Button variant="outline" onClick={() => disableUploader(row)}>Disable</Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        <section className="section-block">
          <h3>Legacy Import</h3>
          <CardDescription>Import users/groups JSON from your previous server while applying migration rules.</CardDescription>
          <div className="field-row">
            <label className="field">
              <span>Users JSON path</span>
              <Input value={importUsersPath} onChange={(event) => setImportUsersPath(event.target.value)} />
            </label>
            <label className="field">
              <span>Groups JSON path</span>
              <Input value={importGroupsPath} onChange={(event) => setImportGroupsPath(event.target.value)} />
            </label>
          </div>
          <Button onClick={runLegacyImport}>Run Legacy Import</Button>
        </section>
      </Card>
    </main>
  )
}
