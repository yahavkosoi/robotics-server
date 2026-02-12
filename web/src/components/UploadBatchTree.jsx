import { useEffect, useState } from 'react'

import { Checkbox } from './ui/checkbox'
import { Button } from './ui/button'
import { Badge } from './ui/badge'

function formatDateTime(value) {
  if (!value) return '-'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString()
}

export function UploadBatchTree({
  uploads,
  selectedFileIds,
  onToggleBatch,
  onToggleFile,
  onDownloadFile,
  onCopyFile,
  onDeleteFile
}) {
  const [collapsedBatchIds, setCollapsedBatchIds] = useState(() => new Set())

  useEffect(() => {
    setCollapsedBatchIds((current) => {
      const validIds = new Set(uploads.map((batch) => batch.id))
      return new Set([...current].filter((id) => validIds.has(id)))
    })
  }, [uploads])

  function toggleBatchCollapsed(batchId) {
    setCollapsedBatchIds((current) => {
      const next = new Set(current)
      if (next.has(batchId)) {
        next.delete(batchId)
      } else {
        next.add(batchId)
      }
      return next
    })
  }

  function onBatchHeaderClick(event, batchId) {
    const target = event.target
    if (target instanceof Element && target.closest('[data-no-batch-collapse]')) {
      return
    }
    toggleBatchCollapsed(batchId)
  }

  function onBatchHeaderKeyDown(event, batchId) {
    const target = event.target
    if (target instanceof Element && target.closest('[data-no-batch-collapse]')) {
      return
    }
    if (event.key !== 'Enter' && event.key !== ' ') {
      return
    }
    event.preventDefault()
    toggleBatchCollapsed(batchId)
  }

  function onFileRowClick(event, fileId) {
    const target = event.target
    if (target instanceof Element && target.closest('[data-no-file-row-toggle]')) {
      return
    }
    onToggleFile(fileId)
  }

  function onFileRowKeyDown(event, fileId) {
    if (event.key !== 'Enter' && event.key !== ' ') {
      return
    }
    const target = event.target
    if (target instanceof Element && target.closest('[data-no-file-row-toggle]')) {
      return
    }
    event.preventDefault()
    onToggleFile(fileId)
  }

  if (!uploads.length) {
    return <p className="muted">No uploads yet.</p>
  }

  return (
    <div className="upload-tree">
      {uploads.map((batch) => {
        const fileIds = batch.files.map((file) => file.id)
        const selectedCount = fileIds.filter((id) => selectedFileIds.has(id)).length
        const allSelected = fileIds.length > 0 && selectedCount === fileIds.length
        const partial = selectedCount > 0 && selectedCount < fileIds.length
        const isCollapsed = collapsedBatchIds.has(batch.id)
        const selectLabel = allSelected ? 'Selected' : partial ? 'Partially Selected' : 'Select Upload'

        return (
          <div key={batch.id} className="batch-block">
            <div
              className="batch-header"
              role="button"
              tabIndex={0}
              aria-expanded={!isCollapsed}
              aria-controls={`batch-files-${batch.id}`}
              onClick={(event) => onBatchHeaderClick(event, batch.id)}
              onKeyDown={(event) => onBatchHeaderKeyDown(event, batch.id)}
            >
              <div className="row-inline batch-header-main">
                <button
                  type="button"
                  className={`batch-select-pill ${allSelected ? 'batch-select-pill-on' : ''} ${partial ? 'batch-select-pill-partial' : ''}`}
                  data-no-batch-collapse
                  aria-pressed={allSelected}
                  onClick={() => onToggleBatch(batch)}
                >
                  <Checkbox
                    className="checkbox-strong"
                    checked={allSelected}
                    indeterminate={partial}
                    onClick={(event) => event.stopPropagation()}
                    onChange={() => onToggleBatch(batch)}
                    data-no-batch-collapse
                  />
                  <span>{selectLabel}</span>
                </button>
                <span className="batch-title">{batch.uploader_name}</span>
                <span className="muted">{formatDateTime(batch.created_at)}</span>
              </div>
              <div className="row-inline">
                <Badge tone={selectedCount ? 'active' : 'neutral'}>
                  {selectedCount}/{fileIds.length} selected
                </Badge>
                <span className="muted">{isCollapsed ? 'Collapsed' : 'Expanded'}</span>
              </div>
            </div>

            {!isCollapsed ? (
              <div className="batch-files" id={`batch-files-${batch.id}`}>
                {batch.files.map((file) => {
                  const isSelected = selectedFileIds.has(file.id)

                  return (
                    <div
                      key={file.id}
                      className={`file-row ${isSelected ? 'file-row-selected' : ''}`}
                      role="button"
                      tabIndex={0}
                      aria-pressed={isSelected}
                      onClick={(event) => onFileRowClick(event, file.id)}
                      onKeyDown={(event) => onFileRowKeyDown(event, file.id)}
                    >
                      <div className="row-inline file-main">
                        <span className="file-select-control" data-no-file-row-toggle>
                          <Checkbox
                            className="checkbox-strong"
                            checked={isSelected}
                            onChange={() => onToggleFile(file.id)}
                          />
                        </span>
                        <span className="file-name">{file.original_filename}</span>
                        <span className="muted">v{file.version}</span>
                      </div>
                      <div className="row-inline file-actions" data-no-file-row-toggle>
                        {file.is_deleted ? <Badge tone="danger">Deleted</Badge> : null}
                        {!file.is_deleted ? (
                          <Button variant="outline" onClick={() => onDownloadFile(file.id)}>
                            Download
                          </Button>
                        ) : null}
                        <Button variant="outline" onClick={() => onCopyFile(file.id)}>
                          Copy
                        </Button>
                        {!file.is_deleted ? (
                          <Button variant="outline" onClick={() => onDeleteFile(file.id)}>
                            Delete
                          </Button>
                        ) : null}
                      </div>
                    </div>
                  )
                })}
              </div>
            ) : null}
          </div>
        )
      })}
    </div>
  )
}
