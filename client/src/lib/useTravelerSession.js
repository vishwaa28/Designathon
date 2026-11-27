import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from './api'
import { fmtTime } from './format'
import { useApi } from './useApi'
import { useVoiceAgent } from './useVoiceAgent'

export const LANGUAGES = [
  { id: 'en', label: 'English', native: 'English' },
  { id: 'ta', label: 'Tamil', native: 'தமிழ்' },
  { id: 'te', label: 'Telugu', native: 'తెలుగు' },
]

const enc = encodeURIComponent

function legLine(leg) {
  const route = `${leg.origin_city} to ${leg.destination_city}`
  const when = `${fmtTime(leg.est_dep)}${leg.delay_min > 0 ? ` (was ${fmtTime(leg.sched_dep)})` : ''}`
  const state = leg.status === 'CANCELLED' ? 'has been cancelled' : leg.delay_min >= 15 ? `is delayed by ${leg.delay_min} min` : 'is on schedule'
  return `${leg.number} ${route} departing ${when} ${state}.`
}

/** Plain-language status of a booking, used by the chat when the voice assistant is not connected. */
export function describeBooking(booking) {
  const p = booking.passenger
  if (!p.legs.length) return 'This booking has been refunded, so there is nothing left to change.'
  const lines = p.legs.map(legLine)
  const note = booking.actionable_legs.length
    ? 'Your journey has been affected. I can show you other flights with seats, or start a refund.'
    : 'Everything looks fine for now. I can still show you other flights if you want to change.'
  return `${lines.join(' ')} ${note}`
}

/**
 * One traveler session shared by the desktop and mobile layouts: booking lookup, the voice assistant, the shared
 * conversation log, and the rebook flow (options, seat selection, confirmation).
 */
