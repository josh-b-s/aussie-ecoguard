
import { useState } from 'react'
import { uploadFileToS3 } from './uploadApi.js'
function Upload({ idToken }) {
  const [selectedFile, setSelectedFile] = useState(null)
  const [isPrivate, setIsPrivate] = useState(false)
  const [checksum, setChecksum] = useState('')
  const [isHashing, setIsHashing] = useState(false)
  const [error, setError] = useState('')
  const [isUploading, setIsUploading] = useState(false)
const [uploadMessage, setUploadMessage] = useState('')

  function handleFileChange(event) {
    setUploadMessage('')
    const file = event.target.files[0]

    setSelectedFile(file || null)
    setChecksum('')
    setError('')
  }

  async function calculateChecksum() {
    if (!selectedFile) return

    setIsHashing(true)
    setError('')

    try {
      const buffer = await selectedFile.arrayBuffer()

      const hashBuffer = await crypto.subtle.digest(
        'SHA-256',
        buffer
      )

      const hashArray = Array.from(
        new Uint8Array(hashBuffer)
      )

      const hash = hashArray
        .map((byte) => byte.toString(16).padStart(2, '0'))
        .join('')

      setChecksum(hash)
    } catch {
      setError('Could not calculate the file checksum.')
    } finally {
      setIsHashing(false)
    }
  }
  
async function handleUpload() {
  if (!selectedFile || !checksum) {
    setError('Please select a file and calculate its checksum.')
    return
  }

  setIsUploading(true)
  setError('')
  setUploadMessage('')

  try {
    const result = await uploadFileToS3(
      selectedFile,
      checksum,
      idToken,
      isPrivate
    )

    if (result.duplicate) {
      setUploadMessage('This file already exists in EcoGuard.')
    } else {
      setUploadMessage(
        'File uploaded successfully! Animal detection is processing.'
      )
    }
  } catch (error) {
    setError(error.message || 'Upload failed.')
  } finally {
    setIsUploading(false)
  }
}

  return (
    <div className="upload-form">
      <p>
        Upload an image or video of an animal sighting.
        EcoGuard will automatically detect animal species.
      </p>

      <label htmlFor="media-file">Choose a file</label>

      <input
        id="media-file"
        type="file"
        accept=".jpg,.jpeg,.png,.mp4,.mov"
        onChange={handleFileChange}
      />

      {selectedFile && (
        <div>
          <p>
            <strong>Selected file:</strong> {selectedFile.name}
          </p>

          <p>
            <strong>Size:</strong>{' '}
            {(selectedFile.size / 1024 / 1024).toFixed(2)} MB
          </p>

          <button
            type="button"
            onClick={calculateChecksum}
            disabled={isHashing}
          >
            {isHashing ? 'Calculating...' : 'Calculate SHA-256'}
          </button>
        </div>
      )}

      {checksum && (
        <div>
          <p><strong>SHA-256 checksum:</strong></p>
          <p style={{ overflowWrap: 'anywhere' }}>
            {checksum}
          </p>
        </div>
      )}
        
{selectedFile && (
  <button
    type="button"
    onClick={handleUpload}
    disabled={!checksum || isUploading || isHashing}
  >
    {isUploading ? 'Uploading...' : 'Upload to EcoGuard'}
  </button>
)}

{uploadMessage && (
  <p role="status">{uploadMessage}</p>
)}

      {error && <p role="alert">{error}</p>}

      <label>
        <input
          type="checkbox"
          checked={isPrivate}
          onChange={(event) => setIsPrivate(event.target.checked)}
        />
        Keep this upload private
      </label>

      <p>Visibility: {isPrivate ? 'Private' : 'Public'}</p>
    </div>
  )
}

export default Upload
