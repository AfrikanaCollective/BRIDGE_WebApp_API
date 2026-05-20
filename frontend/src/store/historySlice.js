// frontend/src/store/historySlice.js

import { createSlice, createAsyncThunk } from '@reduxjs/toolkit';
import axios from 'axios';

const API_BASE_URL = process.env.REACT_APP_API_URL;

export const fetchHistory = createAsyncThunk(
    'history/fetchHistory',
    async (_, { rejectWithValue }) => {
        try {
            const response = await axios.get(`${API_BASE_URL}/history`);
            return response.data;
        } catch (error) {
            return rejectWithValue(error.response?.data || 'Failed to fetch history');
        }
    }
);

export const fetchHistoryDetail = createAsyncThunk(
    'history/fetchHistoryDetail',
    async (processingId, { rejectWithValue }) => {
        try {
            const response = await axios.get(
                `${API_BASE_URL}/history/${processingId}`
            );
            return response.data;
        } catch (error) {
            return rejectWithValue(error.response?.data || 'Failed to fetch history detail');
        }
    }
);

export const fetchProcessingStatus = createAsyncThunk(
    'history/fetchProcessingStatus',
    async (processingId, { rejectWithValue }) => {
        try {
            const response = await axios.get(
                `${API_BASE_URL}/upload/status/${processingId}`
            );
            return response.data;
        } catch (error) {
            return rejectWithValue(error.response?.data || 'Failed to fetch processing status');
        }
    }
);

const initialState = {
    items: [],
    detailItem: null,
    statusItem: null,
    loading: false,
    detailLoading: false,
    statusLoading: false,
    error: null,
    detailError: null,
    statusError: null,
};

const historySlice = createSlice({
    name: 'history',
    initialState,
    reducers: {
        clearError: (state) => {
            state.error = null;
        },
        clearDetailError: (state) => {
            state.detailError = null;
        },
        clearStatusError: (state) => {
            state.statusError = null;
        },
        clearDetail: (state) => {
            state.detailItem = null;
        },
    },
    extraReducers: (builder) => {
        builder
            // fetchHistory
            .addCase(fetchHistory.pending, (state) => {
                state.loading = true;
                state.error = null;
            })
            .addCase(fetchHistory.fulfilled, (state, action) => {
                state.loading = false;
                state.items = action.payload;
            })
            .addCase(fetchHistory.rejected, (state, action) => {
                state.loading = false;
                state.error = action.payload;
            })
            // fetchHistoryDetail
            .addCase(fetchHistoryDetail.pending, (state) => {
                state.detailLoading = true;
                state.detailError = null;
            })
            .addCase(fetchHistoryDetail.fulfilled, (state, action) => {
                state.detailLoading = false;
                state.detailItem = action.payload;
            })
            .addCase(fetchHistoryDetail.rejected, (state, action) => {
                state.detailLoading = false;
                state.detailError = action.payload;
            })
            // fetchProcessingStatus
            .addCase(fetchProcessingStatus.pending, (state) => {
                state.statusLoading = true;
                state.statusError = null;
            })
            .addCase(fetchProcessingStatus.fulfilled, (state, action) => {
                state.statusLoading = false;
                state.statusItem = action.payload;
            })
            .addCase(fetchProcessingStatus.rejected, (state, action) => {
                state.statusLoading = false;
                state.statusError = action.payload;
            });
    },
});

export const { clearError, clearDetailError, clearStatusError, clearDetail } =
    historySlice.actions;
export default historySlice.reducer;
