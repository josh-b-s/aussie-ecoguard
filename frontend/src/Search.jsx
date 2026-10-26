
import { useState } from 'react'
import { searchByTags } from './searchApi.js'

function Search({ idToken }) {
  const [species, setSpecies] = useState('')
const [count, setCount] = useState(1)

const [secondSpecies, setSecondSpecies] = useState('')
const [secondCount, setSecondCount] = useState(1)

const [results, setResults] = useState(null)
  const [isSearching, setIsSearching] = useState(false)
  const [error, setError] = useState('')

  async function handleSearch(event) {
    event.preventDefault()

    const animal = species.trim().toLowerCase()
    const minimumCount = Number(count)

    if (!animal || !Number.isInteger(minimumCount) || minimumCount < 1) {
      setError('Enter a species and a valid minimum count.')
      return
    }

    setIsSearching(true)
    setError('')
    setResults(null)

   
try {
  const tags = {
    [animal]: minimumCount
  }

  const secondAnimal = secondSpecies.trim().toLowerCase()

  if (secondAnimal) {
    const secondMinimum = Number(secondCount)

    if (!Number.isInteger(secondMinimum) || secondMinimum < 1) {
      throw new Error('Enter a valid count for the second animal.')
    }

    if (secondAnimal === animal) {
      throw new Error('Choose two different animal species.')
    }

    tags[secondAnimal] = secondMinimum
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
      <p>Find animal sightings by species and minimum count.</p>

      <form onSubmit={handleSearch}>
        <label htmlFor="species">Animal species</label>
        <input
          id="species"
          type="text"
          placeholder="e.g. dog, fox, cat"
          value={species}
          onChange={(event) => setSpecies(event.target.value)}
          required
        />

        <label htmlFor="count">Minimum count</label>
        <input
          id="count"
          type="number"
          min="1"
          step="1"
          value={count}
          onChange={(event) => setCount(event.target.value)}
          required
        />
        
<label htmlFor="second-species">
  Second animal species (optional)
</label>

<input
  id="second-species"
  type="text"
  placeholder="e.g. fox"
  value={secondSpecies}
  onChange={(event) => setSecondSpecies(event.target.value)}
/>

{secondSpecies.trim() && (
  <>
    <label htmlFor="second-count">
      Minimum count for second species
    </label>

    <input
      id="second-count"
      type="number"
      min="1"
      step="1"
      value={secondCount}
      onChange={(event) => setSecondCount(event.target.value)}
      required
    />
  </>
)}


        <button type="submit" disabled={isSearching}>
          {isSearching ? 'Searching...' : 'Search Animals'}
        </button>
      </form>

      {error && <p role="alert">{error}</p>}

      {results && (
        <div>
          <h3>Search Results</h3>
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
          alt={`Animal sighting: ${Object.keys(file.tags || {}).join(', ')}`}
          style={{
            width: '100%',
            maxWidth: '260px',
            borderRadius: '12px',
            marginTop: '16px'
          }}
        />
      </a>
    )}

    <p>
      <strong>Type:</strong> {file.file_type}
    </p>

    <p>
      <strong>Tags:</strong> {JSON.stringify(file.tags)}
    </p>

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
    </div>
  )
}

export default Search
