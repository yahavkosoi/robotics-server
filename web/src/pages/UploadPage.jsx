import { useEffect, useMemo, useRef, useState } from 'react'

import { api } from '../lib/api'
import { Button } from '../components/ui/button'
import { Card, CardDescription, CardTitle } from '../components/ui/card'
import { Input } from '../components/ui/input'
import { SearchableSelect } from '../components/ui/searchable-select'
import { Select } from '../components/ui/select'
import { Textarea } from '../components/ui/textarea'

const NEW_UPLOADER_VALUE = '__new__'
const createId = () =>
  typeof crypto !== 'undefined' && crypto.randomUUID
    ? crypto.randomUUID()
    : `${Date.now()}-${Math.random().toString(16).slice(2)}`

export function UploadPage() {
  const [uploaders, setUploaders] = useState([])
  const [allowedExtensions, setAllowedExtensions] = useState(['.json', '.stl'])
  const [selectedUploader, setSelectedUploader] = useState('')
  const [newUploaderName, setNewUploaderName] = useState('')
  const [newUploaderGrade, setNewUploaderGrade] = useState('')
  const [fileItems, setFileItems] = useState([])
  const [isDragActive, setIsDragActive] = useState(false)
  const [status, setStatus] = useState('')
  const [error, setError] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const fileInputRef = useRef(null)

  useEffect(() => {
    loadUploaders()
  }, [])

  async function loadUploaders() {
    try {
      const data = await api.getUploaders()
      const rows = data.uploaders || []
      const allowed = Array.isArray(data.allowed_extensions) ? data.allowed_extensions : []
      const normalizedAllowed = allowed
        .map((value) => String(value || '').trim().toLowerCase())
        .filter(Boolean)
      setAllowedExtensions(normalizedAllowed)
      setUploaders(rows)
      if (rows.length > 0) {
        setSelectedUploader((current) => current || rows[0].display_name)
      }
    } catch (err) {
      setError(err.message)
    }
  }

  function fileKey(file) {
    return `${file.name}:${file.size}:${file.lastModified}`
  }

  function isAllowedFile(file) {
    if (!allowedExtensions.length) return true
    const lower = file.name.toLowerCase()
    return allowedExtensions.some((ext) => lower.endsWith(ext))
  }

  function appendFiles(nextFiles) {
    if (!nextFiles.length) return

    const invalid = nextFiles.filter((file) => !isAllowedFile(file))
    const valid = nextFiles.filter((file) => isAllowedFile(file))

    if (invalid.length) {
      const allowedLabel = allowedExtensions.length ? allowedExtensions.join(', ') : 'any extension'
      setError(`Only ${allowedLabel} are allowed. Ignored: ${invalid.map((f) => f.name).join(', ')}`)
    } else {
      setError('')
    }

    if (!valid.length) return

    setFileItems((current) => {
      const existingKeys = new Set(current.map((item) => fileKey(item.file)))
      const additions = valid
        .filter((file) => !existingKeys.has(fileKey(file)))
        .map((file) => ({
          id: createId(),
          file,
          description: '',
          version: ''
        }))
      return [...current, ...additions]
    })
  }

  function handleFilesChange(event) {
    const nextFiles = Array.from(event.target.files || [])
    appendFiles(nextFiles)
    event.target.value = ''
  }

  function updateMeta(fileId, key, value) {
    setFileItems((current) => current.map((item) => (item.id === fileId ? { ...item, [key]: value } : item)))
  }

  function removeFile(fileId) {
    setFileItems((current) => current.filter((item) => item.id !== fileId))
  }

  function handleDrop(event) {
    event.preventDefault()
    setIsDragActive(false)
    const droppedFiles = Array.from(event.dataTransfer.files || [])
    appendFiles(droppedFiles)
  }

  const uploaderName = useMemo(() => {
    if (selectedUploader === NEW_UPLOADER_VALUE) {
      return newUploaderName.trim()
    }
    return selectedUploader
  }, [selectedUploader, newUploaderName])

  const uploaderOptions = useMemo(
    () =>
      uploaders.map((uploader) => ({
        key: uploader.id,
        value: uploader.display_name,
        label: uploader.display_name
      })),
    [uploaders]
  )

  const allowedExtensionsText = useMemo(() => {
    if (!allowedExtensions.length) {
      return 'any extension'
    }
    return allowedExtensions.join(', ')
  }, [allowedExtensions])

  async function handleSubmit(event) {
    event.preventDefault()
    setError('')
    setStatus('')

    if (!uploaderName) {
      setError('Uploader name is required')
      return
    }
    if (fileItems.length === 0) {
      setError('Please select at least one file')
      return
    }

    const missing = fileItems.find((item) => !item.description.trim() || !item.version.trim())
    if (missing) {
      setError(`Missing description/version for ${missing.file.name}`)
      return
    }

    const formData = new FormData()
    formData.append('uploader_name', uploaderName)

    if (selectedUploader === NEW_UPLOADER_VALUE) {
      if (!newUploaderGrade) {
        setError('New uploader grade is required')
        return
      }
      formData.append('uploader_grade', newUploaderGrade)
    }

    fileItems.forEach((item) => {
      formData.append('files', item.file)
      formData.append('descriptions', item.description)
      formData.append('versions', item.version)
    })

    try {
      setIsSubmitting(true)
      await api.uploadBatch(formData)
      setStatus('Upload completed successfully.')
      setFileItems([])
      if (selectedUploader === NEW_UPLOADER_VALUE) {
        setSelectedUploader('')
        setNewUploaderName('')
        setNewUploaderGrade('')
      }
      await loadUploaders()
    } catch (err) {
      setError(err.message)
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <main className="page-shell">
      <Card>
        <CardTitle>Robotics Lab Upload Portal</CardTitle>
        <CardDescription>Upload one batch containing multiple files with required metadata.</CardDescription>
        <div className="row-inline" style={{ marginBottom: "1rem" }}>
          <a href="/admin/login"><button type="button" className="btn btn-outline">Admin login</button></a>
        </div>

        <form className="form-grid" onSubmit={handleSubmit}>
          <label className="field">
            <span>Uploader name</span>
            <SearchableSelect
              value={selectedUploader}
              onChange={setSelectedUploader}
              options={uploaderOptions}
              placeholder="Select uploader name"
              searchPlaceholder="Search uploader names..."
              fixedOption={{ value: NEW_UPLOADER_VALUE, label: '+ Create new name' }}
            />
          </label>

          {selectedUploader === NEW_UPLOADER_VALUE ? (
            <div className="field-row">
              <label className="field">
                <span>New name</span>
                <Input value={newUploaderName} onChange={(event) => setNewUploaderName(event.target.value)} />
              </label>
              <label className="field">
                <span>Grade</span>
                <Select value={newUploaderGrade} onChange={(event) => setNewUploaderGrade(event.target.value)}>
                  <option value="">Select grade</option>
                  {[7, 8, 9, 10, 11, 12].map((grade) => (
                    <option key={grade} value={grade}>
                      {grade}
                    </option>
                  ))}
                </Select>
              </label>
            </div>
          ) : null}

          <div className="field">
            <span>Files ({allowedExtensionsText})</span>
            <div
              className={`dropzone ${isDragActive ? 'dropzone-active' : ''}`}
              onDragOver={(event) => {
                event.preventDefault()
                setIsDragActive(true)
              }}
              onDragLeave={() => setIsDragActive(false)}
              onDrop={handleDrop}
            >
              <Input
                ref={fileInputRef}
                className="file-picker-hidden"
                type="file"
                multiple
                accept={allowedExtensions.join(',')}
                onChange={handleFilesChange}
              />
              <p className="dropzone-title">Drag and drop files here</p>
              <p className="dropzone-subtitle">or</p>
              <Button type="button" variant="outline" onClick={() => fileInputRef.current?.click()}>
                Choose files
              </Button>
              <p className="muted">You can add files multiple times. New selections are appended.</p>
            </div>
          </div>

          {fileItems.length ? (
            <div className="file-meta-grid">
              {fileItems.map((item) => (
                <Card key={item.id} className="file-meta-card">
                  <div className="file-meta-head">
                    <CardTitle className="compact-title">{item.file.name}</CardTitle>
                    <Button type="button" variant="outline" onClick={() => removeFile(item.id)}>
                      Remove
                    </Button>
                  </div>
                  <label className="field">
                    <span>Description</span>
                    <Textarea
                      rows={2}
                      value={item.description}
                      onChange={(event) => updateMeta(item.id, 'description', event.target.value)}
                    />
                  </label>
                  <label className="field">
                    <span>Version</span>
                    <Input
                      value={item.version}
                      onChange={(event) => updateMeta(item.id, 'version', event.target.value)}
                      placeholder="example: 1.0.3"
                    />
                  </label>
                </Card>
              ))}
            </div>
          ) : null}

          {error ? <p className="error-text">{error}</p> : null}
          {status ? <p className="ok-text">{status}</p> : null}

          <div className="row-inline">
            <Button type="submit" disabled={isSubmitting}>
              {isSubmitting ? 'Uploading...' : 'Upload Batch'}
            </Button>
          </div>
        </form>
      </Card>
    </main>
  )
}
