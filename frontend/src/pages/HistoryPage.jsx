// frontend/src/pages/HistoryPage.jsx
import React from 'react';
import HistoryPanel from '../components/HistoryPanel';

const HistoryPage = () => {
    return (
        <div style={{ padding: '24px' }}>
            <h1>Processing History</h1>
            <HistoryPanel />
        </div>
    );
};

export default HistoryPage;
