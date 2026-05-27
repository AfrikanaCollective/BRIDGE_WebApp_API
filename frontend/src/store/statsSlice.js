// frontend/src/store/statsSlice.js

import { createSlice, createAsyncThunk } from '@reduxjs/toolkit';
import { createSelector } from 'reselect';
import axios from 'axios';

const API_BASE_URL = process.env.REACT_APP_API_URL;

// ==================== COOLDOWN STATE ====================
const COOLDOWN_MS = 5 * 60 * 1000; // 5 minutes
let lastFetchTime = 0;

// ==================== ASYNC THUNKS ====================
/**
 * Fetch stats with built-in cooldown enforcement
 * ✅ Prevents API calls within 5-minute window
 */
export const fetchStats = createAsyncThunk(
    'stats/fetchStats',
    async (_, { rejectWithValue }) => {
        const now = Date.now();
        const timeSinceLastFetch = now - lastFetchTime;

        // ==================== COOLDOWN CHECK ====================
        if (timeSinceLastFetch < COOLDOWN_MS) {
            const remainingSeconds = Math.ceil((COOLDOWN_MS - timeSinceLastFetch) / 1000);
            console.log(
                `⏭️  COOLDOWN ACTIVE: Skipping stats fetch (${remainingSeconds}s remaining)`
            );
            // Reject with cooldown error - component should ignore this gracefully
            return rejectWithValue({
                type: 'COOLDOWN',
                remainingSeconds,
                message: `Stats fetch on cooldown. Retry in ${remainingSeconds}s`,
            });
        }

        // ==================== UPDATE TIMESTAMP ====================
        lastFetchTime = now;
        console.log('📊 FETCHING STATS from backend...');

        try {
            // Backend endpoint: GET /api/stats/overview
            const endpoint = `${API_BASE_URL}/stats/overview`;
            console.log(`🔗 Request to: ${endpoint}`);

            const response = await axios.get(endpoint, {
                timeout: 30000,
            });

            console.log('✅ STATS FETCH SUCCESS:', response.data);
            return response.data;
        } catch (error) {
            console.error('❌ STATS FETCH ERROR:', {
                message: error.message,
                status: error.response?.status,
                statusText: error.response?.statusText,
                data: error.response?.data,
                config: error.config?.url,
            });

            return rejectWithValue({
                type: 'API_ERROR',
                message:
                    error.response?.data?.detail ||
                    error.response?.data?.message ||
                    `Failed to fetch stats: ${error.message}`,
            });
        }
    }
);

// ==================== INITIAL STATE ====================
const initialState = {
    data: {
        totalForms: 0,
        successRate: 0,
        avgProcessingTime: 0,
        activeSessions: 0,
    },
    loading: false,
    error: null,
    lastUpdated: null,
    lastError: null, // Track cooldown errors separately
};

// ==================== SLICE ====================
const statsSlice = createSlice({
    name: 'stats',
    initialState,
    reducers: {
        resetStats: (state) => {
            state.data = initialState.data;
            state.lastUpdated = null;
            state.error = null;
            state.lastError = null;
        },
        clearStatsError: (state) => {
            state.error = null;
        },
    },
    extraReducers: (builder) => {
        builder
            // ==================== PENDING ====================
            .addCase(fetchStats.pending, (state) => {
                console.log('⏳ Stats fetch PENDING');
                state.loading = true;
                state.error = null;
            })
            // ==================== FULFILLED ====================
            .addCase(fetchStats.fulfilled, (state, action) => {
                console.log('✅ Stats fetch FULFILLED');
                state.loading = false;
                state.error = null;
                state.lastError = null;

                // Transform snake_case to camelCase
                const backendData = action.payload;

                state.data = {
                    totalForms: backendData.total_processed ?? 0,
                    successRate: backendData.success_rate ?? 0,
                    avgProcessingTime:
                        backendData.processing_time_breakdown?.total_seconds?.average ?? 0,
                    activeSessions: backendData.active_sessions ?? 0,
                };

                state.lastUpdated = new Date().toISOString();
            })
            // ==================== REJECTED ====================
            .addCase(fetchStats.rejected, (state, action) => {
                console.log('❌ Stats fetch REJECTED:', action.payload);
                state.loading = false;

                // Only set error if it's NOT a cooldown rejection
                if (action.payload?.type === 'COOLDOWN') {
                    console.log(`⏭️  Cooldown: ${action.payload.remainingSeconds}s remaining`);
                    state.lastError = action.payload;
                    // ⭐ IMPORTANT: Don't set state.error for cooldown
                    // This prevents the UI from showing an error banner
                } else {
                    // Real API error
                    state.error = action.payload?.message || 'Failed to fetch statistics';
                    state.lastError = action.payload;
                }
            });
    },
});

export const { resetStats, clearStatsError } = statsSlice.actions;

// ==================== SELECTORS ====================
/**
 * Base selector to get stats state
 */
const selectStatsState = (state) => state.stats;

/**
 * Memoized selector for primary stats data
 * Returns: { totalForms, successRate, avgProcessingTime, activeSessions }
 */
export const selectPrimaryStats = createSelector(
    [selectStatsState],
    (stats) => stats.data
);

/**
 * Memoized selector for loading and error state
 * Returns: { loading, error }
 */
export const selectStatsLoadingState = createSelector(
    [selectStatsState],
    (stats) => ({
        loading: stats.loading,
        error: stats.error,
    })
);

/**
 * Memoized selector for last updated timestamp
 */
export const selectStatsLastUpdated = createSelector(
    [selectStatsState],
    (stats) => stats.lastUpdated
);

/**
 * Memoized selector to get a specific stat by key
 * Usage: selectStatByKey(state, 'totalForms')
 */
export const selectStatByKey = createSelector(
    [selectStatsState, (_, key) => key],
    (stats, key) => stats.data[key]
);

export default statsSlice.reducer;
