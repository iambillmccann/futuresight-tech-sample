export type WeeklyReviews = {
  week_start: string
  review_count: number
  average_rating: number
}

type Props = {
  distribution: Record<string, number>
  weeks: WeeklyReviews[]
  undatedCount: number
}

const weekMilliseconds = 7 * 24 * 60 * 60 * 1000

function WeeklyChart({ weeks, rating }: { weeks: WeeklyReviews[]; rating: boolean }) {
  const title = rating ? 'Weekly average rating' : 'Weekly review count'
  const maximum = rating ? 5 : Math.max(1, ...weeks.map((week) => week.review_count))
  const minimum = rating ? 1 : 0
  const first = weeks.length ? Date.parse(weeks[0].week_start) : 0
  const last = weeks.length ? Date.parse(weeks[weeks.length - 1].week_start) : 0
  const x = (time: number) => first === last ? 164 : 36 + (time - first) / (last - first) * 256
  const y = (value: number) => 124 - (value - minimum) / (maximum - minimum) * 100
  const path = weeks.map((week, index) => {
    const time = Date.parse(week.week_start)
    const previous = weeks[index - 1]
    const previousTime = previous ? Date.parse(previous.week_start) : time
    const gap = time - previousTime > weekMilliseconds
    const value = rating ? week.average_rating : week.review_count
    if (!index) return `M ${x(time)} ${y(value)}`
    if (gap && rating) return `M ${x(time)} ${y(value)}`
    if (gap) return `L ${x(previousTime + weekMilliseconds)} ${y(0)} L ${x(time - weekMilliseconds)} ${y(0)} L ${x(time)} ${y(value)}`
    return `L ${x(time)} ${y(value)}`
  }).join(' ')

  return (
    <section className="min-w-0 rounded-xl border border-slate-200 bg-surface p-3">
      <h3 className="text-sm font-semibold text-slate-800">{title}</h3>
      <p className="mt-1 text-xs text-slate-500">Weeks beginning Monday</p>
      {weeks.length ? (
        <>
          <svg viewBox="0 0 320 166" className="mt-2 w-full text-brand-ink" role="img" aria-label={`${title}, ${weeks.length} weeks with reviews`}>
            {[minimum, (minimum + maximum) / 2, maximum].map((tick) => (
              <g key={tick}>
                <line x1="36" x2="292" y1={y(tick)} y2={y(tick)} className="stroke-slate-200" />
                <text x="30" y={y(tick) + 4} textAnchor="end" fontSize="10" className="fill-slate-500">
                  {rating ? tick.toFixed(1) : Number(tick.toFixed(1))}
                </text>
              </g>
            ))}
            <path d={path} fill="none" stroke="currentColor" strokeWidth="2" />
            {weeks.map((week) => (
              <circle key={week.week_start} cx={x(Date.parse(week.week_start))} cy={y(rating ? week.average_rating : week.review_count)} r="3" fill="currentColor">
                <title>{`${week.week_start}: ${rating ? week.average_rating.toFixed(2) + ' stars' : week.review_count + ' reviews'}`}</title>
              </circle>
            ))}
            <text x="36" y="152" fontSize="10" className="fill-slate-500">{weeks[0].week_start}</text>
            {weeks.length > 1 ? <text x="292" y="152" textAnchor="end" fontSize="10" className="fill-slate-500">{weeks[weeks.length - 1].week_start}</text> : null}
          </svg>
          <details className="text-xs text-slate-500">
            <summary className="cursor-pointer rounded focus-visible:outline focus-visible:outline-2 focus-visible:outline-brand">View weekly values</summary>
            <div className="mt-2 max-h-40 overflow-auto">
              <table className="w-full text-left">
                <thead><tr><th scope="col">Week of</th><th scope="col">{rating ? 'Average rating' : 'Reviews'}</th></tr></thead>
                <tbody>{weeks.map((week) => <tr key={week.week_start}><td>{week.week_start}</td><td>{rating ? week.average_rating.toFixed(2) : week.review_count}</td></tr>)}</tbody>
              </table>
            </div>
          </details>
        </>
      ) : <p className="flex h-40 items-center justify-center text-sm text-slate-500">No dated reviews available.</p>}
      <p className="mt-2 text-xs text-slate-500">{rating ? 'Gaps indicate weeks with no dated reviews.' : 'Weeks between observations with no dated reviews count as zero.'}</p>
    </section>
  )
}

export function ReviewCharts({ distribution, weeks, undatedCount }: Props) {
  const maximum = Math.max(1, ...Object.values(distribution))
  return (
    <div className="mt-3">
      <div className="grid gap-3 md:grid-cols-3">
        <section className="min-w-0 rounded-xl border border-slate-200 bg-surface p-3">
          <h3 className="text-sm font-semibold text-slate-800">Rating distribution</h3>
          <p className="mt-1 text-xs text-slate-500">Reviews by star rating</p>
          <ul className="mt-4 space-y-3" aria-label="Rating distribution">
            {[5, 4, 3, 2, 1].map((rating) => (
              <li key={rating} className="flex items-center gap-2 text-xs">
                <span className="w-12 shrink-0 text-slate-600">{rating} stars</span>
                <div className="h-3 flex-1 overflow-hidden rounded bg-slate-100" aria-hidden="true">
                  <div className="h-full rounded bg-brand" style={{ width: `${(distribution[String(rating)] ?? 0) / maximum * 100}%` }} />
                </div>
                <span className="w-8 text-right font-medium text-slate-700">{distribution[String(rating)] ?? 0}</span>
              </li>
            ))}
          </ul>
        </section>
        <WeeklyChart weeks={weeks} rating />
        <WeeklyChart weeks={weeks} rating={false} />
      </div>
      <p className="mt-2 text-xs text-slate-500">
        Charts describe the collected reviews, not the full platform history.
        {undatedCount > 0 ? ` ${undatedCount} review${undatedCount === 1 ? '' : 's'} without a recognized date excluded from weekly trends.` : ''}
      </p>
    </div>
  )
}
