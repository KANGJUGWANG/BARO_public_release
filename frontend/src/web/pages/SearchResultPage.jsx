import { useEffect, useRef, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { ArrowLeft } from 'lucide-react'
import {
  analyzeJob,
  cancelAnalyzeJob,
  fetchOnewayCandidates,
  fetchRoundtripCandidates,
  getAnalyzeJobStatus,
  getOnewayRefreshJob,
  getRoundtripRefreshJob,
  searchFlights,
  startOnewayRefreshJob,
  startRoundtripRefreshJob,
} from '../../api/client'
import styles from './SearchResultPage.module.css'
import FlightCard from '../components/FlightCard'
import RoundTripCard from '../components/RoundTripCard'

const ACTIVE_ANALYZE_JOB_KEY = 'baro_active_analyze_job'
const POLLING_INTERVAL_MS = 2500
const MAX_POLLING_MS = 5 * 60 * 1000
const TERMINAL_JOB_STATUSES = new Set(['done', 'failed', 'cancelled', 'not_found'])
const MAX_SEARCH_RETRIES = 2
const onewayCandidatePromiseMap = new Map()
const roundtripCandidatePromiseMap = new Map()
const RT_REFRESH_POLLING_INTERVAL_MS = 5000
const RT_REFRESH_MAX_POLLING_MS = 200 * 1000
const OW_REFRESH_POLLING_INTERVAL_MS = 5000
const OW_REFRESH_MAX_POLLING_MS = 200 * 1000
const RT_REFRESH_TERMINAL_STATUSES = new Set([
  'success',
  'partial_success',
  'timeout_with_partial',
  'no_result',
  'failed',
  'timeout',
  'disabled',
  'route_not_allowed',
  'executor_unavailable',
  'writer_unavailable',
  'dry_run',
  'duplicate_running',
  'lane_busy',
  'global_busy',
  'busy_scheduled_crawler',
])
const roundtripRefreshJobMap = new Map()
const OW_REFRESH_TERMINAL_STATUSES = new Set([
  'success',
  'partial_success',
  'timeout_with_partial',
  'no_result',
  'failed',
  'timeout',
  'disabled',
  'route_not_allowed',
  'executor_unavailable',
  'dry_run',
  'duplicate_running',
  'lane_busy',
  'global_busy',
  'busy_scheduled_crawler',
  'skipped_fresh_realtime',
])
const onewayRefreshJobMap = new Map()
const OW_REFRESH_SUCCESS_STATUSES = new Set([
  'success',
  'partial_success',
  'timeout_with_partial',
  'skipped_fresh_realtime',
])
const RT_REFRESH_SUCCESS_STATUSES = OW_REFRESH_SUCCESS_STATUSES
const ANALYSIS_CONTEXT_KEY = 'baro_last_analysis_context'
const ANALYSIS_VALID_ROUTES = new Set(['ICN-NRT', 'NRT-ICN', 'ICN-HND', 'HND-ICN'])
const roundtripPredictionRunningMap = new Map()
const roundtripPredictionDoneSet = new Set()
const SEARCH_RESULT_SCROLL_PREFIX = 'baro_search_result_scroll:'
const SEARCH_RESULT_SCROLL_TTL_MS = 10 * 60 * 1000

function normalizeCode(value) {
  return String(value || '').trim().toUpperCase()
}

function buildSearchCacheKey({ origin, destination, departDate }) {
  return `baro_search_${normalizeCode(origin)}_${normalizeCode(destination)}_${String(departDate || '').trim()}_oneway`
}

function addDays(dateStr, days) {
  if (!dateStr) return ''
  const [y, m, d] = dateStr.split('-').map(Number)
  if (!y || !m || !d) return ''
  const date = new Date(Date.UTC(y, m - 1, d))
  date.setUTCDate(date.getUTCDate() + days)
  return date.toISOString().slice(0, 10)
}

function buildRoundtripCacheKey({ origin, destination, departDate, returnDate }) {
  return `baro_search_${normalizeCode(origin)}_${normalizeCode(destination)}_${String(departDate || '').trim()}_${String(returnDate || '').trim()}_roundtrip_7d`
}

function buildSearchResultScrollKey(searchKey) {
  return `${SEARCH_RESULT_SCROLL_PREFIX}${searchKey}`
}

function getPageScrollContainer(pageElement) {
  return pageElement?.parentElement || document.querySelector('#root > div') || document.scrollingElement
}

function readScrollTop(container) {
  if (!container) return 0
  if (container === document.scrollingElement || container === document.documentElement || container === document.body) {
    return window.scrollY || document.documentElement.scrollTop || document.body.scrollTop || 0
  }
  return container.scrollTop || 0
}

function writeScrollTop(container, scrollTop) {
  const next = Math.max(0, Number(scrollTop) || 0)
  if (container && container !== document.scrollingElement && container !== document.documentElement && container !== document.body) {
    container.scrollTop = next
  }
  window.scrollTo(0, next)
  if (document.scrollingElement) document.scrollingElement.scrollTop = next
}

function createSearchRequestId() {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return crypto.randomUUID()
  }
  return `${Date.now()}_${Math.random()}`
}

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms))
}

function formatDuration(durationMin) {
  if (durationMin === null || durationMin === undefined) return '-'
  const minutes = Number(durationMin)
  if (!Number.isFinite(minutes)) return '-'

  const hours = Math.floor(minutes / 60)
  const rest = minutes % 60
  if (hours > 0 && rest > 0) return `${hours}시간 ${rest}분`
  if (hours > 0) return `${hours}시간`
  return `${rest}분`
}

function firstValue(source, keys) {
  for (const key of keys) {
    const value = source?.[key]
    if (value !== null && value !== undefined && value !== '') return value
  }
  return null
}

function parseClockMinutes(value) {
  if (!value) return null
  const match = String(value).match(/^(\d{1,2}):(\d{2})/)
  if (!match) return null
  const hours = Number(match[1])
  const minutes = Number(match[2])
  if (!Number.isFinite(hours) || !Number.isFinite(minutes)) return null
  return hours * 60 + minutes
}

function parseDurationMinutes(value) {
  if (value === null || value === undefined || value === '') return null
  const numeric = Number(value)
  if (Number.isFinite(numeric)) return numeric

  const text = String(value)
  const hourMatch = text.match(/(\d+)\s*시간/)
  const minuteMatch = text.match(/(\d+)\s*분/)
  const hours = hourMatch ? Number(hourMatch[1]) : 0
  const minutes = minuteMatch ? Number(minuteMatch[1]) : 0
  const total = hours * 60 + minutes
  return total > 0 ? total : null
}

function formatClockMinutes(totalMinutes) {
  const normalized = ((totalMinutes % 1440) + 1440) % 1440
  const hours = Math.floor(normalized / 60)
  const minutes = normalized % 60
  const dayOffset = Math.floor(totalMinutes / 1440)
  const suffix = dayOffset > 0 ? `(+${dayOffset}일)` : ''
  return `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}${suffix}`
}

function resolveArrivalTime(offer, { arrivalKeys, departureKeys, durationKeys }) {
  const explicitArrival = firstValue(offer, arrivalKeys)
  if (explicitArrival) return explicitArrival

  const departure = firstValue(offer, departureKeys)
  const duration = firstValue(offer, durationKeys)
  const depMinutes = parseClockMinutes(departure)
  const durationMinutes = parseDurationMinutes(duration)

  if (depMinutes === null || durationMinutes === null) return '-'
  return formatClockMinutes(depMinutes + durationMinutes)
}

function mapOfferToFlight(offer, index) {
  const prediction = offer.prediction || null
  const depTime = offer.dep_time_local || offer.dep_time || '-'
  return {
    id: offer.flight_number || `${offer.airline_code || 'flight'}-${index}`,
    flightNumber: offer.flight_number,
    airline: offer.airline_name || offer.airline_code || 'Unknown',
    dep: depTime,
    arr: resolveArrivalTime(offer, {
      arrivalKeys: ['arr_time_local', 'arrival_time', 'arr_time'],
      departureKeys: ['dep_time_local', 'dep_time'],
      durationKeys: ['duration_min', 'duration', 'duration_text'],
    }),
    duration: formatDuration(offer.duration_min),
    price: offer.price_krw,
    direct: offer.stops === 0,
    tag: prediction?.prediction_status === 'ok' ? prediction.decision : null,
    prediction,
    rawOffer: offer,
  }
}

function candidateToRoundGroup(offer, observedAt, index = 0) {
  const id = offer.offer_observation_id ||
    `${offer.flight_number || 'out'}_${offer.ret_flight_number || 'ret'}_${offer.price_krw || index}`
  const rawOffer = { ...offer, _observedAt: observedAt }
  const prediction = offer.prediction || null
  const airline = offer.airline_code || 'Unknown'
  const outboundArr = resolveArrivalTime(offer, {
    arrivalKeys: ['arr_time_local', 'arrival_time', 'arr_time'],
    departureKeys: ['dep_time_local', 'dep_time'],
    durationKeys: ['duration_min', 'duration', 'duration_text'],
  })
  const inboundArr = resolveArrivalTime(offer, {
    arrivalKeys: ['ret_arr_time_local', 'ret_arrival_time', 'ret_arr_time'],
    departureKeys: ['ret_dep_time_local', 'ret_dep_time'],
    durationKeys: ['ret_duration_min', 'ret_duration', 'ret_duration_text'],
  })

  return {
    id,
    airline,
    totalPrice: offer.price_krw,
    observedAt,
    outbound: {
      id,
      flightNumber: offer.flight_number,
      airline,
      dep: offer.dep_time_local || '-',
      arr: outboundArr,
      duration: formatDuration(offer.duration_min),
      price: offer.price_krw,
      direct: offer.stops === 0,
      tag: prediction?.prediction_status === 'ok' ? prediction.decision : null,
      prediction,
      rawOffer,
      retFlightNumber: offer.ret_flight_number,
      retDep: offer.ret_dep_time_local || '-',
      retArr: inboundArr,
      retDuration: formatDuration(offer.ret_duration_min),
    },
    inbound: {
      id: `${id}-return`,
      flightNumber: offer.ret_flight_number,
      airline: offer.ret_airline_code || airline,
      dep: offer.ret_dep_time_local || '-',
      arr: inboundArr,
      duration: formatDuration(offer.ret_duration_min),
      price: null,
      direct: offer.stops === 0,
      rawOffer,
    },
  }
}

function getCachedOffers(searchKey) {
  try {
    const cached = sessionStorage.getItem(searchKey)
    if (!cached) return null

    const parsed = JSON.parse(cached)
    if (Array.isArray(parsed)) return parsed
    if (Array.isArray(parsed?.offers)) return parsed.offers
  } catch {
    return null
  }
  return null
}

function getCachedSearch(searchKey) {
  try {
    const cached = sessionStorage.getItem(searchKey)
    if (!cached) return null

    const parsed = JSON.parse(cached)
    if (Array.isArray(parsed)) {
      return { offers: parsed }
    }
    if (parsed?.dbResult || parsed?.realtimeResult) {
      return parsed
    }
    if (Array.isArray(parsed?.offers)) {
      return parsed
    }
  } catch {
    return null
  }
  return null
}

