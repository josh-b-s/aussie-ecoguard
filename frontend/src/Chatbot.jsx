
import { useState } from 'react'
import { sendChatMessage } from './chatApi.js'
import { searchByTags } from './searchApi.js'
import MediaBadges from './MediaBadges.jsx'

function Chatbot({ idToken }) {
  const [message, setMessage] = useState('')
  const [messages, setMessages] = useState([])
  const [isSending, setIsSending] = useState(false)
  const [error, setError] = useState('')

  async function handleSend(event) {
    event.preventDefault()

    const cleanMessage = message.trim()

    if (!cleanMessage || isSending) return

    setMessages((current) => [
      ...current,
      { role: 'user', text: cleanMessage }
    ])

    setMessage('')
    setIsSending(true)
    setError('')

    try {
      

const response = await sendChatMessage(cleanMessage, idToken)

let botReply = response.reply || 'I could not understand that request.'
let matchingFiles = []

if (response.intent === 'animal.search') {
  const animalParameter = response.parameters?.animal

  const animal = Array.isArray(animalParameter)
    ? animalParameter[0]
    : animalParameter

  if (typeof animal === 'string' && animal.trim()) {
    const searchResults = await searchByTags(
      { [animal.trim().toLowerCase()]: 1 },
      idToken
    )

    matchingFiles = Array.isArray(searchResults.results)
      ? searchResults.results
      : []

    botReply += ` Found ${searchResults.total ?? matchingFiles.length} matching sighting(s).`
  }
}

setMessages((current) => [
  ...current,
  {
    role: 'bot',
    text: botReply,
    files: matchingFiles
  }
])


setMessages((current) => [
  ...current,
  {
    role: 'bot',
    text: botReply
  }
])

    } catch (err) {
      setError(err.message || 'Could not contact the chatbot.')
    } finally {
      setIsSending(false)
    }
  }

  return (
    <section className="chatbot">
      <h3>EcoGuard Assistant</h3>

      <p>
        Ask questions about animal sightings or lost pets.
      </p>

      <div className="chat-messages" role="log" aria-live="polite">
        {messages.length === 0 && (
          <p>Try asking: "Show me pictures of foxes"</p>
        )}

        {messages.map((item, index) => (
          <div
            key={index}
            className={`chat-message ${item.role}`}
          >
            <strong>
              {item.role === 'user' ? 'You' : 'EcoGuard Assistant'}
            </strong>
            <p>{item.text}</p>
            
{item.files?.length > 0 && (
  <div className="chatbot-results">
    {item.files.map((file) => (
      <div key={file.file_id} className="search-result">
        {file.thumbnail_url && (
          <a
            href={file.original_url || file.thumbnail_url}
            target="_blank"
            rel="noopener noreferrer"
          >
            <img
              src={file.thumbnail_url}
              alt="Animal sighting"
              style={{
                width: '100%',
                maxWidth: '260px',
                borderRadius: '12px'
              }}
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

          </div>
        ))}

        {isSending && <p>Assistant is responding...</p>}
      </div>

      <form onSubmit={handleSend}>
        <label htmlFor="chat-input">Your message</label>

        <input
          id="chat-input"
          type="text"
          placeholder="Ask about animal sightings..."
          value={message}
          onChange={(event) => setMessage(event.target.value)}
          maxLength={256}
          disabled={isSending}
        />

        <button
          type="submit"
          disabled={isSending || !message.trim()}
        >
          {isSending ? 'Sending...' : 'Send Message'}
        </button>
      </form>

      {error && <p role="alert">{error}</p>}
    </section>
  )
}

export default Chatbot
