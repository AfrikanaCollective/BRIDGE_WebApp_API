// frontend/src/components/charts/DiagnosisVennChart.jsx
//
// Custom SVG three-set Venn diagram.
// Circle geometry (radius 110):
//   Sepsis    — centre (190, 185)
//   Pneumonia — centre (310, 185)
//   Meningitis — centre (250, 280)
// All seven region label positions were verified to lie inside the correct
// intersection regions by distance-to-centre checks.

import { useEffect, useRef, useCallback } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import {
    fetchDiagnosisOverlap,
    selectDiagnosisOverlapSets,
    selectDiagnosisOverlapTotal,
    selectDiagnosisOverlapLoading,
    selectDiagnosisOverlapError,
} from '../../store/indicatorsSlice';

const POLL_INTERVAL_MS = 2 * 60 * 1000;

const S_COLOR  = '#e6194b';  // Bacterial Sepsis    — vivid red
const P_COLOR  = '#4363d8';  // Pneumonia           — royal blue
const M_COLOR  = '#911eb4';  // Bacterial Meningitis — vivid purple

// Two-line text block centred on (x, y)
const RegionLabel = ({ x, y, pct, count }) => (
    <g>
        <text
            x={x} y={y - 8}
            textAnchor="middle" dominantBaseline="middle"
            fontSize={13} fontWeight={700} fill="#222"
        >
            {pct}%
        </text>
        <text
            x={x} y={y + 8}
            textAnchor="middle" dominantBaseline="middle"
            fontSize={10} fill="#555"
        >
            {count.toLocaleString()}
        </text>
    </g>
);

// ==================== COMPONENT ====================
export default function DiagnosisVennChart() {
    const dispatch   = useDispatch();
    const sets       = useSelector(selectDiagnosisOverlapSets);
    const total      = useSelector(selectDiagnosisOverlapTotal);
    const loading    = useSelector(selectDiagnosisOverlapLoading);
    const error      = useSelector(selectDiagnosisOverlapError);
    const intervalRef = useRef(null);

    const triggerFetch = useCallback(() => {
        dispatch(fetchDiagnosisOverlap());
    }, [dispatch]);

    useEffect(() => {
        triggerFetch();
        intervalRef.current = setInterval(triggerFetch, POLL_INTERVAL_MS);
        return () => clearInterval(intervalRef.current);
    }, [triggerFetch]);

    if (loading && !sets) {
        return (
            <div style={{ padding: '24px 0', color: '#888', fontSize: 13 }}>
                Loading diagnosis overlap…
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
    if (!sets) {
        return (
            <div style={{ padding: '14px 0', color: '#888', fontSize: 13 }}>
                No data available yet.
            </div>
        );
    }

    const s = sets;

    return (
        <div>
            {/* Header */}
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, marginBottom: 16 }}>
                <span style={{ fontWeight: 600, fontSize: 15 }}>
                    Suspected Diagnosis Overlap
                </span>
                <span style={{ color: '#888', fontSize: 12 }}>
                    n&nbsp;=&nbsp;{total.toLocaleString()} patients
                </span>
                {loading && (
                    <span style={{ color: '#aaa', fontSize: 11 }}>(refreshing…)</span>
                )}
            </div>

            {/* Legend */}
            <div style={{ display: 'flex', gap: 20, marginBottom: 12, flexWrap: 'wrap' }}>
                {[
                    { color: S_COLOR, label: 'Bacterial Sepsis (≥ 3 of 5)' },
                    { color: P_COLOR, label: 'Pneumonia (≥ 2 of 5)' },
                    { color: M_COLOR, label: 'Bacterial Meningitis (≥ 2 of 4)' },
                ].map(({ color, label }) => (
                    <div key={label} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                        <div style={{
                            width: 14, height: 14, borderRadius: 3,
                            background: color, opacity: 0.7, flexShrink: 0,
                        }} />
                        <span style={{ fontSize: 12, color: '#555' }}>{label}</span>
                    </div>
                ))}
            </div>

            {/* SVG Venn diagram */}
            <svg
                viewBox="0 0 500 410"
                style={{ width: '100%', maxWidth: 520, display: 'block', margin: '0 auto' }}
                aria-label="Three-set Venn diagram of suspected pSBI diagnoses"
            >
                {/* ── Circles ── */}
                <circle cx={190} cy={185} r={110}
                    fill={S_COLOR} fillOpacity={0.15}
                    stroke={S_COLOR} strokeWidth={2.5} />
                <circle cx={310} cy={185} r={110}
                    fill={P_COLOR} fillOpacity={0.15}
                    stroke={P_COLOR} strokeWidth={2.5} />
                <circle cx={250} cy={280} r={110}
                    fill={M_COLOR} fillOpacity={0.15}
                    stroke={M_COLOR} strokeWidth={2.5} />

                {/* ── Circle name labels (outside overlapping zones) ── */}
                <text x={118} y={62} textAnchor="middle"
                    fontSize={12} fontWeight={700} fill={S_COLOR}>
                    Bacterial Sepsis
                </text>
                <text x={382} y={62} textAnchor="middle"
                    fontSize={12} fontWeight={700} fill={P_COLOR}>
                    Pneumonia
                </text>
                <text x={250} y={402} textAnchor="middle"
                    fontSize={12} fontWeight={700} fill={M_COLOR}>
                    Bacterial Meningitis
                </text>

                {/* ── Region labels — verified geometry ── */}

                {/* Sepsis only */}
                <RegionLabel x={145} y={168}
                    pct={s.sepsis_only.pct}
                    count={s.sepsis_only.count} />

                {/* Pneumonia only */}
                <RegionLabel x={355} y={168}
                    pct={s.pneumonia_only.pct}
                    count={s.pneumonia_only.count} />

                {/* Meningitis only */}
                <RegionLabel x={250} y={358}
                    pct={s.meningitis_only.pct}
                    count={s.meningitis_only.count} />

                {/* Sepsis ∩ Pneumonia (not Meningitis) */}
                <RegionLabel x={250} y={143}
                    pct={s.sepsis_pneumonia.pct}
                    count={s.sepsis_pneumonia.count} />

                {/* Sepsis ∩ Meningitis (not Pneumonia) */}
                <RegionLabel x={178} y={272}
                    pct={s.sepsis_meningitis.pct}
                    count={s.sepsis_meningitis.count} />

                {/* Pneumonia ∩ Meningitis (not Sepsis) */}
                <RegionLabel x={322} y={272}
                    pct={s.pneumonia_meningitis.pct}
                    count={s.pneumonia_meningitis.count} />

                {/* All three */}
                <RegionLabel x={250} y={222}
                    pct={s.all_three.pct}
                    count={s.all_three.count} />
            </svg>

            {/* Patients meeting no criteria */}
            <div style={{
                textAlign: 'center',
                color: '#999',
                fontSize: 12,
                marginTop: 8,
            }}>
                No suspected diagnosis:&nbsp;
                <strong style={{ color: '#555' }}>{s.none.pct}%</strong>
                &nbsp;({s.none.count.toLocaleString()}&nbsp;/&nbsp;{total.toLocaleString()} patients)
            </div>
        </div>
    );
}