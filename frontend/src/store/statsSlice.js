// frontend/src/store/slices/statsSlice.js
import { createSlice, createAsyncThunk } from '@reduxjs/toolkit';
import { createSelector } from 'reselect';
import axios from 'axios';

const API_BASE_URL = process.env.REACT_APP_API_BASE_URL;

// ==================== ASYNC THUNKS ====================
export const fetchStats = createAsyncThunk(
    'stats/fetchStats',
    async (_, { rejectWithValue }) => {
        try {
            const response = await axios.get(`${API_BASE_URL}/stats/overview`);
            return response.data;
        } catch (error) {
            return rejectWithValue(error.response?.data || 'Failed to fetch stats');
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
                    avgProcessingTime:
                        backendData.processing_time_breakdown?.total_seconds?.average ?? 0,
                    activeSessions: backendData.active_sessions ?? 0,
                };

                state.lastUpdated = new Date().toISOString();
            })
            // Rejected
            .addCase(fetchStats.rejected, (state, action) => {
                state.loading = false;
                state.error = action.payload || 'Failed to fetch statistics';
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
