// frontend/src/store/indicatorsSlice.js

import { createSlice, createAsyncThunk } from '@reduxjs/toolkit';
import { createSelector } from 'reselect';
import axios from 'axios';

const API_BASE_URL = process.env.REACT_APP_API_URL;
const COOLDOWN_MS = 2 * 60 * 1000; // 2 minutes, matching statsSlice
let lastInfectionFetch = 0;

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

// ==================== INITIAL STATE ====================
const initialState = {
    infection: { total: 0, bars: [] },
    loading: false,
    error: null,
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

export default indicatorsSlice.reducer;