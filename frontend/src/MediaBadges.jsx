
function MediaBadges({ file }) {
  const tags = Object.entries(file.tags || {})

  const fileType =
    file.file_type === 'video'
      ? '🎬 Video'
      : file.file_type === 'image'
        ? '📷 Image'
        : '📁 Media'

  return (
    <div className="media-badges">
      <span className="media-type-badge">
        {fileType}
      </span>

      {tags.length > 0 ? (
        tags.map(([animal, count]) => (
          <span key={animal} className="media-tag-badge">
            🐾 {animal.replace(/\b\w/g, (letter) => letter.toUpperCase())}
            {' × '}{count}
          </span>
        ))
      ) : (
        <span className="media-empty-badge">
          No animals detected
        </span>
      )}
    </div>
  )
}

export default MediaBadges
