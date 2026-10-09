import { useEffect, useMemo, useState } from 'react'
import {
  ArrowRight,
  CircleHelp,
  Globe,
  MapPinned,
  MessageSquareText,
  Plus,
  Search,
  ShieldAlert,
  Sparkles,
} from 'lucide-react'

type Review = {
  review_id: string
  author: string
  date: string
  rating: number
  text: string
}

type DatasetSummary = {
  review_count: number
  average_rating: number
  earliest_review: string
  latest_review: string
  rating_distribution: Record<string, number>
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
}

type Message = {
  id: string
  role: 'question' | 'answer'
  text: string
  timestamp: string
  evidence?: Review[]
}

const defaultUrl =
  'https://www.google.com/maps/place/Blue+Bottle+Coffee+%E2%80%94+Mint+Plaza'

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

function App() {
  const [sourceUrl, setSourceUrl] = useState(defaultUrl)
  const [analysis, setAnalysis] = useState<Analysis | null>(null)
  const [question, setQuestion] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [transcript, setTranscript] = useState<Message[]>([
    {
      id: 'seed-1',
      role: 'question',
      text: 'What do customers like most about this place?',
      timestamp: '2:45 PM',
    },
    {
      id: 'seed-2',
      role: 'answer',
      text:
        'Customers most frequently praise the quality of the food and coffee, especially the eggs Benedict, brunch items, and overall atmosphere.',
      timestamp: '2:45 PM',
      evidence: [
        {
          review_id: 'r1',
          author: 'Sarah M.',
          date: '2024-01-18',
          rating: 5,
          text: 'Best sounding in the city! The eggs Benedict were perfectly poached.',
        },
      ],
    },
    {
      id: 'seed-3',
      role: 'question',
      text: 'What are the most common complaints?',
      timestamp: '2:48 PM',
    },
    {
      id: 'seed-4',
      role: 'answer',
      text:
        'The most common complaints are long wait times, higher prices, and noise during busy periods.',
      timestamp: '2:48 PM',
      evidence: [
        {
          review_id: 'r6',
          author: 'Alex P.',
          date: '2024-01-08',
          rating: 2,
          text: 'Usually a long wait, even on weekdays. Plan ahead.',
        },
      ],
    },
  ])

  const loadAnalysis = async (urlToAnalyze = sourceUrl) => {
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
        throw new Error(payload.detail || 'Unable to ingest source.')
      }
      setAnalysis(payload)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to analyze the source.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void loadAnalysis(defaultUrl)
  }, [])

  const askQuestion = async (promptText?: string) => {
    const nextQuestion = (promptText ?? question).trim()
    if (!nextQuestion || !analysis) return

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
      if (!response.ok) throw new Error(payload.detail || 'Unable to answer question.')

      const answerText = payload.answer
      setTranscript((current) => [
        ...current,
        {
          id: `a-${Date.now() + 1}`,
          role: 'answer',
          text: answerText,
          timestamp: 'now',
          evidence: payload.matching_reviews || [],
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
        },
      ])
    }
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
            <button className="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 shadow-sm transition hover:border-slate-300 hover:text-slate-900">
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
                  placeholder="https://www.google.com/maps/place/..."
                  aria-label="Google Maps source URL"
                />
              </div>
              <button
                onClick={() => void loadAnalysis()}
                className="inline-flex h-11 items-center justify-center rounded-md bg-[#5b4ad9] px-5 text-sm font-semibold text-white shadow-sm transition hover:bg-[#4f41cc] disabled:opacity-60"
                disabled={loading}
              >
                {loading ? 'Analyzing…' : 'Analyze Reviews'}
              </button>
            </div>
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
                    <span>{new Date().toLocaleString([], { month: 'short', day: 'numeric', year: 'numeric', hour: 'numeric', minute: '2-digit' })}</span>
                  </div>
                  <div className="flex items-center gap-2 text-sm text-emerald-700">
                    <span className="inline-flex h-2.5 w-2.5 rounded-full bg-emerald-500" />
                    Active dataset
                  </div>
                </div>

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
                    <div className="mt-2 text-base font-semibold text-slate-900">{analysis.dataset.summary.earliest_review}</div>
                  </div>
                  <div className="rounded-lg bg-slate-50 p-3">
                    <div className="text-[11px] uppercase tracking-wide text-slate-500">Latest review</div>
                    <div className="mt-2 text-base font-semibold text-slate-900">{analysis.dataset.summary.latest_review}</div>
                  </div>
                  <div className="rounded-lg bg-slate-50 p-3">
                    <div className="text-[11px] uppercase tracking-wide text-slate-500">Platform</div>
                    <div className="mt-2 text-base font-semibold text-slate-900">{analysis.source.platform}</div>
                  </div>
                </div>
              </div>

              <div className="border-t border-slate-200 px-4 py-4">
                <div className="mb-3 flex items-center justify-between">
                  <h3 className="text-base font-semibold text-slate-800">Review preview</h3>
                  <button className="text-sm font-medium text-[#5b4ad9]">View more reviews</button>
                </div>

                <div className="overflow-hidden rounded-xl border border-slate-200 bg-white">
                  <table className="min-w-full text-left text-sm">
                    <thead className="bg-slate-50 text-slate-600">
                      <tr>
                        <th className="px-4 py-3 font-medium">Rating</th>
                        <th className="px-4 py-3 font-medium">Date</th>
                        <th className="px-4 py-3 font-medium">Reviewer</th>
                        <th className="px-4 py-3 font-medium">Review Text</th>
                      </tr>
                    </thead>
                    <tbody>
                      {analysis.dataset.sample_reviews.map((review) => (
                        <tr key={review.review_id} className="border-t border-slate-200 align-top">
                          <td className="px-4 py-3 text-slate-800">
                            <div className="flex items-center gap-1 text-[#f5b301]">
                              {getStars(review.rating).map((star, idx) => (
                                <span key={`${review.review_id}-${idx}`}>{star}</span>
                              ))}
                            </div>
                          </td>
                          <td className="px-4 py-3 text-slate-600">{review.date}</td>
                          <td className="px-4 py-3 font-medium text-slate-800">{review.author}</td>
                          <td className="max-w-[760px] px-4 py-3 text-slate-700">“{review.text}”</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
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

                  <div className="px-4 py-4">
                    <div className="flex gap-3">
                      <div className="mt-0.5 flex h-8 w-8 items-center justify-center rounded-md bg-[#eef1ff] text-[#5b4ad9]">
                        {message.role === 'question' ? <CircleHelp className="h-4 w-4" /> : <Sparkles className="h-4 w-4" />}
                      </div>
                      <div className="flex-1">
                        <div className="text-[15px] leading-7 text-slate-900">{message.text}</div>
                        {message.role === 'answer' && message.evidence && message.evidence.length > 0 ? (
                          <div className="mt-4 rounded-xl border border-slate-200 bg-slate-50 p-3">
                            <div className="mb-3 flex items-center justify-between gap-4">
                              <span className="text-sm font-semibold text-slate-800">Supporting Evidence</span>
                              <span className="text-xs text-slate-500">View all {message.evidence.length} matching reviews</span>
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
                                  <div className="mt-3 text-xs text-slate-500">— {review.author}</div>
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
              >
                <ArrowRight className="h-4 w-4" />
              </button>
            </div>

            <div className="mt-4 flex flex-wrap gap-2 text-sm">
              {suggestionPrompts.map((prompt) => (
                <button
                  key={prompt}
                  onClick={() => void askQuestion(prompt)}
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
                  <div className="text-[11px] uppercase tracking-wide text-slate-500">Business</div>
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
                    {analysis.dataset.summary.earliest_review} - {analysis.dataset.summary.latest_review}
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
