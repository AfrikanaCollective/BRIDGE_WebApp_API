// frontend/src/pages/HomePage.jsx
import React, { useEffect, useRef, useMemo, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { useDispatch, useSelector } from 'react-redux';
import { fetchStats, selectPrimaryStats, selectStatsLoadingState } from '../store/statsSlice';
import '../styles/HomePage.css';

const HomePage = () => {
    const dispatch = useDispatch();
    const stats = useSelector(selectPrimaryStats);
    const { loading, error } = useSelector(selectStatsLoadingState);

    // ==================== REFS ====================
    const refreshIntervalRef = useRef(null);
    const fetchInProgressRef = useRef(false);
    const lastFetchTimeRef = useRef(0);

    // ==================== MEMOIZED FUNCTIONS ====================
    /**
     * Fetch stats with deduplication and cooldown
     */
    const fetchStatsWithDeduplication = useCallback(
        (force = false) => {
            const now = Date.now();
            const timeSinceLastFetch = now - lastFetchTimeRef.current;

            // ✅ Prevent duplicate requests within 1 minute
            if (timeSinceLastFetch < 5000 * 12 && !force) {
                console.log('⏭️  Skipping stats fetch (cooldown active)');
                return;
            }

            // ✅ Prevent concurrent requests
            if (fetchInProgressRef.current) {
                console.log('⏭️  Skipping stats fetch (request in progress)');
                return;
            }

            try {
                fetchInProgressRef.current = true;
                lastFetchTimeRef.current = now;

                console.log('📊 Dispatching fetchStats action');
                dispatch(fetchStats());
            } catch (err) {
                console.error('❌ Error dispatching fetchStats:', err);
            } finally {
                fetchInProgressRef.current = false;
            }
        },
        [dispatch]
    );

    // ==================== EFFECTS ====================
    /**
     * Fetch stats on component mount and set up auto-refresh interval
     * ✅ Only depends on fetchStatsWithDeduplication
     */
    useEffect(() => {
        console.log('🚀 HomePage mounted, initializing stats');

        // ✅ Initial fetch with force flag
        fetchStatsWithDeduplication(true);

        // ✅ Set up 5-minute auto-refresh interval
        refreshIntervalRef.current = setInterval(() => {
            console.log('⏱️  Stats refresh interval triggered (5 minutes)');
            fetchStatsWithDeduplication();
        }, 5 * 60 * 1000); // 5 minutes

        // ✅ Cleanup interval on unmount
        return () => {
            if (refreshIntervalRef.current) {
                clearInterval(refreshIntervalRef.current);
                refreshIntervalRef.current = null;
                console.log('🧹 Cleanup: Stats refresh interval cleared');
            }
        };
    }, [fetchStatsWithDeduplication]);

    // ==================== RENDER ====================
    return (
        <div className="home-page">
            {/* Hero */}
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

            {/* Features */}
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

            {/* Statistics */}
            <article className="statistics-card">
                {/* Loading State */}
                {loading && (
                    <div className="stats-loading" aria-label="Loading statistics">
                        <div className="spinner-border spinner-border-sm" role="status">
                            <span className="visually-hidden">Loading...</span>
                        </div>
                        <span>Updating statistics...</span>
                    </div>
                )}

                {/* Error State */}
                {error && !loading && (
                    <div className="alert alert-warning alert-dismissible fade show" role="alert">
                        <i className="bi bi-exclamation-triangle" aria-hidden="true" />
                        <span>{error}</span>
                        <button
                            type="button"
                            className="btn-close"
                            data-bs-dismiss="alert"
                            aria-label="Close"
                        />
                    </div>
                )}

                {/* Stats Grid - Always render with reserved space */}
                <div className="stats-grid">
                    <div className="stat-item">
                        <div className="stat-value">{stats?.totalForms ?? 0}</div>
                        <div className="stat-label">Forms Processed</div>
                    </div>
                    <div className="stat-item">
                        <div className="stat-value">
                            {stats?.successRate != null ? `${Number(stats.successRate).toFixed(1)}%` : '0%'}
                        </div>
                        <div className="stat-label">Success Rate</div>
                    </div>
                    <div className="stat-item">
                        <div className="stat-value">
                            {stats?.avgProcessingTime != null
                                ? `${Number(stats.avgProcessingTime).toFixed(2)}s`
                                : '0s'}
                        </div>
                        <div className="stat-label">Avg. Processing Time</div>
                    </div>
                    <div className="stat-item">
                        <div className="stat-value">{stats?.activeSessions ?? 0}</div>
                        <div className="stat-label">Active Sessions</div>
                    </div>
                </div>
            </article>

            {/* CTA */}
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
