// frontend/src/components/charts/PsbiSignCountChart.jsx

import { useEffect, useRef, useCallback } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import {
    BarChart,
    Bar,
    XAxis,
    YAxis,
    ReferenceLine,
    Tooltip,
    Cell,
    ResponsiveContainer,
    Label,
} from 'recharts';
import {
    fetchPsbiSignCount,
    selectPsbiSignCountBars,
    selectPsbiSignCountTotal,
    selectPsbiSignCountLoading,
    selectPsbiSignCountError,
} from '../../store/indicatorsSlice';

const POLL_INTERVAL_MS = 2 * 60 * 1000;

// Gradient from light blue → deep blue as sign count increases
const barColor = (index, total) => {
    const ratio = total > 1 ? index / (total - 1) : 0;
    const r = Math.round(22 + ratio * (9 - 22));
    const g = Math.round(119 + ratio * (74 - 119));
    const b = Math.round(255 + ratio * (140 - 255));
    return `rgb(${r},${g},${b})`;
};

// ==================== CUSTOM TOOLTIP ====================
const CustomTooltip = ({ active, payload }) => {
    if (!active || !payload?.length) return null;
    const d = payload[0].payload;
    return (
        <div style={{
            background: '#fff',
            border: '1px solid #d9d9d9',
            borderRadius: 6,
            padding: '8px 12px',
            fontSize: 13,
            boxShadow: '0 2px 8px rgba(0,0,0,0.08)',
        }}>
            <div style={{ color: '#666', marginBottom: 4 }}>
                {d.count === 1 ? '1 pSBI sign' : `${d.count} pSBI signs`}
            </div>
            <div style={{ fontWeight: 700, fontSize: 18, color: '#111' }}>
                {d.value}%
            </div>
            <div style={{ color: '#aaa', fontSize: 11, marginTop: 2 }}>
                {d.numerator.toLocaleString()} / {d.denominator.toLocaleString()} patients
            </div>
        </div>
    );
};

// ==================== COMPONENT ====================
export default function PsbiSignCountChart() {
    const dispatch = useDispatch();
    const bars = useSelector(selectPsbiSignCountBars);
    const total = useSelector(selectPsbiSignCountTotal);
    const loading = useSelector(selectPsbiSignCountLoading);
    const error = useSelector(selectPsbiSignCountError);
    const intervalRef = useRef(null);

    const triggerFetch = useCallback(() => {
        dispatch(fetchPsbiSignCount());
    }, [dispatch]);

    useEffect(() => {
        triggerFetch();
        intervalRef.current = setInterval(triggerFetch, POLL_INTERVAL_MS);
        return () => clearInterval(intervalRef.current);
    }, [triggerFetch]);

    if (loading && !bars.length) {
        return (
            <div style={{ padding: '24px 0', color: '#888', fontSize: 13 }}>
                Loading pSBI sign-count distribution…
            </div>
        );
    }

    if (error) {
        return (
            <div style={{ padding: '14px 0', color: '#cf1322', fontSize: 13 }}>
                {error}
            </div>
        );
    }

    if (!bars.length) {
        return (
            <div style={{ padding: '14px 0', color: '#888', fontSize: 13 }}>
                No data available yet.
            </div>
        );
    }

    const maxValue = Math.max(...bars.map((b) => b.value));
    const yMax = Math.min(100, Math.ceil((maxValue + 5) / 10) * 10);

    const gridLines = [];
    for (let v = 0; v <= yMax; v += 10) gridLines.push(v);

    return (
        <div>
            <div style={{
                display: 'flex',
                alignItems: 'baseline',
                gap: 8,
                marginBottom: 16,
            }}>
                <span style={{ fontWeight: 600, fontSize: 15 }}>
                    pSBI Sign Count Distribution
                </span>
                <span style={{ color: '#888', fontSize: 12 }}>
                    n&nbsp;=&nbsp;{total.toLocaleString()} patients
                </span>
                {loading && (
                    <span style={{ color: '#aaa', fontSize: 11 }}>
                        (refreshing…)
                    </span>
                )}
            </div>

            <ResponsiveContainer width="100%" height={340}>
                <BarChart
                    data={bars}
                    margin={{ top: 16, right: 24, bottom: 48, left: 48 }}
                    barCategoryGap="20%"
                >
                    {gridLines.map((v) => (
                        <ReferenceLine
                            key={v}
                            y={v}
                            stroke={v % 20 === 0 ? '#d4d4d4' : '#efefef'}
                            strokeWidth={1}
                            strokeDasharray={v % 20 === 0 ? undefined : '4 3'}
                        />
                    ))}

                    <XAxis
                        dataKey="count"
                        type="number"
                        allowDecimals={false}
                        domain={[0, bars.length - 1]}
                        ticks={bars.map((b) => b.count)}
                        tick={{ fontSize: 12, fill: '#666' }}
                        axisLine={{ stroke: '#d4d4d4' }}
                        tickLine={false}
                    >
                        <Label
                            value="Number of pSBI signs / symptoms"
                            position="insideBottom"
                            offset={-32}
                            style={{ fontSize: 12, fill: '#888' }}
                        />
                    </XAxis>

                    <YAxis
                        domain={[0, yMax]}
                        ticks={gridLines}
                        tickFormatter={(v) => `${v}%`}
                        tick={{ fontSize: 12, fill: '#999' }}
                        axisLine={false}
                        tickLine={false}
                    >
                        <Label
                            value="% of patients"
                            angle={-90}
                            position="insideLeft"
                            offset={-32}
                            style={{ fontSize: 12, fill: '#888' }}
                        />
                    </YAxis>

                    <Tooltip
                        content={<CustomTooltip />}
                        cursor={{ fill: '#fafafa' }}
                    />

                    <Bar dataKey="value" radius={[4, 4, 0, 0]}>
                        {bars.map((_, i) => (
                            <Cell
                                key={i}
                                fill={barColor(i, bars.length)}
                            />
                        ))}
                    </Bar>
                </BarChart>
            </ResponsiveContainer>
        </div>
    );
}