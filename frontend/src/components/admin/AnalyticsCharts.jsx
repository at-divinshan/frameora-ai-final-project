import { useId } from 'react';
import { ResponsiveContainer, LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, PieChart, Pie, Cell } from 'recharts';

const colors = ['#00b9d8', '#a477ed', '#ed80ba', '#eda064', '#597be8', '#9b64bf', '#2ca991', '#c885a0'];
const format = (value, currency = false) => currency
  ? `LKR ${Number(value).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
  : Number(value).toLocaleString();
const serial = month => Number(month.slice(0, 4)) * 12 + Number(month.slice(5)) - 1;
const monthKey = index => `${Math.floor(index / 12)}-${String(index % 12 + 1).padStart(2, '0')}`;
export const monthLabel = month => new Intl.DateTimeFormat(undefined, { month: 'short', year: '2-digit', timeZone: 'UTC' }).format(new Date(`${month}-01T00:00:00Z`));

// API returns the latest 12 populated months. Every intervening month is therefore
// known to have zero matching records. Do not extrapolate beyond returned coverage.
export function continuousMonths(rows) {
  if (rows == null) return null;
  if (!Array.isArray(rows) || rows.some(row => !/^\d{4}-(0[1-9]|1[0-2])$/.test(row.month) || row.value == null || !Number.isFinite(Number(row.value)) || Number(row.value) < 0)) return null;
  if (!rows.length) return [];
  const values = new Map(rows.map(row => [serial(row.month), Number(row.value)]));
  const end = Math.max(...values.keys()), start = Math.max(Math.min(...values.keys()), end - 11);
  return Array.from({ length: end - start + 1 }, (_, offset) => ({ month: monthKey(start + offset), value: values.get(start + offset) ?? 0 }));
}

function ChartTooltip({ active, payload, label, currency }) {
  if (!active || !payload?.length) return null;
  return <div className="analytics-tooltip"><strong>{label && /^\d{4}-\d{2}$/.test(label) ? monthLabel(label) : payload[0].name}</strong>
    <p>{format(payload[0].value, currency)}</p></div>;
}

export function AnalyticsChart({ title, rows, currency = false, type = 'bar' }) {
  const data = continuousMonths(rows), gradient = `analytics-${useId().replaceAll(':', '')}`;
  const Chart = type === 'line' ? LineChart : BarChart;
  return <section className="analytics-panel"><h2>{title}</h2>{data == null ? <p>Not available</p> : !data.length ? <p>No recorded data</p> : <>
    <p className="analytics-axis-caption">{currency ? 'Test payments (LKR)' : type === 'line' ? 'Registered users' : 'Image records'} · Month (UTC)</p>
    <div className="analytics-plot" aria-label={title}>
      <ResponsiveContainer width="100%" height="100%" minWidth={0}>
        <Chart data={data} margin={{ top: 12, right: 12, left: 0, bottom: 8 }} accessibilityLayer>
          <defs><linearGradient id={gradient} x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#a477ed" /><stop offset="100%" stopColor="#00b9d8" /></linearGradient></defs>
          <CartesianGrid stroke="var(--border-color)" strokeDasharray="3 3" vertical={false} />
          <XAxis dataKey="month" tickFormatter={monthLabel} minTickGap={24} tick={{ fill: 'var(--text-muted)', fontSize: 11 }} stroke="var(--border-color)" />
          <YAxis width={48} allowDecimals={currency} tickFormatter={value => new Intl.NumberFormat(undefined, { notation: 'compact' }).format(value)} tick={{ fill: 'var(--text-muted)', fontSize: 11 }} stroke="var(--border-color)" />
          <Tooltip content={<ChartTooltip currency={currency} />} cursor={{ stroke: 'var(--text-muted)', fill: 'var(--bg-input)' }} />
          <Legend wrapperStyle={{ fontSize: 12, color: 'var(--text-main)' }} />
          {type === 'line' ? <Line type="linear" dataKey="value" name="Registrations" stroke="#a477ed" strokeWidth={3} dot={{ r: 4 }} activeDot={{ r: 6 }} isAnimationActive={false} />
            : <Bar dataKey="value" name={currency ? 'Test payments (LKR)' : 'Generated image records'} fill={`url(#${gradient})`} maxBarSize={44} radius={[5, 5, 0, 0]} isAnimationActive={false} />}
        </Chart>
      </ResponsiveContainer>
    </div>
    <details className="analytics-chart-data"><summary>View chart data</summary><table><thead><tr><th scope="col">Month (UTC)</th><th scope="col">{currency ? 'Test payments (LKR)' : 'Count'}</th></tr></thead><tbody>{data.map(row => <tr key={row.month}><th scope="row">{monthLabel(row.month)}</th><td>{format(row.value, currency)}</td></tr>)}</tbody></table></details>
  </>}</section>;
}

export function SubscriptionChart({ rows }) {
  const data = Array.isArray(rows) ? rows.map(row => ({ name: `${row.role === 'owner' ? 'Studio Owner' : 'Normal User'} · ${row.plan}`, value: Number(row.count) })) : null;
  const valid = data && data.every(row => Number.isFinite(row.value) && row.value >= 0);
  const total = valid ? data.reduce((sum, row) => sum + row.value, 0) : 0;
  return <section className="analytics-panel"><h2>Active subscriptions by plan</h2><p>Recorded active periods that have started and have not expired.</p>
    {!valid ? <p>Not available</p> : total === 0 ? <p>No active subscriptions</p> : <div className="analytics-donut-layout">
      <div className="analytics-plot analytics-donut" aria-label="Active subscriptions by plan">
        <ResponsiveContainer width="100%" height="100%" minWidth={0}><PieChart accessibilityLayer>
          <Pie data={data} dataKey="value" nameKey="name" innerRadius="55%" outerRadius="80%" paddingAngle={2} isAnimationActive={false} stroke="var(--bg-panel)">
            {data.map((row, index) => <Cell key={row.name} fill={colors[index % colors.length]} />)}
          </Pie><Tooltip content={<ChartTooltip />} />
        </PieChart></ResponsiveContainer>
      </div>
      <ul className="analytics-plans">{data.map((row, index) => <li key={row.name}><span><i aria-hidden="true" style={{ background: colors[index % colors.length] }} />{row.name}</span><strong>{format(row.value)} <small>({(row.value / total * 100).toFixed(1)}%)</small></strong></li>)}</ul>
    </div>}
  </section>;
}
export default function AnalyticsCharts({ data }) {
  return <><SubscriptionChart rows={data.subscriptions} /><div className="analytics-charts">
    <AnalyticsChart title="Monthly Test Mode payments" rows={data.payment_trend} currency />
    <AnalyticsChart title="Monthly registrations" rows={data.registration_trend} type="line" />
    <AnalyticsChart title="Monthly AI-generated image records" rows={data.image_trend} />
  </div></>;
}
