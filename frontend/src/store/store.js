// frontend/src/store/store.js

import { configureStore } from '@reduxjs/toolkit';
import statsReducer from './statsSlice';
import historyReducer from './historySlice';
import indicatorsReducer from './indicatorsSlice';

export const store = configureStore({
    reducer: {
        stats: statsReducer,
        history: historyReducer,
        indicators: indicatorsReducer,
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
