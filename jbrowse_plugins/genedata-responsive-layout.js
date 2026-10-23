/* globals self, window */
;(function () {
  const GLOBAL_KEY = '__geneDataResponsiveLayout'
  const TRACK_PREFIX = 'annotation-'
  const TRACK_SUFFIX = '-features'
  const APP_CHROME_HEIGHT = 84
  const BOTTOM_GAP = 6
  const MIN_TRACK_HEIGHT = 180
  const MAX_TRACK_HEIGHT = 1200

  const clamp = value => Math.min(MAX_TRACK_HEIGHT, Math.max(MIN_TRACK_HEIGHT, value))

  class Plugin {
    name = 'GeneDataResponsiveLayout'
    version = '1.0.0'

    install(pluginManager) {
      if (typeof window !== 'undefined') {
        window[GLOBAL_KEY] = { status: 'installing', controllers: new Map() }
      }
      const { getContainingTrack, getContainingView } = pluginManager.jbrequire('@jbrowse/core/util')
      const { addDisposer, isAlive } = pluginManager.jbrequire('@jbrowse/mobx-state-tree')

      pluginManager.addToExtensionPoint('Core-extendPluggableElement', element => {
        if (element.name !== 'LinearBasicDisplay') return element

        element.stateModel = element.stateModel.actions(display => ({
          afterAttach() {
            if (typeof window === 'undefined' || typeof window.ResizeObserver !== 'function') return
            const track = getContainingTrack(display)
            const trackId = track.configuration?.trackId || ''
            if (!trackId.startsWith(TRACK_PREFIX) || !trackId.endsWith(TRACK_SUFFIX)) return

            const registry = window[GLOBAL_KEY] || { controllers: new Map() }
            window[GLOBAL_KEY] = registry
            registry.controllers.get(display.id)?.dispose()

            let animationFrame = 0
            let disposed = false
            const dispose = () => {
              if (disposed) return
              disposed = true
              observer.disconnect()
              window.clearInterval(interval)
              if (animationFrame) window.cancelAnimationFrame(animationFrame)
              registry.controllers.delete(display.id)
            }
            const resize = () => {
              animationFrame = 0
              if (!isAlive(display)) return dispose()
              const view = getContainingView(display)
              if (!view?.initialized || !Number.isFinite(view.height) || !Number.isFinite(display.height)) return

              const unusedHeight = window.innerHeight - APP_CHROME_HEIGHT - view.height - BOTTOM_GAP
              const nextHeight = Math.round(clamp(display.height + unusedHeight))
              if (Math.abs(nextHeight - display.height) >= 2) display.setHeight(nextHeight)
            }
            const schedule = () => {
              if (animationFrame || disposed) return
              animationFrame = window.requestAnimationFrame(resize)
            }
            const observer = new window.ResizeObserver(schedule)
            observer.observe(document.documentElement)
            const interval = window.setInterval(schedule, 500)
            registry.controllers.set(display.id, { dispose })
            addDisposer(display, dispose)
            schedule()
          },
        }))
        return element
      })
      if (typeof window !== 'undefined') window[GLOBAL_KEY].status = 'installed'
    }

    configure() {}
  }

  ;(typeof self !== 'undefined' ? self : window).JBrowsePluginGeneDataResponsiveLayout = {
    default: Plugin,
  }
})()
