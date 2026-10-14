import { useEffect, useRef, useState } from 'react'
import WaveSurfer from 'wavesurfer.js'
import RegionsPlugin, { type Region } from 'wavesurfer.js/dist/plugins/regions.esm.js'
import type { MarkKey, Marks } from '../api/types'

const SPEEDS = [0.5, 1, 1.25, 1.5]

const MARK_STYLE: Record<MarkKey, { color: string; label: string; button: string }> = {
  first: { color: '#16a34a', label: 'First word', button: 'Set first-word mark here' },
  last: { color: '#dc2626', label: 'Last word', button: 'Set last-word mark' },
  boundary: { color: '#2563eb', label: '60s', button: 'Set 60s boundary' },
}

function round3(n: number): number {
  return Math.round(n * 1000) / 1000
}

export function formatTime(seconds: number | null): string {
  if (seconds === null || Number.isNaN(seconds)) return '—'
  const m = Math.floor(seconds / 60)
  const s = seconds - m * 60
  return `${m}:${s.toFixed(3).padStart(6, '0')}`
}

function markerContent(key: MarkKey): HTMLElement {
  const el = document.createElement('div')
  el.textContent = MARK_STYLE[key].label
  el.style.cssText = `font-size:11px;color:#fff;background:${MARK_STYLE[key].color};padding:1px 4px;border-radius:3px;white-space:nowrap;`
  return el
}

interface Props {
  url: string
  marks: Marks
  onMarkChange: (key: MarkKey, seconds: number) => void
}

/**
 * Audio player with waveform and three draggable timing marks. Marks are
 * controlled by the parent; dragging a marker reports the new position.
 */
export function Waveform({ url, marks, onMarkChange }: Props) {
  const containerRef = useRef<HTMLDivElement>(null)
  const wsRef = useRef<WaveSurfer | null>(null)
  const regionsRef = useRef<RegionsPlugin | null>(null)
  const markerRefs = useRef<Partial<Record<MarkKey, Region>>>({})
  const onMarkChangeRef = useRef(onMarkChange)
  onMarkChangeRef.current = onMarkChange

  const [ready, setReady] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [playing, setPlaying] = useState(false)
  const [time, setTime] = useState(0)
  const [duration, setDuration] = useState(0)
  const [speed, setSpeed] = useState(1)

  useEffect(() => {
    if (!containerRef.current) return
    const regions = RegionsPlugin.create()
    const ws = WaveSurfer.create({
      container: containerRef.current,
      url,
      height: 128,
      waveColor: '#9db4d6',
      progressColor: '#3d6db5',
      cursorColor: '#111827',
      cursorWidth: 2,
      normalize: true,
      dragToSeek: true,
      fetchParams: { credentials: 'include' },
      plugins: [regions],
    })
    wsRef.current = ws
    regionsRef.current = regions
    markerRefs.current = {}

    const subs = [
      ws.on('ready', (d) => {
        setDuration(d)
        setReady(true)
      }),
      ws.on('error', (e) => setError(String(e))),
      ws.on('timeupdate', (t) => setTime(t)),
      ws.on('play', () => setPlaying(true)),
      ws.on('pause', () => setPlaying(false)),
      ws.on('finish', () => setPlaying(false)),
      regions.on('region-updated', (region) => {
        const key = region.id as MarkKey
        if (key in MARK_STYLE) onMarkChangeRef.current(key, round3(region.start))
      }),
    ]
    return () => {
      subs.forEach((unsub) => unsub())
      ws.destroy()
      wsRef.current = null
      regionsRef.current = null
      setReady(false)
    }
  }, [url])

  // Sync controlled marks onto the waveform markers.
  useEffect(() => {
    const regions = regionsRef.current
    if (!ready || !regions) return
    for (const key of Object.keys(MARK_STYLE) as MarkKey[]) {
      const value = marks[key]
      const existing = markerRefs.current[key]
      if (value === null) {
        existing?.remove()
        delete markerRefs.current[key]
      } else if (!existing) {
        markerRefs.current[key] = regions.addRegion({
          id: key,
          start: value,
          color: MARK_STYLE[key].color,
          drag: true,
          resize: false,
          content: markerContent(key),
        })
      } else if (Math.abs(existing.start - value) > 0.0005) {
        existing.setOptions({ start: value })
      }
    }
  }, [marks, ready])

  const ws = wsRef.current

  function setMarkHere(key: MarkKey) {
    if (!ws) return
    onMarkChange(key, round3(ws.getCurrentTime()))
  }

  function changeSpeed(rate: number) {
    setSpeed(rate)
    ws?.setPlaybackRate(rate, true)
  }

  function replayLast2s() {
    if (!ws) return
    ws.setTime(Math.max(0, ws.getCurrentTime() - 2))
    void ws.play()
  }

  return (
    <div className="waveform-box">
      {error && <div className="alert error">Could not load audio: {error}</div>}
      {!ready && !error && <div className="muted small-text">Loading audio…</div>}
      <div ref={containerRef} />
      <div className="wave-controls">
        <button className="primary" disabled={!ready} onClick={() => void ws?.playPause()}>
          {playing ? 'Pause' : 'Play'}
        </button>
        <button disabled={!ready} onClick={replayLast2s}>
          Replay last 2s
        </button>
        <span className="time">
          {formatTime(time)} / {formatTime(duration)}
        </span>
        <input
          type="range"
          aria-label="Scrub"
          min={0}
          max={duration || 0}
          step={0.01}
          value={time}
          disabled={!ready}
          onChange={(e) => ws?.setTime(Number(e.target.value))}
        />
        <span className="row speed">
          {SPEEDS.map((s) => (
            <button key={s} className={`small ${speed === s ? 'on' : ''}`} disabled={!ready} onClick={() => changeSpeed(s)}>
              {s}x
            </button>
          ))}
        </span>
      </div>
      <div className="marks">
        {(Object.keys(MARK_STYLE) as MarkKey[]).map((key) => (
          <button key={key} className={`mark-btn ${key}`} disabled={!ready} onClick={() => setMarkHere(key)}>
            {MARK_STYLE[key].button}
            <span className="v">{formatTime(marks[key])}</span>
          </button>
        ))}
      </div>
    </div>
  )
}
