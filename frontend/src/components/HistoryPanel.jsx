// frontend/src/components/HistoryPanel.jsx
import React, { useState, useEffect, useCallback } from 'react';
import { toast } from 'react-toastify';
import axios from 'axios';
import '../styles/HistoryPanel.css';

const PAGE_SIZE_OPTIONS = [5, 10, 20, 50];

const HistoryPanel = () => {
    // ✅ Single source of truth for history data
    const [history, setHistory] = useState({
        total: 0,
        page: 1,
        limit: 20,
        records: [],
    });

    const [loading, setLoading] = useState(false);
    const [selectedRecord, setSelectedRecord] = useState(null);
    const [detailsVisible, setDetailsVisible] = useState(false);
    const [refreshing, setRefreshing] = useState(false);
    const [page, setPage] = useState(1);
    const [pageSize, setPageSize] = useState(10);
    const [statusFilter, setStatusFilter] = useState('all');
    const [sortField, setSortField] = useState('timestamp');
    const [sortOrder, setSortOrder] = useState('desc');

    const fetchResponses = useCallback(async () => {
        setLoading(true);
        try {
            const response = await axios.get(`${process.env.REACT_APP_API_URL}/api/history`);

            // ✅ Map backend field names to frontend expectations
            const mappedRecords = (response.data.records || []).map(rec => ({
                ...rec,
                processingId: rec.processingId || rec.processing_id,
                formType: rec.formType || rec.form_type,
                caseId: rec.caseId || rec.case_id,
                timestamp: rec.timestamp || rec.created_at,
                documentUrl: rec.documentUrl || rec.file_url,
            }));

            setHistory({
                total: response.data.total || 0,
                page: response.data.page || 1,
                limit: response.data.limit || 20,
                records: mappedRecords,
            });
        } catch (error) {
            console.error('Error fetching history:', error);
            toast.error('Failed to load history');
            setHistory({ total: 0, page: 1, limit: 20, records: [] });
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        fetchResponses();
    }, [fetchResponses]);

    const handleDelete = async (processingId) => {
        if (!window.confirm('Delete this record? This action cannot be undone.')) return;
        try {
            await axios.delete(`${process.env.REACT_APP_API_URL}/api/history/${processingId}`);
            toast.success('Record deleted successfully');
            fetchResponses();
        } catch (error) {
            console.error('Error deleting record:', error);
            toast.error('Failed to delete record');
        }
    };

    const handleViewDetails = (record) => {
        setSelectedRecord(record);
        setDetailsVisible(true);
    };

    const handleDownload = (record) => {
        if (!record.documentUrl) return;
        const link = document.createElement('a');
        link.href = record.documentUrl;
        link.download = `${record.processingId}.pdf`;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        toast.success('Download started');
    };

    const handleRefresh = async () => {
        setRefreshing(true);
        await fetchResponses();
        setRefreshing(false);
    };

    const handleCopyId = (id) => {
        navigator.clipboard.writeText(id);
        toast.success('Processing ID copied to clipboard');
    };

    const renderStatusBadge = (status) => {
        const config = {
            completed: { cls: 'completed', label: 'Completed' },
            processing: { cls: 'processing', label: 'Processing' },
            failed: { cls: 'failed', label: 'Failed' },
            pending: { cls: 'pending', label: 'Pending' },
        };
        const c = config[status] || { cls: '', label: status || 'Unknown' };
        return <span className={`status-badge ${c.cls}`}>{c.label}</span>;
    };

    const renderConfidence = (confidence) => {
        if (confidence == null) return <span className="confidence-empty">—</span>;
        const pct = confidence * 100;
        const cls = pct >= 80 ? 'confidence-high' : pct >= 50 ? 'confidence-medium' : 'confidence-low';
        return (
            <div className="confidence-wrapper">
                <div className="confidence-bar">
                    <div className={`confidence-fill ${cls}`} style={{ width: `${pct}%` }} />
                </div>
                <span className={`confidence-text ${cls}`}>{pct.toFixed(0)}%</span>
            </div>
        );
    };

    // ✅ Filter + sort + paginate using history.records
    const filtered = history.records.filter(
        r => statusFilter === 'all' || r.status === statusFilter
    );

    const sorted = [...filtered].sort((a, b) => {
        let av = sortField === 'timestamp'
            ? (a.timestamp ? new Date(a.timestamp).getTime() : 0)
            : (a[sortField] ?? 0);
        let bv = sortField === 'timestamp'
            ? (b.timestamp ? new Date(b.timestamp).getTime() : 0)
            : (b[sortField] ?? 0);
        if (av < bv) return sortOrder === 'asc' ? -1 : 1;
        if (av > bv) return sortOrder === 'asc' ? 1 : -1;
        return 0;
    });

    const totalPages = Math.max(1, Math.ceil(sorted.length / pageSize));
    const paginated = sorted.slice((page - 1) * pageSize, page * pageSize);

    const handleSort = (field) => {
        if (sortField === field) setSortOrder(o => o === 'asc' ? 'desc' : 'asc');
        else {
            setSortField(field);
            setSortOrder('desc');
        }
        setPage(1);
    };

    const sortIcon = (field) => {
        if (sortField !== field) return <i className="bi bi-chevron-expand sort-icon" aria-hidden="true" />;
        return sortOrder === 'asc'
            ? <i className="bi bi-chevron-up sort-icon active" aria-hidden="true" />
            : <i className="bi bi-chevron-down sort-icon active" aria-hidden="true" />;
    };

    // Pagination page range (up to 5 pages centered around current)
    const pageRange = (() => {
        const start = Math.max(1, Math.min(totalPages - 4, page - 2));
        return Array.from({ length: Math.min(5, totalPages) }, (_, i) => start + i);
    })();

    return (
        <div className="history-panel">
            {/* Header */}
            <div className="history-header">
                <div className="history-header-left">
                    <h1 className="history-title">Processing History</h1>
                    <span className="history-count">
                        {history.total} record{history.total !== 1 ? 's' : ''}
                    </span>
                </div>
                <div className="history-actions">
                    <select
                        className="history-filter-select"
                        value={statusFilter}
                        onChange={e => {
                            setStatusFilter(e.target.value);
                            setPage(1);
                        }}
                        aria-label="Filter by status"
                    >
                        <option value="all">All Status</option>
                        <option value="completed">Completed</option>
                        <option value="processing">Processing</option>
                        <option value="failed">Failed</option>
                        <option value="pending">Pending</option>
                    </select>
                    <button
                        type="button"
                        className="refresh-btn"
                        onClick={handleRefresh}
                        disabled={refreshing}
                        aria-label="Refresh history"
                    >
                        <i className={`bi bi-arrow-clockwise${refreshing ? ' spin' : ''}`} aria-hidden="true" />
                        Refresh
                    </button>
                </div>
            </div>

            {/* Content */}
            <div className="history-content">
                {loading ? (
                    <div className="history-loading">
                        <div className="spinner spinner-lg" role="status" aria-label="Loading history" />
                        <p>Loading history records…</p>
                    </div>
                ) : history.records.length === 0 ? (
                    <div className="history-empty">
                        <i className="bi bi-inbox" aria-hidden="true" style={{ fontSize: '48px', color: 'var(--color-gray-400, #9ca3af)', display: 'block', marginBottom: '12px' }} />
                        <p>No history records found</p>
                    </div>
                ) : (
                    <>
                        {/* Desktop table */}
                        <div className="history-table-view">
                            <table className="history-table-native">
                                <thead>
                                    <tr>
                                        <th>Processing ID</th>
                                        <th>Form Type</th>
                                        <th>Case ID</th>
                                        <th>Status</th>
                                        <th>
                                            <button
                                                type="button"
                                                className="sort-btn"
                                                onClick={() => handleSort('confidence')}
                                            >
                                                Confidence {sortIcon('confidence')}
                                            </button>
                                        </th>
                                        <th>
                                            <button
                                                type="button"
                                                className="sort-btn"
                                                onClick={() => handleSort('timestamp')}
                                            >
                                                Timestamp {sortIcon('timestamp')}
                                            </button>
                                        </th>
                                        <th>Actions</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {paginated.length === 0 ? (
                                        <tr>
                                            <td
                                                colSpan={7}
                                                style={{
                                                    textAlign: 'center',
                                                    padding: '40px',
                                                    color: 'var(--color-gray-500)',
                                                }}
                                            >
                                                No records match the selected filter
                                            </td>
                                        </tr>
                                    ) : (
                                        paginated.map(record => (
                                            <tr key={record.processingId}>
                                                <td>
                                                    <span
                                                        className="processing-id-cell"
                                                        title={record.processingId}
                                                    >
                                                        {record.processingId?.substring(0, 8)}…
                                                        <button
                                                            type="button"
                                                            className="copy-btn"
                                                            onClick={() =>
                                                                handleCopyId(record.processingId)
                                                            }
                                                            aria-label="Copy full ID"
                                                            title="Copy full ID"
                                                        >
                                                            <i className="bi bi-clipboard" aria-hidden="true" />
                                                        </button>
                                                    </span>
                                                </td>
                                                <td>
                                                    <span className="form-type-tag">
                                                        {record.formType || 'Unknown'}
                                                    </span>
                                                </td>
                                                <td>
                                                    {record.caseId || (
                                                        <span className="text-muted">—</span>
                                                    )}
                                                </td>
                                                <td>{renderStatusBadge(record.status)}</td>
                                                <td>{renderConfidence(record.confidence)}</td>
                                                <td
                                                    title={
                                                        record.timestamp
                                                            ? new Date(
                                                                record.timestamp
                                                            ).toLocaleString()
                                                            : ''
                                                    }
                                                >
                                                    {record.timestamp ? (
                                                        <span>
                                                            {new Date(
                                                                record.timestamp
                                                            ).toLocaleDateString()}{' '}
                                                            {new Date(record.timestamp).toLocaleTimeString(
                                                                [],
                                                                {
                                                                    hour: '2-digit',
                                                                    minute: '2-digit',
                                                                }
                                                            )}
                                                        </span>
                                                    ) : (
                                                        <span className="text-muted">—</span>
                                                    )}
                                                </td>
                                                <td>
                                                    <div className="actions-space">
                                                        <button
                                                            type="button"
                                                            className="action-btn-view"
                                                            onClick={() =>
                                                                handleViewDetails(record)
                                                            }
                                                            title="View Details"
                                                            aria-label="View Details"
                                                        >
                                                            <i
                                                                className="bi bi-eye"
                                                                aria-hidden="true"
                                                            />
                                                        </button>
                                                        <button
                                                            type="button"
                                                            className="action-btn-download"
                                                            onClick={() =>
                                                                handleDownload(record)
                                                            }
                                                            disabled={!record.documentUrl}
                                                            title={
                                                                record.documentUrl
                                                                    ? 'Download'
                                                                    : 'No document available'
                                                            }
                                                            aria-label="Download"
                                                        >
                                                            <i
                                                                className="bi bi-download"
                                                                aria-hidden="true"
                                                            />
                                                        </button>
                                                        <button
                                                            type="button"
                                                            className="action-btn-delete"
                                                            onClick={() =>
                                                                handleDelete(
                                                                    record.processingId
                                                                )
                                                            }
                                                            title="Delete"
                                                            aria-label="Delete"
                                                        >
                                                            <i
                                                                className="bi bi-trash"
                                                                aria-hidden="true"
                                                            />
                                                        </button>
                                                    </div>
                                                </td>
                                            </tr>
                                        ))
                                    )}
                                </tbody>
                            </table>

                            {/* Pagination */}
                            {totalPages > 1 && (
                                <div className="table-pagination">
                                    <div className="pagination-info">
                                        Showing {(page - 1) * pageSize + 1}–
                                        {Math.min(page * pageSize, sorted.length)} of{' '}
                                        {sorted.length} records
                                    </div>
                                    <div className="pagination-controls">
                                        <select
                                            className="page-size-select"
                                            value={pageSize}
                                            onChange={e => {
                                                setPageSize(Number(e.target.value));
                                                setPage(1);
                                            }}
                                            aria-label="Records per page"
                                        >
                                            {PAGE_SIZE_OPTIONS.map(s => (
                                                <option key={s} value={s}>
                                                    {s} / page
                                                </option>
                                            ))}
                                        </select>
                                        <div className="pagination">
                                            <button
                                                className="pagination-item"
                                                onClick={() => setPage(1)}
                                                disabled={page === 1}
                                                aria-label="First page"
                                            >
                                                «
                                            </button>
                                            <button
                                                className="pagination-item"
                                                onClick={() => setPage(p => p - 1)}
                                                disabled={page === 1}
                                                aria-label="Previous page"
                                            >
                                                ‹
                                            </button>
                                            {pageRange.map(p => (
                                                <button
                                                    key={p}
                                                    className={`pagination-item${
                                                        p === page ? ' active' : ''
                                                    }`}
                                                    onClick={() => setPage(p)}
                                                    aria-label={`Page ${p}`}
                                                    aria-current={
                                                        p === page ? 'page' : undefined
                                                    }
                                                >
                                                    {p}
                                                </button>
                                            ))}
                                            <button
                                                className="pagination-item"
                                                onClick={() => setPage(p => p + 1)}
                                                disabled={page === totalPages}
                                                aria-label="Next page"
                                            >
                                                ›
                                            </button>
                                            <button
                                                className="pagination-item"
                                                onClick={() => setPage(totalPages)}
                                                disabled={page === totalPages}
                                                aria-label="Last page"
                                            >
                                                »
                                            </button>
                                        </div>
                                    </div>
                                </div>
                            )}
                        </div>

                        {/* Mobile card view */}
                        <div className="history-cards-mobile">
                            {sorted.map(record => (
                                <div key={record.processingId} className="history-card">
                                    <div className="history-card-top">
                                        {renderStatusBadge(record.status)}
                                        <span className="form-type-tag">
                                            {record.formType || 'Unknown'}
                                        </span>
                                        {record.confidence != null && (
                                            <span
                                                className={`history-card-confidence confidence-${
                                                    record.confidence * 100 >= 80
                                                        ? 'high'
                                                        : record.confidence * 100 >= 50
                                                            ? 'medium'
                                                            : 'low'
                                                }`}
                                            >
                                                {(record.confidence * 100).toFixed(0)}%
                                            </span>
                                        )}
                                    </div>
                                    <div className="history-card-id">
                                        <code>
                                            {record.processingId?.substring(0, 16)}…
                                        </code>
                                        <button
                                            type="button"
                                            className="copy-btn"
                                            onClick={() =>
                                                handleCopyId(record.processingId)
                                            }
                                            aria-label="Copy ID"
                                        >
                                            <i className="bi bi-clipboard" aria-hidden="true" />
                                        </button>
                                    </div>
                                    {record.caseId && (
                                        <div className="history-card-meta">
                                            Case: {record.caseId}
                                        </div>
                                    )}
                                    <div className="history-card-time">
                                        {record.timestamp
                                            ? new Date(record.timestamp).toLocaleString()
                                            : '—'}
                                    </div>
                                    <div className="history-card-actions">
                                        <button
                                            type="button"
                                            className="btn btn-primary btn-sm"
                                            onClick={() => handleViewDetails(record)}
                                            style={{ flex: 1 }}
                                        >
                                            <i className="bi bi-eye" aria-hidden="true" />{' '}
                                            View
                                        </button>
                                        <button
                                            type="button"
                                            className="btn btn-error btn-sm"
                                            onClick={() =>
                                                handleDelete(record.processingId)
                                            }
                                            style={{ flex: 1 }}
                                        >
                                            <i className="bi bi-trash" aria-hidden="true" />{' '}
                                            Delete
                                        </button>
                                    </div>
                                </div>
                            ))}
                        </div>
                    </>
                )}
            </div>

            {/* Drawer overlay */}
            <div
                className={`drawer-overlay${detailsVisible ? ' open' : ''}`}
                onClick={() => setDetailsVisible(false)}
                aria-hidden="true"
            />

            {/* Details drawer */}
            <aside
                className={`details-drawer${detailsVisible ? ' open' : ''}`}
                role="dialog"
                aria-modal="true"
                aria-label="Record Details"
            >
                <div className="drawer-header">
                    <h2 className="drawer-title">Record Details</h2>
                    <button
                        type="button"
                        className="drawer-close"
                        onClick={() => setDetailsVisible(false)}
                        aria-label="Close"
                    >
                        <i className="bi bi-x-lg" aria-hidden="true" />
                    </button>
                </div>
                <div className="drawer-body">
                    {selectedRecord && (
                        <div className="details-content">
                            <dl className="details-list">
                                <div className="details-row">
                                    <dt>Processing ID</dt>
                                    <dd>
                                        <div className="details-id-row">
                                            <code>{selectedRecord.processingId}</code>
                                            <button
                                                type="button"
                                                className="copy-btn"
                                                onClick={() =>
                                                    handleCopyId(
                                                        selectedRecord.processingId
                                                    )
                                                }
                                                aria-label="Copy ID"
                                            >
                                                <i className="bi bi-clipboard" aria-hidden="true" />
                                            </button>
                                        </div>
                                    </dd>
                                </div>
                                <div className="details-row">
                                    <dt>Form Type</dt>
                                    <dd>
                                        <span className="form-type-tag">
                                            {selectedRecord.formType || 'Unknown'}
                                        </span>
                                    </dd>
                                </div>
                                <div className="details-row">
                                    <dt>Case ID</dt>
                                    <dd>{selectedRecord.caseId || '—'}</dd>
                                </div>
                                <div className="details-row">
                                    <dt>Status</dt>
                                    <dd>{renderStatusBadge(selectedRecord.status)}</dd>
                                </div>
                                <div className="details-row">
                                    <dt>Confidence</dt>
                                    <dd>{renderConfidence(selectedRecord.confidence)}</dd>
                                </div>
                                <div className="details-row">
                                    <dt>Timestamp</dt>
                                    <dd>
                                        {selectedRecord.timestamp
                                            ? new Date(
                                                selectedRecord.timestamp
                                            ).toLocaleString()
                                            : '—'}
                                    </dd>
                                </div>
                                {selectedRecord.documentUrl && (
                                    <div className="details-row">
                                        <dt>Document</dt>
                                        <dd>
                                            <button
                                                type="button"
                                                className="btn btn-primary btn-sm"
                                                onClick={() =>
                                                    handleDownload(selectedRecord)
                                                }
                                            >
                                                <i
                                                    className="bi bi-download"
                                                    aria-hidden="true"
                                                />{' '}
                                                Download
                                            </button>
                                        </dd>
                                    </div>
                                )}
                            </dl>

                            <div className="details-raw-section">
                                <h4>Raw Data</h4>
                                <pre className="details-json">
                                    {JSON.stringify(selectedRecord, null, 2)}
                                </pre>
                            </div>
                        </div>
                    )}
                </div>
            </aside>
        </div>
    );
};

export default HistoryPanel;
