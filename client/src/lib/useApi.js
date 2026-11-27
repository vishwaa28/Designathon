import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from './api'
import { useStream } from './stream'

/**
 * Fetch a resource and keep it fresh.
 * - `refreshOn`: event-type prefixes from the live stream that should trigger a reload
 * - `match`: optional predicate to narrow which events count
 */
export function useApi(path, { refreshOn = [], match, interval } = {}) {
  const [state, setState] = useState({ key: null, data: null, error: null })
  const timer = useRef(null)

  const load = useCallback(async () => {
    if (!path) return
    try {
      const result = await api.get(path)
      setState({ key: path, data: result, error: null })
    } catch (e) {
      setState((s) => ({ key: path, data: s.key === path ? s.data : null, error: e.message }))
    }
  }, [path])

  useEffect(() => {
    load()
  }, [load])

  useEffect(() => {
    if (!interval) return undefined
    const id = setInterval(load, interval)
    return () => clearInterval(id)
  }, [interval, load])

  useStream((event) => {
    if (!refreshOn.length) return
    if (!refreshOn.some((prefix) => event.type.startsWith(prefix))) return
    if (match && !match(event)) return
    clearTimeout(timer.current)
    timer.current = setTimeout(load, 250)
  })

  const fresh = state.key === path
  const setData = useCallback((data) => setState({ key: path, data, error: null }), [path])
  return {
    data: fresh ? state.data : null,
    error: fresh ? state.error : null,
    loading: Boolean(path) && !fresh,
    reload: load,
    setData,
  }
}