function sourceModeFromSource(source) {
  return source === 'realtime_refresh' ? 'realtime' : 'db'
}

function sourceFromMode(mode) {
  return mode === 'realtime' ? 'realtime_refresh' : 'db_observation'
}

function sourceResultKey(mode) {
  return mode === 'realtime' ? 'realtimeResult' : 'dbResult'
}

function buildAnalyzeKey(searchKey, sourceMode, tripType = 'oneway') {
  const mode = sourceMode === 'realtime' ? 'realtime' : 'db'
  return `${searchKey}:${mode}:${tripType === 'roundtrip' ? 'roundtrip' : 'oneway'}`
}

function parseAnalyzeKey(analyzeKey) {
  if (typeof analyzeKey !== 'string') {
    return { searchKey: analyzeKey, sourceMode: 'db', tripType: 'oneway' }
  }
  if (analyzeKey.endsWith(':realtime:roundtrip')) {
    return {
      searchKey: analyzeKey.slice(0, -':realtime:roundtrip'.length),
      sourceMode: 'realtime',
      tripType: 'roundtrip',
    }
  }
  if (analyzeKey.endsWith(':db:roundtrip')) {
    return {
      searchKey: analyzeKey.slice(0, -':db:roundtrip'.length),
      sourceMode: 'db',
      tripType: 'roundtrip',
    }
  }
  if (analyzeKey.endsWith(':realtime:oneway')) {
    return {
      searchKey: analyzeKey.slice(0, -':realtime:oneway'.length),
      sourceMode: 'realtime',
      tripType: 'oneway',
    }
  }
  if (analyzeKey.endsWith(':db:oneway')) {
    return {
      searchKey: analyzeKey.slice(0, -':db:oneway'.length),
      sourceMode: 'db',
      tripType: 'oneway',
    }
  }
  if (analyzeKey.endsWith(':realtime')) {
    return { searchKey: analyzeKey.slice(0, -':realtime'.length), sourceMode: 'realtime', tripType: 'oneway' }
  }
  if (analyzeKey.endsWith(':db')) {
    return { searchKey: analyzeKey.slice(0, -':db'.length), sourceMode: 'db', tripType: 'oneway' }
  }
  return { searchKey: analyzeKey, sourceMode: 'db', tripType: 'oneway' }
}

function makeSourceResult(offers, meta = {}) {
  return {
    rawOffers: offers,
    offers,
    source: meta.source || sourceFromMode(meta.sourceMode),
    sourceLabel: meta.sourceLabel || null,
    observedAt: meta.observedAt || null,
    expiresAt: meta.expiresAt || null,
    status: meta.status || null,
    analyzeJob: meta.analyzeJob || null,
    analyzedAt: meta.analyzedAt || null,
    savedAt: Date.now(),
  }
}

function getSourceResult(cached, sourceMode = 'db') {
  if (!cached) return null
  const result = cached[sourceResultKey(sourceMode)]
  if (result && Array.isArray(result.offers)) return result
  if (result && Array.isArray(result.rawOffers)) {
    return { ...result, offers: result.rawOffers }
  }
  const legacyOffers = Array.isArray(cached.offers) ? cached.offers : null
  if (!legacyOffers) return null
  const legacyMode = sourceModeFromSource(cached.source)
  if (legacyMode !== sourceMode) return null
  return makeSourceResult(legacyOffers, {
    source: cached.source || sourceFromMode(sourceMode),
    sourceLabel: cached.sourceLabel || cached.source_label || null,
    observedAt: cached.observedAt || null,
    expiresAt: cached.expiresAt || null,
    status: cached.status || null,
    analyzeJob: cached.analyzeJob || null,
  })
}

function writeSourceResultCache(searchKey, base, sourceMode, result, activeSourceMode = sourceMode) {
  try {
    const current = getCachedSearch(searchKey) || {}
    const mode = sourceMode === 'realtime' ? 'realtime' : 'db'
    const activeResult = mode === activeSourceMode ? result : getSourceResult(current, activeSourceMode) || result
    const updated = {
      ...current,
      ...base,
      activeSourceMode,
      [sourceResultKey(mode)]: result,
      source: activeResult.source,
      sourceLabel: activeResult.sourceLabel || null,
      observedAt: activeResult.observedAt || null,
      expiresAt: activeResult.expiresAt || null,
      status: activeResult.status || null,
      offers: activeResult.offers || activeResult.rawOffers || [],
      analyzeJob: activeResult.analyzeJob || null,
      savedAt: Date.now(),
    }
    sessionStorage.setItem(searchKey, JSON.stringify(updated))
    return updated
  } catch {
    return null
  }
}

function setCachedOffers(searchKey, search, offers, meta = {}) {
  const sourceMode = meta.sourceMode || sourceModeFromSource(meta.source)
  const source = meta.source || sourceFromMode(sourceMode)
  writeSourceResultCache(
    searchKey,
    {
      origin: normalizeCode(search.origin),
      destination: normalizeCode(search.destination),
      departDate: String(search.departDate || '').trim(),
      tripType: 'oneway',
    },
    sourceMode,
    makeSourceResult(offers, { ...meta, source, sourceMode }),
    meta.activeSourceMode || sourceMode,
  )
}

function updateCachedSearch(searchKey, updater) {
  try {
    const current = getCachedSearch(searchKey)
    if (!current) return null
    const updated = updater(current)
    if (!updated) return null
    sessionStorage.setItem(searchKey, JSON.stringify(updated))
    return updated
  } catch {
    return null
  }
}

function saveActiveAnalyzeJob(jobId, searchKey, status = 'running') {
  try {
    sessionStorage.setItem(ACTIVE_ANALYZE_JOB_KEY, JSON.stringify({
      job_id: jobId,
      searchKey,
      status,
      savedAt: Date.now(),
    }))
  } catch {
    // Best-effort active job marker.
  }
}

function getActiveAnalyzeJob() {
  try {
    const raw = sessionStorage.getItem(ACTIVE_ANALYZE_JOB_KEY)
    return raw ? JSON.parse(raw) : null
  } catch {
    return null
  }
}

function makeOfferMatchKey(offer) {
  const fn = String(offer.flight_number || offer.flightNumber || '').trim()
  const dep = String(offer.dep_time || offer.dep_time_local || offer.dep || '').trim()
  const price = offer.price_krw ?? offer.price ?? ''
  return `${fn}_${dep}_${price}`
}

function shouldApplyPrediction(currentPrediction, nextPrediction) {
  const currentStatus = currentPrediction?.prediction_status
  const nextStatus = nextPrediction?.prediction_status
  if (!nextStatus) return false
  if (currentStatus === 'ok' && nextStatus !== 'ok') return false
  if (nextStatus === 'ok') return true
  return !currentStatus
}

function mergePredictionsToOffers(offers, predictions) {
  if (!Array.isArray(predictions) || predictions.length === 0) {
    return { offers, changed: false }
  }

  const predictionByKey = new Map()
  predictions.forEach(item => {
    predictionByKey.set(makeOfferMatchKey({
      flight_number: item.flight_number,
      dep_time: item.dep_time,
      price_krw: item.price_krw,
    }), item.prediction)
  })

  let changed = false
  const merged = offers.map(offer => {
    const prediction = predictionByKey.get(makeOfferMatchKey(offer))
    if (!prediction || !shouldApplyPrediction(offer.prediction, prediction)) {
      return offer
    }
    changed = true
    return { ...offer, prediction }
  })

  return { offers: merged, changed }
}

function analyzeJobMeta(jobId, data) {
  return {
    job_id: jobId,
    status: data.status,
    completed_count: data.completed_count || 0,
    total_count: data.total_count || 0,
    failed_count: data.failed_count || 0,
    updatedAt: Date.now(),
  }
}

function formatAnalyzeStatus(status, progress) {
  if (status === 'starting' || status === 'queued') return '추천 결과를 분석 중입니다. 잠시만 기다려주세요.'
  if (status === 'running' || status === 'partial') {
    if (progress?.total) {
      return `추천 결과를 분석 중입니다. ${progress.completed}/${progress.total}`
    }
    return '추천 결과를 분석 중입니다. 잠시만 기다려주세요.'
  }
  if (status === 'done') return '추천 분석 완료'
  if (status === 'failed') return '일부 항공편은 분석하지 못했습니다.'
  if (status === 'cancelled') return '추천 분석이 취소되었습니다.'
  if (status === 'timeout') return '추천 분석 시간이 초과되었습니다.'
  if (status === 'error') return '추천 분석을 시작하지 못했습니다.'
  if (status === 'unsupported_trip_type') return '현재 서버가 이 검색 유형의 목록 분석을 지원하지 않습니다.'
  if (status === 'rejected_max_jobs') return '추천 분석 요청이 많습니다. 잠시 후 다시 시도해주세요.'
  return ''
}

function makeRoundtripOfferMatchKey(offer) {
  const id = offer.source_offer_id || offer.offer_observation_id || offer.refresh_offer_id
  if (id) return `id:${id}`
  return [
    offer.flight_number || '',
    offer.ret_flight_number || '',
    offer.dep_time_local || offer.dep_time || '',
    offer.ret_dep_time_local || offer.ret_dep_time || '',
    offer.price_krw ?? '',
  ].map(value => String(value).trim()).join('_')
}

function mergeRoundtripPredictionsToOffers(offers, predictionByKey) {
  if (!predictionByKey || predictionByKey.size === 0) {
    return { offers, changed: false }
  }
  let changed = false
  const merged = offers.map(offer => {
    const prediction = predictionByKey.get(makeRoundtripOfferMatchKey(offer))
    if (!prediction || !shouldApplyPrediction(offer.prediction, prediction)) {
      return offer
    }
    changed = true
    return { ...offer, prediction }
  })
  return { offers: merged, changed }
}

function mergeRoundtripJobPredictionsToOffers(offers, predictions) {
  if (!Array.isArray(predictions) || predictions.length === 0) {
    return { offers, changed: false }
  }

  const predictionByKey = new Map()
  predictions.forEach(item => {
    predictionByKey.set(makeRoundtripOfferMatchKey({
      source_offer_id: item.source_offer_id,
      offer_observation_id: item.offer_observation_id,
      refresh_offer_id: item.refresh_offer_id,
      flight_number: item.flight_number,
      ret_flight_number: item.ret_flight_number,
      dep_time_local: item.dep_time_local || item.dep_time,
      ret_dep_time_local: item.ret_dep_time_local,
      price_krw: item.price_krw,
    }), item.prediction)
  })

  return mergeRoundtripPredictionsToOffers(offers, predictionByKey)
}

