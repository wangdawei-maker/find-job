import { useEffect, useRef, useState } from 'react'
import * as PIXI from 'pixi.js'
import 'live2dcubismcore/live2d.min.js'
import { Live2DModel } from 'pixi-live2d-display/cubism2'

const MODEL_PATH = '/live2d/haru01/haru01.model.json'
const MIN_WIDTH = 900
const CANVAS_W = 240
const CANVAS_H = 340

function canShow() {
  if (typeof window === 'undefined') return false
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return false
  if (window.matchMedia('(pointer: coarse)').matches) return false
  return window.innerWidth >= MIN_WIDTH
}

export default function Live2DWidget() {
  const wrapRef = useRef(null)
  const pixiHostRef = useRef(null)
  const appRef = useRef(null)
  const modelRef = useRef(null)
  const [open, setOpen] = useState(true)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    if (!canShow() || failed || !open) return undefined

    let disposed = false
    let releaseDrag = null
    const host = pixiHostRef.current
    if (!host) return undefined

    window.PIXI = PIXI

    let app
    try {
      app = new PIXI.Application({
        width: CANVAS_W,
        height: CANVAS_H,
        backgroundAlpha: 0,
        antialias: true,
        autoStart: true,
        resolution: Math.min(window.devicePixelRatio || 1, 2),
        autoDensity: true,
      })
    } catch (e) {
      console.error('Pixi / WebGL init failed:', e)
      setFailed(true)
      return undefined
    }

    host.appendChild(app.view)
    appRef.current = app

    const loadModel = async () => {
      try {
        const model = await Live2DModel.from(MODEL_PATH)
        if (disposed) {
          model.destroy()
          return
        }

        modelRef.current = model
        model.anchor.set(0.5, 1)
        model.position.set(CANVAS_W / 2, CANVAS_H - 10)
        model.scale.set(1)
        model.interactive = true
        model.buttonMode = true
        model.on('pointertap', () => {
          model.motion('tap_body')
        })

        app.stage.addChild(model)

        const pad = 14
        const fit = () => {
          const b = model.getBounds()
          if (b.width > 0 && b.height > 0) {
            const s = Math.min(
              (CANVAS_W - pad * 2) / b.width,
              (CANVAS_H - pad * 2) / b.height,
            )
            model.scale.set(Math.min(Math.max(s, 0.04), 0.45))
          } else {
            model.scale.set(0.12)
          }
        }
        requestAnimationFrame(fit)
      } catch (error) {
        console.error('Live2D model load failed:', error)
        setFailed(true)
      }
    }

    const makeDraggable = () => {
      const el = wrapRef.current
      if (!el) return () => {}
      let dragging = false
      let startX = 0
      let startY = 0
      let right = 20
      let bottom = 16

      const onDown = (e) => {
        if (!(e.target instanceof HTMLElement)) return
        if (!e.target.closest('.l2d-drag-handle')) return
        dragging = true
        startX = e.clientX
        startY = e.clientY
        el.classList.add('is-dragging')
      }

      const onMove = (e) => {
        if (!dragging) return
        const dx = e.clientX - startX
        const dy = e.clientY - startY
        right -= dx
        bottom -= dy
        right = Math.max(8, Math.min(window.innerWidth - 260, right))
        bottom = Math.max(8, Math.min(window.innerHeight - 260, bottom))
        el.style.right = `${right}px`
        el.style.bottom = `${bottom}px`
        startX = e.clientX
        startY = e.clientY
      }

      const onUp = () => {
        dragging = false
        el.classList.remove('is-dragging')
      }

      window.addEventListener('pointerdown', onDown)
      window.addEventListener('pointermove', onMove)
      window.addEventListener('pointerup', onUp)
      return () => {
        window.removeEventListener('pointerdown', onDown)
        window.removeEventListener('pointermove', onMove)
        window.removeEventListener('pointerup', onUp)
      }
    }

    loadModel()
    releaseDrag = makeDraggable()

    return () => {
      disposed = true
      if (releaseDrag) releaseDrag()
      if (modelRef.current) {
        modelRef.current.removeAllListeners()
        modelRef.current.destroy()
        modelRef.current = null
      }
      if (appRef.current) {
        const view = appRef.current.view
        appRef.current.destroy(true, { children: true })
        if (view?.parentNode) {
          view.parentNode.removeChild(view)
        }
        appRef.current = null
      }
    }
  }, [failed, open])

  if (!open || !canShow() || failed) {
    return (
      <button type="button" className="l2d-open-btn" onClick={() => setOpen(true)}>
        看板娘
      </button>
    )
  }

  return (
    <aside className="l2d-widget" ref={wrapRef}>
      <div className="l2d-toolbar l2d-drag-handle">
        <span>Haru</span>
        <button type="button" onClick={() => setOpen(false)}>
          收起
        </button>
      </div>
      <div className="l2d-canvas-wrap" ref={pixiHostRef} />
    </aside>
  )
}
