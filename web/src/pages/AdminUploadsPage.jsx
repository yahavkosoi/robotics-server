import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'

import { api } from '../lib/api'
import { useAdminGuard } from '../lib/useAdminGuard'
import { Button } from '../components/ui/button'
import { Card, CardDescription, CardTitle } from '../components/ui/card'
import { UploadBatchTree } from '../components/UploadBatchTree'

function getFilenameFromDisposition(disposition, fallbackFilename = 'download') {
  const utfMatch = disposition.match(/filename\*=UTF-8''([^;]+)/i)
  const quotedMatch = disposition.match(/filename=\"([^\"]+)\"/i)
  const plainMatch = disposition.match(/filename=([^;]+)/i)

  if (utfMatch?.[1]) {
    return decodeURIComponent(utfMatch[1])
  }
  if (quotedMatch?.[1]) {
    return quotedMatch[1]
  }
  if (plainMatch?.[1]) {
    return plainMatch[1].trim()
  }
  return fallbackFilename
}

function saveBlobAs(blob, filename) {
  const objectUrl = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = objectUrl
  anchor.download = filename
  document.body.appendChild(anchor)
  anchor.click()
  document.body.removeChild(anchor)
  setTimeout(() => URL.revokeObjectURL(objectUrl), 1000)
}

function triggerDirectDownload(url, fallbackFilename = 'download') {
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = fallbackFilename
  anchor.style.display = 'none'
  document.body.appendChild(anchor)
  anchor.click()
  document.body.removeChild(anchor)
}

async function copyToClipboard(text) {
  if (navigator.clipboard && navigator.clipboard.writeText) {
    await navigator.clipboard.writeText(text)
    return
  }
  const textArea = document.createElement('textarea')
  textArea.value = text
  document.body.appendChild(textArea)
  textArea.select()
  document.execCommand('copy')
  document.body.removeChild(textArea)
}

async function downloadFile(url, fallbackFilename = 'download') {
  const response = await fetch(url, { credentials: 'include' })
  if (!response.ok) {
    throw new Error(`Download failed (${response.status})`)
  }

  const disposition = response.headers.get('content-disposition') || ''
  const filename = getFilenameFromDisposition(disposition, fallbackFilename)

  const blob = await response.blob()
  saveBlobAs(blob, filename || fallbackFilename)
}

export function AdminUploadsPage() {
  const { admin, loading } = useAdminGuard()

  const [uploads, setUploads] = useState([])
  const [selectedFileIds, setSelectedFileIds] = useState(() => new Set())
  const [error, setError] = useState('')
  const [status, setStatus] = useState('')

  useEffect(() => {
    if (!loading) {
      loadUploads()
    }
  }, [loading])

  const uiOrderedFileIds = useMemo(() => uploads.flatMap((batch) => batch.files.map((file) => file.id)), [uploads])
  const filenamesById = useMemo(() => {
    const map = new Map()
    uploads.forEach((batch) => {
      batch.files.forEach((file) => {
        map.set(file.id, file.original_filename)
      })
    })
    return map
  }, [uploads])

  function getOrderedSelectedIds() {
    return uiOrderedFileIds.filter((id) => selectedFileIds.has(id))
  }

  async function loadUploads() {
    setError('')
    try {
      const data = await api.getAdminUploads()
      setUploads(data.uploads || [])
      setSelectedFileIds((current) => {
        const allowed = new Set((data.uploads || []).flatMap((batch) => batch.files.map((file) => file.id)))
        return new Set([...current].filter((id) => allowed.has(id)))
      })
    } catch (err) {
      setError(err.message)
    }
  }

  function toggleFile(fileId) {
    setSelectedFileIds((current) => {
      const next = new Set(current)
      if (next.has(fileId)) {
        next.delete(fileId)
      } else {
        next.add(fileId)
      }
      return next
    })
  }

  function toggleBatch(batch) {
    const batchIds = batch.files.map((file) => file.id)
    const allSelected = batchIds.every((id) => selectedFileIds.has(id))

    setSelectedFileIds((current) => {
      const next = new Set(current)
      if (allSelected) {
        batchIds.forEach((id) => next.delete(id))
      } else {
        batchIds.forEach((id) => next.add(id))
      }
      return next
    })
  }

  async function downloadSelected() {
    const fileIds = getOrderedSelectedIds()
    if (!fileIds.length) {
      setError('Select at least one file first')
      return
    }
    setError('')
    setStatus('')

    try {
      const data = await api.getDownloadLinks({ file_ids: fileIds })
      const links = data.downloads || []
      if (!links.length) {
        setError('No downloadable files found for this selection')
        return
      }

      for (let index = 0; index < links.length; index += 1) {
        const item = links[index]
        triggerDirectDownload(item.url, item.filename || 'download')
        if (index < links.length - 1) {
          await new Promise((resolve) => setTimeout(resolve, 120))
        }
      }

      setStatus(`Started ${links.length} download(s).`)
    } catch (err) {
      setError(err.message)
    }
  }

  async function copySelected() {
    const fileIds = getOrderedSelectedIds()
    if (!fileIds.length) {
      setError('Select at least one file first')
      return
    }
    setError('')
    setStatus('')

    try {
      const data = await api.buildCopyString({ file_ids: fileIds })
      await copyToClipboard(data.text)
      setStatus('Copied selection string to clipboard.')
    } catch (err) {
      setError(err.message)
    }
  }

  async function deleteSelected() {
    const fileIds = getOrderedSelectedIds()
    if (!fileIds.length) {
      setError('Select at least one file first')
      return
    }
    if (!window.confirm(`Delete ${fileIds.length} selected upload(s)? This cannot be undone.`)) {
      return
    }

    setError('')
    setStatus('')
    try {
      const data = await api.deleteFiles({ file_ids: fileIds })
      const deleted = Number(data?.deleted_count || 0)
      if (!deleted) {
        setError('No selected uploads were deleted')
        return
      }
      setStatus(`Deleted ${deleted} upload(s).`)
      await loadUploads()
    } catch (err) {
      setError(err.message)
    }
  }

  async function downloadSingle(fileId) {
    setError('')
    setStatus('')
    try {
      await downloadFile(`/api/admin/files/${fileId}/download`, filenamesById.get(fileId) || 'download')
      setStatus('File downloaded.')
    } catch (err) {
      setError(err.message)
    }
  }

  async function copySingle(fileId) {
    setError('')
    setStatus('')
    try {
      const data = await api.buildCopyString({ file_ids: [fileId] })
      await copyToClipboard(data.text)
      setStatus('Copied file string to clipboard.')
    } catch (err) {
      setError(err.message)
    }
  }

  async function deleteSingle(fileId) {
    if (!window.confirm('Delete this upload? This cannot be undone.')) {
      return
    }
    setError('')
    setStatus('')
    try {
      const data = await api.deleteFiles({ file_ids: [fileId] })
      const deleted = Number(data?.deleted_count || 0)
      if (!deleted) {
        setError('Upload was already deleted or unavailable')
        return
      }
      setStatus('Upload deleted.')
      await loadUploads()
    } catch (err) {
      setError(err.message)
    }
  }

  if (loading) {
    return <main className="page-shell"><p className="muted">Loading admin session...</p></main>
  }

  return (
    <main className="page-shell">
      <Card>
        <div className="page-topbar">
          <div>
            <CardTitle>Admin Uploads</CardTitle>
            <CardDescription>Signed in as {admin?.username}. Select upload blocks or individual files.</CardDescription>
          </div>
          <div className="row-inline">
            <Button variant="outline" onClick={loadUploads}>Refresh</Button>
            <Link to="/admin/settings"><Button variant="outline">Settings</Button></Link>
            <Link to="/"><Button variant="outline">Back to Uploader</Button></Link>
          </div>
        </div>

        <div className="toolbar">
          <Button onClick={downloadSelected}>Download Selected</Button>
          <Button variant="outline" onClick={copySelected}>Copy Selected</Button>
          <Button variant="outline" onClick={deleteSelected}>Delete Selected</Button>
        </div>

        {error ? <p className="error-text">{error}</p> : null}
        {status ? <p className="ok-text">{status}</p> : null}

        <UploadBatchTree
          uploads={uploads}
          selectedFileIds={selectedFileIds}
          onToggleBatch={toggleBatch}
          onToggleFile={toggleFile}
          onDownloadFile={downloadSingle}
          onCopyFile={copySingle}
          onDeleteFile={deleteSingle}
        />
      </Card>
    </main>
  )
}
