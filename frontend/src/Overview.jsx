
function Overview({ onNavigate }) {
  const features = [
    {
      icon: '📸',
      title: 'Upload Media',
      description: 'Upload images or videos of animal sightings for automatic species detection.',
      section: 'Upload'
    },
    {
      icon: '🔎',
      title: 'Search Sightings',
      description: 'Find animal sightings using species tags, images or thumbnail URLs.',
      section: 'Search'
    },
    {
      icon: '🔔',
      title: 'Notifications',
      description: 'Subscribe to email alerts for the animal species you want to monitor.',
      section: 'Notifications'
    },
    {
      icon: '💬',
      title: 'AI Chatbot',
      description: 'Ask the chatbot about animals and search for matching sightings.',
      section: 'Chatbot'
    }
  ]

  return (
    <div className="overview-page">
      <section className="overview-hero">
        <span className="overview-label">
          PLATFORM OVERVIEW
        </span>

        <h2>Welcome to Aussie EcoGuard</h2>

        <p>
          Help protect Australia's environment by monitoring
          invasive pests, recording animal sightings and
          exploring wildlife data.
        </p>

      </section>

      <section className="overview-features">
        <div className="overview-section-heading">
          <h3>Explore EcoGuard</h3>
          <p>
            Quick access to the tools available on the platform.
          </p>
        </div>

        <div className="overview-grid">
          {features.map((feature) => (
            <button
              key={feature.section}
              type="button"
              className="overview-feature-card"
              onClick={() => onNavigate(feature.section)}
            >
              <span className="overview-feature-icon">
                {feature.icon}
              </span>

              <h4>{feature.title}</h4>
              <p>{feature.description}</p>

              <span className="overview-feature-link">
                Open feature →
              </span>
            </button>
          ))}
        </div>
      </section>

      <section className="overview-lost-pets">
        <div>
          <span className="overview-label">
            IN DEVELOPMENT
          </span>

          <h3>Lost Pet Search</h3>

          <p>
            The Lost Pets section is being connected to
            the animal matching backend.
          </p>
        </div>

        <button
          type="button"
          className="overview-secondary-button"
          onClick={() => onNavigate('Lost Pets')}
        >
          View Lost Pets
        </button>
      </section>
    </div>
  )
}

export default Overview
