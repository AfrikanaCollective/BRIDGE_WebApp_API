// frontend/src/pages/UploadPage.jsx

import React, { useState } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import UploadForm from '../components/UploadForm';
import '../styles/UploadPage.css';

const UploadPage = () => {
    const [searchParams] = useSearchParams();
    const navigate = useNavigate();

    const isBatchMode = searchParams.get('mode') === 'batch';

    const handleUploadSuccess = (processingId) => {
        // Redirect to history page with the processing ID
        setTimeout(() => {
            navigate(`/history/${processingId}`);
        }, 2000);
    };

    return (
        <div className="upload-page">
            <UploadForm
                onSuccess={handleUploadSuccess}
                isBatchMode={isBatchMode}
            />
        </div>
    );
};

export default UploadPage;
