// frontend/src/components/charts/InfectionBarChart.jsx

import { useEffect, useRef, useCallback } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import {
    BarChart,
    Bar,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    Cell,
    ResponsiveContainer,
    LabelList,
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
        }}>
            <div style={{ color: '#666', marginBottom: 4 }}>{label}</div>
            <div style={{ fontWeight: 700, fontSize: 18, color: '#111' }}>
                {value}%
            </div>
        </div>
    );
};

// ==================== VALUE LABEL ABOVE BAR ====================
const BarValueLabel = (props) => {
    const { x, y, width, value } = props;
    return (
        <text
            x={x + width / 2}
            y={y - 8}
            textAnchor="middle"
            fill="#444"
            fontSize={13}
            fontWeight={600}
        >
            {value}%
        </text>
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

    useEffect(() => {
        triggerFetch();
        intervalRef.current = setInterval(triggerFetch, POLL_INTERVAL_MS);
        return () => clearInterval(intervalRef.current);
    }, [triggerFetch]);

    // ==================== LOADING (first load only) ====================
    if (loading && !bars.length) {
        return (
            <div style={{ padding: '24px 0', color: '#888', fontSize: 13 }}>
                Loading infection indicators…
            </div>
        );
    }

    // ==================== ERROR ====================
    if (error) {
        return (
            <div style={{ padding: '12px 0', color: '#cf1322', fontSize: 13 }}>
                {error}
            </div>
        );
    }

    // ==================== EMPTY ====================
    if (!bars.length) {
        return (
            <div style={{ padding: '12px 0', color: '#888', fontSize: 13 }}>
                No data available yet.
            </div>
        );
    }

    // ==================== CHART ====================
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

            <ResponsiveContainer width="100%" height={320}>
                <BarChart
                    data={bars}
                    margin={{ top: 32, right: 24, bottom: 8, left: 0 }}
                    barSize={72}
                >
                    <CartesianGrid
                        strokeDasharray="3 3"
                        vertical={false}
                        stroke="#f0f0f0"
                    />
                    <XAxis
                        dataKey="label"
                        tick={{ fontSize: 12, fill: '#555' }}
                        axisLine={false}
                        tickLine={false}
                    />
                    <YAxis
                        domain={[0, 100]}
                        tickFormatter={(v) => `${v}%`}
                        tick={{ fontSize: 12, fill: '#999' }}
                        axisLine={false}
                        tickLine={false}
                        width={40}
                    />
                    <Tooltip
                        content={<CustomTooltip />}
                        cursor={{ fill: '#fafafa' }}
                    />
                    <Bar dataKey="value" radius={[4, 4, 0, 0]}>
                        <LabelList dataKey="value" content={<BarValueLabel />} />
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