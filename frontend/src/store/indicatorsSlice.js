// frontend/src/store/indicatorsSlice.js

import { createSlice, createAsyncThunk } from '@reduxjs/toolkit';
import { createSelector } from 'reselect';
import axios from 'axios';

const API_BASE_URL = process.env.REACT_APP_API_URL;
const COOLDOWN_MS = 2 * 60 * 1000; // 2 minutes, matching statsSlice
let lastInfectionFetch = 0;
let lastPsbiSignCountFetch = 0;

// ==================== ASYNC THUNKS ====================
export const fetchInfectionIndicators = createAsyncThunk(
    'indicators/fetchInfection',
    async (_, { rejectWithValue }) => {
        const now = Date.now();
        const elapsed = now - lastInfectionFetch;

        if (elapsed < COOLDOWN_MS) {
            return rejectWithValue({
                type: 'COOLDOWN',
                remainingSeconds: Math.ceil((COOLDOWN_MS - elapsed) / 1000),
            });
        }

        lastInfectionFetch = now;

        try {
            const { data } = await axios.get(
                `${API_BASE_URL}/indicators/infection`,
                { timeout: 30000 }
            );
            return data;
        } catch (error) {
            return rejectWithValue({
                type: 'API_ERROR',
                message:
                    error.response?.data?.detail ||
                    error.response?.data?.message ||
                    `Failed to fetch infection indicators: ${error.message}`,
            });
        }
    }
);

export const fetchPsbiSignCount = createAsyncThunk(
    'indicators/fetchPsbiSignCount',
    async (_, { rejectWithValue }) => {
        const now = Date.now();
        const elapsed = now - lastPsbiSignCountFetch;

        if (elapsed < COOLDOWN_MS) {
            return rejectWithValue({
                type: 'COOLDOWN',
                remainingSeconds: Math.ceil((COOLDOWN_MS - elapsed) / 1000),
            });
        }

        lastPsbiSignCountFetch = now;

        try {
            const { data } = await axios.get(
                `${API_BASE_URL}/indicators/psbi-sign-count`,
                { timeout: 30000 }
            );
            return data;
        } catch (error) {
            return rejectWithValue({
                type: 'API_ERROR',
                message:
                    error.response?.data?.detail ||
                    error.response?.data?.message ||
                    `Failed to fetch pSBI sign-count distribution: ${error.message}`,
            });
        }
    }
);

// ==================== INITIAL STATE ====================
const initialState = {
    infection: { total: 0, bars: [] },
    psbiSignCount: { total: 0, bars: [] },
    loading: false,
    error: null,
    psbiSignCountLoading: false,
    psbiSignCountError: null,
    lastUpdated: null,
};

// ==================== SLICE ====================
const indicatorsSlice = createSlice({
    name: 'indicators',
    initialState,
    reducers: {
        clearIndicatorsError: (state) => {
            state.error = null;
        },
    },
    extraReducers: (builder) => {
        builder
            .addCase(fetchInfectionIndicators.pending, (state) => {
                state.loading = true;
                state.error = null;
            })
            .addCase(fetchInfectionIndicators.fulfilled, (state, action) => {
                state.loading = false;
                state.infection = action.payload;
                state.lastUpdated = new Date().toISOString();
            })
            .addCase(fetchInfectionIndicators.rejected, (state, action) => {
                state.loading = false;
                if (action.payload?.type !== 'COOLDOWN') {
                    state.error =
                        action.payload?.message || 'Failed to fetch indicators';
                }
            })
            .addCase(fetchPsbiSignCount.pending, (state) => {
                state.psbiSignCountLoading = true;
                state.psbiSignCountError = null;
            })
            .addCase(fetchPsbiSignCount.fulfilled, (state, action) => {
                state.psbiSignCountLoading = false;
                state.psbiSignCount = action.payload;
                state.lastUpdated = new Date().toISOString();
            })
            .addCase(fetchPsbiSignCount.rejected, (state, action) => {
                state.psbiSignCountLoading = false;
                if (action.payload?.type !== 'COOLDOWN') {
                    state.psbiSignCountError =
                        action.payload?.message || 'Failed to fetch pSBI sign-count';
                }
            });
    },
});

export const { clearIndicatorsError } = indicatorsSlice.actions;

// ==================== SELECTORS ====================
const selectIndicatorsState = (state) => state.indicators;

export const selectInfectionBars = createSelector(
    [selectIndicatorsState],
    (ind) => ind.infection.bars
);

export const selectInfectionTotal = createSelector(
    [selectIndicatorsState],
    (ind) => ind.infection.total
);

export const selectIndicatorsLoading = createSelector(
    [selectIndicatorsState],
    (ind) => ind.loading
);

export const selectIndicatorsError = createSelector(
    [selectIndicatorsState],
    (ind) => ind.error
);

export const selectPsbiSignCountBars = createSelector(
    [selectIndicatorsState],
    (ind) => ind.psbiSignCount.bars
);

export const selectPsbiSignCountTotal = createSelector(
    [selectIndicatorsState],
    (ind) => ind.psbiSignCount.total
);

export const selectPsbiSignCountLoading = createSelector(
    [selectIndicatorsState],
    (ind) => ind.psbiSignCountLoading
);

export const selectPsbiSignCountError = createSelector(
    [selectIndicatorsState],
    (ind) => ind.psbiSignCountError
);

export default indicatorsSlice.reducer;