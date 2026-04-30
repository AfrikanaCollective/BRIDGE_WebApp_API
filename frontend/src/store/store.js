// frontend/src/store/store.js

import { configureStore } from '@reduxjs/toolkit';
import statsReducer from './statsSlice';
import historyReducer from './historySlice';

export const store = configureStore({
    reducer: {
        stats: statsReducer,
        history: historyReducer,
    },
    middleware: (getDefaultMiddleware) =>
        getDefaultMiddleware({
            serializableCheck: {
                ignoredActions: ['history/fetchHistoryDetail/fulfilled'],
                ignoredPaths: ['history.detailItem'],
            },
        }),
});

export default store;