function roundtripStatusMessage(status) {
  if (status === 'unavailable_no_observation') {
    return '해당 7일 왕복 일정의 관측 데이터가 없습니다. 출발일을 변경해 다시 검색해주세요.'
  }
  if (status === 'unavailable_no_offers') {
    return '해당 조건의 유효한 항공권 후보가 없습니다. 출발일을 변경해 다시 검색해주세요.'
  }
  if (status === 'unavailable_db_pool' || status === 'unavailable_db_query_error') {
    return '서버 데이터 조회 중 문제가 발생했습니다. 잠시 후 다시 시도해주세요.'
  }
  return '왕복 후보 조회 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.'
}

function onewayStatusMessage(status) {
  if (status === 'unavailable_no_observation') {
    return '조건에 맞는 관측 결과가 없습니다. 출발일을 변경해 다시 검색해주세요.'
  }
  if (status === 'unavailable_no_offers') {
    return '관측은 있었지만 표시 가능한 항공권 후보가 없습니다.'
  }
  if (status?.startsWith('unavailable_')) {
    return '서버 데이터 조회 중 문제가 발생했습니다. 잠시 후 다시 시도해주세요.'
  }
  return '항공권 후보를 불러오지 못했습니다.'
}

function formatRtRefreshRunningMessage(elapsedSeconds = 0) {
  return `실시간 검색 중 · ${elapsedSeconds}초 경과. 결과가 준비되면 자동으로 갱신됩니다. 왕복 검색은 시간이 조금 걸릴 수 있습니다.`
}

function formatOwRefreshRunningMessage(elapsedSeconds = 0) {
  return `실시간 검색 중 · ${elapsedSeconds}초 경과`
}

function getRtRefreshTerminalMessage(status) {
  if (status === 'skipped_fresh_realtime') {
    return '최근 갱신된 실시간 검색 결과를 표시합니다.'
  }
  if (status === 'success' || status === 'partial_success' || status === 'timeout_with_partial') {
    return '실시간 검색 결과로 업데이트되었습니다.'
  }
  if (status === 'no_result') {
    return '실시간 검색에서 새 후보를 찾지 못해 최신 관측 결과를 유지합니다.'
  }
  if (status === 'timeout') {
    return '실시간 검색이 지연되어 최신 관측 결과를 유지합니다.'
  }
  if (status === 'failed') {
    return '실시간 검색을 완료하지 못해 최신 관측 결과를 유지합니다.'
  }
  if (status === 'disabled' || status === 'executor_unavailable' || status === 'writer_unavailable') {
    return '최신 관측 결과를 표시 중입니다.'
  }
  if (status === 'route_not_allowed') {
    return '해당 조건은 현재 실시간 갱신 대상이 아니므로 최신 관측 결과를 표시합니다.'
  }
  if (status === 'dry_run') {
    return '실시간 갱신 점검 중입니다. 최신 관측 결과를 표시합니다.'
  }
  if (status === 'lane_busy') {
    return '현재 같은 유형의 실시간 검색 요청이 많아 최신 관측 결과를 먼저 표시합니다.'
  }
  if (status === 'global_busy') {
    return '현재 실시간 검색 요청이 많아 최신 관측 결과를 먼저 표시합니다.'
  }
  if (status === 'busy_scheduled_crawler') {
    return '서버 데이터 업데이트 중입니다. 최신 관측 결과를 표시합니다.'
  }
  if (status === 'duplicate_running') {
    return '같은 조건의 실시간 검색이 이미 진행 중입니다. 결과가 준비되면 자동으로 반영됩니다.'
  }
  return '최신 관측 결과를 표시합니다.'
}

