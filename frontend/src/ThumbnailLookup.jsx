
import { useState } from 'react'
import { findOriginalByThumbnail } from './searchApi.js'

function ThumbnailLookup({ idToken, initialThumbnailUrl = '' }) {
  const [thumbnailUrl, setThumbnailUrl] = useState(initialThumbnailUrl)
  const [result, setResult] = useState(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState('')

  async function handleSubmit(event) {
    event.preventDefault()

    setIsLoading(true)
    setError('')
    setResult(null)

    try {
      const data = await findOriginalByThumbnail(
        thumbnailUrl,
        idToken
      )

      setResult(data)
    } catch (err) {
      setError(err.message || 'Thumbnail lookup failed.')
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <section className="thumbnail-lookup">
      <h3>Find Original by Thumbnail URL</h3>

      <p>
        Enter a thumbnail URL to find its original image.
      </p>

      <form onSubmit={handleSubmit}>
        <label htmlFor="thumbnail-url">
          Thumbnail URL
        </label>

        <input
          id="thumbnail-url"
          type="url"
          placeholder="https://..."
          value={thumbnailUrl}
          onChange={(event) => setThumbnailUrl(event.target.value)}
          required
        />

        <button type="submit" disabled={isLoading}>
          {isLoading ? 'Searching...' : 'Find Original'}
        </button>
      </form>

      {error && <p role="alert">{error}</p>}

      {result && (
        <div>
          <p>Original image found!</p>

          <a
            href={result.original_url}
            target="_blank"
            rel="noopener noreferrer"
          >
            Open Original Image
          </a>
        </div>
      )}
    </section>
  )
}

export default ThumbnailLookup
