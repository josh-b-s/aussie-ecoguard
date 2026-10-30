
import { useState } from 'react'
import Upload from './Upload.jsx'
import Search from './Search.jsx'
import LostPets from './LostPets.jsx'
import Notifications from './Notifications.jsx'
import Chatbot from './Chatbot.jsx'
import DeleteFile from './DeleteFile.jsx'
import Overview from './Overview.jsx'

const sections = {
  Overview: 'Manage your wildlife sightings and explore EcoGuard.',
  Upload: 'Upload images and videos of animal sightings.',
  Search: 'Search for animals using species and tags.',
  'Lost Pets': 'Find potential sightings of missing pets.',
  Notifications: 'Manage your animal sighting email alerts.',
  Chatbot: 'Search for wildlife sightings using natural language.',
}

function Dashboard({ email, idToken }) {
  const [activeSection, setActiveSection] = useState('Overview')

  return (
    <section className="dashboard-content">
      <p>Welcome back, {email ?? 'EcoGuard user'}!</p>

      <div className="dashboard-nav" aria-label="Dashboard sections">
        {Object.keys(sections).map((name) => (
          <button
            key={name}
            type="button"
            className={activeSection === name ? 'active' : ''}
            aria-pressed={activeSection === name}
            onClick={() => setActiveSection(name)}
          >
            {name}
          </button>
        ))}
      </div>

      <div className="dashboard-panel">
        {activeSection !== 'Overview' && (
          <h2>{activeSection}</h2>
        )}

        {activeSection === 'Overview' ? (
          <Overview onNavigate={setActiveSection} />
        ) : activeSection === 'Upload' ? (
          <>
            <Upload idToken={idToken} />

            <details className="delete-file-section">
              <summary>Manage Uploads — Delete a File</summary>
              <DeleteFile idToken={idToken} />
            </details>
          </>
        ) : activeSection === 'Search' ? (
          <Search idToken={idToken} />
        ) : activeSection === 'Lost Pets' ? (
          <LostPets />
        ) : activeSection === 'Notifications' ? (
          <Notifications idToken={idToken} />
        ) : activeSection === 'Chatbot' ? (
          <Chatbot idToken={idToken} />
        ) : (
          <p>{sections[activeSection]}</p>
        )}
      </div>
    </section>
  )
}

export default Dashboard
