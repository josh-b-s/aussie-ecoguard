
import { useState } from 'react'
import {
  initImageSearch,
  uploadTemporarySearchImage,
  searchByUploadedImage
} from './searchApi.js'
import MediaBadges from './MediaBadges.jsx'

function ImageSearch({ idToken }) {
  const [selectedFile, setSelectedFile] = useState(null)
  const [results, setResults] = useState(null)
  const [isSearching, setIsSearching] = useState(false)
  const [error, setError] = useState('')

  function handleFileChange(event) {
    setSelectedFile(event.target.files[0] || null)
    setResults(null)
    setError('')
  }

  async function handleSearch(event) {
    event.preventDefault()

    if (!selectedFile) {
      setError('Please select an image.')
      return
    }

    if (!['image/jpeg', 'image/png'].includes(selectedFile.type)) {
      setError('Only JPG and PNG images are supported.')
      return
    }

    if (selectedFile.size === 0 || selectedFile.size > 10 * 1024 * 1024) {
      setError('The image must be smaller than 10 MB.')
      return
    }

    setIsSearching(true)
    setError('')
    setResults(null)

    try {
      const upload = await initImageSearch(selectedFile, idToken)

      await uploadTemporarySearchImage(
        selectedFile,
        upload.uploadUrl
      )

      const data = await searchByUploadedImage(
        upload.imageKey,
        idToken
      )

      setResults(data)
    } catch (err) {
      setError(err.message || 'Image search failed.')
    } finally {
      setIsSearching(false)
    }
  }

  return (
    <section className="search-form">
      <h3>Search by Uploaded Image</h3>

      <p>
        Upload a photo to find existing sightings containing
        the same detected animal species.
      </p>

      <form onSubmit={handleSearch}>
        <label htmlFor="search-image">Choose an image</label>

        <input
          id="search-image"
          type="file"
          accept=".jpg,.jpeg,.png"
          onChange={handleFileChange}
        />

        {selectedFile && (
          <p>Selected: {selectedFile.name}</p>
        )}

        <button type="submit" disabled={isSearching}>
          {isSearching ? 'Searching...' : 'Search by Image'}
        </button>
      </form>

      {error && <p role="alert">{error}</p>}

      {results && (
        <div>
          
<h3>Detected Animals</h3>

<div className="detected-tags">
  {Object.entries(results.detected_tags || {}).length > 0 ? (
    Object.entries(results.detected_tags).map(([animal, count]) => (
      <span key={animal} className="detected-tag">
        {animal.charAt(0).toUpperCase() + animal.slice(1)}
        {' · '}
        {count} detected
      </span>
    ))
  ) : (
    <p>No animals detected.</p>
  )}
</div>


          <h3>Matching Sightings</h3>
          <p>Found {results.total} matching file(s).</p>

          {results.results.map((file) => (
            <div key={file.file_id} className="search-result">
              {file.thumbnail_url && (
                <a
                  href={file.original_url || file.thumbnail_url}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  <img
                    src={file.thumbnail_url}
                    alt="Matching animal sighting"
                    style={{ width: '100%', maxWidth: '260px' }}
                  />
                </a>
              )}

              <MediaBadges file={file} />

              {!file.thumbnail_url && file.original_url && (
                <a
                  href={file.original_url}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  View original media
                </a>
              )}
            </div>
          ))}
        </div>
      )}
    </section>
  )
}

export default ImageSearch
