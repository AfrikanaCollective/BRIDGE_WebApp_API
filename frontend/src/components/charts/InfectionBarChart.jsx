// frontend/src/components/charts/InfectionBarChart.jsx

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
} from 'recharts';
import {
    fetchInfectionIndicators,
    selectInfectionBars,
    selectInfectionTotal,
    selectIndicatorsLoading,
    selectIndicatorsError,
} from '../../store/indicatorsSlice';

const BAR_COLORS = ['#1677ff', '#52c41a', '#fa8c16'];
const POLL_INTERVAL_MS = 2 * 60 * 1000;

// Characters per line before wrapping (≈ 6.5 px per char at 12 px font, Y-axis width 260 px)
const CHARS_PER_LINE = 30;
const LINE_HEIGHT = 16;
const Y_AXIS_WIDTH = 270;
const BAR_SIZE = 56;

// ==================== WRAPPED Y-AXIS TICK ====================
const WrappedYAxisTick = ({ x, y, payload }) => {
    const words = (payload.value || '').split(' ');
    const lines = [];
    let current = '';

    for (const word of words) {
        const candidate = current ? `${current} ${word}` : word;
        if (candidate.length > CHARS_PER_LINE) {
            if (current) lines.push(current);
            current = word;
        } else {
            current = candidate;
        }
    }
    if (current) lines.push(current);

    const totalHeight = lines.length * LINE_HEIGHT;
    const startY = -(totalHeight / 2) + LINE_HEIGHT / 2;

    return (
        <g transform={`translate(${x},${y})`}>
            {lines.map((line, i) => (
                <text
                    key={i}
                    x={-6}
                    y={startY + i * LINE_HEIGHT}
                    textAnchor="end"
                    fill="#555"
                    fontSize={12}
                    dominantBaseline="middle"
                >
                    {line}
                </text>
            ))}
        </g>
    );
};

// ==================== CUSTOM TOOLTIP ====================
const CustomTooltip = ({ active, payload }) => {
    if (!active || !payload?.length) return null;
    const { label, value } = payload[0].payload;
    return (
        <div style={{
            background: '#fff',
            border: '1px solid #d9d9d9',
            borderRadius: 6,
            padding: '8px 12px',
            fontSize: 13,
            boxShadow: '0 2px 8px rgba(0,0,0,0.08)',
            maxWidth: 260,
        }}>
            <div style={{ color: '#666', marginBottom: 4, lineHeight: 1.4 }}>{label}</div>
            <div style={{ fontWeight: 700, fontSize: 18, color: '#111' }}>
                {value}%
            </div>
        </div>
    );
};

// ==================== COMPONENT ====================
export default function InfectionBarChart() {
    const dispatch = useDispatch();
    const bars = useSelector(selectInfectionBars);
    const total = useSelector(selectInfectionTotal);
    const loading = useSelector(selectIndicatorsLoading);
    const error = useSelector(selectIndicatorsError);
    const intervalRef = useRef(null);

    const triggerFetch = useCallback(() => {
        dispatch(fetchInfectionIndicators());
    }, [dispatch]);

    // Recharts Bar `label` only receives x/y/width/height/value/index — not the
    // full data entry. Close over `bars` and use `index` to look up the entry.
    const renderBarLabel = useCallback(({ x, y, width, height, value, index }) => {
        if (width <= 0) return null;
        const bar = bars[index];
        const rightX = x + width + 8;
        const midY = y + height / 2;
        return (
            <g key={index}>
                <text x={rightX} y={midY - 7} fontSize={12} fontWeight={700}
                    fill="#333" dominantBaseline="middle">
                    {value}%
                </text>
                <text x={rightX} y={midY + 7} fontSize={11}
                    fill="#777" dominantBaseline="middle">
                    {bar?.numerator}/{bar?.denominator}
                </text>
            </g>
        );
    }, [bars]);

    useEffect(() => {
        triggerFetch();
        intervalRef.current = setInterval(triggerFetch, POLL_INTERVAL_MS);
        return () => clearInterval(intervalRef.current);
    }, [triggerFetch]);

    if (loading && !bars.length) {
        return (
            <div style={{ padding: '24px 0', color: '#888', fontSize: 13 }}>
                Loading infection indicators…
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

    // X-axis upper bound: max plotted value + 5%, capped at 100
    const maxValue = Math.max(...bars.map((b) => b.value));
    const xMax = Math.min(100, maxValue + 5);

    // Grid lines: major every 10%, minor every 5% (non-major positions only)
    const majorGridLines = [];
    const minorGridLines = [];
    for (let v = 0; v <= xMax; v += 5) {
        if (v % 10 === 0) majorGridLines.push(v);
        else minorGridLines.push(v);
    }

    // Chart height scales with number of bars so wrapped labels have room
    const chartHeight = bars.length * (BAR_SIZE + 60) + 40;

    return (
        <div>
            <div style={{
                display: 'flex',
                alignItems: 'baseline',
                gap: 8,
                marginBottom: 16,
            }}>
                <span style={{ fontWeight: 600, fontSize: 15 }}>
                    Infection Overview
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

            <ResponsiveContainer width="100%" height={chartHeight}>
                <BarChart
                    layout="vertical"
                    data={bars}
                    margin={{ top: 8, right: 96, bottom: 8, left: 0 }}
                    barSize={BAR_SIZE}
                    barCategoryGap="30%"
                >
                    {/* Minor grid lines every 5% */}
                    {minorGridLines.map((v) => (
                        <ReferenceLine
                            key={`minor-${v}`}
                            x={v}
                            stroke="#efefef"
                            strokeWidth={1}
                            strokeDasharray="4 3"
                        />
                    ))}
                    {/* Major grid lines every 10% */}
                    {majorGridLines.map((v) => (
                        <ReferenceLine
                            key={`major-${v}`}
                            x={v}
                            stroke="#d4d4d4"
                            strokeWidth={1}
                        />
                    ))}
                    <XAxis
                        type="number"
                        domain={[0, xMax]}
                        ticks={majorGridLines}
                        tickFormatter={(v) => `${v}%`}
                        tick={{ fontSize: 12, fill: '#999' }}
                        axisLine={false}
                        tickLine={false}
                    />
                    <YAxis
                        type="category"
                        dataKey="label"
                        width={Y_AXIS_WIDTH}
                        tick={<WrappedYAxisTick />}
                        axisLine={false}
                        tickLine={false}
                    />
                    <Tooltip
                        content={<CustomTooltip />}
                        cursor={{ fill: '#fafafa' }}
                    />
                    <Bar dataKey="value" radius={[0, 4, 4, 0]} label={renderBarLabel}>
                        {bars.map((_, i) => (
                            <Cell
                                key={i}
                                fill={BAR_COLORS[i % BAR_COLORS.length]}
                            />
                        ))}
                    </Bar>
                </BarChart>
            </ResponsiveContainer>
        </div>
    );
}