/**
 * EduGuard <-> PPTist bridge. Copy into PPTist at src/eduguardBridge.ts and call it from
 * src/main.ts right after app.mount('#app'):
 *
 *   import { installEduguardBridge } from './eduguardBridge'
 *   const pinia = createPinia()
 *   app.use(pinia)            // (replace app.use(createPinia()))
 *   app.mount('#app')
 *   installEduguardBridge(import.meta.env.VITE_EDUGUARD_ORIGIN || '*')
 *
 * Messages from the parent window (React app):
 *   { type: 'eduguard:load', slides, title?, viewportSize?, viewportRatio? }
 *   { type: 'eduguard:get' }                    -> replies 'eduguard:slides'
 *   { type: 'eduguard:goto', index }
 * Messages to the parent:
 *   { type: 'eduguard:ready' }
 *   { type: 'eduguard:change', slides, title }   (debounced, on every edit)
 *   { type: 'eduguard:slides', slides, title }
 */
import { useSlidesStore } from '@/store'
import type { Slide } from '@/types/slides'

export function installEduguardBridge(allowedOrigin = '*') {
  if (window.parent === window) return // not embedded
  const slidesStore = useSlidesStore()
  let applyingRemote = false
  let timer: number | undefined

  const post = (msg: Record<string, unknown>) =>
    window.parent.postMessage(JSON.parse(JSON.stringify(msg)), allowedOrigin)

  window.addEventListener('message', (e: MessageEvent) => {
    if (allowedOrigin !== '*' && e.origin !== allowedOrigin) return
    const data = e.data || {}
    if (data.type === 'eduguard:load') {
      applyingRemote = true
      if (data.viewportSize) slidesStore.setViewportSize(data.viewportSize)
      if (data.viewportRatio) slidesStore.setViewportRatio(data.viewportRatio)
      if (data.title) slidesStore.setTitle(data.title)
      slidesStore.setSlides(data.slides as Slide[])
      slidesStore.updateSlideIndex(0)
      setTimeout(() => { applyingRemote = false }, 0)
    }
    else if (data.type === 'eduguard:get') {
      post({ type: 'eduguard:slides', slides: slidesStore.slides, title: slidesStore.title })
    }
    else if (data.type === 'eduguard:goto' && typeof data.index === 'number') {
      slidesStore.updateSlideIndex(data.index)
    }
  })

  slidesStore.$subscribe(() => {
    if (applyingRemote) return
    window.clearTimeout(timer)
    timer = window.setTimeout(() => {
      post({ type: 'eduguard:change', slides: slidesStore.slides, title: slidesStore.title })
    }, 600)
  })

  post({ type: 'eduguard:ready' })
}
