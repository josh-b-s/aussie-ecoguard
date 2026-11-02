
import { useState } from 'react'
import { editBulkTags } from './bulkTagsApi.js'

function BulkTagEditor({ files = [], idToken }) {
  const [selectedIds, setSelectedIds] = useState([])
  const [tagInput, setTagInput] = useState('')
  const [operation, setOperation] = useState(1)
  const [isSaving, setIsSaving] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')

 
const availableFiles = files.filter(
  (file) => file.file_id && file.original_url
)


  const selectedFiles = availableFiles.filter(
    (file) => selectedIds.includes(file.file_id)
  )

  function toggleFile(fileId) {
    setMessage('')
    setError('')

    setSelectedIds((current) => {
      if (current.includes(fileId)) {
        return current.filter((id) => id !== fileId)
      }

      if (current.length >= 50) {
        return current
      }

      return [...current, fileId]
    })
  }

  async function handleSubmit(event) {
    event.preventDefault()

    
const urls = selectedFiles.map(
  (file) => file.original_url
)


    const tags = tagInput
      .split(',')
      .map((tag) => tag.trim())
      .filter(Boolean)

    setIsSaving(true)
    setMessage('')
    setError('')

    try {
      const result = await editBulkTags(
        urls,
        tags,
        operation,
        idToken
      )

      const updated = result.updated || []
      const failed = result.failed || []

      setMessage(
        `${updated.length} file(s) updated successfully.` +
        (failed.length > 0
          ? ` ${failed.length} file(s) failed.`
          : '')
      )

      if (failed.length > 0) {
        setError(
          failed.map((file) =>
            `${file.file_id}: ${file.error}`
          ).join(' | ')
        )
      }

      const updatedIds = new Set(
        updated.map((file) => file.file_id)
      )

      setSelectedIds((current) =>
        current.filter((id) => !updatedIds.has(id))
      )
    } catch (err) {
      setError(err.message || 'Could not update tags.')
    } finally {
      setIsSaving(false)
    }
  }

  return (
    <section className="bulk-tag-editor">
      <h3>Bulk Tag Editing</h3>

      <p>
        Select your uploaded files to add or remove tags.
        You can only modify files that belong to you.
      </p>

      {availableFiles.length === 0 ? (
        <p>Search for animal sightings to select files.</p>
      ) : (
        <div className="bulk-file-list">
          {availableFiles.map((file) => (
            <label key={file.file_id}>
              <input
                type="checkbox"
                checked={selectedIds.includes(file.file_id)}
                onChange={() => toggleFile(file.file_id)}
                disabled={
                  isSaving ||
                  (selectedIds.length >= 50 &&
                    !selectedIds.includes(file.file_id))
                }
              />

              {Object.keys(file.tags || {}).join(', ') || 'Media'}
              {' — '}
              {file.file_id.slice(0, 12)}...
            </label>
          ))}
        </div>
      )}

      <p>{selectedFiles.length} file(s) selected</p>

      <form onSubmit={handleSubmit}>
        <label htmlFor="bulk-tags">Tags</label>

        <input
          id="bulk-tags"
          type="text"
          placeholder="e.g. fox, wildlife"
          value={tagInput}
          onChange={(event) => setTagInput(event.target.value)}
          disabled={isSaving}
          required
        />

        <label htmlFor="bulk-operation">Operation</label>

        <select
          id="bulk-operation"
          value={operation}
          onChange={(event) =>
            setOperation(Number(event.target.value))
          }
          disabled={isSaving}
        >
          <option value={1}>Add tags</option>
          <option value={0}>Remove tags</option>
        </select>

        <button
          type="submit"
          disabled={
            isSaving ||
            selectedFiles.length === 0 ||
            !tagInput.trim()
          }
        >
          {isSaving ? 'Updating...' : 'Update Tags'}
        </button>
      </form>

      {message && <p role="status">{message}</p>}
      {error && <p role="alert">{error}</p>}
    </section>
  )
}

export default BulkTagEditor
