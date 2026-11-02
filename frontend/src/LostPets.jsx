
import { useState } from 'react'
import { searchForLostPet } from './lostPetsApi.js'

function LostPets({ idToken }) {
  const [species, setSpecies] = useState('')
  const [color, setColor] = useState('')
  const [breed, setBreed] = useState('')
  const [photo, setPhoto] = useState(null)

  const [matches, setMatches] = useState([])
  const [isSearching, setIsSearching] = useState(false)
  const [hasSearched, setHasSearched] = useState(false)
  const [error, setError] = useState('')

  async function handleSearch(event) {
    event.preventDefault()

    setError('')
    setMatches([])
    setHasSearched(false)

    if (!photo) {
      setError('Please select a photo of your missing pet.')
      return
    }

    if (!['image/jpeg', 'image/png'].includes(photo.type)) {
      setError('Please select a JPG or PNG image.')
      return
    }

    if (photo.size === 0 || photo.size > 10 * 1024 * 1024) {
      setError('Image must be between 1 byte and 10 MB.')
      return
    }

    setIsSearching(true)

    try {
      const result = await searchForLostPet(photo, idToken)

      setMatches(
        Array.isArray(result.matches) ? result.matches : []
      )
      setHasSearched(true)
    } catch (err) {
      setError(err.message || 'Lost pet search failed.')
    } finally {
      setIsSearching(false)
    }
  }

  return (
    <section className="search-form">
      <h3>Find a Lost Pet</h3>

      <p>
        Upload a photo of your missing pet to find
        potential matches among recent public sightings.
      </p>

      <form onSubmit={handleSearch}>
        <label htmlFor="pet-species">
          Animal species (optional)
        </label>
        <input
          id="pet-species"
          type="text"
          placeholder="e.g. cat, dog"
          value={species}
          onChange={(event) => setSpecies(event.target.value)}
        />

        <label htmlFor="pet-color">
          Colour (optional)
        </label>
        <input
          id="pet-color"
          type="text"
          placeholder="e.g. orange, brown"
          value={color}
          onChange={(event) => setColor(event.target.value)}
        />

        <label htmlFor="pet-breed">
          Breed (optional)
        </label>
        <input
          id="pet-breed"
          type="text"
          placeholder="e.g. Labrador, Tabby"
          value={breed}
          onChange={(event) => setBreed(event.target.value)}
        />

        <label htmlFor="pet-photo">
          Pet photo (required)
        </label>
        <input
          id="pet-photo"
          type="file"
          accept=".jpg,.jpeg,.png"
          onChange={(event) =>
            setPhoto(event.target.files?.[0] || null)
          }
        />

        <p>
          Matching currently uses the uploaded photo.
          Species, colour and breed are not yet used
          to filter results.
        </p>

        <button
          type="submit"
          disabled={isSearching || !photo}
        >
          {isSearching
            ? 'Finding Potential Matches...'
            : 'Find Potential Matches'}
        </button>
      </form>

      {isSearching && (
        <p role="status">
          Comparing your pet photo with public sightings...
        </p>
      )}

      {error && (
        <p role="alert" className="delete-error">
          {error}
        </p>
      )}

      {hasSearched && (
        <div className="lost-pet-results">
          <h3>Potential Matches</h3>

          <p>
            {matches.length} potential match(es) found.
            Similarity scores do not confirm that
            an animal is your missing pet.
          </p>

          {matches.length === 0 && (
            <p>
              No matching public sightings were found.
              Try again with another photo.
            </p>
          )}

          <div
            style={{
              display: 'grid',
              gridTemplateColumns:
                'repeat(auto-fit, minmax(220px, 1fr))',
              gap: '16px',
              marginTop: '20px'
            }}
          >
            {matches.map((match) => (
              <article
                key={match.file_id}
                style={{
                  padding: '16px',
                  background: '#ffffff',
                  border: '1px solid #dce9df',
                  borderRadius: '12px'
                }}
              >
                {match.thumbnail_url && (
                  <a
                    href={match.thumbnail_url}
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    <img
                      src={match.thumbnail_url}
                      alt="Potential matching animal sighting"
                      loading="lazy"
                      style={{
                        width: '100%',
                        height: '180px',
                        objectFit: 'cover',
                        borderRadius: '8px'
                      }}
                    />
                  </a>
                )}

                <p>
                  <strong>Similarity:</strong>{' '}
                  {typeof match.score === 'number'
                    ? `${Math.round(match.score * 100)}%`
                    : 'Not available'}
                </p>

                <p>
                  <strong>Detected tags:</strong>{' '}
                  {Object.entries(match.tags || {})
                    .map(([tag, count]) => `${tag} × ${count}`)
                    .join(', ') || 'None'}
                </p>

                {match.thumbnail_url && (
                  <a
                    href={match.thumbnail_url}
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    View sighting thumbnail
                  </a>
                )}
              </article>
            ))}
          </div>
        </div>
      )}
    </section>
  )
}

export default LostPets
