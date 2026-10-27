
import { useState } from 'react'

function LostPets() {
  const [species, setSpecies] = useState('')
  const [color, setColor] = useState('')
  const [breed, setBreed] = useState('')
  const [photo, setPhoto] = useState(null)
  const [preview, setPreview] = useState(null)

  function handleSearch(event) {
    event.preventDefault()

    setPreview({
      species: species.trim(),
      color: color.trim(),
      breed: breed.trim(),
      photoName: photo?.name || null
    })
  }

  return (
    <section className="search-form">
      <h3>Find a Lost Pet</h3>
      <p>
        Search public animal sightings using a description
        or a photo of your missing pet.
      </p>

      <form onSubmit={handleSearch}>
        <label htmlFor="pet-species">Animal species</label>
        <input
          id="pet-species"
          type="text"
          placeholder="e.g. cat, dog"
          value={species}
          onChange={(event) => setSpecies(event.target.value)}
          required={!photo}
        />

        <label htmlFor="pet-color">Colour (optional)</label>
        <input
          id="pet-color"
          type="text"
          placeholder="e.g. orange, brown"
          value={color}
          onChange={(event) => setColor(event.target.value)}
        />

        <label htmlFor="pet-breed">Breed (optional)</label>
        <input
          id="pet-breed"
          type="text"
          placeholder="e.g. Labrador, Tabby"
          value={breed}
          onChange={(event) => setBreed(event.target.value)}
        />

        <label htmlFor="pet-photo">Pet photo (optional)</label>
        <input
          id="pet-photo"
          type="file"
          accept=".jpg,.jpeg,.png"
          onChange={(event) =>
            setPhoto(event.target.files[0] || null)
          }
        />

        <button type="submit">Preview Lost Pet Search</button>
      </form>

      {preview && (
        <div role="status">
          <h3>Search Details</h3>
          <p>Species: {preview.species || 'From photo'}</p>
          <p>Colour: {preview.color || 'Any'}</p>
          <p>Breed: {preview.breed || 'Any'}</p>
          <p>Photo: {preview.photoName || 'Not provided'}</p>
          <p>Search API integration is not connected yet.</p>
        </div>
      )}
    </section>
  )
}

export default LostPets
