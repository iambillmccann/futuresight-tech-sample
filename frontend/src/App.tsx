import { useMemo, useState } from 'react'
import {
  ArrowRight,
  ChevronLeft,
  ChevronRight,
  CircleHelp,
  Download,
  ExternalLink,
  Filter,
  Globe,
  MapPinned,
  MessageSquareText,
  Plus,
  RefreshCw,
  Search,
  ShieldAlert,
  Sparkles,
} from 'lucide-react'

type Review = {
  review_id: string
  author: string
  date: string | null
  rating: number
  text: string
  review_url?: string | null
}

function safeExternalUrl(value: string | null | undefined) {
  if (!value) return null
  try {
    const url = new URL(value)
    return url.protocol === 'https:' ? url.toString() : null
  } catch {
    return null
  }
}

type DatasetSummary = {
  review_count: number
  average_rating: number
  earliest_review: string | null
  latest_review: string | null
  rating_distribution: Record<string, number>
  skipped_review_count: number
  ingestion_status: 'complete' | 'partial'
}

type Analysis = {
  source: {
    source_key: string
    business_name: string
    platform: string
    source_url: string
  }
  dataset: {
    total_reviews: number
    sample_reviews: Review[]
    summary: DatasetSummary
  }
  cache_hit: boolean
  fetched_at: string
  warnings: string[]
}

type Message = {
  id: string
  role: 'question' | 'answer'
  text: string
  timestamp: string
  evidence?: Review[]
  status?: 'ok' | 'refused' | 'insufficient' | 'error'
}

const suggestionPrompts = [
  'What are the biggest complaints?',
  'How has customer sentiment changed over time?',
  'What themes appear most frequently?',
  'Is there feedback about prices?',
]

function getStars(rating: number) {
  return Array.from({ length: 5 }, (_, i) => i < Math.round(rating)).map((filled) =>
    filled ? '★' : '☆',
  )
}

function downloadFile(filename: string, content: string, type: string) {
  const url = URL.createObjectURL(new Blob([content], { type }))
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.click()
  setTimeout(() => URL.revokeObjectURL(url), 0)
}

function csvCell(value: string) {
  const safeValue = /^[\t\r ]*[=+\-@]/.test(value) ? `'${value}` : value
  return `"${safeValue.replaceAll('"', '""')}"`
}

