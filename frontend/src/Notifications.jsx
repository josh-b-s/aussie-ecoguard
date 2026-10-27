
import { useState } from 'react'
import { subscribeToAlerts } from './notificationsApi.js'

const ANIMALS = [
  'Dog',
  'Cat',
  'Fox',
  'Rabbit',
  'Feral Pig',
  'Cane Toad',
]

function Notifications({ idToken }) {
  const [selectedAnimals, setSelectedAnimals] = useState([])
  const [isSubscribing, setIsSubscribing] = useState(false)
  const [subscriptionMessage, setSubscriptionMessage] = useState('')
  const [subscriptionError, setSubscriptionError] = useState('')

  function toggleAnimal(animal) {
    setSelectedAnimals((current) =>
      current.includes(animal)
        ? current.filter((item) => item !== animal)
        : [...current, animal]
    )

    setSubscriptionMessage('')
    setSubscriptionError('')
  }

  function clearSelections() {
    setSelectedAnimals([])
    setSubscriptionMessage('')
    setSubscriptionError('')
  }

  async function handleSubscribe() {
    if (selectedAnimals.length === 0 || isSubscribing) {
      return
    }

    setIsSubscribing(true)
    setSubscriptionMessage('')
    setSubscriptionError('')

    try {
      await subscribeToAlerts(selectedAnimals, idToken)

      setSubscriptionMessage(
        'Subscription requested! Please check your email to confirm.'
      )
    } catch (err) {
      setSubscriptionError(
        err.message || 'Could not subscribe to alerts.'
      )
    } finally {
      setIsSubscribing(false)
    }
  }

  return (
    <div className="notifications-form">
      <p className="section-text">
        Choose which animals you want to receive email notifications
        about when new sightings are uploaded.
      </p>

      <div className="notification-card">
        <div className="notification-header">
          <div>
            <h3 className="notification-title">
              Animal Sighting Alerts
            </h3>

            <p className="notification-subtext">
              Select one or more species to subscribe to alerts.
            </p>
          </div>

          <div className="notification-summary">
            {selectedAnimals.length} selected
          </div>
        </div>

        <div className="species-grid">
          {ANIMALS.map((animal) => {
            const isSelected = selectedAnimals.includes(animal)

            return (
              <label
                key={animal}
                className={`species-pill ${isSelected ? 'selected' : ''}`}
              >
                <input
                  type="checkbox"
                  checked={isSelected}
                  onChange={() => toggleAnimal(animal)}
                />

                <span>{animal}</span>
              </label>
            )
          })}
        </div>

        <div className="notification-footer">
          <div className="selected-species-wrap">
            {selectedAnimals.length > 0 ? (
              selectedAnimals.map((animal) => (
                <span
                  key={animal}
                  className="selected-species-badge"
                >
                  {animal}
                </span>
              ))
            ) : (
              <span className="no-selection-text">
                No animals selected yet.
              </span>
            )}
          </div>
        </div>

        <div className="notification-actions">
          <button
            type="button"
            className="upload-primary-action"
            onClick={handleSubscribe}
            disabled={
              selectedAnimals.length === 0 || isSubscribing
            }
          >
            {isSubscribing
              ? 'Subscribing...'
              : 'Subscribe to Alerts'}
          </button>

          <button
            type="button"
            className="clear-selection-button"
            onClick={clearSelections}
            disabled={selectedAnimals.length === 0 || isSubscribing}
          >
            Clear all
          </button>
        </div>

        {subscriptionMessage && (
          <p className="upload-success" role="status">
            {subscriptionMessage}
          </p>
        )}

        {subscriptionError && (
          <p className="upload-error" role="alert">
            {subscriptionError}
          </p>
        )}
      </div>
    </div>
  )
}

export default Notifications
