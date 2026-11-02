
import { useState } from 'react'
import { deleteMediaFile } from './deleteApi.js'

function DeleteFile({ idToken }) {
  const [fileId, setFileId] = useState('')
  const [confirmation, setConfirmation] = useState('')
  const [isDeleting, setIsDeleting] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  const cleanedFileId = fileId.trim().toLowerCase()
  const isValidFileId = /^[0-9a-f]{64}$/.test(cleanedFileId)
  const canDelete =
    isValidFileId &&
    confirmation === 'DELETE' &&
    !isDeleting

  async function handleDelete(event) {
    event.preventDefault()

    if (!canDelete) return

    setError('')
    setSuccess('')
    setIsDeleting(true)

    try {
      const result = await deleteMediaFile(cleanedFileId, idToken)

      setSuccess(result.message || 'File deleted successfully.')
      setFileId('')
      setConfirmation('')
    } catch (err) {
      setError(err.message || 'Unable to delete file.')
    } finally {
      setIsDeleting(false)
    }
  }

  return (
    <section className="delete-file-panel">
      <h3>Delete an Uploaded File</h3>

      <p>
        Permanently remove one of your uploaded files
        from EcoGuard.
      </p>

      <div className="delete-warning">
        <strong>Important</strong>
        <p>
          Deleting a file removes its original media,
          thumbnail and database record.
          This action cannot be undone.
        </p>
      </div>

      <form onSubmit={handleDelete}>
        <label htmlFor="delete-file-id">
          File ID (SHA-256)
        </label>

        <input
          id="delete-file-id"
          type="text"
          placeholder="Paste the uploaded file's SHA-256 checksum"
          value={fileId}
          onChange={(event) => {
            setFileId(event.target.value)
            setSuccess('')
            setError('')
            setConfirmation('')
          }}
          disabled={isDeleting}
          required
        />

        {fileId.trim() && !isValidFileId && (
          <p className="delete-validation">
            Enter a valid 64-character SHA-256 file ID.
          </p>
        )}

        <label htmlFor="delete-confirmation">
          Type DELETE to confirm
        </label>

        <input
          id="delete-confirmation"
          type="text"
          placeholder="DELETE"
          value={confirmation}
          onChange={(event) =>
            setConfirmation(event.target.value)
          }
          disabled={isDeleting}
          autoComplete="off"
          required
        />

        <button
          type="submit"
          className="delete-button"
          disabled={!canDelete}
        >
          {isDeleting ? 'Deleting...' : 'Delete File Permanently'}
        </button>
      </form>

      {success && (
        <p role="status" className="delete-success">
          {success}
        </p>
      )}

      {error && (
        <p role="alert" className="delete-error">
          {error}
        </p>
      )}
    </section>
  )
}

export default DeleteFile
