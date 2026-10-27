
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
      <p className="upload-description">
        Upload an image or video of an animal sighting.
        EcoGuard will automatically detect animal species.
      </p>

      <div className="upload-card">
        <div className="upload-file-section">
          <label className="upload-field-label" htmlFor="media-file">
            Select your media
          </label>

          <p className="upload-helper">
            Supported formats: JPG, PNG, MP4 and MOV
          </p>

          <input
            id="media-file"
            type="file"
            accept=".jpg,.jpeg,.png,.mp4,.mov"
            onChange={handleFileChange}
            className="upload-file-input"
          />

          <label htmlFor="media-file" className="upload-file-button">
            Choose File
          </label>

          <span className="upload-file-name">
            {selectedFile ? selectedFile.name : 'No file selected'}
          </span>
        </div>

        {selectedFile && (
          <div className="upload-file-details">
            <span className="upload-detail-badge">
              {selectedFile.type.startsWith('image/')
                ? '📷 Image'
                : '🎬 Video'}
            </span>

            <span className="upload-detail-badge">
              {(selectedFile.size / 1024 / 1024).toFixed(2)} MB
            </span>
          </div>
        )}

        <div className="upload-privacy-section">
          <label className="upload-checkbox-label">
            <input
              type="checkbox"
              checked={isPrivate}
              onChange={(event) => setIsPrivate(event.target.checked)}
            />
            <span>Keep this upload private</span>
          </label>

          <p className="upload-helper">
            {isPrivate
              ? 'Only you can access this sighting.'
              : 'This sighting can appear in public searches.'}
          </p>
        </div>

        {selectedFile && (
          <div className="upload-actions">
            <button
              type="button"
              onClick={calculateChecksum}
              disabled={isHashing || isUploading}
              className="upload-secondary-action"
            >
              {isHashing ? 'Calculating...' : 'Calculate SHA-256'}
            </button>

            <button
              type="button"
              onClick={handleUpload}
              disabled={!checksum || isUploading || isHashing}
              className="upload-primary-action"
            >
              {isUploading ? 'Uploading...' : 'Upload to EcoGuard'}
            </button>
          </div>
        )}

        {checksum && (
          <div className="upload-checksum-box">
            <strong>SHA-256 Checksum</strong>
            <p style={{ overflowWrap: 'anywhere' }}>
              {checksum}
            </p>
          </div>
        )}

        {uploadMessage && (
          <p className="upload-success" role="status">
            {uploadMessage}
          </p>
        )}

        {error && (
          <p className="upload-error" role="alert">
            {error}
          </p>
        )}
      </div>
    </div>
  )
}

export default Upload

