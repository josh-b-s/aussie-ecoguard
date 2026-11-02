
import { useState } from 'react'
import { searchByTags } from './searchApi.js'
import ThumbnailLookup from './ThumbnailLookup.jsx'
import ImageSearch from './ImageSearch.jsx'
import MediaBadges from './MediaBadges.jsx'
import BulkTagEditor from './BulkTagEditor.jsx'

function Search({ idToken }) {
  const [activeTab, setActiveTab] = useState('species')
  const [species, setSpecies] = useState('')
  const [count, setCount] = useState(1)
  const [secondSpecies, setSecondSpecies] = useState('')
  const [secondCount, setSecondCount] = useState(1)
  const [results, setResults] = useState(null)
  const [isSearching, setIsSearching] = useState(false)
  const [error, setError] = useState('')

  const matchingFiles = Array.isArray(results?.results)
    ? results.results
    : []

  async function handleSearch(event) {
    event.preventDefault()

    const animal = species.trim().toLowerCase()
    const minimumCount = Number(count)
    const secondAnimal = secondSpecies.trim().toLowerCase()

    if (!animal || !Number.isInteger(minimumCount) || minimumCount < 1) {
      setError('Enter a species and a valid minimum count.')
      return
    }

    if (secondAnimal) {
      const secondMinimum = Number(secondCount)

      if (!Number.isInteger(secondMinimum) || secondMinimum < 1) {
        setError('Enter a valid count for the second animal.')
        return
      }

      if (secondAnimal === animal) {
        setError('Choose two different animal species.')
        return
      }
    }

    setIsSearching(true)
    setError('')
    setResults(null)

    try {
      const tags = {
        [animal]: minimumCount
      }

      if (secondAnimal) {
        tags[secondAnimal] = Number(secondCount)
      }

      const data = await searchByTags(tags, idToken)
      setResults(data)
    } catch (err) {
      setError(err.message || 'Search failed.')
    } finally {
      setIsSearching(false)
    }
  }

  return (
    <div className="search-form">
      <p className="search-intro">
        Choose a search method to find animal sightings.
      </p>

      <div
        className="search-method-tabs"
        role="tablist"
        aria-label="Search methods"
      >
        <button
          id="tab-species"
          type="button"
          role="tab"
          aria-selected={activeTab === 'species'}
          aria-controls="panel-species"
          className={activeTab === 'species' ? 'active' : ''}
          onClick={() => setActiveTab('species')}
        >
          Species Search
        </button>

        <button
          id="tab-image"
          type="button"
          role="tab"
          aria-selected={activeTab === 'image'}
          aria-controls="panel-image"
          className={activeTab === 'image' ? 'active' : ''}
          onClick={() => setActiveTab('image')}
        >
          Image Search
        </button>

        <button
          id="tab-thumbnail"
          type="button"
          role="tab"
          aria-selected={activeTab === 'thumbnail'}
          aria-controls="panel-thumbnail"
          className={activeTab === 'thumbnail' ? 'active' : ''}
          onClick={() => setActiveTab('thumbnail')}
        >
          Thumbnail Lookup
        </button>
      </div>

      <section
        id="panel-species"
        role="tabpanel"
        aria-labelledby="tab-species"
        className="search-tab-panel"
        hidden={activeTab !== 'species'}
      >
        <h3>Search by Animal Species</h3>

        <p>
          Find sightings by species and minimum animal count.
        </p>

        <form
          onSubmit={handleSearch}
          className="species-search-form"
        >
          <div className="search-field-grid">
            <div className="search-field">
              <label htmlFor="species">
                Animal species
              </label>

              <input
                id="species"
                type="text"
                placeholder="e.g. fox"
                value={species}
                onChange={(event) => setSpecies(event.target.value)}
                required
              />
            </div>

            <div className="search-field">
              <label htmlFor="count">
                Minimum count
              </label>

              <input
                id="count"
                type="number"
                min="1"
                step="1"
                value={count}
                onChange={(event) => setCount(event.target.value)}
                required
              />
            </div>

            <div className="search-field">
              <label htmlFor="second-species">
                Second animal (optional)
              </label>

              <input
                id="second-species"
                type="text"
                placeholder="e.g. dog"
                value={secondSpecies}
                onChange={(event) =>
                  setSecondSpecies(event.target.value)
                }
              />
            </div>

            {secondSpecies.trim() && (
              <div className="search-field">
                <label htmlFor="second-count">
                  Second animal minimum count
                </label>

                <input
                  id="second-count"
                  type="number"
                  min="1"
                  step="1"
                  value={secondCount}
                  onChange={(event) =>
                    setSecondCount(event.target.value)
                  }
                  required
                />
              </div>
            )}
          </div>

          <button
            type="submit"
            disabled={isSearching}
          >
            {isSearching ? 'Searching...' : 'Search Animals'}
          </button>
        </form>

        {error && (
          <p role="alert" className="search-error">
            {error}
          </p>
        )}

        {results && (
          <div className="species-results">
            <div className="search-results-heading">
              <h3>Search Results</h3>

              <span>
                {results.total ?? matchingFiles.length} matching sighting(s)
              </span>
            </div>

            {matchingFiles.length === 0 ? (
              <p>No matching animal sightings found.</p>
            ) : (
              <div className="search-results-grid">
                {matchingFiles.map((file) => (
                  <article
                    key={file.file_id}
                    className="search-result-card"
                  >
                    {file.thumbnail_url ? (
                      <a
                        href={file.original_url || file.thumbnail_url}
                        target="_blank"
                        rel="noopener noreferrer"
                      >
                        <img
                          src={file.thumbnail_url}
                          alt={`Animal sighting: ${Object.keys(file.tags || {}).join(', ')}`}
                          className="search-result-image"
                          loading="lazy"
                        />
                      </a>
                    ) : (
                      <div className="search-result-placeholder">
                        <span aria-hidden="true">🎬</span>
                        <span>Video sighting</span>
                      </div>
                    )}

                    <div className="search-result-details">
                      <MediaBadges file={file} />

                      {file.original_url && (
                        <a
                          href={file.original_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="search-result-link"
                        >
                          View original media
                        </a>
                      )}
                    </div>
                  </article>
                ))}
              </div>
            )}

            {matchingFiles.length > 0 && (
              <details className="bulk-tag-panel">
                <summary>
                  Edit Tags (Files You Own)
                </summary>

                <p>
                  Select only files you uploaded yourself.
                  The backend verifies ownership before
                  allowing any tag changes.
                </p>

                <BulkTagEditor
                  files={matchingFiles}
                  idToken={idToken}
                />
              </details>
            )}
          </div>
        )}
      </section>

      <section
        id="panel-image"
        role="tabpanel"
        aria-labelledby="tab-image"
        className="search-tab-panel"
        hidden={activeTab !== 'image'}
      >
        <ImageSearch idToken={idToken} />
      </section>

      <section
        id="panel-thumbnail"
        role="tabpanel"
        aria-labelledby="tab-thumbnail"
        className="search-tab-panel"
        hidden={activeTab !== 'thumbnail'}
      >
        <ThumbnailLookup
          key={
            matchingFiles.length === 1
              ? matchingFiles[0].thumbnail_url || 'single-no-thumbnail'
              : 'empty'
          }
          idToken={idToken}
          initialThumbnailUrl={
            matchingFiles.length === 1
              ? matchingFiles[0].thumbnail_url || ''
              : ''
          }
        />
      </section>
    </div>
  )
}

export default Search
