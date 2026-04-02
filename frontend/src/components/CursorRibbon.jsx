import { useEffect, useRef } from 'react'

/** 丝带节点数：越多越长、略吃性能 */
const SEGMENTS = 44
/** 跟随系数：越小拖尾越长、越「飘」 */
const LERP = 0.13
const MIN_VIEWPORT = 768

function shouldDisable() {
  if (typeof window === 'undefined') return true
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return true
  if (window.matchMedia('(pointer: coarse)').matches) return true
  if (window.innerWidth < MIN_VIEWPORT) return true
  return false
}

export default function CursorRibbon() {
  const canvasRef = useRef(null)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    const points = Array.from({ length: SEGMENTS }, () => ({ x: 0, y: 0 }))
    let mx = window.innerWidth / 2
    let my = window.innerHeight / 2
    let moved = false
    let dpr = Math.min(window.devicePixelRatio || 1, 2)
    let rafId = 0

    const resize = () => {
      dpr = Math.min(window.devicePixelRatio || 1, 2)
      const w = window.innerWidth
      const h = window.innerHeight
      canvas.width = w * dpr
      canvas.height = h * dpr
      canvas.style.width = `${w}px`
      canvas.style.height = `${h}px`
    }

    const onMove = (e) => {
      mx = e.clientX
      my = e.clientY
      if (!moved) {
        for (let i = 0; i < SEGMENTS; i++) {
          points[i].x = mx
          points[i].y = my
        }
        moved = true
      }
    }

    const tick = () => {
      rafId = requestAnimationFrame(tick)

      if (shouldDisable()) {
        ctx.setTransform(1, 0, 0, 1, 0, 0)
        ctx.clearRect(0, 0, canvas.width, canvas.height)
        return
      }

      const w = window.innerWidth
      const h = window.innerHeight
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
      ctx.clearRect(0, 0, w, h)

      if (!moved) return

      points[0].x = mx
      points[0].y = my
      for (let i = 1; i < SEGMENTS; i++) {
        points[i].x += (points[i - 1].x - points[i].x) * LERP
        points[i].y += (points[i - 1].y - points[i].y) * LERP
      }

      ctx.lineCap = 'round'
      ctx.lineJoin = 'round'
      ctx.shadowBlur = 4
      ctx.shadowColor = 'rgba(56, 189, 248, 0.12)'

      const last = SEGMENTS - 2
      for (let k = last; k >= 0; k--) {
        const t = last === 0 ? 1 : (last - k) / last
        const alpha = 0.04 + t * 0.18
        ctx.strokeStyle = `rgba(148, 163, 184, ${alpha})`
        ctx.lineWidth = 0.75 + t * 0.4
        ctx.beginPath()
        ctx.moveTo(points[k + 1].x, points[k + 1].y)
        ctx.lineTo(points[k].x, points[k].y)
        ctx.stroke()
      }
      ctx.shadowBlur = 0
    }

    resize()
    window.addEventListener('resize', resize, { passive: true })
    window.addEventListener('mousemove', onMove, { passive: true })

    rafId = requestAnimationFrame(tick)

    return () => {
      cancelAnimationFrame(rafId)
      window.removeEventListener('resize', resize)
      window.removeEventListener('mousemove', onMove)
    }
  }, [])

  return <canvas className="cursor-ribbon" ref={canvasRef} aria-hidden />
}