function App() {
  const [sourceUrl, setSourceUrl] = useState('')
  const [analysis, setAnalysis] = useState<Analysis | null>(null)
  const [question, setQuestion] = useState('')
  const [loading, setLoading] = useState(false)
  const [asking, setAsking] = useState(false)
  const [error, setError] = useState('')
  const [transcript, setTranscript] = useState<Message[]>([])
  const [refreshing, setRefreshing] = useState(false)
  const [exporting, setExporting] = useState(false)
  const [browseOpen, setBrowseOpen] = useState(false)
  const [reviews, setReviews] = useState<Review[]>([])
  const [reviewPage, setReviewPage] = useState(1)
  const [reviewTotal, setReviewTotal] = useState(0)
  const [ratingFilter, setRatingFilter] = useState('')
  const [startDateFilter, setStartDateFilter] = useState('')
  const [endDateFilter, setEndDateFilter] = useState('')

  const loadAnalysis = async (urlToAnalyze = sourceUrl) => {
    if (loading || asking || refreshing || exporting) return
    if (!urlToAnalyze.trim()) {
      setError('Enter a full Google Maps place URL or amazon.com product URL to begin.')
      return
    }
    setLoading(true)
    setError('')
    try {
      const response = await fetch('/api/ingest', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ source_url: urlToAnalyze }),
      })
      const payload = await response.json()
      if (!response.ok) {
        throw new Error(payload.error?.message || 'Unable to ingest source.')
      }
      setAnalysis(payload.data)
      setTranscript([])
      setReviews([])
      setReviewPage(1)
      setReviewTotal(0)
      setBrowseOpen(false)
      setRatingFilter('')
      setStartDateFilter('')
      setEndDateFilter('')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to analyze the source.')
    } finally {
      setLoading(false)
    }
  }

  const askQuestion = async (promptText?: string) => {
    const nextQuestion = (promptText ?? question).trim()
    if (!nextQuestion || !analysis || asking || loading || refreshing) return

    setAsking(true)
    setQuestion('')
    setTranscript((current) => [
      ...current,
      { id: `q-${Date.now()}`, role: 'question', text: nextQuestion, timestamp: 'now' },
    ])

    try {
      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          source_key: analysis.source.source_key,
          question: nextQuestion,
        }),
      })
      const payload = await response.json()
      if (!response.ok) {
        throw new Error(payload.error?.message || 'Unable to answer question.')
      }

      const answer = payload.data
      setTranscript((current) => [
        ...current,
        {
          id: `a-${Date.now() + 1}`,
          role: 'answer',
          text: answer.answer,
          timestamp: 'now',
          evidence: answer.matching_reviews || [],
          status: answer.status,
        },
      ])
    } catch (err) {
      setTranscript((current) => [
        ...current,
        {
          id: `a-${Date.now() + 2}`,
          role: 'answer',
          text:
            err instanceof Error ? err.message : 'Unable to answer that question from the current dataset.',
          timestamp: 'now',
          status: 'error',
        },
      ])
    } finally {
      setAsking(false)
    }
  }

  const startNewAnalysis = () => {
    if (loading || asking || refreshing || exporting) return
    setSourceUrl('')
    setAnalysis(null)
    setTranscript([])
    setQuestion('')
    setError('')
    setReviews([])
    setBrowseOpen(false)
  }

  const refreshAnalysis = async () => {
    if (!analysis || refreshing || loading || asking || exporting) return
    setRefreshing(true)
    setError('')
    try {
      const response = await fetch('/api/refresh', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ source_key: analysis.source.source_key }),
      })
      const payload = await response.json()
      if (!response.ok) {
        throw new Error(payload.error?.message || 'Unable to refresh reviews.')
      }
      setAnalysis(payload.data)
      setTranscript([])
      setReviews([])
      setReviewPage(1)
      setReviewTotal(0)
      setBrowseOpen(false)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to refresh reviews.')
    } finally {
      setRefreshing(false)
    }
  }

  const loadReviews = async (
    page = 1,
    filters = {
      rating: ratingFilter,
      startDate: startDateFilter,
      endDate: endDateFilter,
    },
  ) => {
    if (!analysis) return
    const query = new URLSearchParams({
      source_key: analysis.source.source_key,
      page: String(page),
      page_size: '25',
    })
    if (filters.rating) query.set('rating', filters.rating)
    if (filters.startDate) query.set('start_date', filters.startDate)
    if (filters.endDate) query.set('end_date', filters.endDate)

    try {
      const response = await fetch(`/api/reviews?${query.toString()}`)
      const payload = await response.json()
      if (!response.ok) {
        throw new Error(payload.error?.message || 'Unable to load reviews.')
      }
      setReviews(payload.data.reviews)
      setReviewTotal(payload.data.total_reviews)
      setReviewPage(page)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to load reviews.')
    }
  }

  const exportReviews = async () => {
    if (!analysis || exporting) return
    setExporting(true)
    setError('')
    try {
      const allReviews: Review[] = []
      let page = 1
      let total = 0
      do {
        const query = new URLSearchParams({
          source_key: analysis.source.source_key,
          page: String(page),
          page_size: '200',
        })
        const response = await fetch(`/api/reviews?${query.toString()}`)
        const payload = await response.json()
        if (!response.ok) {
          throw new Error(payload.error?.message || 'Unable to export reviews.')
        }
        allReviews.push(...payload.data.reviews)
        total = payload.data.total_reviews
        page += 1
      } while (allReviews.length < total)

      const rows = [
        ['business', 'platform', 'source_url', 'review_id', 'author', 'date', 'rating', 'text', 'review_url'],
        ...allReviews.map((review) => [
          analysis.source.business_name,
          analysis.source.platform,
          analysis.source.source_url,
          review.review_id,
          review.author,
          review.date ?? '',
          String(review.rating),
          review.text,
          review.review_url ?? '',
        ]),
      ]
      const csv = rows.map((row) => row.map(csvCell).join(',')).join('\r\n')
      const slug = analysis.source.business_name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '')
      downloadFile(`${slug || 'reviews'}-reviews.csv`, csv, 'text/csv;charset=utf-8')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to export reviews.')
    } finally {
      setExporting(false)
    }
  }

  const exportSession = () => {
    if (!analysis) return
    const lines = [
      '# ReviewLens AI session analysis',
      '',
      `- Entity: ${analysis.source.business_name}`,
      `- Platform: ${analysis.source.platform}`,
      `- Source: ${analysis.source.source_url}`,
      `- Retrieved: ${new Date(analysis.fetched_at).toLocaleString()}`,
      `- Reviews: ${analysis.dataset.summary.review_count}`,
      `- Average rating: ${analysis.dataset.summary.average_rating.toFixed(2)}`,
      `- Review date range: ${analysis.dataset.summary.earliest_review ?? 'Unavailable'} – ${analysis.dataset.summary.latest_review ?? 'Unavailable'}`,
      '',
      '## Current session Q&A',
      '',
      ...(transcript.length
        ? transcript.map((message) => {
            const label = message.role === 'question' ? 'Question' : 'Answer'
            const evidence = message.evidence?.length
              ? `\n\nSupporting review IDs: ${message.evidence.map((review) => review.review_id).join(', ')}`
              : ''
            return `### ${label}\n\n${message.text}${evidence}`
          })
        : ['No questions have been asked in this session.']),
      '',
    ]
    const slug = analysis.source.business_name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '')
    downloadFile(`${slug || 'analysis'}-analysis.md`, lines.join('\n'), 'text/markdown;charset=utf-8')
  }

  const averageRating = useMemo(() => {
    if (!analysis) return 0
    return Number(analysis.dataset.summary.average_rating.toFixed(1))
  }, [analysis])

  return (
    <div className="min-h-screen bg-[#f3f4f6] text-slate-800 antialiased">
      <header className="border-b border-slate-200 bg-white/80 backdrop-blur-sm">
        <div className="mx-auto flex max-w-[1600px] items-center justify-between px-5 py-3.5">
          <div className="flex items-center gap-3">
            <div className="flex h-8 w-8 items-center justify-center rounded-full bg-[#eef1ff] text-[#4f46e5] shadow-sm">
              <Search className="h-4 w-4" />
            </div>
            <div className="text-[15px] font-semibold tracking-tight text-slate-900">
              ReviewLens AI
            </div>
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={startNewAnalysis}
              disabled={loading || asking || refreshing || exporting}
              className="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 shadow-sm transition hover:border-slate-300 hover:text-slate-900"
            >
              <Plus className="h-4 w-4" />
              New Analysis
            </button>
            <button className="rounded-lg px-3 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-100">
              How it works
            </button>
          </div>
        </div>
      </header>

      <main className="mx-auto flex max-w-[1600px] gap-6 px-5 py-5 lg:gap-8">
        <section className="flex-1 min-w-0 rounded-xl border border-slate-200 bg-white shadow-sm">
          <div className="border-b border-slate-200 px-4 py-3">
            <div className="flex flex-col gap-3 lg:flex-row lg:items-center">
              <div className="relative flex-1">
                <div className="pointer-events-none absolute inset-y-0 left-3 flex items-center text-slate-400">
                  <Globe className="h-4 w-4" />
                </div>
                <input
                  value={sourceUrl}
                  onChange={(event) => setSourceUrl(event.target.value)}
                  className="h-11 w-full rounded-md border border-slate-200 bg-slate-50 pl-10 pr-3 text-sm text-slate-700 outline-none ring-0 transition focus:border-[#5b4ad9] focus:bg-white"
                  placeholder="Google Maps place URL or https://www.amazon.com/dp/ASIN"
                  aria-label="Google Maps place or Amazon product source URL"
                />
              </div>
              <button
                onClick={() => void loadAnalysis()}
                className="inline-flex h-11 items-center justify-center rounded-md bg-[#5b4ad9] px-5 text-sm font-semibold text-white shadow-sm transition hover:bg-[#4f41cc] disabled:opacity-60"
                disabled={loading || asking || refreshing || exporting || !sourceUrl.trim()}
              >
                {loading ? 'Analyzing…' : 'Analyze Reviews'}
              </button>
            </div>
            <p className="mt-2 text-xs text-slate-500">
              Google Maps places and amazon.com products are supported. Amazon retrieves
              only the customer reviews visible on the product page, not the full review history.
            </p>
          </div>

          {error ? (
            <div className="border-b border-rose-100 bg-rose-50 px-4 py-3 text-sm text-rose-700">
              {error}
            </div>
          ) : null}

          {analysis ? (
            <>
              <div className="px-4 py-4">
                <div className="flex flex-col gap-3 rounded-xl border border-slate-200 bg-slate-50 px-4 py-4 md:flex-row md:items-center md:justify-between">
                  <div className="flex items-center gap-2 text-sm text-slate-500">
                    <div className="flex h-7 w-7 items-center justify-center rounded-md bg-[#eef1ff] text-[#5b4ad9]">
                      <MapPinned className="h-4 w-4" />
                    </div>
                    <span className="font-medium text-slate-700">Analysis completed</span>
                    <span className="text-slate-400">•</span>
                    <span>{new Date(analysis.fetched_at).toLocaleString([], { month: 'short', day: 'numeric', year: 'numeric', hour: 'numeric', minute: '2-digit' })}</span>
                  </div>
                  <div className="flex items-center gap-2 text-sm text-emerald-700">
                    <span className="inline-flex h-2.5 w-2.5 rounded-full bg-emerald-500" />
                    {analysis.dataset.summary.ingestion_status === 'partial' ? 'Partial dataset' : 'Active dataset'}
                  </div>
                </div>

                {analysis.dataset.summary.skipped_review_count > 0 ? (
                  <div className="mt-3 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
                    {analysis.dataset.summary.skipped_review_count.toLocaleString()} malformed review
                    {analysis.dataset.summary.skipped_review_count === 1 ? ' was' : 's were'} skipped during ingestion.
                  </div>
                ) : null}
                {analysis.warnings.map((warning) => (
                  <div
                    key={warning}
                    className="mt-3 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800"
                  >
                    {warning}
                  </div>
                ))}

                <div className="mt-4 grid gap-3 rounded-xl border border-slate-200 bg-white p-3 md:grid-cols-5">
                  <div className="rounded-lg bg-slate-50 p-3">
                    <div className="text-[11px] uppercase tracking-wide text-slate-500">Reviews collected</div>
                    <div className="mt-2 text-2xl font-semibold text-slate-900">{analysis.dataset.total_reviews.toLocaleString()}</div>
                  </div>
                  <div className="rounded-lg bg-slate-50 p-3">
                    <div className="text-[11px] uppercase tracking-wide text-slate-500">Average rating</div>
                    <div className="mt-2 flex items-center gap-2 text-2xl font-semibold text-slate-900">
                      {averageRating.toFixed(1)}
                      <div className="flex text-[#f5b301] text-lg">
                        {getStars(averageRating).map((star, idx) => (
                          <span key={`${star}-${idx}`}>{star}</span>
                        ))}
                      </div>
                    </div>
                  </div>
                  <div className="rounded-lg bg-slate-50 p-3">
                    <div className="text-[11px] uppercase tracking-wide text-slate-500">Earliest review</div>
                    <div className="mt-2 text-base font-semibold text-slate-900">{analysis.dataset.summary.earliest_review ?? 'Unavailable'}</div>
                  </div>
                  <div className="rounded-lg bg-slate-50 p-3">
                    <div className="text-[11px] uppercase tracking-wide text-slate-500">Latest review</div>
                    <div className="mt-2 text-base font-semibold text-slate-900">{analysis.dataset.summary.latest_review ?? 'Unavailable'}</div>
                  </div>
                  <div className="rounded-lg bg-slate-50 p-3">
                    <div className="text-[11px] uppercase tracking-wide text-slate-500">Platform</div>
                    <div className="mt-2 text-base font-semibold text-slate-900">{analysis.source.platform}</div>
                  </div>
                </div>
                <div className="mt-3 flex flex-wrap items-center gap-2">
                  <button
                    onClick={() => void refreshAnalysis()}
                    disabled={refreshing || loading || asking || exporting}
                    className="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 transition hover:border-slate-300 disabled:opacity-60"
                  >
                    <RefreshCw className={`h-4 w-4 ${refreshing ? 'animate-spin' : ''}`} />
                    {refreshing ? 'Refreshing…' : 'Refresh reviews'}
                  </button>
                  <button
                    onClick={() => void exportReviews()}
                    disabled={exporting || loading || refreshing}
                    className="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 transition hover:border-slate-300 disabled:opacity-60"
                  >
                    <Download className="h-4 w-4" />
                    {exporting ? 'Preparing CSV…' : 'Export reviews CSV'}
                  </button>
                  <button
                    onClick={exportSession}
                    className="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 transition hover:border-slate-300"
                  >
                    <Download className="h-4 w-4" />
                    Export session Markdown
                  </button>
                </div>
              </div>

              <div className="border-t border-slate-200 px-4 py-4">
                <div className="mb-3 flex items-center justify-between">
                  <h3 className="text-base font-semibold text-slate-800">
                    {browseOpen ? 'Browse reviews' : 'Review preview'}
                  </h3>
                  <button
                    onClick={() => {
                      const willOpen = !browseOpen
                      setBrowseOpen(willOpen)
                      if (willOpen) void loadReviews(1)
                    }}
                    className="text-sm font-medium text-[#5b4ad9]"
                  >
                    {browseOpen ? 'Show preview' : 'Browse all reviews'}
                  </button>
                </div>

                {browseOpen ? (
                  <div className="mb-3 grid gap-3 rounded-xl border border-slate-200 bg-slate-50 p-3 sm:grid-cols-3">
                    <label className="flex items-center gap-2 text-sm text-slate-600">
                      <Filter className="h-4 w-4" />
                      <span className="sr-only">Filter by rating</span>
                      <select
                        value={ratingFilter}
                        onChange={(event) => {
                          const rating = event.target.value
                          setRatingFilter(rating)
                          void loadReviews(1, { rating, startDate: startDateFilter, endDate: endDateFilter })
                        }}
                        className="h-10 w-full rounded-md border border-slate-200 bg-white px-3"
                        aria-label="Filter by rating"
                      >
                        <option value="">All ratings</option>
                        {[5, 4, 3, 2, 1].map((rating) => (
                          <option key={rating} value={rating}>{rating} stars</option>
                        ))}
                      </select>
                    </label>
                    <label className="text-sm text-slate-600">
                      <span className="sr-only">Reviews from</span>
                      <input
                        type="date"
                        value={startDateFilter}
                        onChange={(event) => {
                          const startDate = event.target.value
                          setStartDateFilter(startDate)
                          void loadReviews(1, { rating: ratingFilter, startDate, endDate: endDateFilter })
                        }}
                        className="h-10 w-full rounded-md border border-slate-200 bg-white px-3"
                        aria-label="Reviews from date"
                      />
                    </label>
                    <label className="text-sm text-slate-600">
                      <span className="sr-only">Reviews through</span>
                      <input
                        type="date"
                        value={endDateFilter}
                        onChange={(event) => {
                          const endDate = event.target.value
                          setEndDateFilter(endDate)
                          void loadReviews(1, { rating: ratingFilter, startDate: startDateFilter, endDate })
                        }}
                        className="h-10 w-full rounded-md border border-slate-200 bg-white px-3"
                        aria-label="Reviews through date"
                      />
                    </label>
                  </div>
                ) : null}

                <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
                  <table className="min-w-full text-left text-sm">
                    <thead className="bg-slate-50 text-slate-600">
                      <tr>
                        <th className="px-4 py-3 font-medium">Rating</th>
                        <th className="px-4 py-3 font-medium">Date</th>
                        <th className="px-4 py-3 font-medium">Reviewer</th>
                        <th className="px-4 py-3 font-medium">Review Text</th>
                        <th className="px-4 py-3 font-medium">Source</th>
                      </tr>
                    </thead>
                    <tbody>
                      {browseOpen && reviews.length === 0 ? (
                        <tr>
                          <td colSpan={5} className="px-4 py-8 text-center text-slate-500">
                            No reviews match these filters.
                          </td>
                        </tr>
                      ) : (browseOpen ? reviews : analysis.dataset.sample_reviews).map((review) => (
                        <tr key={review.review_id} className="border-t border-slate-200 align-top">
                          <td className="px-4 py-3 text-slate-800">
                            <div className="flex items-center gap-1 text-[#f5b301]">
                              {getStars(review.rating).map((star, idx) => (
                                <span key={`${review.review_id}-${idx}`}>{star}</span>
                              ))}
                            </div>
                          </td>
                          <td className="px-4 py-3 text-slate-600">{review.date ?? 'Unavailable'}</td>
                          <td className="px-4 py-3 font-medium text-slate-800">{review.author}</td>
                          <td className="max-w-[760px] px-4 py-3 text-slate-700">“{review.text}”</td>
                          <td className="px-4 py-3">
                            {safeExternalUrl(review.review_url) ? (
                              <a
                                href={safeExternalUrl(review.review_url) ?? undefined}
                                target="_blank"
                                rel="noreferrer"
                                className="inline-flex items-center gap-1 whitespace-nowrap text-[#5b4ad9] hover:underline"
                              >
                                Source <ExternalLink className="h-3 w-3" />
                              </a>
                            ) : (
                              <span className="text-xs text-slate-500" title={review.review_id}>
                                ID {review.review_id.slice(0, 8)}
                              </span>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                {browseOpen ? (
                  <div className="mt-3 flex flex-wrap items-center justify-between gap-3 text-sm text-slate-600">
                    <span>{reviewTotal.toLocaleString()} reviews match these filters</span>
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => void loadReviews(reviewPage - 1)}
                        disabled={reviewPage <= 1}
                        className="inline-flex items-center gap-1 rounded-md border border-slate-200 bg-white px-3 py-2 disabled:opacity-50"
                      >
                        <ChevronLeft className="h-4 w-4" /> Previous
                      </button>
                      <span>Page {reviewPage} of {Math.max(1, Math.ceil(reviewTotal / 25))}</span>
                      <button
                        onClick={() => void loadReviews(reviewPage + 1)}
                        disabled={reviewPage >= Math.ceil(reviewTotal / 25)}
                        className="inline-flex items-center gap-1 rounded-md border border-slate-200 bg-white px-3 py-2 disabled:opacity-50"
                      >
                        Next <ChevronRight className="h-4 w-4" />
                      </button>
                    </div>
                  </div>
                ) : null}
              </div>
            </>
          ) : null}

          <div className="border-t border-slate-200 bg-white px-4 py-4">
            <div className="space-y-3">
              {transcript.map((message) => (
                <div key={message.id} className="rounded-xl border border-slate-200 bg-slate-50/60">
                  <div className="border-b border-slate-200 bg-white/70 px-4 py-3 text-xs font-medium uppercase tracking-[0.12em] text-slate-500">
                    {message.role === 'question' ? 'Question' : 'Analysis'}
                    <span className="ml-2 font-normal normal-case tracking-normal text-slate-400">
                      • {message.timestamp}
                    </span>
                  </div>

                  <div className={`px-4 py-4 ${message.status === 'refused' ? 'bg-amber-50' : ''}`}>
                    <div className="flex gap-3">
                      <div className="mt-0.5 flex h-8 w-8 items-center justify-center rounded-md bg-[#eef1ff] text-[#5b4ad9]">
                        {message.status === 'refused' ? (
                          <ShieldAlert className="h-4 w-4 text-amber-700" />
                        ) : message.role === 'question' ? (
                          <CircleHelp className="h-4 w-4" />
                        ) : (
                          <Sparkles className="h-4 w-4" />
                        )}
                      </div>
                      <div className="flex-1">
                        <div className="text-[15px] leading-7 text-slate-900">{message.text}</div>
                        {message.role === 'answer' && message.evidence && message.evidence.length > 0 ? (
                          <div className="mt-4 rounded-xl border border-slate-200 bg-slate-50 p-3">
                            <div className="mb-3 flex items-center justify-between gap-4">
                              <span className="text-sm font-semibold text-slate-800">Supporting Evidence</span>
                              <span className="text-xs text-slate-500">
                                {message.evidence.length} cited review{message.evidence.length === 1 ? '' : 's'}
                              </span>
                            </div>
                            <div className="grid gap-3 md:grid-cols-3">
                              {message.evidence.slice(0, 3).map((review) => (
                                <div key={review.review_id} className="rounded-lg border border-slate-200 bg-white p-3">
                                  <div className="mb-2 flex items-center justify-between">
                                    <div className="flex items-center gap-1 text-[#f5b301] text-xs">
                                      {getStars(review.rating).map((star, idx) => (
                                        <span key={`${message.id}-${review.review_id}-${idx}`}>{star}</span>
                                      ))}
                                    </div>
                                  </div>
                                  <p className="text-sm leading-6 text-slate-700">“{review.text}”</p>
                                  <div className="mt-3 flex flex-wrap items-center justify-between gap-2 text-xs text-slate-500">
                                    <span>— {review.author}</span>
                                    {safeExternalUrl(review.review_url) ? (
                                      <a
                                        href={safeExternalUrl(review.review_url) ?? undefined}
                                        target="_blank"
                                        rel="noreferrer"
                                        className="inline-flex items-center gap-1 text-[#5b4ad9] hover:underline"
                                      >
                                        Review {review.review_id.slice(0, 8)}
                                        <ExternalLink className="h-3 w-3" />
                                      </a>
                                    ) : (
                                      <span title={review.review_id}>ID {review.review_id.slice(0, 8)}</span>
                                    )}
                                  </div>
                                </div>
                              ))}
                            </div>
                          </div>
                        ) : null}
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="border-t border-slate-200 bg-slate-50 px-4 py-4">
            <div className="flex flex-col gap-3 lg:flex-row lg:items-center">
              <div className="relative flex-1 rounded-xl border border-slate-200 bg-white px-3">
                <textarea
                  value={question}
                  onChange={(event) => setQuestion(event.target.value)}
                  rows={1}
                  className="w-full resize-none bg-transparent py-3 text-sm text-slate-700 outline-none placeholder:text-slate-400"
                  placeholder="Ask another question about these reviews..."
                />
              </div>
              <button
                onClick={() => void askQuestion()}
                className="inline-flex h-12 items-center justify-center rounded-xl bg-[#5b4ad9] px-4 text-white shadow-sm transition hover:bg-[#4f41cc]"
                disabled={!analysis || asking || loading || refreshing || !question.trim()}
                aria-label="Submit question"
              >
                {asking ? <span className="text-sm">Thinking…</span> : <ArrowRight className="h-4 w-4" />}
              </button>
            </div>

            <div className="mt-4 flex flex-wrap gap-2 text-sm">
              {suggestionPrompts.map((prompt) => (
                <button
                  key={prompt}
                  onClick={() => void askQuestion(prompt)}
                  disabled={!analysis || asking || loading || refreshing}
                  className="rounded-full border border-slate-200 bg-white px-3 py-1.5 text-slate-600 transition hover:border-slate-300 hover:text-slate-900"
                >
                  {prompt}
                </button>
              ))}
            </div>
          </div>
        </section>

        <aside className="hidden w-[320px] shrink-0 rounded-xl border border-slate-200 bg-white p-4 shadow-sm lg:block">
          <div className="mb-4 flex items-center justify-between">
            <div className="text-sm font-semibold uppercase tracking-wide text-slate-500">Current analysis scope</div>
            <button className="inline-flex items-center gap-1 rounded-full bg-[#eef1ff] px-2 py-1 text-xs font-medium text-[#5b4ad9]">
              <MessageSquareText className="h-3.5 w-3.5" />
              Active
            </button>
          </div>

          {analysis ? (
            <>
              <div className="space-y-4 text-sm">
                <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
                  <div className="text-[11px] uppercase tracking-wide text-slate-500">
                    {analysis.source.platform === 'Amazon' ? 'Product' : 'Business'}
                  </div>
                  <div className="mt-2 text-base font-semibold text-slate-900">{analysis.source.business_name}</div>
                </div>
                <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
                  <div className="text-[11px] uppercase tracking-wide text-slate-500">Platform</div>
                  <div className="mt-2 text-base font-semibold text-slate-900">{analysis.source.platform}</div>
                </div>
                <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
                  <div className="text-[11px] uppercase tracking-wide text-slate-500">Reviews analyzed</div>
                  <div className="mt-2 text-base font-semibold text-slate-900">{analysis.dataset.total_reviews.toLocaleString()}</div>
                </div>
                <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
                  <div className="text-[11px] uppercase tracking-wide text-slate-500">Date range</div>
                  <div className="mt-2 text-base font-semibold text-slate-900">
                    {analysis.dataset.summary.earliest_review ?? 'Unavailable'} - {analysis.dataset.summary.latest_review ?? 'Unavailable'}
                  </div>
                </div>
              </div>

              <div className="mt-4 rounded-xl border border-[#f7d57a] bg-[#fff8df] p-3 text-sm text-slate-700">
                <div className="flex items-center gap-2 font-semibold text-slate-800">
                  <ShieldAlert className="h-4 w-4 text-[#b97300]" />
                  This AI answers questions only from this dataset.
                </div>
              </div>
            </>
          ) : null}
        </aside>
      </main>
    </div>
  )
}

export default App