export default function SearchResultPage({ onMenuOpen }) {
  const navigate = useNavigate()
  const location = useLocation()
  const state = location.state || {}
  const isRound = state.tripType === 'round'
  const requesting = useRef(false)
  const pollingTimerRef = useRef(null)
  const pollingStartedAtRef = useRef(null)
  const activeJobIdRef = useRef(null)
  const activeSearchKeyRef = useRef(null)
  const abortControllerRef = useRef(null)
  const activeSearchRequestIdRef = useRef(null)
  const rtRefreshPollingTimerRef = useRef(null)
  const rtRefreshElapsedTimerRef = useRef(null)
  const rtRefreshJobIdRef = useRef(null)
  const rtRefreshStartedAtRef = useRef(null)
  const rtRefreshCacheKeyRef = useRef(null)
  const owRefreshPollingTimerRef = useRef(null)
  const owRefreshElapsedTimerRef = useRef(null)
  const owRefreshJobIdRef = useRef(null)
  const owRefreshStartedAtRef = useRef(null)
  const owRefreshCacheKeyRef = useRef(null)
  const activeOwSourceModeRef = useRef('db')
  const activeRtSourceModeRef = useRef('db')
  const pageRef = useRef(null)
  const restoredScrollKeyRef = useRef(null)
  const [flights, setFlights] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [analyzeStatus, setAnalyzeStatus] = useState('')
  const [analyzeProgress, setAnalyzeProgress] = useState(null)
  const [searchRetrying, setSearchRetrying] = useState(false)
  const [roundGroups, setRoundGroups] = useState([])
  const [roundLoading, setRoundLoading] = useState(false)
  const [roundError, setRoundError] = useState('')
  const [roundObservedAt, setRoundObservedAt] = useState(null)
  const [roundSource, setRoundSource] = useState(null)
  const [roundExpiresAt, setRoundExpiresAt] = useState(null)
  const [roundRefreshStatus, setRoundRefreshStatus] = useState(null)
  const [roundRefreshMessage, setRoundRefreshMessage] = useState('')
  const [roundRefreshElapsedSeconds, setRoundRefreshElapsedSeconds] = useState(null)
  const [owSource, setOwSource] = useState(null)
  const [owSourceLabel, setOwSourceLabel] = useState(null)
  const [owObservedAt, setOwObservedAt] = useState(null)
  const [owExpiresAt, setOwExpiresAt] = useState(null)
  const [owRefreshStatus, setOwRefreshStatus] = useState(null)
  const [owRefreshMessage, setOwRefreshMessage] = useState('')
  const [owRefreshElapsed, setOwRefreshElapsed] = useState(0)
  const [activeOwSourceMode, setActiveOwSourceMode] = useState('db')
  const [owDbFlights, setOwDbFlights] = useState([])
  const [owDbObservedAt, setOwDbObservedAt] = useState(null)
  const [owDbExpiresAt, setOwDbExpiresAt] = useState(null)
  const [owDbAnalyzeJob, setOwDbAnalyzeJob] = useState(null)
  const [owRealtimeFlights, setOwRealtimeFlights] = useState([])
  const [owRealtimeAvailable, setOwRealtimeAvailable] = useState(false)
  const [owRealtimeObservedAt, setOwRealtimeObservedAt] = useState(null)
  const [owRealtimeExpiresAt, setOwRealtimeExpiresAt] = useState(null)
  const [owRealtimeAnalyzeJob, setOwRealtimeAnalyzeJob] = useState(null)
  const [activeRtSourceMode, setActiveRtSourceMode] = useState('db')
  const [rtDbGroups, setRtDbGroups] = useState([])
  const [rtDbObservedAt, setRtDbObservedAt] = useState(null)
  const [rtDbExpiresAt, setRtDbExpiresAt] = useState(null)
  const [rtRealtimeGroups, setRtRealtimeGroups] = useState([])
  const [rtRealtimeAvailable, setRtRealtimeAvailable] = useState(false)
  const [rtRealtimeObservedAt, setRtRealtimeObservedAt] = useState(null)
  const [rtRealtimeExpiresAt, setRtRealtimeExpiresAt] = useState(null)

  useEffect(() => {
    activeOwSourceModeRef.current = activeOwSourceMode
  }, [activeOwSourceMode])

  useEffect(() => {
    activeRtSourceModeRef.current = activeRtSourceMode
  }, [activeRtSourceMode])

  const origin = state.origin
  const destination = state.destination
  const departDate = state.departDate
  const computedReturnDate = isRound && departDate ? addDays(departDate, 7) : state.returnDate
  const roundSearch = isRound
    ? {
        ...state,
        returnDate: computedReturnDate,
        stayNights: 7,
      }
    : state
  const currentSearchKey = isRound
    ? buildRoundtripCacheKey({
        origin,
        destination,
        departDate,
        returnDate: computedReturnDate,
      })
    : buildSearchCacheKey({ origin, destination, departDate })
  const currentScrollKey = buildSearchResultScrollKey(currentSearchKey)

  const saveSearchResultScroll = () => {
    if (!currentScrollKey) return
    try {
      const container = getPageScrollContainer(pageRef.current)
      sessionStorage.setItem(currentScrollKey, JSON.stringify({
        scrollTop: readScrollTop(container),
        savedAt: Date.now(),
      }))
    } catch {
      // best-effort scroll restoration
    }
  }

  useEffect(() => {
    restoredScrollKeyRef.current = null
  }, [currentScrollKey])

  useEffect(() => {
    const hasResults = isRound ? roundGroups.length > 0 : flights.length > 0
    if (!hasResults || !currentScrollKey) return undefined
    if (restoredScrollKeyRef.current === currentScrollKey) return undefined

    let parsed
    try {
      const raw = sessionStorage.getItem(currentScrollKey)
      if (!raw) return undefined
      parsed = JSON.parse(raw)
    } catch {
      sessionStorage.removeItem(currentScrollKey)
      return undefined
    }

    const savedAt = Number(parsed?.savedAt)
    const scrollTop = Number(parsed?.scrollTop)
    if (!Number.isFinite(savedAt) || Date.now() - savedAt > SEARCH_RESULT_SCROLL_TTL_MS || !Number.isFinite(scrollTop)) {
      sessionStorage.removeItem(currentScrollKey)
      return undefined
    }

    restoredScrollKeyRef.current = currentScrollKey
    let cancelled = false
    let attempts = 0

    const restore = () => {
      if (cancelled) return
      writeScrollTop(getPageScrollContainer(pageRef.current), scrollTop)
      attempts += 1
      if (attempts < 3) {
        requestAnimationFrame(restore)
      } else {
        sessionStorage.removeItem(currentScrollKey)
      }
    }

    requestAnimationFrame(restore)
    return () => {
      cancelled = true
    }
  }, [currentScrollKey, flights.length, isRound, roundGroups.length])

  useEffect(() => {
    const normalizedOrigin = normalizeCode(origin)
    const normalizedDestination = normalizeCode(destination)
    const routeKey = `${normalizedOrigin}-${normalizedDestination}`
    if (!ANALYSIS_VALID_ROUTES.has(routeKey)) return

    const ctx = {
      tripType: isRound ? 'round' : 'oneway',
      origin: normalizedOrigin,
      destination: normalizedDestination,
      stayNights: isRound ? (state.stayNights || 7) : null,
      savedAt: Date.now(),
    }
    try {
      sessionStorage.setItem(ANALYSIS_CONTEXT_KEY, JSON.stringify(ctx))
    } catch {
      // best-effort only
    }
  }, [isRound, origin, destination, state.stayNights])

  const stopPolling = () => {
    if (pollingTimerRef.current) {
      clearTimeout(pollingTimerRef.current)
      pollingTimerRef.current = null
    }
  }

  const applyAnalyzeMetaToUi = (meta, totalFallback = 0) => {
    if (!meta) {
      setAnalyzeStatus('')
      setAnalyzeProgress(null)
      return
    }
    setAnalyzeStatus(meta.status || '')
    setAnalyzeProgress({
      completed: (meta.completed_count || 0) + (meta.failed_count || 0),
      total: meta.total_count || totalFallback || 0,
      failed: meta.failed_count || 0,
    })
  }

  const applyJobStatus = (jobId, analyzeKey, data) => {
    if (jobId !== activeJobIdRef.current) return
    if (analyzeKey !== activeSearchKeyRef.current) return

    const { searchKey, sourceMode, tripType } = parseAnalyzeKey(analyzeKey)
    const meta = analyzeJobMeta(jobId, data)
    setAnalyzeStatus(data.status)
    setAnalyzeProgress({
      completed: (data.completed_count || 0) + (data.failed_count || 0),
      total: data.total_count || 0,
      failed: data.failed_count || 0,
    })

    let nextOffers = null
    updateCachedSearch(searchKey, cached => {
      const currentResult = getSourceResult(cached, sourceMode)
      const offers = currentResult?.offers || []
      const merged = tripType === 'roundtrip'
        ? mergeRoundtripJobPredictionsToOffers(offers, data.predictions || [])
        : mergePredictionsToOffers(offers, data.predictions || [])
      nextOffers = merged.offers
      const nextResult = makeSourceResult(merged.offers, {
        ...currentResult,
        sourceMode,
        source: currentResult?.source || sourceFromMode(sourceMode),
        analyzeJob: meta,
        analyzedAt: TERMINAL_JOB_STATUSES.has(data.status) ? Date.now() : currentResult?.analyzedAt || null,
      })
      return {
        ...cached,
        activeSourceMode: cached.activeSourceMode || sourceMode,
        [sourceResultKey(sourceMode)]: nextResult,
        offers: (cached.activeSourceMode || sourceMode) === sourceMode
          ? merged.offers
          : cached.offers,
        analyzeJob: (cached.activeSourceMode || sourceMode) === sourceMode
          ? meta
          : cached.analyzeJob,
      }
    })

    if (nextOffers && tripType === 'roundtrip') {
      const searchMeta = getCachedSearch(searchKey) || {}
      const nextGroups = nextOffers.map((offer, index) => (
        candidateToRoundGroup(offer, getSourceResult(searchMeta, sourceMode)?.observedAt || searchMeta.observedAt || null, index)
      ))
      if (sourceMode === 'realtime') {
        setRtRealtimeGroups(nextGroups)
      } else {
        setRtDbGroups(nextGroups)
      }
      if (isRound && activeRtSourceModeRef.current === sourceMode) {
        setRoundGroups(nextGroups)
      }
    } else if (nextOffers) {
      const nextFlights = nextOffers.map(mapOfferToFlight)
      if (sourceMode === 'realtime') {
        setOwRealtimeFlights(nextFlights)
        setOwRealtimeAnalyzeJob(meta)
      } else {
        setOwDbFlights(nextFlights)
        setOwDbAnalyzeJob(meta)
      }
      if (!isRound && activeOwSourceModeRef.current === sourceMode) {
        setFlights(nextFlights)
      }
    }

    if (TERMINAL_JOB_STATUSES.has(data.status)) {
      saveActiveAnalyzeJob(jobId, analyzeKey, data.status)
    }
  }

  const schedulePolling = (jobId, analyzeKey) => {
    stopPolling()
    activeJobIdRef.current = jobId
    activeSearchKeyRef.current = analyzeKey
    if (!pollingStartedAtRef.current) {
      pollingStartedAtRef.current = Date.now()
    }

    const poll = () => {
      if (jobId !== activeJobIdRef.current || analyzeKey !== activeSearchKeyRef.current) return
      if (Date.now() - pollingStartedAtRef.current > MAX_POLLING_MS) {
        setAnalyzeStatus('timeout')
        stopPolling()
        return
      }

      getAnalyzeJobStatus(jobId)
        .then(data => {
          if (jobId !== activeJobIdRef.current || analyzeKey !== activeSearchKeyRef.current) return
          applyJobStatus(jobId, analyzeKey, data)
          if (!TERMINAL_JOB_STATUSES.has(data.status)) {
            pollingTimerRef.current = setTimeout(poll, POLLING_INTERVAL_MS)
          }
        })
        .catch(() => {
          if (jobId !== activeJobIdRef.current || analyzeKey !== activeSearchKeyRef.current) return
          pollingTimerRef.current = setTimeout(poll, POLLING_INTERVAL_MS)
        })
    }

    poll()
  }

  const startAnalyzeJob = (searchKey, offers, sourceMode = activeOwSourceMode || 'db', tripType = 'oneway', searchMeta = {}) => {
    const normalizedTripType = tripType === 'roundtrip' ? 'roundtrip' : 'oneway'
    const analyzeKey = buildAnalyzeKey(searchKey, sourceMode, normalizedTripType)
    const cachedResult = getSourceResult(getCachedSearch(searchKey), sourceMode)
    const cachedJob = cachedResult?.analyzeJob
    if (cachedJob?.status === 'done') {
      applyAnalyzeMetaToUi(cachedJob, cachedResult.offers?.length || offers.length)
      return Promise.resolve(true)
    }
    if (
      cachedJob?.job_id
      && !TERMINAL_JOB_STATUSES.has(cachedJob.status)
    ) {
      activeJobIdRef.current = cachedJob.job_id
      activeSearchKeyRef.current = analyzeKey
      pollingStartedAtRef.current = Date.now()
      applyAnalyzeMetaToUi(cachedJob, cachedResult.offers?.length || offers.length)
      schedulePolling(cachedJob.job_id, analyzeKey)
      return Promise.resolve(true)
    }

    const eligibleOffers = offers.filter(offer => (
      offer.flight_number
      && (normalizedTripType !== 'roundtrip' || offer.ret_flight_number)
      && offer.price_krw !== null
      && offer.price_krw !== undefined
    )).map(offer => {
      if (normalizedTripType !== 'roundtrip') return offer
      return {
        ...offer,
        return_date: offer.return_date || searchMeta.returnDate || searchMeta.return_date || null,
        stay_nights: offer.stay_nights || searchMeta.stayNights || searchMeta.stay_nights || 7,
      }
    })
    if (eligibleOffers.length === 0) return Promise.resolve(false)

    setAnalyzeStatus('starting')
    return analyzeJob({
      origin: normalizeCode(origin),
      destination: normalizeCode(destination),
      depart_date: String(departDate).trim(),
      trip_type: normalizedTripType,
      offers: eligibleOffers,
    })
      .then(data => {
        if (!data?.job_id || data.status === 'rejected_max_jobs') {
          setAnalyzeStatus(data?.status || 'error')
          return false
        }

        activeJobIdRef.current = data.job_id
        activeSearchKeyRef.current = analyzeKey
        pollingStartedAtRef.current = Date.now()
        setAnalyzeStatus(data.status)
        setAnalyzeProgress({
          completed: 0,
          total: data.total_count || eligibleOffers.length,
          failed: 0,
        })
        saveActiveAnalyzeJob(data.job_id, analyzeKey, data.status)
        const meta = {
          job_id: data.job_id,
          status: data.status,
          completed_count: 0,
          total_count: data.total_count || eligibleOffers.length,
          failed_count: 0,
          updatedAt: Date.now(),
        }
        if (normalizedTripType === 'oneway' && sourceMode === 'realtime') {
          setOwRealtimeAnalyzeJob(meta)
        } else if (normalizedTripType === 'oneway') {
          setOwDbAnalyzeJob(meta)
        }
        updateCachedSearch(searchKey, cached => ({
          ...cached,
          activeSourceMode: sourceMode,
          [sourceResultKey(sourceMode)]: {
            ...(getSourceResult(cached, sourceMode) || makeSourceResult(offers, { sourceMode })),
            analyzeJob: meta,
          },
          analyzeJob: meta,
        }))
        schedulePolling(data.job_id, analyzeKey)
        return true
      })
      .catch(() => {
        setAnalyzeStatus('error')
        return false
      })
  }

  const startRoundtripPrediction = (cacheKey, offers, sourceMode, searchMeta) => {
    const mode = sourceMode === 'realtime' ? 'realtime' : 'db'
    const predictKey = `${cacheKey}:${mode}`
    if (roundtripPredictionRunningMap.has(predictKey) || roundtripPredictionDoneSet.has(predictKey)) return
    if (!Array.isArray(offers) || offers.length === 0) return

    const eligibleOffers = offers
      .filter(offer => (
        !offer.prediction
        && offer.flight_number
        && offer.ret_flight_number
        && offer.price_krw !== null
        && offer.price_krw !== undefined
      ))
    if (eligibleOffers.length === 0) return

    const promise = Promise.resolve()
      .then(() => startAnalyzeJob(cacheKey, eligibleOffers, mode, 'roundtrip', searchMeta))
      .then(accepted => {
        if (accepted) {
          roundtripPredictionDoneSet.add(predictKey)
        }
      })
      .catch(() => {
        setAnalyzeStatus('failed')
      })
      .finally(() => {
        roundtripPredictionRunningMap.delete(predictKey)
      })
    roundtripPredictionRunningMap.set(predictKey, promise)
  }

  const stopRtRefreshPolling = () => {
    if (rtRefreshPollingTimerRef.current) {
      clearTimeout(rtRefreshPollingTimerRef.current)
      rtRefreshPollingTimerRef.current = null
    }
    if (rtRefreshElapsedTimerRef.current) {
      clearInterval(rtRefreshElapsedTimerRef.current)
      rtRefreshElapsedTimerRef.current = null
    }
  }

  const stopOwRefreshPolling = () => {
    if (owRefreshPollingTimerRef.current) {
      clearTimeout(owRefreshPollingTimerRef.current)
      owRefreshPollingTimerRef.current = null
    }
    if (owRefreshElapsedTimerRef.current) {
      clearInterval(owRefreshElapsedTimerRef.current)
      owRefreshElapsedTimerRef.current = null
    }
  }

  const isFreshRealtimeSource = (source, expiresAt) => {
    if (source !== 'realtime_refresh') return false
    if (!expiresAt) return false
    const expiresMs = Date.parse(expiresAt)
    return Number.isFinite(expiresMs) && expiresMs > Date.now()
  }

  const clearOnewayRefreshJob = cacheKey => {
    if (cacheKey && onewayRefreshJobMap.get(cacheKey) === owRefreshJobIdRef.current) {
      onewayRefreshJobMap.delete(cacheKey)
    }
  }

  const handleOwSourceToggle = mode => {
    if (mode === activeOwSourceMode) return
    if (mode === 'realtime') {
      if (!owRealtimeAvailable || owRealtimeFlights.length === 0) return
      setFlights(owRealtimeFlights)
      setOwSource('realtime_refresh')
      setOwSourceLabel('실시간 검색 결과')
      setOwObservedAt(owRealtimeObservedAt)
      setOwExpiresAt(owRealtimeExpiresAt)
      setActiveOwSourceMode('realtime')
      applyAnalyzeMetaToUi(owRealtimeAnalyzeJob, owRealtimeFlights.length)
      updateCachedSearch(
        buildSearchCacheKey({ origin, destination, departDate }),
        cached => ({
          ...cached,
          activeSourceMode: 'realtime',
          offers: getSourceResult(cached, 'realtime')?.offers || cached.offers,
          source: 'realtime_refresh',
          observedAt: owRealtimeObservedAt,
          expiresAt: owRealtimeExpiresAt,
          analyzeJob: owRealtimeAnalyzeJob,
        }),
      )
      return
    }

    setFlights(owDbFlights)
    setOwSource('db_observation')
    setOwSourceLabel('최신 DB 관측 결과')
    setOwObservedAt(owDbObservedAt)
    setOwExpiresAt(owDbExpiresAt)
    setActiveOwSourceMode('db')
    applyAnalyzeMetaToUi(owDbAnalyzeJob, owDbFlights.length)
    updateCachedSearch(
      buildSearchCacheKey({ origin, destination, departDate }),
      cached => ({
        ...cached,
        activeSourceMode: 'db',
        offers: getSourceResult(cached, 'db')?.offers || cached.offers,
        source: 'db_observation',
        observedAt: owDbObservedAt,
        expiresAt: owDbExpiresAt,
        analyzeJob: owDbAnalyzeJob,
      }),
    )
  }

  const handleRtSourceToggle = mode => {
    if (mode === activeRtSourceMode) return
    if (mode === 'realtime') {
      if (!rtRealtimeAvailable || rtRealtimeGroups.length === 0) return
      setRoundGroups(rtRealtimeGroups)
      setRoundSource('realtime_refresh')
      setRoundObservedAt(rtRealtimeObservedAt)
      setRoundExpiresAt(rtRealtimeExpiresAt)
      activeRtSourceModeRef.current = 'realtime'
      setActiveRtSourceMode('realtime')
      startRoundtripPrediction(
        buildRoundtripCacheKey({
          origin,
          destination,
          departDate,
          returnDate: computedReturnDate,
        }),
        rtRealtimeGroups.map(group => group.outbound.rawOffer || {}).filter(Boolean),
        'realtime',
        {
          origin,
          destination,
          departDate,
          returnDate: computedReturnDate,
          stayNights: 7,
          observedAt: rtRealtimeObservedAt,
        },
      )
      updateCachedSearch(
        buildRoundtripCacheKey({
          origin,
          destination,
          departDate,
          returnDate: computedReturnDate,
        }),
        cached => ({
          ...cached,
          activeSourceMode: 'realtime',
          offers: getSourceResult(cached, 'realtime')?.offers || cached.offers,
          source: 'realtime_refresh',
          observedAt: rtRealtimeObservedAt,
          expiresAt: rtRealtimeExpiresAt,
        }),
      )
      return
    }

    setRoundGroups(rtDbGroups)
    setRoundSource('db_observation')
    setRoundObservedAt(rtDbObservedAt)
    setRoundExpiresAt(rtDbExpiresAt)
    activeRtSourceModeRef.current = 'db'
    setActiveRtSourceMode('db')
    startRoundtripPrediction(
      buildRoundtripCacheKey({
        origin,
        destination,
        departDate,
        returnDate: computedReturnDate,
      }),
      rtDbGroups.map(group => group.outbound.rawOffer || {}).filter(Boolean),
      'db',
      {
        origin,
        destination,
        departDate,
        returnDate: computedReturnDate,
        stayNights: 7,
        observedAt: rtDbObservedAt,
      },
    )
    updateCachedSearch(
      buildRoundtripCacheKey({
        origin,
        destination,
        departDate,
        returnDate: computedReturnDate,
      }),
      cached => ({
        ...cached,
        activeSourceMode: 'db',
        offers: getSourceResult(cached, 'db')?.offers || cached.offers,
        source: 'db_observation',
        observedAt: rtDbObservedAt,
        expiresAt: rtDbExpiresAt,
      }),
    )
  }

  const refreshOnewayCandidates = async (
    cacheKey,
    requestOrigin,
    requestDestination,
    requestDepartDate,
  ) => {
    try {
      const payload = {
        origin: normalizeCode(requestOrigin),
        destination: normalizeCode(requestDestination),
        depart_date: String(requestDepartDate).trim(),
        limit: 20,
        source_mode: 'realtime',
      }
      const data = await fetchOnewayCandidates(payload)
      if (data?.status !== 'ok' || !Array.isArray(data.offers) || data.offers.length === 0) {
        return
      }

      const offers = data.offers
      const observedAt = data.observed_at || null
      const expiresAt = data.expires_at || null
      const realtimeFlights = offers.map(mapOfferToFlight)

      setOwRealtimeFlights(realtimeFlights)
      setOwRealtimeAvailable(true)
      setOwRealtimeObservedAt(observedAt)
      setOwRealtimeExpiresAt(expiresAt)
      setOwRealtimeAnalyzeJob(null)
      setActiveOwSourceMode('realtime')
      setFlights(realtimeFlights)
      setOwSource('realtime_refresh')
      setOwSourceLabel(data.source_label || '실시간 검색 결과')
      setOwObservedAt(observedAt)
      setOwExpiresAt(expiresAt)
      setAnalyzeStatus('')
      setAnalyzeProgress(null)
      setError('')
      writeSourceResultCache(
        cacheKey,
        {
          origin: normalizeCode(requestOrigin),
          destination: normalizeCode(requestDestination),
          departDate: String(requestDepartDate).trim(),
          tripType: 'oneway',
        },
        'realtime',
        makeSourceResult(offers, {
          sourceMode: 'realtime',
          source: 'realtime_refresh',
          sourceLabel: data.source_label || '실시간 검색 결과',
          observedAt,
          expiresAt,
          status: data.status || null,
        }),
        'realtime',
      )
      startAnalyzeJob(cacheKey, offers, 'realtime')
    } catch {
      // Keep existing candidates if refresh readback fails.
    }
  }
  const scheduleOwRefreshPolling = (
    jobId,
    cacheKey,
    requestOrigin,
    requestDestination,
    requestDepartDate,
  ) => {
    stopOwRefreshPolling()
    owRefreshJobIdRef.current = jobId
    owRefreshCacheKeyRef.current = cacheKey
    if (!owRefreshStartedAtRef.current) {
      owRefreshStartedAtRef.current = Date.now()
    }
    setOwRefreshStatus('running')
    setOwRefreshElapsed(0)
    setOwRefreshMessage(formatOwRefreshRunningMessage(0))

    owRefreshElapsedTimerRef.current = setInterval(() => {
      if (!owRefreshStartedAtRef.current) return
      const elapsed = Math.floor((Date.now() - owRefreshStartedAtRef.current) / 1000)
      setOwRefreshElapsed(elapsed)
      setOwRefreshMessage(formatOwRefreshRunningMessage(elapsed))
    }, 1000)

    const poll = () => {
      if (owRefreshJobIdRef.current !== jobId || owRefreshCacheKeyRef.current !== cacheKey) return
      if (Date.now() - owRefreshStartedAtRef.current > OW_REFRESH_MAX_POLLING_MS) {
        setOwRefreshStatus('timeout')
        setOwRefreshMessage(getRtRefreshTerminalMessage('timeout'))
        clearOnewayRefreshJob(cacheKey)
        stopOwRefreshPolling()
        return
      }

      getOnewayRefreshJob(jobId)
        .then(data => {
          if (owRefreshJobIdRef.current !== jobId || owRefreshCacheKeyRef.current !== cacheKey) return
          const status = data?.status || 'unknown'
          setOwRefreshStatus(status)

          if (
            status === 'success'
            || status === 'partial_success'
            || status === 'timeout_with_partial'
            || status === 'skipped_fresh_realtime'
          ) {
            clearOnewayRefreshJob(cacheKey)
            stopOwRefreshPolling()
            setOwRefreshMessage(getRtRefreshTerminalMessage(status))
            refreshOnewayCandidates(cacheKey, requestOrigin, requestDestination, requestDepartDate)
            return
          }

          if (OW_REFRESH_TERMINAL_STATUSES.has(status)) {
            clearOnewayRefreshJob(cacheKey)
            stopOwRefreshPolling()
            setOwRefreshMessage(getRtRefreshTerminalMessage(status))
            return
          }

          owRefreshPollingTimerRef.current = setTimeout(poll, OW_REFRESH_POLLING_INTERVAL_MS)
        })
        .catch(() => {
          if (owRefreshJobIdRef.current !== jobId || owRefreshCacheKeyRef.current !== cacheKey) return
          owRefreshPollingTimerRef.current = setTimeout(poll, OW_REFRESH_POLLING_INTERVAL_MS)
        })
    }

    owRefreshPollingTimerRef.current = setTimeout(poll, OW_REFRESH_POLLING_INTERVAL_MS)
  }

  const startOwRefreshIfNeeded = (
    cacheKey,
    source,
    expiresAt,
    requestOrigin,
    requestDestination,
    requestDepartDate,
  ) => {
    if (isFreshRealtimeSource(source, expiresAt)) {
      setOwRefreshStatus(null)
      setOwRefreshMessage('')
      setOwRefreshElapsed(0)
      return
    }

    if (onewayRefreshJobMap.has(cacheKey)) {
      const existingJobId = onewayRefreshJobMap.get(cacheKey)
      if (existingJobId && owRefreshJobIdRef.current !== existingJobId) {
        owRefreshStartedAtRef.current = Date.now()
        scheduleOwRefreshPolling(
          existingJobId,
          cacheKey,
          requestOrigin,
          requestDestination,
          requestDepartDate,
        )
      }
      return
    }

    const payload = {
      origin: normalizeCode(requestOrigin),
      destination: normalizeCode(requestDestination),
      depart_date: String(requestDepartDate).trim(),
      force_refresh: false,
      timeout_seconds: 180,
    }

    setOwRefreshStatus('starting')
    setOwRefreshElapsed(0)
    setOwRefreshMessage('실시간 검색을 시작합니다...')

    startOnewayRefreshJob(payload)
      .then(data => {
        const jobId = data?.job_id
        const postStatus = data?.status

        if (postStatus && OW_REFRESH_TERMINAL_STATUSES.has(postStatus)) {
          setOwRefreshStatus(postStatus)
          setOwRefreshMessage(getRtRefreshTerminalMessage(postStatus))
          if (
            postStatus === 'success'
            || postStatus === 'partial_success'
            || postStatus === 'timeout_with_partial'
            || postStatus === 'skipped_fresh_realtime'
          ) {
            refreshOnewayCandidates(cacheKey, requestOrigin, requestDestination, requestDepartDate)
          }
          return
        }

        if (!jobId) {
          setOwRefreshStatus(null)
          setOwRefreshMessage('')
          return
        }

        onewayRefreshJobMap.set(cacheKey, jobId)
        owRefreshJobIdRef.current = jobId
        owRefreshCacheKeyRef.current = cacheKey
        owRefreshStartedAtRef.current = Date.now()
        scheduleOwRefreshPolling(
          jobId,
          cacheKey,
          requestOrigin,
          requestDestination,
          requestDepartDate,
        )
      })
      .catch(() => {
        setOwRefreshStatus(null)
        setOwRefreshMessage('')
      })
  }

  const startRtRefreshElapsedTimer = () => {
    if (rtRefreshElapsedTimerRef.current) {
      clearInterval(rtRefreshElapsedTimerRef.current)
    }
    const updateElapsed = () => {
      const startedAt = rtRefreshStartedAtRef.current || Date.now()
      const elapsed = Math.max(0, Math.floor((Date.now() - startedAt) / 1000))
      setRoundRefreshElapsedSeconds(elapsed)
      setRoundRefreshMessage(formatRtRefreshRunningMessage(elapsed))
    }
    updateElapsed()
    rtRefreshElapsedTimerRef.current = setInterval(updateElapsed, 1000)
  }

  const refreshRoundtripCandidates = async (
    cacheKey,
    requestOrigin,
    requestDestination,
    requestDepartDate,
    requestReturnDate,
    requestStayNights,
  ) => {
    try {
      const payload = {
        origin: normalizeCode(requestOrigin),
        destination: normalizeCode(requestDestination),
        depart_date: String(requestDepartDate).trim(),
        return_date: requestReturnDate,
        stay_nights: requestStayNights,
        limit: 20,
        source_mode: 'realtime',
      }
      const data = await fetchRoundtripCandidates(payload)
      if (data?.status !== 'ok' || !Array.isArray(data.offers) || data.offers.length === 0) {
        return
      }

      const offers = data.offers
      const observedAt = data.observed_at || null
      const expiresAt = data.expires_at || null
      const realtimeGroups = offers.map((offer, index) => (
        candidateToRoundGroup(offer, observedAt, index)
      ))
      setRtRealtimeGroups(realtimeGroups)
      setRtRealtimeAvailable(true)
      setRtRealtimeObservedAt(observedAt)
      setRtRealtimeExpiresAt(expiresAt)
      activeRtSourceModeRef.current = 'realtime'
      setActiveRtSourceMode('realtime')
      setRoundGroups(realtimeGroups)
      setRoundObservedAt(observedAt)
      setRoundSource('realtime_refresh')
      setRoundExpiresAt(expiresAt)
      setRoundError('')

      writeSourceResultCache(
        cacheKey,
        {
          tripType: 'roundtrip',
          origin: normalizeCode(requestOrigin),
          destination: normalizeCode(requestDestination),
          departDate: String(requestDepartDate).trim(),
          returnDate: requestReturnDate,
          stayNights: requestStayNights,
        },
        'realtime',
        makeSourceResult(offers, {
          sourceMode: 'realtime',
          source: 'realtime_refresh',
          sourceLabel: data.source_label || null,
          observedAt,
          expiresAt,
          status: data.status || null,
        }),
        'realtime',
      )
      startRoundtripPrediction(cacheKey, offers, 'realtime', {
        origin: requestOrigin,
        destination: requestDestination,
        departDate: requestDepartDate,
        returnDate: requestReturnDate,
        stayNights: requestStayNights,
        observedAt,
      })
    } catch {
      // Keep the already rendered DB candidates if the refresh readback fails.
    }
  }

  const scheduleRtRefreshPolling = (
    jobId,
    cacheKey,
    requestOrigin,
    requestDestination,
    requestDepartDate,
    requestReturnDate,
    requestStayNights,
  ) => {
    stopRtRefreshPolling()
    rtRefreshJobIdRef.current = jobId
    rtRefreshCacheKeyRef.current = cacheKey
    if (!rtRefreshStartedAtRef.current) {
      rtRefreshStartedAtRef.current = Date.now()
    }
    setRoundRefreshStatus('running')
    startRtRefreshElapsedTimer()

    const poll = () => {
      if (rtRefreshJobIdRef.current !== jobId || rtRefreshCacheKeyRef.current !== cacheKey) return
      if (Date.now() - rtRefreshStartedAtRef.current > RT_REFRESH_MAX_POLLING_MS) {
        setRoundRefreshStatus('timeout')
        setRoundRefreshMessage('실시간 검색이 지연되어 최신 관측 결과를 유지합니다.')
        setRoundRefreshElapsedSeconds(null)
        stopRtRefreshPolling()
        return
      }

      getRoundtripRefreshJob(jobId)
        .then(data => {
          if (rtRefreshJobIdRef.current !== jobId || rtRefreshCacheKeyRef.current !== cacheKey) return
          const status = data?.status || 'unknown'
          setRoundRefreshStatus(status)

          if (status === 'success' || status === 'partial_success' || status === 'timeout_with_partial') {
            stopRtRefreshPolling()
            setRoundRefreshElapsedSeconds(null)
            setRoundRefreshMessage(getRtRefreshTerminalMessage(status))
            refreshRoundtripCandidates(
              cacheKey,
              requestOrigin,
              requestDestination,
              requestDepartDate,
              requestReturnDate,
              requestStayNights,
            )
            return
          }
          if (RT_REFRESH_TERMINAL_STATUSES.has(status)) {
            stopRtRefreshPolling()
            setRoundRefreshElapsedSeconds(null)
            setRoundRefreshMessage(getRtRefreshTerminalMessage(status))
            return
          }

          rtRefreshPollingTimerRef.current = setTimeout(poll, RT_REFRESH_POLLING_INTERVAL_MS)
        })
        .catch(() => {
          if (rtRefreshJobIdRef.current !== jobId || rtRefreshCacheKeyRef.current !== cacheKey) return
          rtRefreshPollingTimerRef.current = setTimeout(poll, RT_REFRESH_POLLING_INTERVAL_MS)
        })
    }

    rtRefreshPollingTimerRef.current = setTimeout(poll, RT_REFRESH_POLLING_INTERVAL_MS)
  }

  const startRtRefreshIfNeeded = (
    cacheKey,
    source,
    requestOrigin,
    requestDestination,
    requestDepartDate,
    requestReturnDate,
    requestStayNights,
  ) => {
    if (source === 'realtime_refresh') {
      setRoundRefreshStatus(null)
      setRoundRefreshMessage('')
      setRoundRefreshElapsedSeconds(null)
      return
    }
    if (roundtripRefreshJobMap.has(cacheKey)) {
      const existingJobId = roundtripRefreshJobMap.get(cacheKey)
      if (existingJobId && rtRefreshJobIdRef.current !== existingJobId) {
        rtRefreshStartedAtRef.current = Date.now()
        scheduleRtRefreshPolling(
          existingJobId,
          cacheKey,
          requestOrigin,
          requestDestination,
          requestDepartDate,
          requestReturnDate,
          requestStayNights,
        )
      }
      return
    }

    const payload = {
      origin: normalizeCode(requestOrigin),
      destination: normalizeCode(requestDestination),
      depart_date: String(requestDepartDate).trim(),
      return_date: requestReturnDate,
      stay_nights: requestStayNights,
      timeout_seconds: 180,
    }

    setRoundRefreshStatus('starting')
    setRoundRefreshElapsedSeconds(0)
    setRoundRefreshMessage(formatRtRefreshRunningMessage(0))

    startRoundtripRefreshJob(payload)
      .then(data => {
        const jobId = data?.job_id
        const postStatus = data?.status

        if (postStatus && RT_REFRESH_TERMINAL_STATUSES.has(postStatus)) {
          setRoundRefreshStatus(postStatus)
          setRoundRefreshMessage(getRtRefreshTerminalMessage(postStatus))
          return
        }

        if (!jobId) {
          setRoundRefreshStatus(null)
          setRoundRefreshMessage('')
          return
        }
        roundtripRefreshJobMap.set(cacheKey, jobId)
        rtRefreshJobIdRef.current = jobId
        rtRefreshCacheKeyRef.current = cacheKey
        rtRefreshStartedAtRef.current = Date.now()
        scheduleRtRefreshPolling(
          jobId,
          cacheKey,
          requestOrigin,
          requestDestination,
          requestDepartDate,
          requestReturnDate,
          requestStayNights,
        )
      })
      .catch(() => {
        setRoundRefreshStatus(null)
        setRoundRefreshMessage('')
      })
  }

  useEffect(() => {
    if (!isRound) return

    stopPolling()
    stopRtRefreshPolling()
    stopOwRefreshPolling()
    rtRefreshJobIdRef.current = null
    rtRefreshCacheKeyRef.current = null
    rtRefreshStartedAtRef.current = null
    owRefreshJobIdRef.current = null
    owRefreshCacheKeyRef.current = null
    owRefreshStartedAtRef.current = null
    setFlights([])
    setAnalyzeStatus('')
    setAnalyzeProgress(null)

    if (!origin || !destination || !departDate) {
      setRoundGroups([])
      setRoundLoading(false)
      setRoundError('검색 조건이 없습니다.')
      setRoundObservedAt(null)
      setRoundSource(null)
      setRoundExpiresAt(null)
      setRoundRefreshStatus(null)
      setRoundRefreshMessage('')
      setRoundRefreshElapsedSeconds(null)
      return
    }

    const returnDate = addDays(departDate, 7)
    const stayNights = 7
    const cacheKey = buildRoundtripCacheKey({
      origin,
      destination,
      departDate,
      returnDate,
    })

    let cancelled = false

    const cachedRoundtrip = getCachedSearch(cacheKey)
    const cachedRtActiveMode = cachedRoundtrip?.activeSourceMode === 'realtime' ? 'realtime' : 'db'
    const cachedRtResult = getSourceResult(cachedRoundtrip, cachedRtActiveMode)
    if (cachedRtResult?.offers?.length > 0) {
      const groups = cachedRtResult.offers.map((offer, index) => (
        candidateToRoundGroup(offer, cachedRtResult.observedAt, index)
      ))
      const dbResult = getSourceResult(cachedRoundtrip, 'db')
      const realtimeResult = getSourceResult(cachedRoundtrip, 'realtime')
      setRoundGroups(groups)
      if (dbResult?.offers?.length > 0) {
        setRtDbGroups(dbResult.offers.map((offer, index) => (
          candidateToRoundGroup(offer, dbResult.observedAt, index)
        )))
        setRtDbObservedAt(dbResult.observedAt || null)
        setRtDbExpiresAt(dbResult.expiresAt || null)
      }
      if (realtimeResult?.offers?.length > 0) {
        setRtRealtimeGroups(realtimeResult.offers.map((offer, index) => (
          candidateToRoundGroup(offer, realtimeResult.observedAt, index)
        )))
        setRtRealtimeAvailable(true)
        setRtRealtimeObservedAt(realtimeResult.observedAt || null)
        setRtRealtimeExpiresAt(realtimeResult.expiresAt || null)
      }
      activeRtSourceModeRef.current = cachedRtActiveMode
      setActiveRtSourceMode(cachedRtActiveMode)
      setRoundObservedAt(cachedRtResult.observedAt || null)
      setRoundSource(cachedRtResult.source || sourceFromMode(cachedRtActiveMode))
      setRoundExpiresAt(cachedRtResult.expiresAt || null)
      setRoundError('')
      setRoundLoading(false)
      startRtRefreshIfNeeded(cacheKey, cachedRtResult.source, origin, destination, departDate, returnDate, stayNights)
      startRoundtripPrediction(cacheKey, cachedRtResult.offers, cachedRtActiveMode, {
        origin,
        destination,
        departDate,
        returnDate,
        stayNights,
        observedAt: cachedRtResult.observedAt || null,
      })
      return () => {
        cancelled = true
        stopRtRefreshPolling()
        stopOwRefreshPolling()
        rtRefreshJobIdRef.current = null
        rtRefreshCacheKeyRef.current = null
        owRefreshJobIdRef.current = null
        owRefreshCacheKeyRef.current = null
      }
    }

    const payload = {
      origin: normalizeCode(origin),
      destination: normalizeCode(destination),
      depart_date: String(departDate).trim(),
      return_date: returnDate,
      stay_nights: stayNights,
      limit: 20,
      source_mode: 'db',
    }
    let requestPromise = roundtripCandidatePromiseMap.get(cacheKey)
    if (!requestPromise) {
      requestPromise = fetchRoundtripCandidates(payload)
      roundtripCandidatePromiseMap.set(cacheKey, requestPromise)
      const clearPromise = () => {
        if (roundtripCandidatePromiseMap.get(cacheKey) === requestPromise) {
          roundtripCandidatePromiseMap.delete(cacheKey)
        }
      }
      requestPromise.then(clearPromise, clearPromise)
    }

    setRoundLoading(true)
    setRoundError('')
    setRoundGroups([])
    setRoundObservedAt(null)
    setRoundSource(null)
    setRoundExpiresAt(null)
    setRoundRefreshStatus(null)
    setRoundRefreshMessage('')
    setRoundRefreshElapsedSeconds(null)
    activeRtSourceModeRef.current = 'db'
    setActiveRtSourceMode('db')
    setRtDbGroups([])
    setRtDbObservedAt(null)
    setRtDbExpiresAt(null)
    setRtRealtimeGroups([])
    setRtRealtimeAvailable(false)
    setRtRealtimeObservedAt(null)
    setRtRealtimeExpiresAt(null)

    requestPromise
      .then(data => {
        if (cancelled) return
        if (data?.status === 'ok' && Array.isArray(data.offers) && data.offers.length > 0) {
          const offers = data.offers
          const source = data.source || 'db_observation'
          const expiresAt = data.expires_at || null
          const groups = offers.map((offer, index) => (
            candidateToRoundGroup(offer, data.observed_at, index)
          ))
          setRoundGroups(groups)
          setRtDbGroups(groups)
          setRtDbObservedAt(data.observed_at || null)
          setRtDbExpiresAt(expiresAt)
          activeRtSourceModeRef.current = 'db'
          setActiveRtSourceMode('db')
          setRoundObservedAt(data.observed_at || null)
          setRoundSource(source)
          setRoundExpiresAt(expiresAt)
          writeSourceResultCache(
            cacheKey,
            {
              tripType: 'roundtrip',
              origin: normalizeCode(origin),
              destination: normalizeCode(destination),
              departDate: String(departDate).trim(),
              returnDate,
              stayNights,
            },
            'db',
            makeSourceResult(offers, {
              sourceMode: 'db',
              source,
              sourceLabel: data.source_label || null,
              observedAt: data.observed_at || null,
              expiresAt,
              status: data.status || null,
            }),
            'db',
          )
          startRoundtripPrediction(cacheKey, offers, 'db', {
            origin,
            destination,
            departDate,
            returnDate,
            stayNights,
            observedAt: data.observed_at || null,
          })
          startRtRefreshIfNeeded(cacheKey, source, origin, destination, departDate, returnDate, stayNights)
        } else {
          setRoundError(roundtripStatusMessage(data?.status))
        }
      })
      .catch(() => {
        if (cancelled) return
        setRoundError('왕복 후보 조회 중 오류가 발생했습니다.')
      })
      .finally(() => {
        if (cancelled) return
        setRoundLoading(false)
      })

    return () => {
      cancelled = true
      stopRtRefreshPolling()
      stopOwRefreshPolling()
      rtRefreshJobIdRef.current = null
      rtRefreshCacheKeyRef.current = null
      owRefreshJobIdRef.current = null
      owRefreshCacheKeyRef.current = null
    }
  }, [isRound, origin, destination, departDate])

  useEffect(() => {
    if (isRound) return

    if (!origin || !destination || !departDate) {
      setFlights([])
      setOwSource(null)
      setOwSourceLabel(null)
      setOwObservedAt(null)
      setOwExpiresAt(null)
      setOwRefreshStatus(null)
      setOwRefreshMessage('')
      setOwRefreshElapsed(0)
      setActiveOwSourceMode('db')
      setOwDbFlights([])
      setOwDbObservedAt(null)
      setOwDbExpiresAt(null)
      setOwDbAnalyzeJob(null)
      setOwRealtimeFlights([])
      setOwRealtimeAvailable(false)
      setOwRealtimeObservedAt(null)
      setOwRealtimeExpiresAt(null)
      setOwRealtimeAnalyzeJob(null)
      setLoading(false)
      setError('검색 조건이 없습니다. 다시 검색해주세요.')
      return
    }

    const searchKey = buildSearchCacheKey({ origin, destination, departDate })
    console.log('[SearchResultPage] cache key', searchKey)

    const cachedSearch = getCachedSearch(searchKey)
    const cachedActiveMode = cachedSearch?.activeSourceMode === 'realtime' ? 'realtime' : 'db'
    const cachedActiveResult = getSourceResult(cachedSearch, cachedActiveMode)
    if (cachedActiveResult?.offers?.length > 0) {
      console.log('[SearchResultPage] cache hit')
      const cachedFlights = cachedActiveResult.offers.map(mapOfferToFlight)
      const dbResult = getSourceResult(cachedSearch, 'db')
      const realtimeResult = getSourceResult(cachedSearch, 'realtime')
      setFlights(cachedFlights)
      setOwSource(cachedActiveResult.source || sourceFromMode(cachedActiveMode))
      setOwSourceLabel(cachedActiveResult.sourceLabel || null)
      setOwObservedAt(cachedActiveResult.observedAt || null)
      setOwExpiresAt(cachedActiveResult.expiresAt || null)
      if (dbResult?.offers?.length > 0) {
        setOwDbFlights(dbResult.offers.map(mapOfferToFlight))
        setOwDbObservedAt(dbResult.observedAt || null)
        setOwDbExpiresAt(dbResult.expiresAt || null)
        setOwDbAnalyzeJob(dbResult.analyzeJob || null)
      }
      if (realtimeResult?.offers?.length > 0) {
        setOwRealtimeFlights(realtimeResult.offers.map(mapOfferToFlight))
        setOwRealtimeAvailable(true)
        setOwRealtimeObservedAt(realtimeResult.observedAt || null)
        setOwRealtimeExpiresAt(realtimeResult.expiresAt || null)
        setOwRealtimeAnalyzeJob(realtimeResult.analyzeJob || null)
      }
      setActiveOwSourceMode(cachedActiveMode)
      startOwRefreshIfNeeded(
        searchKey,
        cachedActiveResult.source || null,
        cachedActiveResult.expiresAt || null,
        origin,
        destination,
        departDate,
      )
      setLoading(false)
      setError('')
      setSearchRetrying(false)
      const cachedJob = cachedActiveResult.analyzeJob
      const analyzeKey = buildAnalyzeKey(searchKey, cachedActiveMode)
      if (cachedJob?.job_id && !TERMINAL_JOB_STATUSES.has(cachedJob.status)) {
        activeJobIdRef.current = cachedJob.job_id
        activeSearchKeyRef.current = analyzeKey
        pollingStartedAtRef.current = Date.now()
        applyAnalyzeMetaToUi(cachedJob, cachedActiveResult.offers.length)
        schedulePolling(cachedJob.job_id, analyzeKey)
      } else if (cachedJob) {
        applyAnalyzeMetaToUi(cachedJob, cachedActiveResult.offers.length)
      } else {
        applyAnalyzeMetaToUi(null)
      }
      return
    }

    console.log('[SearchResultPage] cache miss, fetching')
    if (requesting.current) return

    let cancelled = false
    if (abortControllerRef.current) {
      abortControllerRef.current.abort()
    }
    const controller = new AbortController()
    abortControllerRef.current = controller
    const requestId = createSearchRequestId()
    activeSearchRequestIdRef.current = requestId

    const previousJob = getActiveAnalyzeJob()
    const previousJobBaseKey = parseAnalyzeKey(previousJob?.searchKey).searchKey
    if (
      previousJob?.job_id &&
      previousJobBaseKey &&
      previousJobBaseKey !== searchKey &&
      !TERMINAL_JOB_STATUSES.has(previousJob.status)
    ) {
      cancelAnalyzeJob(previousJob.job_id).catch(() => {})
    }
    stopPolling()
    activeJobIdRef.current = null
    activeSearchKeyRef.current = buildAnalyzeKey(searchKey, 'db')
    pollingStartedAtRef.current = null
    setAnalyzeStatus('')
    setAnalyzeProgress(null)
    requesting.current = true
    setLoading(true)
    setError('')
    setFlights([])
    setOwSource(null)
    setOwSourceLabel(null)
    setOwObservedAt(null)
    setOwExpiresAt(null)
    setOwRefreshStatus(null)
    setOwRefreshMessage('')
    setOwRefreshElapsed(0)
    setActiveOwSourceMode('db')
    setOwDbFlights([])
    setOwDbObservedAt(null)
    setOwDbExpiresAt(null)
    setOwDbAnalyzeJob(null)
    setOwRealtimeFlights([])
    setOwRealtimeAvailable(false)
    setOwRealtimeObservedAt(null)
    setOwRealtimeExpiresAt(null)
    setOwRealtimeAnalyzeJob(null)
    setSearchRetrying(false)

    const candidatesPayload = {
      origin: normalizeCode(origin),
      destination: normalizeCode(destination),
      depart_date: String(departDate).trim(),
      limit: 20,
      source_mode: 'db',
    }

    let requestPromise = onewayCandidatePromiseMap.get(searchKey)
    if (!requestPromise) {
      requestPromise = fetchOnewayCandidates(candidatesPayload)
      onewayCandidatePromiseMap.set(searchKey, requestPromise)
      const clearPromise = () => {
        if (onewayCandidatePromiseMap.get(searchKey) === requestPromise) {
          onewayCandidatePromiseMap.delete(searchKey)
        }
      }
      requestPromise.then(clearPromise, clearPromise)
    }

    requestPromise
      .then(data => {
        if (cancelled) return
        if (controller.signal.aborted) return
        if (activeSearchRequestIdRef.current !== requestId) return
        if (false && data.retryable && data.error === 'crawler busy retryable') {
          setError('현재 실시간 검색 요청이 많습니다. 잠시 후 다시 시도해주세요.')
          return
        }
        if (false && data.error) {
          setError(`검색 중 오류가 발생했습니다: ${data.error}`)
          return
        }

        if (data?.status !== 'ok' || !Array.isArray(data.offers) || data.offers.length === 0) {
          setError(onewayStatusMessage(data?.status))
          return
        }

        const offers = data.offers
        const source = data.source || 'db_observation'
        const sourceLabel = data.source_label || null
        const observedAt = data.observed_at || null
        const expiresAt = data.expires_at || null
        setCachedOffers(
          searchKey,
          { origin, destination, departDate },
          offers,
          {
            source,
            sourceLabel,
            observedAt,
            expiresAt,
            status: data.status || null,
          },
        )
        console.log('[SearchResultPage] cache saved')
        const dbFlights = offers.map(mapOfferToFlight)
        setFlights(dbFlights)
        setOwDbFlights(dbFlights)
        setOwDbObservedAt(observedAt)
        setOwDbExpiresAt(expiresAt)
        setActiveOwSourceMode('db')
        setOwSource(source)
        setOwSourceLabel(sourceLabel)
        setOwObservedAt(observedAt)
        setOwExpiresAt(expiresAt)
        if (offers.length > 0 && activeSearchRequestIdRef.current === requestId) {
          startAnalyzeJob(searchKey, offers, 'db')
        }
        startOwRefreshIfNeeded(searchKey, source, expiresAt, origin, destination, departDate)
      })
      .catch(err => {
        if (cancelled) return
        if (err?.name === 'AbortError') return
        if (activeSearchRequestIdRef.current !== requestId) return
        setError('현재 실시간 검색 요청이 많습니다. 잠시 후 다시 시도해주세요.')
      })
      .finally(() => {
        if (cancelled) return
        if (activeSearchRequestIdRef.current !== requestId) return
        setLoading(false)
        setSearchRetrying(false)
        requesting.current = false
      })

    return () => {
      cancelled = true
      stopPolling()
      stopOwRefreshPolling()
      clearOnewayRefreshJob(searchKey)
      owRefreshJobIdRef.current = null
      owRefreshCacheKeyRef.current = null
      owRefreshStartedAtRef.current = null
      if (abortControllerRef.current === controller) {
        abortControllerRef.current.abort()
        abortControllerRef.current = null
      }
      requesting.current = false
    }
  }, [origin, destination, departDate, isRound])

  const renderOnewayContent = () => {
    if (loading) {
      if (searchRetrying) {
        return (
          <div className={styles.emptyState}>
            <span>검색 요청이 많아 잠시 대기 중입니다. 곧 다시 시도합니다.</span>
          </div>
        )
      }
      return (
        <div className={styles.emptyState}>
          <span>항공권 정보를 검색 중입니다. 잠시만 기다려주세요.</span>
        </div>
      )
    }
    if (error && flights.length === 0) {
      return <div className={styles.emptyState}>{error}</div>
    }
    if (flights.length === 0) {
      return <div className={styles.emptyState}>검색 결과가 없습니다.</div>
    }

    return flights.map(f => (
      <FlightCard
        key={f.id}
        flight={f}
        onClick={() => {
          saveSearchResultScroll()
          navigate(`/card/${f.id}`, {
            state: {
              flight: f,
              search: {
                ...state,
                sourceMode: activeOwSourceMode,
                source: owSource,
                observedAt: owObservedAt,
                expiresAt: owExpiresAt,
              },
            },
          })
        }}
      />
    ))
  }

  const renderRoundContent = () => {
    if (roundLoading) {
      return (
        <div className={styles.emptyState}>
          왕복 후보를 불러오는 중입니다. 잠시만 기다려주세요.
        </div>
      )
    }
    if (roundError) {
      return (
        <div className={styles.emptyState}>
          {roundError}
        </div>
      )
    }
    if (roundGroups.length === 0) {
      return (
        <div className={styles.emptyState}>
          해당 7일 왕복 일정의 후보가 없습니다.
        </div>
      )
    }

    return roundGroups.map(g => (
      <RoundTripCard
        key={g.id || g.airline}
        group={g}
        search={roundSearch}
        onClick={() => {
          saveSearchResultScroll()
          navigate(`/card/${g.outbound.id}`, {
            state: {
              flight: g.outbound,
              returnFlight: g.inbound,
              search: {
                ...roundSearch,
                sourceMode: activeRtSourceMode,
                source: roundSource,
                observedAt: roundObservedAt,
                expiresAt: roundExpiresAt,
              },
            },
          })
        }}
      />
    ))
  }

  return (
    <div className={styles.page} ref={pageRef}>
      <header className={styles.header}>
        <button className={styles.backBtn} onClick={() => navigate(-1)}>
          <ArrowLeft size={22} color="#fff" />
        </button>
        <div className={styles.headerCenter}>
          <span className={styles.route}>
            {`${origin || '-'} → ${destination || '-'}`}
          </span>
          <span className={styles.date}>
            {isRound
              ? `출발 ${departDate || '-'} · 귀국 ${computedReturnDate || '-'}`
              : departDate}
          </span>
        </div>
        <div style={{ width: 36 }} />
      </header>

      <main className={styles.main}>
        <div className={styles.statusSummary}>
          <div className={styles.statusRow}>
            <span className={styles.statusCount}>
              {isRound
                ? (!roundLoading && !roundError && roundGroups.length > 0 ? `${roundGroups.length}개 항공권 왕복 조합` : '왕복 조합 확인 중')
                : `${flights.length}개 항공편 검색됨`}
            </span>
            <span className={styles.sourceBadge}>
              {isRound
                ? (activeRtSourceMode === 'realtime' ? '실시간' : 'DB 관측')
                : (activeOwSourceMode === 'realtime' ? '실시간' : 'DB 관측')}
            </span>
          </div>

          {analyzeStatus && (
            <div className={styles.statusRow}>
              <span className={styles.statusLabel}>
                {formatAnalyzeStatus(analyzeStatus, analyzeProgress)}
              </span>
            </div>
          )}

          {!isRound && owSource && flights.length > 0 && (
            <div className={styles.statusRow}>
              <span className={styles.statusLabel}>
                {owSource === 'realtime_refresh'
                  ? (owSourceLabel || '실시간 검색 결과')
                  : (owSourceLabel || '최신 DB 관측 결과')}
              </span>
              {owObservedAt && (
                <span className={styles.statusMeta}>
                  {owSource === 'realtime_refresh' ? `기준 ${owObservedAt}` : `관측 ${owObservedAt}`}
                </span>
              )}
              {owExpiresAt && owSource === 'realtime_refresh' && (
                <span className={styles.statusMeta}>만료 {owExpiresAt}</span>
              )}
            </div>
          )}

          {!isRound && owRefreshStatus === 'running' && (
            <div className={styles.statusRow}>
              <span className={styles.statusLabel}>{formatOwRefreshRunningMessage(owRefreshElapsed)}</span>
              <span className={styles.statusMeta}>결과가 준비되면 자동으로 갱신됩니다.</span>
            </div>
          )}

          {!isRound && owRefreshMessage && owRefreshStatus !== 'running' && (
            <div className={styles.statusRow}>
              <span className={styles.statusLabel}>{owRefreshMessage}</span>
            </div>
          )}

          {isRound && !roundLoading && !roundError && roundGroups.length > 0 && (
            <>
              <div className={styles.statusRow}>
                <span className={styles.statusLabel}>
                  {roundSource === 'realtime_refresh'
                    ? '실시간 검색 결과 · 7일 왕복 기준'
                    : '7일 왕복 기준 · 최신 DB 관측 결과'}
                </span>
              </div>
              <div className={styles.statusRow}>
                <span className={styles.statusMeta}>
                  {roundSource === 'realtime_refresh'
                    ? `방금 갱신된 결과입니다.${roundObservedAt ? ` 기준 ${roundObservedAt}` : ''}${roundExpiresAt ? ` · 만료 ${roundExpiresAt}` : ''}`
                    : `실시간 검색 중 또는 최신 관측 기준.${roundObservedAt ? ` 관측 ${roundObservedAt}` : ''}`}
                </span>
              </div>
              {roundRefreshMessage && (
                <div className={styles.statusRow}>
                  <span className={styles.statusLabel}>{roundRefreshMessage}</span>
                </div>
              )}
            </>
          )}

          {!isRound && (owDbFlights.length > 0 || owRealtimeAvailable) && (
            <div className={styles.sourceToggleRow}>
              <button
                type="button"
                onClick={() => handleOwSourceToggle('db')}
                style={{
                  padding: '4px 12px',
                  borderRadius: '16px',
                  fontSize: '11px',
                  border: 'none',
                  cursor: 'pointer',
                  background: activeOwSourceMode === 'db' ? '#1d4ed8' : '#e2e8f0',
                  color: activeOwSourceMode === 'db' ? '#fff' : '#64748b',
                }}
              >
                DB 관측
              </button>
              <button
                type="button"
                onClick={() => owRealtimeAvailable && handleOwSourceToggle('realtime')}
                style={{
                  padding: '4px 12px',
                  borderRadius: '16px',
                  fontSize: '11px',
                  border: 'none',
                  cursor: owRealtimeAvailable ? 'pointer' : 'default',
                  background: activeOwSourceMode === 'realtime' ? '#1d4ed8' : '#e2e8f0',
                  color: activeOwSourceMode === 'realtime' ? '#fff' : owRealtimeAvailable ? '#64748b' : '#cbd5e1',
                  opacity: owRealtimeAvailable ? 1 : 0.5,
                }}
              >
                실시간
              </button>
            </div>
          )}

          {isRound && !roundLoading && (rtDbGroups.length > 0 || rtRealtimeAvailable) && (
            <div className={styles.sourceToggleRow}>
              <button
                type="button"
                onClick={() => handleRtSourceToggle('db')}
                style={{
                  padding: '4px 12px',
                  borderRadius: '16px',
                  fontSize: '11px',
                  border: 'none',
                  cursor: 'pointer',
                  background: activeRtSourceMode === 'db' ? '#1d4ed8' : '#e2e8f0',
                  color: activeRtSourceMode === 'db' ? '#fff' : '#64748b',
                }}
              >
                DB 관측
              </button>
              <button
                type="button"
                onClick={() => rtRealtimeAvailable && handleRtSourceToggle('realtime')}
                style={{
                  padding: '4px 12px',
                  borderRadius: '16px',
                  fontSize: '11px',
                  border: 'none',
                  cursor: rtRealtimeAvailable ? 'pointer' : 'default',
                  background: activeRtSourceMode === 'realtime' ? '#1d4ed8' : '#e2e8f0',
                  color: activeRtSourceMode === 'realtime' ? '#fff' : rtRealtimeAvailable ? '#64748b' : '#cbd5e1',
                  opacity: rtRealtimeAvailable ? 1 : 0.5,
                }}
              >
                실시간
              </button>
            </div>
          )}
        </div>
        <div className={styles.list}>
          {isRound ? renderRoundContent() : renderOnewayContent()}
        </div>
      </main>
    </div>
  )
}
