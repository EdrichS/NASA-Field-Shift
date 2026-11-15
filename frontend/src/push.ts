// Browser push opt-in: register the service worker, subscribe with the backend's public VAPID
// key, and send the subscription to the backend. Needs HTTPS (or localhost).
import { pushKey, savePushSubscription } from './api'

export function pushSupported() {
  return 'serviceWorker' in navigator && 'PushManager' in window && 'Notification' in window
}

function keyBytes(base64url: string) {
  const padded = base64url.replace(/-/g, '+').replace(/_/g, '/') + '='.repeat((4 - (base64url.length % 4)) % 4)
  const raw = atob(padded)
  return Uint8Array.from(raw, (c) => c.charCodeAt(0))
}

export async function pushStatus(): Promise<'unsupported' | 'denied' | 'on' | 'off'> {
  if (!pushSupported()) return 'unsupported'
  if (Notification.permission === 'denied') return 'denied'
  const registration = await navigator.serviceWorker.getRegistration('/sw.js')
  const subscription = await registration?.pushManager.getSubscription()
  return subscription ? 'on' : 'off'
}

export async function enablePush(token: string): Promise<string | null> {
  if (!pushSupported()) return 'This browser cannot show notifications. On iPhone, add SowSmart to your Home Screen first.'
  const { public_key } = await pushKey()
  if (!public_key) return 'Notifications are not set up on this server.'
  const permission = await Notification.requestPermission()
  if (permission !== 'granted') return 'Notifications were not allowed.'
  const registration = await navigator.serviceWorker.register('/sw.js')
  await navigator.serviceWorker.ready
  const subscription =
    (await registration.pushManager.getSubscription()) ??
    (await registration.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: keyBytes(public_key) }))
  await savePushSubscription(token, subscription.toJSON())
  return null
}
