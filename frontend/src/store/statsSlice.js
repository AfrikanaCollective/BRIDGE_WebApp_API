// frontend/src/store/slices/statsSlice.js

import { createSlice, createAsyncThunk } from '@reduxjs/toolkit';
import axios from 'axios';

const API_BASE_URL = process.env.REACT_APP_API_URL;

// ==================== ASYNC THUNK ====================
export const fetchStats = createAsyncThunk(
    'stats/fetchStats',
    async (_, { rejectWithValue }) => {
        try {
            const response = await axios.get(`${API_BASE_URL}/stats/overview`);
            return response.data;
        } catch (error) {
            console.error('fetchStats error:', error);
            return rejectWithValue(
                error.response?.data?.message ||
                error.message ||
                'Failed to fetch statistics'
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
        clearStatsError: (state) => {
            state.error = null;
        },
        resetStats: (state) => {
            state.data = initialState.data;
            state.error = null;
            state.lastUpdated = null;
        },
    },
    extraReducers: (builder) => {
        builder
            .addCase(fetchStats.pending, (state) => {
                state.loading = true;
                state.error = null;
            })
            .addCase(fetchStats.fulfilled, (state, action) => {
                state.loading = false;
                const response = action.payload;

                // Extract avgProcessingTime from processing_time_breakdown.total_seconds.average
                const avgProcessingTime =
                    response?.processing_time_breakdown?.total_seconds?.average ?? 0;

                state.data = {
                    totalForms: response?.total_processed ?? 0,
                    successRate: response?.success_rate ?? 0,
                    avgProcessingTime: avgProcessingTime,
                    activeSessions: response?.active_sessions ?? 0,
                };
                state.lastUpdated = new Date().toISOString();
            })
            .addCase(fetchStats.rejected, (state, action) => {
                state.loading = false;
                state.error = action.payload || 'Failed to fetch statistics';
            });
    },
});

// ==================== SELECTORS ====================
/**
 * Select primary statistics for display
 * @param {Object} state Redux state
 * @returns {Object} Statistics data object
 */
export const selectPrimaryStats = (state) => state.stats.data;

/**
 * Select loading and error states
 * @param {Object} state Redux state
 * @returns {Object} Loading and error flags
 */
export const selectStatsLoadingState = (state) => ({
    loading: state.stats.loading,
    error: state.stats.error,
});

/**
 * Select last updated timestamp
 * @param {Object} state Redux state
 * @returns {string|null} ISO timestamp or null
 */
export const selectStatsLastUpdated = (state) => state.stats.lastUpdated;

/**
 * Select individual stats by key
 * @param {Object} state Redux state
 * @param {string} key Stat key (totalForms, successRate, avgProcessingTime, activeSessions)
 * @returns {number|string} Stat value
 */
export const selectStatByKey = (state, key) => state.stats.data[key];

// ==================== ACTIONS ====================
export const { clearStatsError, resetStats } = statsSlice.actions;

// ==================== DEFAULT EXPORT ====================
export default statsSlice.reducer;