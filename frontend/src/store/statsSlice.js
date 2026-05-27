// frontend/src/store/slices/statsSlice.js
import { createSlice, createAsyncThunk } from '@reduxjs/toolkit';
import { createSelector } from 'reselect';
import axios from 'axios';

const API_BASE_URL = process.env.REACT_APP_API_URL;

// ==================== ASYNC THUNKS ====================
export const fetchStats = createAsyncThunk(
    'stats/fetchStats',
    async (_, { rejectWithValue }) => {
        try {
            // Backend endpoint: GET /api/stats/overview
            const endpoint = `${API_BASE_URL}/stats/overview`;
            console.log('🔍 Fetching stats from:', endpoint);

            const response = await axios.get(endpoint, {
                timeout: 5000,
            });

            console.log('✅ Stats response received:', response.data);
            return response.data;
        } catch (error) {
            console.error('❌ Stats fetch error:', {
                message: error.message,
                status: error.response?.status,
                statusText: error.response?.statusText,
                data: error.response?.data,
                config: error.config?.url,
            });

            return rejectWithValue(
                error.response?.data?.detail ||
                error.response?.data?.message ||
                `Failed to fetch stats: ${error.message}`
            );
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
};

// ==================== SLICE ====================
const statsSlice = createSlice({
    name: 'stats',
    initialState,
    reducers: {
        resetStats: (state) => {
            state.data = initialState.data;
            state.lastUpdated = null;
        },
        clearStatsError: (state) => {
            state.error = null;
        },
    },
    extraReducers: (builder) => {
        builder
            // Pending
            .addCase(fetchStats.pending, (state) => {
                state.loading = true;
                state.error = null;
            })
            // Fulfilled
            .addCase(fetchStats.fulfilled, (state, action) => {
                state.loading = false;
                state.error = null;

                // Transform snake_case to camelCase
                const backendData = action.payload;

                state.data = {
                    totalForms: backendData.total_processed ?? 0,
                    successRate: backendData.success_rate ?? 0,
                    avgProcessingTime: backendData.processing_time_breakdown?.total_seconds?.average ?? 0,
                    activeSessions: backendData.active_sessions ?? 0,
                };

                state.lastUpdated = new Date().toISOString();
            })
            // Rejected
            .addCase(fetchStats.rejected, (state, action) => {
                state.loading = false;
                state.error = action.payload || 'Failed to fetch statistics';
                console.error('❌ Stats fetch rejected:', state.error);
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