export function useTravelerSession(initial = {}) {
  const [pnr, setPnr] = useState(initial.pnr || '')
  const [name, setName] = useState(initial.name || '')
  const [booking, setBooking] = useState(null)
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)
  const [language, setLanguage] = useState('en')
  // flow: { step: 'options' | 'seat' | 'done' | 'refund', legId, alts, trip, seatMap, seat, record, error }
  const [flow, setFlow] = useState(null)
  const voiceRef = useRef(null)
  const bookingRef = useRef(null)
  bookingRef.current = booking

  const who = booking?.passenger

  const fetchBooking = useCallback(async (p, n) => {
    const data = await api.get(`/traveler/${enc(p)}?last_name=${enc(n)}`)
    setBooking(data)
    return data
  }, [])

  const refresh = useCallback(async () => {
    const b = bookingRef.current?.passenger
    if (b) await fetchBooking(b.pnr, b.last_name)
  }, [fetchBooking])

  const loadOptions = useCallback(async (legId, announce = true) => {
    const b = bookingRef.current?.passenger
    if (!b) return null
    const alts = await api.get(`/traveler/${enc(b.pnr)}/alternatives?last_name=${enc(b.last_name)}&leg_trip_id=${enc(legId)}`)
    setFlow({ step: 'options', legId, alts })
    if (announce) voiceRef.current?.pushMessage({ kind: 'options', legId, items: alts.items, leg: alts.leg })
    return alts
  }, [])

  const onToolResult = useCallback((toolName, data) => {
    if (toolName === 'get_alternatives') {
      setFlow({ step: 'options', legId: data.leg_id, alts: { leg: data.leg, items: data.items } })
      voiceRef.current?.pushMessage({ kind: 'options', legId: data.leg_id, items: data.items, leg: data.leg })
    } else if (toolName === 'rebook' || toolName === 'request_refund') {
      const record = data.notification
      setFlow({ step: 'done', record })
      voiceRef.current?.pushMessage({ kind: 'confirmation', record })
    }
  }, [])

  const voice = useVoiceAgent({
    pnr: who?.pnr || '',
    name: who?.last_name || '',
    language,
    onBookingChanged: refresh,
    onToolResult,
  })
  useEffect(() => {
    voiceRef.current = voice
  })

  const connected = ['connecting', 'listening', 'thinking', 'speaking'].includes(voice.status)
  const { data: voiceStatus } = useApi('/voice/status')
  const voiceAvailable = Boolean(booking) && voiceStatus?.configured !== false

  const lookup = useCallback(
    async (p = pnr, n = name) => {
      if (!p || !n) return false
      setBusy(true)
      setError(null)
      try {
        const data = await fetchBooking(p, n)
        setFlow(null)
        if (['en', 'ta', 'te'].includes(data.passenger.language)) setLanguage(data.passenger.language)
        return data
      } catch (e) {
        setBooking(null)
        setError(e.message)
        return false
      } finally {
        setBusy(false)
      }
    },
    [pnr, name, fetchBooking],
  )

  // Booking links from notification messages open the page with ?pnr=&name= already filled in.
  const autoLookup = useRef(false)
  useEffect(() => {
    if (autoLookup.current || !initial.pnr || !initial.name) return
    autoLookup.current = true
    fetchBooking(initial.pnr, initial.name)
      .then((data) => {
        if (['en', 'ta', 'te'].includes(data.passenger.language)) setLanguage(data.passenger.language)
      })
      .catch((e) => setError(e.message))
  }, [initial.pnr, initial.name, fetchBooking])

  const reset = useCallback(() => {
    voice.stop()
    voice.clearMessages()
    setBooking(null)
    setFlow(null)
    setPnr('')
    setName('')
    setError(null)
  }, [voice])

  const showOptions = useCallback(
    async (legId) => {
      setBusy(true)
      try {
        return await loadOptions(legId)
      } catch (e) {
        voice.pushMessage({ role: 'assistant', text: `Sorry, I could not look up other flights: ${e.message}` })
        return null
      } finally {
        setBusy(false)
      }
    },
    [loadOptions, voice],
  )

  const chooseTrip = useCallback(
    async (trip, legId) => {
      const b = bookingRef.current?.passenger
      if (!b) return
      setBusy(true)
      setFlow((f) => ({ ...(f || {}), step: 'seat', legId: legId || f?.legId, trip, seatMap: null, seat: null, error: null }))
      try {
        const seatMap = await api.get(`/traveler/${enc(b.pnr)}/seats?last_name=${enc(b.last_name)}&trip_id=${enc(trip.id)}`)
        setFlow((f) => ({ ...(f || {}), step: 'seat', trip, seatMap }))
        voice.pushMessage({ kind: 'seatmap', tripId: trip.id })
      } catch (e) {
        setFlow((f) => ({ ...(f || {}), error: e.message }))
      } finally {
        setBusy(false)
      }
    },
    [voice],
  )

  const pickSeat = useCallback((seat) => setFlow((f) => (f ? { ...f, seat, error: null } : f)), [])

  const confirmSeat = useCallback(async () => {
    const b = bookingRef.current?.passenger
    const f = flow
    if (!b || !f?.trip || !f.seat) return
    setBusy(true)
    try {
      const res = await api.post(`/traveler/${enc(b.pnr)}/rebook`, {
        last_name: b.last_name,
        leg_trip_id: f.legId,
        new_trip_id: f.trip.id,
        seat: f.seat,
      })
      const record = res.notification
      setFlow({ step: 'done', record, trip: f.trip })
      voice.pushMessage({ kind: 'confirmation', record, trip: f.trip })
      voice.pushMessage({ role: 'assistant', text: 'Anything else I can help you with?' })
      voice.pushMessage({ kind: 'menu' })
      await refresh()
      voice.sendNotice(
        `[Update from the app] The traveler just rebooked from the app: ${record.message} Confirm this to them warmly in one or two short sentences, and ask if they need anything else.`,
      )
    } catch (e) {
      setFlow((cur) => ({ ...cur, error: e.message }))
      if (/seat/i.test(e.message) && f.trip) {
        try {
          const seatMap = await api.get(`/traveler/${enc(b.pnr)}/seats?last_name=${enc(b.last_name)}&trip_id=${enc(f.trip.id)}`)
          setFlow((cur) => ({ ...cur, seatMap, seat: null }))
        } catch {
          /* keep the previous map */
        }
      }
    } finally {
      setBusy(false)
    }
  }, [flow, refresh, voice])

  const requestRefund = useCallback(
    async (legId) => {
      const b = bookingRef.current?.passenger
      if (!b) return
      setBusy(true)
      try {
        const res = await api.post(`/traveler/${enc(b.pnr)}/refund`, { last_name: b.last_name, leg_trip_id: legId })
        setFlow({ step: 'done', record: res.notification })
        voice.pushMessage({ kind: 'confirmation', record: res.notification })
        voice.pushMessage({ kind: 'menu' })
        await refresh()
        voice.sendNotice(`[Update from the app] The traveler just requested a refund from the app: ${res.notification.message} Confirm this to them kindly in one short sentence.`)
      } catch (e) {
        voice.pushMessage({ role: 'assistant', text: `I could not process the refund: ${e.message}` })
      } finally {
        setBusy(false)
      }
    },
    [refresh, voice],
  )

  const closeFlow = useCallback(() => setFlow(null), [])

  /** Free-text from the chat box: goes to the voice assistant when connected, otherwise handled by simple intents. */
  const ask = useCallback(
    async (text) => {
      const t = text.trim()
      if (!t) return
      if (connected && voice.status !== 'connecting') {
        voice.sendText(t)
        return
      }
      voice.pushMessage({ role: 'user', text: t })
      const b = bookingRef.current
      if (!b) {
        voice.pushMessage({ role: 'assistant', text: 'Please share your booking reference (PNR) and last name first, then I can help.' })
        return
      }
      const legId = b.actionable_legs[0] || b.passenger.legs[0]?.id
      const lower = t.toLowerCase()
      if (!legId) {
        voice.pushMessage({ role: 'assistant', text: describeBooking(b) })
      } else if (/refund|money back|cancel my/.test(lower)) {
        voice.pushMessage({ role: 'assistant', text: 'I can cancel this leg and start a full refund. Shall I go ahead?' })
        voice.pushMessage({ kind: 'refund_prompt', legId })
      } else if (/other|alternat|option|available|avail|rebook|change|another|flight|book/.test(lower)) {
        voice.pushMessage({ role: 'assistant', text: 'Here are the other flights with open seats in the next 24 hours.' })
        await showOptions(legId)
      } else if (/status|what happened|journey|delay|cancel|update|booking|trip/.test(lower)) {
        voice.pushMessage({ role: 'assistant', text: describeBooking(b) })
      } else {
        voice.pushMessage({ role: 'assistant', text: 'I can explain what happened to your journey, show other flights with seats, rebook you or start a refund. What would you like?' })
      }
    },
    [connected, voice, showOptions],
  )

  return {
    pnr, setPnr, name, setName, booking, who, error, setError, busy,
    language, setLanguage, flow, voice, connected, voiceAvailable,
    lookup, reset, refresh, showOptions, chooseTrip, pickSeat, confirmSeat, requestRefund, closeFlow, ask,
  }
}
