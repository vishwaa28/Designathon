import { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react'
import { api } from './api'

const StreamContext = createContext({ connected: false, subscribe: () => () => {} })

export function StreamProvider({ children }) {
  const [connected, setConnected] = useState(false)
  const listeners = useRef(new Set())

  useEffect(() => {
    const source = new EventSource(api.streamUrl)
    source.onopen = () => setConnected(true)
    source.onerror = () => setConnected(false)
    source.onmessage = (msg) => {
      try {
        const event = JSON.parse(msg.data)
        listeners.current.forEach((fn) => fn(event))
      } catch {
        /* ignore malformed frames */
      }
    }
    return () => source.close()
  }, [])

  const subscribe = useCallback((fn) => {
    listeners.current.add(fn)
    return () => listeners.current.delete(fn)
  }, [])

  return <StreamContext.Provider value={{ connected, subscribe }}>{children}</StreamContext.Provider>
}

export function useStreamStatus() {
  return useContext(StreamContext).connected
}

/** Subscribe to stream events. `handler` receives every event; keep it cheap. */
export function useStream(handler) {
  const { subscribe } = useContext(StreamContext)
  const ref = useRef(handler)
  useEffect(() => {
    ref.current = handler
  })
  useEffect(() => subscribe((e) => ref.current(e)), [subscribe])
}
