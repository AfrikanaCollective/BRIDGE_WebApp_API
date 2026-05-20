// frontend/src/components/UploadForm.jsx
import React, { useState, useCallback, useRef } from 'react';
import { toast } from 'react-toastify';
import axios from 'axios';
import '../styles/UploadForm.css';

const ALLOWED_EXTENSIONS = ['png', 'jpg', 'jpeg', 'pdf', 'tiff'];
const MAX_FILE_SIZE = 15 * 1024 * 1024; // 15MB

const UploadForm = ({ onSuccess, isBatchMode = false }) => {
    const [loading, setLoading] = useState(false);
    const [fileList, setFileList] = useState([]);
    const [uploadProgress, setUploadProgress] = useState(0);
    const [processingId, setProcessingId] = useState(null);
    const [uploadStatus, setUploadStatus] = useState(null); // 'success' | 'error'
    const [errorMessage, setErrorMessage] = useState('');
    const [dragOver, setDragOver] = useState(false);
    const fileInputRef = useRef(null);
    const cameraInputRef = useRef(null);

    const API_BASE_URL = process.env.REACT_APP_API_URL;

    const validateFile = useCallback((file) => {
        const ext = file.name.split('.').pop().toLowerCase();
        if (!ALLOWED_EXTENSIONS.includes(ext)) {
            toast.error(`Invalid file type. Allowed: ${ALLOWED_EXTENSIONS.join(', ').toUpperCase()}`);
            return false;
        }
        if (file.size > MAX_FILE_SIZE) {
            toast.error(`File size must not exceed 15MB. Yours is ${(file.size / 1024 / 1024).toFixed(2)}MB`);
            return false;
        }
        return true;
    }, []);

    const addFiles = useCallback((files) => {
        const valid = Array.from(files).filter(validateFile);
        if (!isBatchMode && valid.length > 1) {
            toast.error('Please select only one file for single upload');
            setFileList([valid[0]]);
        } else {
            setFileList(prev => isBatchMode ? [...prev, ...valid] : valid);
        }
        setErrorMessage('');
    }, [validateFile, isBatchMode]);

    const handleFileChange = useCallback((e) => addFiles(e.target.files), [addFiles]);
    const handleCameraCapture = useCallback((e) => {
        if (e.target.files?.[0]) addFiles(e.target.files);
    }, [addFiles]);

    const handleDragOver = useCallback((e) => { e.preventDefault(); setDragOver(true); }, []);
    const handleDragLeave = useCallback(() => setDragOver(false), []);
    const handleDrop = useCallback((e) => {
        e.preventDefault();
        setDragOver(false);
        addFiles(e.dataTransfer.files);
    }, [addFiles]);

    const removeFile = useCallback((index) => {
        setFileList(prev => prev.filter((_, i) => i !== index));
    }, []);

    const handleSubmit = useCallback(async (e) => {
        e.preventDefault();
        if (fileList.length === 0) { toast.error('Please select a file'); return; }

        setLoading(true);
        setUploadStatus(null);
        setUploadProgress(0);
        setErrorMessage('');

        try {
            const formData = new FormData();
            let url;

            if (isBatchMode) {
                fileList.forEach(f => formData.append('files', f));
                url = `${API_BASE_URL}/upload/`;
            } else {
                formData.append('file', fileList[0]);
                url = `${API_BASE_URL}/upload/`;
            }

            const response = await axios.post(url, formData, {
                headers: { 'Content-Type': 'multipart/form-data' },
                onUploadProgress: (ev) =>
                    setUploadProgress(Math.round((ev.loaded * 100) / ev.total)),
            });

            const id = response.data.batch_id || response.data.processing_id;
            setProcessingId(id);
            setUploadStatus('success');
            toast.success(isBatchMode
                ? `Batch upload started! Processing ${fileList.length} files.`
                : 'File uploaded successfully! Processing started.');
            setFileList([]);
            if (onSuccess) onSuccess(id);
        } catch (error) {
            setUploadStatus('error');
            const msg = error.response?.data?.detail || error.message || 'Upload failed';
            setErrorMessage(msg);
            toast.error(msg);
            console.error('Upload error:', error);
        } finally {
            setLoading(false);
        }
    }, [fileList, isBatchMode, onSuccess, API_BASE_URL]);

    return (
        <div className="upload-form-container">
            <div className="upload-form-card card">
                <div className="upload-form-header">
                    <h2>{isBatchMode ? 'Batch Upload' : 'Upload Document'}</h2>
                    <p className="upload-form-subtitle">
                        {isBatchMode
                            ? 'Upload multiple documents for batch processing'
                            : 'Upload a document for processing and extraction'}
                    </p>
                </div>

                {uploadStatus === 'success' && (
                    <div className="alert alert-success" role="alert">
                        <i className="bi bi-check-circle-fill" aria-hidden="true" />
                        <div className="alert-body">
                            <strong>Upload Successful!</strong>
                            <div>Processing ID: <code>{processingId}</code></div>
                            <div className="alert-actions">
                                <button
                                    type="button"
                                    className="btn btn-sm btn-primary"
                                    onClick={() => { window.location.href = `/history/${processingId}`; }}
                                >
                                    View Status
                                </button>
                                <button
                                    type="button"
                                    className="btn btn-sm btn-outline"
                                    onClick={() => { setUploadStatus(null); setProcessingId(null); setUploadProgress(0); }}
                                >
                                    Upload Another
                                </button>
                            </div>
                        </div>
                    </div>
                )}

                {uploadStatus === 'error' && (
                    <div className="alert alert-error" role="alert">
                        <i className="bi bi-x-circle-fill" aria-hidden="true" />
                        <div className="alert-body">
                            <strong>Upload Failed</strong>
                            <div>{errorMessage}</div>
                        </div>
                        <button
                            type="button"
                            className="alert-close"
                            aria-label="Dismiss"
                            onClick={() => { setUploadStatus(null); setErrorMessage(''); }}
                        >
                            <i className="bi bi-x" aria-hidden="true" />
                        </button>
                    </div>
                )}

                <form onSubmit={handleSubmit} className="upload-form" noValidate>
                    {/* Camera capture — mobile only */}
                    <div className="mobile-camera-section">
                        <input
                            ref={cameraInputRef}
                            type="file"
                            accept="image/*"
                            capture="environment"
                            style={{ display: 'none' }}
                            onChange={handleCameraCapture}
                        />
                        <button
                            type="button"
                            className="btn btn-primary btn-full camera-capture-btn"
                            onClick={() => cameraInputRef.current?.click()}
                        >
                            <i className="bi bi-camera" aria-hidden="true" />
                            Take Photo with Camera
                        </button>
                        <div className="divider-with-text">
                            <span>or choose a file</span>
                        </div>
                    </div>

                    {/* Drop zone */}
                    <div className="form-group">
                        <label className="required" htmlFor="file-input">
                            Select File{isBatchMode ? '(s)' : ''}
                        </label>
                        <div
                            id="file-drop-zone"
                            className={`file-input-drop${dragOver ? ' dragover' : ''}`}
                            onClick={() => !loading && fileInputRef.current?.click()}
                            onDragOver={handleDragOver}
                            onDragLeave={handleDragLeave}
                            onDrop={handleDrop}
                            role="button"
                            tabIndex={0}
                            aria-label="File drop zone — click or drag files here"
                            onKeyDown={(e) => e.key === 'Enter' && !loading && fileInputRef.current?.click()}
                        >
                            <input
                                id="file-input"
                                ref={fileInputRef}
                                type="file"
                                multiple={isBatchMode}
                                accept=".png,.jpg,.jpeg,.pdf,.tiff"
                                onChange={handleFileChange}
                                disabled={loading}
                                style={{ display: 'none' }}
                            />
                            <i className="bi bi-cloud-upload drop-zone-icon" aria-hidden="true" />
                            <p className="file-input-text">
                                {isBatchMode
                                    ? 'Drag multiple files here or click to select'
                                    : 'Drag a file here or click to select'}
                            </p>
                            <p className="drop-zone-hint">
                                Supported: PNG, JPG, JPEG, PDF, TIFF (Max 15MB each)
                            </p>
                        </div>
                    </div>

                    {/* File list */}
                    {fileList.length > 0 && (
                        <div className="upload-file-list">
                            <div className="divider" />
                            <p className="file-list-title">
                                Selected Files ({fileList.length})
                            </p>
                            <div className="file-list-items">
                                {fileList.map((file, index) => (
                                    <div key={index} className="file-list-item">
                                        <i className="bi bi-file-earmark file-icon" aria-hidden="true" />
                                        <span className="file-name">{file.name}</span>
                                        <span className="file-size">
                                            {(file.size / 1024 / 1024).toFixed(2)} MB
                                        </span>
                                        <button
                                            type="button"
                                            className="btn btn-sm btn-error file-remove-btn"
                                            onClick={() => removeFile(index)}
                                            aria-label={`Remove ${file.name}`}
                                        >
                                            Remove
                                        </button>
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}

                    {/* Progress */}
                    {loading && uploadProgress > 0 && (
                        <div className="upload-progress">
                            <div className="progress" role="progressbar" aria-valuenow={uploadProgress} aria-valuemin={0} aria-valuemax={100}>
                                <div
                                    className={`progress-bar${uploadProgress === 100 ? ' success' : ''}`}
                                    style={{ width: `${uploadProgress}%` }}
                                />
                            </div>
                            <p className="progress-text">{uploadProgress}% uploaded</p>
                        </div>
                    )}

                    {/* Submit */}
                    <button
                        type="submit"
                        className="btn btn-primary btn-full upload-submit-btn"
                        disabled={fileList.length === 0 || loading}
                    >
                        {loading ? (
                            <>
                                <span className="spinner" role="status" aria-label="Uploading" />
                                Uploading…
                            </>
                        ) : (
                            <>
                                <i className="bi bi-cloud-upload" aria-hidden="true" />
                                Upload &amp; Process
                            </>
                        )}
                    </button>
                </form>

                {/* Info */}
                <div className="divider" />
                <div className="info-grid">
                    <div className="info-box">
                        <h4>Supported Formats</h4>
                        <ul>
                            <li>PNG (.png)</li>
                            <li>JPEG (.jpg, .jpeg)</li>
                            <li>PDF (.pdf)</li>
                            <li>TIFF (.tiff)</li>
                        </ul>
                    </div>
                    <div className="info-box">
                        <h4>Processing Details</h4>
                        <ul>
                            <li>Max file size: 15MB</li>
                            <li>Processing time: 1-2 minutes</li>
                            <li>Results available in history</li>
                        </ul>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default UploadForm;
