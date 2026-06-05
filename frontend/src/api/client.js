// frontend/src/api/client.js
// 백엔드 API 호출 헬퍼
// Vercel 프록시(/api/*) 사용 — Mixed Content 방지

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || ''

export class ApiError extends Error {
  constructor(status) {
    super(`API 오류 ${status}`)
    this.status = status
  }
}

export async function apiCall(path, options = {}, token = null) {
  const { signal, ...restOptions } = options
  const headers = { 'Content-Type': 'application/json', ...(restOptions.headers || {}) }
  if (token) headers['Authorization'] = `Bearer ${token}`

  // VITE_BACKEND_URL 없으면 /api 프록시 경로 사용 (Vercel 배포)
  // 있으면 직접 호출 (로컬 개발)
  const base = BACKEND_URL || '/api'
  const resp = await fetch(`${base}${path}`, { ...restOptions, signal, headers })

  if (resp.status === 401) {
    localStorage.removeItem('airchoice_user')
    window.location.href = '/login'
    throw new ApiError(401)
  }

  if (!resp.ok) throw new ApiError(resp.status)
  return resp.json()
}

export async function recommendSearch(request) {
  return apiCall('/recommend/search', {
    method: 'POST',
    body: JSON.stringify(request),
  })
}

export async function searchFlights(request, { signal } = {}) {
  return apiCall('/flights/search', {
    method: 'POST',
    body: JSON.stringify(request),
    signal,
  })
}

export async function predictOne(request) {
  return apiCall('/recommend/predict-one', {
    method: 'POST',
    body: JSON.stringify(request),
  })
}

export async function fetchRoundtripCandidates(request) {
  const body = {
    origin: request.origin,
    destination: request.destination,
    depart_date: request.depart_date || request.departDate,
    return_date: request.return_date || request.returnDate,
    stay_nights: request.stay_nights ?? request.stayNights,
    limit: request.limit || 20,
  }
  if (request.sourceMode) body.source_mode = request.sourceMode
  if (request.source_mode) body.source_mode = request.source_mode
  return apiCall('/recommend/roundtrip-candidates', {
    method: 'POST',
    body: JSON.stringify(body),
  })
}

export async function fetchOnewayCandidates(request) {
  const body = {
    origin: request.origin,
    destination: request.destination,
    depart_date: request.depart_date || request.departDate,
    limit: request.limit || 20,
  }
  if (request.sourceMode) body.source_mode = request.sourceMode
  if (request.source_mode) body.source_mode = request.source_mode
  return apiCall('/recommend/oneway-candidates', {
    method: 'POST',
    body: JSON.stringify(body),
  })
}

export async function startRoundtripRefreshJob(request) {
  return apiCall('/recommend/roundtrip-refresh-job', {
    method: 'POST',
    body: JSON.stringify(request),
  })
}

export async function startOnewayRefreshJob(request) {
  return apiCall('/recommend/oneway-refresh-job', {
    method: 'POST',
    body: JSON.stringify(request),
  })
}

export async function getOnewayRefreshJob(jobId) {
  return apiCall(`/recommend/oneway-refresh-job/${jobId}`, {
    method: 'GET',
  })
}

export async function getRoundtripRefreshJob(jobId) {
  return apiCall(`/recommend/roundtrip-refresh-job/${jobId}`, {
    method: 'GET',
  })
}

export async function fetchRouteAnalysis() {
  return apiCall('/recommend/route-analysis', {
    method: 'GET',
  })
}

export async function fetchFlightHistory(request) {
  return apiCall('/recommend/history', {
    method: 'POST',
    body: JSON.stringify(request),
  })
}

export async function analyzeJob(request) {
  return apiCall('/recommend/analyze-job', {
    method: 'POST',
    body: JSON.stringify(request),
  })
}

export async function getAnalyzeJobStatus(jobId) {
  return apiCall(`/recommend/jobs/${jobId}`, {
    method: 'GET',
  })
}

export async function cancelAnalyzeJob(jobId) {
  return apiCall(`/recommend/jobs/${jobId}/cancel`, {
    method: 'POST',
  })
}

export async function fetchModelInfo() {
  return apiCall('/recommend/model-info', {
    method: 'GET',
  })
}
