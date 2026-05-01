// frontend/src/components/UploadForm.jsx

import React, { useState, useCallback } from 'react';
import {
    Form,
    Button,
    Upload,
    Card,
    Row,
    Col,
    Spin,
    message,
    Progress,
    Alert,
    Space,
    Divider,
    Tooltip,
} from 'antd';
import {
    UploadOutlined,
    FileOutlined,
    CheckCircleOutlined,
    CloseCircleOutlined,
    InfoCircleOutlined,
} from '@ant-design/icons';
import axios from 'axios';
import '../styles/UploadForm.css';

const UploadForm = ({ onSuccess, isBatchMode = false }) => {
    const [form] = Form.useForm();
    const [loading, setLoading] = useState(false);
    const [fileList, setFileList] = useState([]);
    const [uploadProgress, setUploadProgress] = useState(0);
    const [processingId, setProcessingId] = useState(null);
    const [uploadStatus, setUploadStatus] = useState(null); // 'pending', 'processing', 'success', 'error'
    const [errorMessage, setErrorMessage] = useState('');

    const API_BASE_URL = process.env.REACT_APP_API_BASE_URL || 'http://localhost:8000/api';

    // Supported file types
    const ALLOWED_EXTENSIONS = ['png', 'jpg', 'jpeg', 'pdf', 'tiff'];
    const MAX_FILE_SIZE = 15 * 1024 * 1024; // 15MB

    // Validate file before upload
    const beforeUpload = useCallback((file) => {
        const fileExt = file.name.split('.').pop().toLowerCase();

        if (!ALLOWED_EXTENSIONS.includes(fileExt)) {
            message.error(
                `Invalid file type. Allowed types: ${ALLOWED_EXTENSIONS.join(', ').toUpperCase()}`
            );
            return false;
        }

        if (file.size > MAX_FILE_SIZE) {
            message.error(`File size must not exceed 15MB. Your file is ${(file.size / 1024 / 1024).toFixed(2)}MB`);
            return false;
        }

        return true;
    }, []);

    // Handle file selection
    const handleFileChange = useCallback(({ fileList: newFileList }) => {
        const validFiles = newFileList.filter((file) => beforeUpload(file.originFileObj || file));
        setFileList(validFiles);
        setErrorMessage('');
    }, [beforeUpload]);

    // Handle single file upload
    const handleSingleUpload = useCallback(async (values) => {
        if (fileList.length === 0) {
            message.error('Please select a file');
            return;
        }

        if (!isBatchMode && fileList.length > 1) {
            message.error('Please select only one file for single upload');
            return;
        }

        setLoading(true);
        setUploadStatus('pending');
        setUploadProgress(0);
        setErrorMessage('');

        try {
            const formData = new FormData();

            if (isBatchMode) {
                // Batch upload
                fileList.forEach((file) => {
                    formData.append('files', file.originFileObj || file);
                });

                const response = await axios.post(`${API_BASE_URL}/upload/form-batch`, formData, {
                    headers: {
                        'Content-Type': 'multipart/form-data',
                    },
                    onUploadProgress: (progressEvent) => {
                        const percentCompleted = Math.round(
                            (progressEvent.loaded * 100) / progressEvent.total
                        );
                        setUploadProgress(percentCompleted);
                    },
                });

                setProcessingId(response.data.batch_id || response.data.processing_id);
                setUploadStatus('success');
                message.success(`Batch upload started! Processing ${fileList.length} files.`);
            } else {
                // Single upload
                formData.append('file', fileList[0].originFileObj || fileList[0]);

                const response = await axios.post(`${API_BASE_URL}/upload/form`, formData, {
                    headers: {
                        'Content-Type': 'multipart/form-data',
                    },
                    onUploadProgress: (progressEvent) => {
                        const percentCompleted = Math.round(
                            (progressEvent.loaded * 100) / progressEvent.total
                        );
                        setUploadProgress(percentCompleted);
                    },
                });

                setProcessingId(response.data.processing_id);
                setUploadStatus('success');
                message.success('File uploaded successfully! Processing started.');
            }

            // Reset form
            form.resetFields();
            setFileList([]);

            // Trigger success callback
            if (onSuccess) {
                onSuccess(processingId);
            }
        } catch (error) {
            setUploadStatus('error');
            const errorMsg = error.response?.data?.detail || error.message || 'Upload failed';
            setErrorMessage(errorMsg);
            message.error(errorMsg);
            console.error('Upload error:', error);
        } finally {
            setLoading(false);
        }
    }, [fileList, isBatchMode, form, onSuccess, processingId, API_BASE_URL]);

    // Handle form submission
    const onFinish = useCallback((values) => {
        handleSingleUpload(values);
    }, [handleSingleUpload]);

    // View processing status
    const handleViewStatus = useCallback(() => {
        if (processingId) {
            window.location.href = `/history/${processingId}`;
        }
    }, [processingId]);

    return (
        <div className="upload-form-container">
            <Card className="upload-form-card">
                <div className="upload-form-header">
                    <h2>
                        {isBatchMode ? '📦 Batch Upload' : '📤 Upload Document'}
                    </h2>
                    <p className="upload-form-subtitle">
                        {isBatchMode
                            ? 'Upload multiple documents for batch processing'
                            : 'Upload a document for processing and extraction'}
                    </p>
                </div>

                {uploadStatus === 'success' && (
                    <Alert
                        message="Upload Successful!"
                        description={`Processing ID: ${processingId}`}
                        type="success"
                        icon={<CheckCircleOutlined />}
                        showIcon
                        closable
                        action={
                            <Space>
                                <Button size="small" type="primary" onClick={handleViewStatus}>
                                    View Status
                                </Button>
                                <Button
                                    size="small"
                                    onClick={() => {
                                        setUploadStatus(null);
                                        setProcessingId(null);
                                        setUploadProgress(0);
                                    }}
                                >
                                    Upload Another
                                </Button>
                            </Space>
                        }
                        style={{ marginBottom: '24px' }}
                    />
                )}

                {uploadStatus === 'error' && (
                    <Alert
                        message="Upload Failed"
                        description={errorMessage}
                        type="error"
                        icon={<CloseCircleOutlined />}
                        showIcon
                        closable
                        onClose={() => {
                            setUploadStatus(null);
                            setErrorMessage('');
                        }}
                        style={{ marginBottom: '24px' }}
                    />
                )}

                <Spin spinning={loading} tip="Uploading...">
                    <Form
                        form={form}
                        layout="vertical"
                        onFinish={onFinish}
                        className="upload-form"
                    >
                        {/* File Upload */}
                        <Form.Item
                            label={
                                <span>
                  Select File(s)
                  <Tooltip title="Supported formats: PNG, JPG, JPEG, PDF, TIFF (Max 100MB)">
                    <InfoCircleOutlined style={{ marginLeft: '8px' }} />
                  </Tooltip>
                </span>
                            }
                            required
                        >
                            <Upload.Dragger
                                name="file"
                                multiple={isBatchMode}
                                fileList={fileList}
                                onChange={handleFileChange}
                                beforeUpload={() => false} // Prevent automatic upload
                                accept=".png,.jpg,.jpeg,.pdf,.tiff"
                                className="upload-dragger"
                                disabled={loading}
                            >
                                <p className="ant-upload-drag-icon">
                                    <UploadOutlined />
                                </p>
                                <p className="ant-upload-text">
                                    {isBatchMode
                                        ? 'Drag multiple files here or click to select'
                                        : 'Drag a file here or click to select'}
                                </p>
                                <p className="ant-upload-hint">
                                    Supported formats: PNG, JPG, JPEG, PDF, TIFF (Max 15MB each)
                                </p>
                            </Upload.Dragger>
                        </Form.Item>

                        {/* File List Preview */}
                        {fileList.length > 0 && (
                            <div className="upload-file-list">
                                <Divider>Selected Files ({fileList.length})</Divider>
                                <div className="file-list-items">
                                    {fileList.map((file, index) => (
                                        <div key={index} className="file-list-item">
                                            <FileOutlined className="file-icon" />
                                            <span className="file-name">
                        {file.name || file.originFileObj?.name}
                      </span>
                                            <span className="file-size">
                        {((file.size || file.originFileObj?.size) / 1024 / 1024).toFixed(2)} MB
                      </span>
                                            <Button
                                                type="text"
                                                danger
                                                size="small"
                                                onClick={() => {
                                                    setFileList(fileList.filter((_, i) => i !== index));
                                                }}
                                            >
                                                Remove
                                            </Button>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}

                        {/* Upload Progress */}
                        {loading && uploadProgress > 0 && (
                            <div className="upload-progress">
                                <Progress
                                    percent={uploadProgress}
                                    status={uploadProgress === 100 ? 'success' : 'active'}
                                    strokeColor={{
                                        '0%': '#108ee9',
                                        '100%': '#87d068',
                                    }}
                                />
                                <p className="progress-text">{uploadProgress}% uploaded</p>
                            </div>
                        )}

                        {/* Submit Button */}
                        <Form.Item>
                            <Button
                                type="primary"
                                htmlType="submit"
                                size="large"
                                block
                                loading={loading}
                                disabled={fileList.length === 0 || loading}
                                className="upload-submit-btn"
                            >
                                {loading ? 'Uploading...' : 'Upload & Process'}
                            </Button>
                        </Form.Item>
                    </Form>

                    {/* Info Section */}
                    <Divider>Additional Information</Divider>
                    <Row gutter={[16, 16]}>
                        <Col xs={24} sm={12}>
                            <div className="info-box">
                                <h4>📋 Supported Formats</h4>
                                <ul>
                                    <li>PNG (.png)</li>
                                    <li>JPEG (.jpg, .jpeg)</li>
                                    <li>PDF (.pdf)</li>
                                    <li>TIFF (.tiff)</li>
                                </ul>
                            </div>
                        </Col>
                        <Col xs={24} sm={12}>
                            <div className="info-box">
                                <h4>⚙️ Processing Details</h4>
                                <ul>
                                    <li>Max file size: 15MB</li>
                                    <li>Processing time: 1-2 minutes</li>
                                    <li>Results available in history</li>
                                </ul>
                            </div>
                        </Col>
                    </Row>
                </Spin>
            </Card>
        </div>
    );
};

export default UploadForm;
