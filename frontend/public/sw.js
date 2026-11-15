// SowSmart service worker: shows alert notifications sent by the backend (Web Push).
self.addEventListener('push', (event) => {
  let data = { title: 'SowSmart alert', body: 'Open SowSmart to see the alert.', url: '/' }
  try {
    data = { ...data, ...event.data.json() }
  } catch {
    /* plain text or empty payload */
  }
  event.waitUntil(
    self.registration.showNotification(data.title, {
      body: data.body,
      tag: data.tag,
      icon: '/favicon.svg',
      badge: '/favicon.svg',
      data: { url: data.url || '/' },
    }),
  )
})

self.addEventListener('notificationclick', (event) => {
  event.notification.close()
  const url = (event.notification.data && event.notification.data.url) || '/'
  event.waitUntil(
    self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then((windows) => {
      for (const w of windows) {
        if ('focus' in w) return w.focus()
      }
      return self.clients.openWindow(url)
    }),
  )
})
