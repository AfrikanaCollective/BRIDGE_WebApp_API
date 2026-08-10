// frontend/src/store/indicatorsSlice.js

import { createSlice, createAsyncThunk } from '@reduxjs/toolkit';
import { createSelector } from 'reselect';
import axios from 'axios';

const API_BASE_URL = process.env.REACT_APP_API_URL;
const COOLDOWN_MS = 2 * 60 * 1000; // 2 minutes, matching statsSlice
let lastInfectionFetch = 0;
let lastPsbiSignCountFetch = 0;
let lastSuspectedDiagnosesFetch = 0;
let lastDiagnosisOverlapFetch = 0;

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

export const fetchSuspectedDiagnoses = createAsyncThunk(
    'indicators/fetchSuspectedDiagnoses',
    async (_, { rejectWithValue }) => {
        const now = Date.now();
        const elapsed = now - lastSuspectedDiagnosesFetch;

        if (elapsed < COOLDOWN_MS) {
            return rejectWithValue({
                type: 'COOLDOWN',
                remainingSeconds: Math.ceil((COOLDOWN_MS - elapsed) / 1000),
            });
        }

        lastSuspectedDiagnosesFetch = now;

        try {
            const { data } = await axios.get(
                `${API_BASE_URL}/indicators/suspected-diagnoses`,
                { timeout: 30000 }
            );
            return data;
        } catch (error) {
            return rejectWithValue({
                type: 'API_ERROR',
                message:
                    error.response?.data?.detail ||
                    error.response?.data?.message ||
                    `Failed to fetch suspected diagnoses: ${error.message}`,
            });
        }
    }
);

export const fetchDiagnosisOverlap = createAsyncThunk(
    'indicators/fetchDiagnosisOverlap',
    async (_, { rejectWithValue }) => {
        const now = Date.now();
        const elapsed = now - lastDiagnosisOverlapFetch;

        if (elapsed < COOLDOWN_MS) {
            return rejectWithValue({
                type: 'COOLDOWN',
                remainingSeconds: Math.ceil((COOLDOWN_MS - elapsed) / 1000),
            });
        }

        lastDiagnosisOverlapFetch = now;

        try {
            const { data } = await axios.get(
                `${API_BASE_URL}/indicators/diagnosis-overlap`,
                { timeout: 30000 }
            );
            return data;
        } catch (error) {
            return rejectWithValue({
                type: 'API_ERROR',
                message:
                    error.response?.data?.detail ||
                    error.response?.data?.message ||
                    `Failed to fetch diagnosis overlap: ${error.message}`,
            });
        }
    }
);

// ==================== INITIAL STATE ====================
const initialState = {
    infection: { total: 0, bars: [] },
    psbiSignCount: { total: 0, bars: [] },
    suspectedDiagnoses: { total: 0, bars: [] },
    diagnosisOverlap: { total: 0, sets: null },
    loading: false,
    error: null,
    psbiSignCountLoading: false,
    psbiSignCountError: null,
    suspectedDiagnosesLoading: false,
    suspectedDiagnosesError: null,
    diagnosisOverlapLoading: false,
    diagnosisOverlapError: null,
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
            })
            .addCase(fetchSuspectedDiagnoses.pending, (state) => {
                state.suspectedDiagnosesLoading = true;
                state.suspectedDiagnosesError = null;
            })
            .addCase(fetchSuspectedDiagnoses.fulfilled, (state, action) => {
                state.suspectedDiagnosesLoading = false;
                state.suspectedDiagnoses = action.payload;
                state.lastUpdated = new Date().toISOString();
            })
            .addCase(fetchSuspectedDiagnoses.rejected, (state, action) => {
                state.suspectedDiagnosesLoading = false;
                if (action.payload?.type !== 'COOLDOWN') {
                    state.suspectedDiagnosesError =
                        action.payload?.message || 'Failed to fetch suspected diagnoses';
                }
            })
            .addCase(fetchDiagnosisOverlap.pending, (state) => {
                state.diagnosisOverlapLoading = true;
                state.diagnosisOverlapError = null;
            })
            .addCase(fetchDiagnosisOverlap.fulfilled, (state, action) => {
                state.diagnosisOverlapLoading = false;
                state.diagnosisOverlap = action.payload;
                state.lastUpdated = new Date().toISOString();
            })
            .addCase(fetchDiagnosisOverlap.rejected, (state, action) => {
                state.diagnosisOverlapLoading = false;
                if (action.payload?.type !== 'COOLDOWN') {
                    state.diagnosisOverlapError =
                        action.payload?.message || 'Failed to fetch diagnosis overlap';
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

export const selectSuspectedDiagnosesBars = createSelector(
    [selectIndicatorsState],
    (ind) => ind.suspectedDiagnoses.bars
);

export const selectSuspectedDiagnosesTotal = createSelector(
    [selectIndicatorsState],
    (ind) => ind.suspectedDiagnoses.total
);

export const selectSuspectedDiagnosesLoading = createSelector(
    [selectIndicatorsState],
    (ind) => ind.suspectedDiagnosesLoading
);

export const selectSuspectedDiagnosesError = createSelector(
    [selectIndicatorsState],
    (ind) => ind.suspectedDiagnosesError
);

export const selectDiagnosisOverlapSets = createSelector(
    [selectIndicatorsState],
    (ind) => ind.diagnosisOverlap.sets
);

export const selectDiagnosisOverlapTotal = createSelector(
    [selectIndicatorsState],
    (ind) => ind.diagnosisOverlap.total
);

export const selectDiagnosisOverlapLoading = createSelector(
    [selectIndicatorsState],
    (ind) => ind.diagnosisOverlapLoading
);

export const selectDiagnosisOverlapError = createSelector(
    [selectIndicatorsState],
    (ind) => ind.diagnosisOverlapError
);

export default indicatorsSlice.reducer;