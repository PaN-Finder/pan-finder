import { useEffect } from 'react'

const UMAMI_SCRIPT_SRC = 'https://cloud.umami.is/script.js'
const UMAMI_SCRIPT_ID = 'umami-analytics-script'
const UMAMI_WEBSITE_ID = process.env.REACT_APP_UMAMI_WEBSITE_ID

function Umami() {
  useEffect(() => {
    if (!UMAMI_WEBSITE_ID) {
      return
    }

    if (document.getElementById(UMAMI_SCRIPT_ID)) {
      return
    }

    const script = document.createElement('script')
    script.id = UMAMI_SCRIPT_ID
    script.defer = true
    script.src = UMAMI_SCRIPT_SRC
    script.dataset.websiteId = UMAMI_WEBSITE_ID
    document.head.appendChild(script)
  }, [])

  return null
}

export default Umami
