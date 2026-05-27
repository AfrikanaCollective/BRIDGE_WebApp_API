// frontend/src/pages/HomePage.jsx

import React, { useEffect, useRef } from 'react';
import { Link } from 'react-router-dom';
import { useSelector, useDispatch } from 'react-redux';
import { fetchStats, selectPrimaryStats, selectStatsLoadingState } from '../store/statsSlice';
import '../styles/HomePage.css';

const HomePage = () => {
    const dispatch = useDispatch();
    const stats = useSelector(selectPrimaryStats);
    const { loading, error, lastUpdated } = useSelector(selectStatsLoadingState);
    const refreshIntervalRef = useRef(null);

    // ==================== EFFECTS ====================
    /**
     * Fetch stats on component mount and set up auto-refresh interval
     */
    useEffect(() => {
        console.log('🏠 HomePage mounted - fetching initial stats');

        // Initial fetch
        dispatch(fetchStats());

        // Auto-refresh every 30 seconds
        refreshIntervalRef.current = setInterval(() => {
            console.log('🔄 Auto-refreshing stats (30s interval)');
            dispatch(fetchStats());
        }, 30000);

        // Cleanup interval on unmount
        return () => {
            if (refreshIntervalRef.current) {
                clearInterval(refreshIntervalRef.current);
                console.log('🏠 HomePage unmounted - cleared refresh interval');
            }
        };
    }, [dispatch]);

    // ==================== FORMATTERS ====================
    /**
     * Format success rate as percentage with 1 decimal place
     */
    const formatSuccessRate = (rate) => {
        if (rate == null) return '0%';
        return `${Number(rate).toFixed(1)}%`;
    };

    /**
     * Format processing time in seconds with 2 decimal places
     */
    const formatProcessingTime = (seconds) => {
        if (seconds == null) return '0s';
        return `${Number(seconds).toFixed(2)}s`;
    };

    /**
     * Format last updated timestamp
     */
    const formatLastUpdated = (timestamp) => {
        if (!timestamp) return 'Never';
        const date = new Date(timestamp);
        return date.toLocaleTimeString();
    };

    // ==================== RENDER ====================
    return (
        <div className="home-page">
            {/* ==================== HERO SECTION ==================== */}
            <article className="hero-card">
                <h1>
                    the data BRIDGE clinical records collation &amp; harmonisation system
                </h1>
                <p>
                    Intelligent data extraction and processing powered by AI. Upload your forms
                    and let our platform using natural language processing and generative AI models
                    harmonise data items, even those collected for different clinical care domains.
                    Currently fine-tuned for the Clinical Information Network (CIN) forms{' '}
                    <b><i>only</i></b> found here:{' '}
                    <a
                        href="https://dataverse.harvard.edu/dataset.xhtml?persistentId=doi:10.7910/DVN/70WJ8O"
                        target="_blank"
                        rel="noreferrer"
                    >
                        Harvard Dataverse Repo
                    </a>
                    . Sample forms for &quot;quick&quot; testing can be found{' '}
                    <a
                        href="https://github.com/AfrikanaCollective/BRIDGE_LLM_extension/tree/main/tests/test_data"
                        target="_blank"
                        rel="noreferrer"
                    >
                        <b>here</b>
                    </a>
                    .
                </p>
                <div className="hero-actions">
                    <Link to="/upload" className="btn btn-outline btn-lg">
                        <i className="bi bi-cloud-upload" aria-hidden="true" />
                        Get Started — Upload Form
                    </Link>
                    <Link to="/history" className="btn btn-outline btn-lg">
                        <i className="bi bi-clock-history" aria-hidden="true" />
                        View Processing History
                    </Link>
                </div>
            </article>

            {/* ==================== FEATURES SECTION ==================== */}
            <div className="features-grid">
                <article className="feature-card">
                    <i className="bi bi-file-earmark-image feature-icon" aria-hidden="true" />
                    <h3>Multiple Formats</h3>
                    <p>Support for PNG, JPG and PDF formats</p>
                    <span className="badge badge-info">Supported</span>
                </article>
                <article className="feature-card">
                    <i className="bi bi-cpu feature-icon" aria-hidden="true" />
                    <h3>AI Extraction</h3>
                    <p>Powered by Large Language Models (LLMs) for accurate data extraction</p>
                    <span className="badge badge-success">Active</span>
                </article>
                <article className="feature-card">
                    <i className="bi bi-layers feature-icon" aria-hidden="true" />
                    <h3>Batch Processing</h3>
                    <p>Upload multiple forms at once for efficient processing</p>
                    <span className="badge badge-warning">Available</span>
                </article>
                <article className="feature-card">
                    <i className="bi bi-clock-history feature-icon" aria-hidden="true" />
                    <h3>History Tracking</h3>
                    <p>Complete audit trail of all processed forms</p>
                    <span className="badge badge-secondary">Enabled</span>
                </article>
            </div>

            {/* ==================== STATISTICS SECTION ==================== */}
            <article className="statistics-card">
                {/* ✅ HEADER WITH REFRESH STATUS */}
                <div className="stats-header">
                    <h2>Platform Statistics</h2>
                    <div className="stats-meta">
                        {loading && (
                            <span className="stats-status loading">
                                <i className="bi bi-arrow-repeat" aria-hidden="true" />
                                Updating...
                            </span>
                        )}
                        {error && (
                            <span className="stats-status error" title={String(error)}>
                                <i className="bi bi-exclamation-circle" aria-hidden="true" />
                                Failed to load
                            </span>
                        )}
                        {!loading && !error && lastUpdated && (
                            <span className="stats-status updated">
                                <i className="bi bi-check-circle" aria-hidden="true" />
                                Last updated: {formatLastUpdated(lastUpdated)}
                            </span>
                        )}
                    </div>
                </div>

                {/* ✅ STATS GRID */}
                <div className={`stats-grid ${loading ? 'loading' : ''}`}>
                    {/* Forms Processed */}
                    <div className="stat-item">
                        <div className="stat-value">
                            {loading ? (
                                <span className="skeleton skeleton-text" />
                            ) : (
                                stats.totalForms
                            )}
                        </div>
                        <div className="stat-label">Forms Processed</div>
                        <div className="stat-icon">
                            <i className="bi bi-file-earmark-check" aria-hidden="true" />
                        </div>
                    </div>

                    {/* Success Rate */}
                    <div className="stat-item">
                        <div className="stat-value">
                            {loading ? (
                                <span className="skeleton skeleton-text" />
                            ) : (
                                formatSuccessRate(stats.successRate)
                            )}
                        </div>
                        <div className="stat-label">Success Rate</div>
                        <div className="stat-icon success">
                            <i className="bi bi-graph-up" aria-hidden="true" />
                        </div>
                    </div>

                    {/* Avg. Processing Time */}
                    <div className="stat-item">
                        <div className="stat-value">
                            {loading ? (
                                <span className="skeleton skeleton-text" />
                            ) : (
                                formatProcessingTime(stats.avgProcessingTime)
                            )}
                        </div>
                        <div className="stat-label">Avg. Processing Time</div>
                        <div className="stat-icon">
                            <i className="bi bi-hourglass-split" aria-hidden="true" />
                        </div>
                    </div>

                    {/* Active Sessions */}
                    <div className="stat-item">
                        <div className="stat-value">
                            {loading ? (
                                <span className="skeleton skeleton-text" />
                            ) : (
                                stats.activeSessions
                            )}
                        </div>
                        <div className="stat-label">Active Sessions</div>
                        <div className="stat-icon">
                            <i className="bi bi-people" aria-hidden="true" />
                        </div>
                    </div>
                </div>

                {/* ✅ ERROR MESSAGE (if any) */}
                {error && (
                    <div className="stats-error-message">
                        <i className="bi bi-exclamation-triangle" aria-hidden="true" />
                        <span>{String(error)}</span>
                    </div>
                )}
            </article>

            {/* ==================== CTA SECTION ==================== */}
            <article className="cta-card">
                <h2>Ready to process your forms?</h2>
                <p>Start uploading forms now and get structured data in seconds</p>
                <Link to="/upload" className="btn btn-primary btn-lg">
                    <i className="bi bi-cloud-upload" aria-hidden="true" />
                    Upload Your First Form
                </Link>
            </article>
        </div>
    );
};

export default HomePage;
