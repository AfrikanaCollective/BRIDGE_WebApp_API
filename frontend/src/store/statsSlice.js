// frontend/src/store/slices/statsSlice.js

import { createSlice, createAsyncThunk } from '@reduxjs/toolkit';
import axios from 'axios';

const API_BASE_URL = process.env.REACT_APP_API_URL;

// ==================== ASYNC THUNK ====================
export const fetchStats = createAsyncThunk(
    'stats/fetchStats',
    async (_, { rejectWithValue }) => {
        try {
            console.log('📡 Fetching statistics from:', `${API_BASE_URL}/stats/overview`);
            const response = await axios.get(`${API_BASE_URL}/stats/overview`);

            console.log('📥 Raw stats response:', response.data);

            return response.data;
        } catch (error) {
            console.error('❌ Stats fetch error:', error.message);
            return rejectWithValue(
                error.response?.data?.detail ||
                error.message ||
                'Failed to fetch statistics'
            );
        }
    }
);

// ==================== HELPER: MAP BACKEND RESPONSE ====================
/**
 * Maps the backend StatsOverviewExtended response to frontend format.
 *
 * Backend response structure:
 * {
 *   total_processed: number,
 *   success_rate: number,
 *   processing_time_breakdown: {
 *     total_seconds: {
 *       average: number,
 *       max: number,
 *       min: number
 *     },
 *     llm_seconds: {...},
 *     agent_seconds: {...}
 *   },
 *   by_status: { completed: 0, failed: 0, ... },
 *   by_form_type: { ITF: 0, NAR: 0, ... },
 *   ...
 * }
 */
const mapStatsResponse = (response) => {
    if (!response) {
        console.warn('⚠️  Empty stats response');
        return {
            totalForms: 0,
            successRate: 0,
            avgProcessingTime: 0,
            activeSessions: 0,
            completedForms: 0,
            failedForms: 0,
            byStatus: {},
            byFormType: {},
            processingTimeBreakdown: {
                llm: { average: 0, min: 0, max: 0 },
                agent: { average: 0, min: 0, max: 0 },
                total: { average: 0, min: 0, max: 0 },
            },
            dateRange: {
                start: null,
                end: null,
            },
            periodDays: 30,
        };
    }

    const breakdown = response.processing_time_breakdown || {};
    const totalSeconds = breakdown.total_seconds || {};
    const llmSeconds = breakdown.llm_seconds || {};
    const agentSeconds = breakdown.agent_seconds || {};
    const byStatus = response.by_status || {};

    const mapped = {
        // ✅ Primary metrics for HomePage
        totalForms: response.total_processed || 0,
        successRate: response.success_rate || 0,
        avgProcessingTime: totalSeconds.average || 0, // Uses total_seconds (LLM + Agent)
        activeSessions: 0, // Not provided by backend currently

        // ✅ Additional metrics
        completedForms: byStatus.completed || 0,
        failedForms: byStatus.failed || 0,

        // ✅ Detailed breakdowns for analytics
        byStatus: {
            completed: byStatus.completed || 0,
            failed: byStatus.failed || 0,
            pending: byStatus.pending || 0,
            processing: byStatus.processing || 0,
            ...byStatus,
        },
        byFormType: response.by_form_type || {},

        // ✅ Processing time breakdown (all in seconds)
        processingTimeBreakdown: {
            llm: {
                average: llmSeconds.average || 0,
                min: llmSeconds.min || 0,
                max: llmSeconds.max || 0,
            },
            agent: {
                average: agentSeconds.average || 0,
                min: agentSeconds.min || 0,
                max: agentSeconds.max || 0,
            },
            total: {
                average: totalSeconds.average || 0,
                min: totalSeconds.min || 0,
                max: totalSeconds.max || 0,
            },
        },

        // ✅ Metadata
        dateRange: response.date_range || {
            start: null,
            end: null,
        },
        periodDays: response.period_days || 30,
    };

    console.log('✅ Mapped stats:', mapped);
    return mapped;
};

// ==================== INITIAL STATE ====================
const initialState = {
    data: {
        // Primary metrics (for HomePage)
        totalForms: 0,
        successRate: 0,
        avgProcessingTime: 0,
        activeSessions: 0,

        // Additional metrics
        completedForms: 0,
        failedForms: 0,

        // Detailed breakdowns
        byStatus: {},
        byFormType: {},
        processingTimeBreakdown: {
            llm: { average: 0, min: 0, max: 0 },
            agent: { average: 0, min: 0, max: 0 },
            total: { average: 0, min: 0, max: 0 },
        },

        // Metadata
        dateRange: {
            start: null,
            end: null,
        },
        periodDays: 30,
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
        clearError: (state) => {
            state.error = null;
        },
        resetStats: (state) => {
            return { ...initialState };
        },
    },
    extraReducers: (builder) => {
        builder
            // ✅ PENDING: Show loading state
            .addCase(fetchStats.pending, (state) => {
                state.loading = true;
                state.error = null;
                console.log('⏳ Stats loading...');
            })

            // ✅ FULFILLED: Map and store data
            .addCase(fetchStats.fulfilled, (state, action) => {
                state.loading = false;
                state.data = mapStatsResponse(action.payload);
                state.lastUpdated = new Date().toISOString();
                state.error = null;

                console.log('📊 Stats updated at:', state.lastUpdated);
                console.log('   Total Forms:', state.data.totalForms);
                console.log('   Success Rate:', state.data.successRate.toFixed(1), '%');
                console.log('   Avg Processing Time:', state.data.avgProcessingTime.toFixed(2), 's');
            })

            // ✅ REJECTED: Handle error
            .addCase(fetchStats.rejected, (state, action) => {
                state.loading = false;
                state.error = action.payload;
                console.error('❌ Stats fetch failed:', action.payload);
            });
    },
});

// ==================== EXPORTS ====================
export const { clearError, resetStats } = statsSlice.actions;
export default statsSlice.reducer;

// ==================== SELECTORS ====================
/**
 * Select primary stats for HomePage
 */
export const selectPrimaryStats = (state) => ({
    totalForms: state.stats.data.totalForms,
    successRate: state.stats.data.successRate,
    avgProcessingTime: state.stats.data.avgProcessingTime,
    activeSessions: state.stats.data.activeSessions,
});

/**
 * Select detailed processing time breakdown
 */
export const selectProcessingTimeBreakdown = (state) =>
    state.stats.data.processingTimeBreakdown;

/**
 * Select status breakdown for analytics
 */
export const selectStatusBreakdown = (state) => state.stats.data.byStatus;

/**
 * Select form type breakdown for analytics
 */
export const selectFormTypeBreakdown = (state) => state.stats.data.byFormType;

/**
 * Select loading and error state
 */
export const selectStatsLoadingState = (state) => ({
    loading: state.stats.loading,
    error: state.stats.error,
    lastUpdated: state.stats.lastUpdated,
});
