// frontend/src/pages/HomePage.jsx
import React from 'react';
import { Card, Row, Col, Button, Space, Statistic, Tag } from 'antd';
import { Link } from 'react-router-dom';
import {
    UploadOutlined,
    HistoryOutlined,
    FileOutlined,
    CheckCircleOutlined,
} from '@ant-design/icons';
import '../styles/HomePage.css';

const HomePage = () => {
    return (
        <div className="home-page">
            {/* Hero Section */}
            <Card className="hero-card" style={{ marginBottom: '32px' }}>
                <h1 style={{ fontSize: '32px', marginBottom: '16px' }}>
                    Form Processing System
                </h1>
                <p style={{ fontSize: '16px', color: '#666', marginBottom: '24px' }}>
                    Intelligent form extraction and processing powered by AI. Upload your forms
                    and let our system extract structured data automatically.
                </p>
                <Space>
                    <Button
                        type="primary"
                        size="large"
                        icon={<UploadOutlined />}
                        style={{ height: '48px', fontSize: '16px' }}
                    >
                        <Link to="/upload" style={{ color: 'white', textDecoration: 'none' }}>
                            Get Started - Upload Form
                        </Link>
                    </Button>
                    <Button
                        size="large"
                        icon={<HistoryOutlined />}
                        style={{ height: '48px', fontSize: '16px' }}
                    >
                        <Link to="/history" style={{ textDecoration: 'none' }}>
                            View Processing History
                        </Link>
                    </Button>
                </Space>
            </Card>

            {/* Features Section */}
            <Row gutter={[24, 24]} style={{ marginBottom: '32px' }}>
                <Col xs={24} sm={12} lg={6}>
                    <Card hoverable className="feature-card">
                        <FileOutlined style={{ fontSize: '32px', color: '#1890ff', marginBottom: '16px' }} />
                        <h3>Multiple Formats</h3>
                        <p>Support for PNG, JPG, PDF, and TIFF formats</p>
                        <Tag color="blue">Supported</Tag>
                    </Card>
                </Col>
                <Col xs={24} sm={12} lg={6}>
                    <Card hoverable className="feature-card">
                        <CheckCircleOutlined style={{ fontSize: '32px', color: '#52c41a', marginBottom: '16px' }} />
                        <h3>AI Extraction</h3>
                        <p>Powered by Qwen LLM for accurate data extraction</p>
                        <Tag color="green">Active</Tag>
                    </Card>
                </Col>
                <Col xs={24} sm={12} lg={6}>
                    <Card hoverable className="feature-card">
                        <UploadOutlined style={{ fontSize: '32px', color: '#faad14', marginBottom: '16px' }} />
                        <h3>Batch Processing</h3>
                        <p>Upload multiple forms at once for efficient processing</p>
                        <Tag color="orange">Available</Tag>
                    </Card>
                </Col>
                <Col xs={24} sm={12} lg={6}>
                    <Card hoverable className="feature-card">
                        <HistoryOutlined style={{ fontSize: '32px', color: '#722ed1', marginBottom: '16px' }} />
                        <h3>History Tracking</h3>
                        <p>Complete audit trail of all processed forms</p>
                        <Tag color="purple">Enabled</Tag>
                    </Card>
                </Col>
            </Row>

            {/* Statistics Section */}
            <Card style={{ marginBottom: '32px' }}>
                <Row gutter={[32, 32]}>
                    <Col xs={24} sm={12} lg={6}>
                        <Statistic title="Forms Processed" value={0} suffix="forms" />
                    </Col>
                    <Col xs={24} sm={12} lg={6}>
                        <Statistic title="Success Rate" value={0} suffix="%" />
                    </Col>
                    <Col xs={24} sm={12} lg={6}>
                        <Statistic title="Avg. Processing Time" value={0} suffix="s" />
                    </Col>
                    <Col xs={24} sm={12} lg={6}>
                        <Statistic title="Active Sessions" value={0} />
                    </Col>
                </Row>
            </Card>

            {/* Call to Action */}
            <Card className="cta-card" style={{ textAlign: 'center', background: '#fafafa' }}>
                <h2>Ready to process your forms?</h2>
                <p style={{ fontSize: '16px', marginBottom: '24px' }}>
                    Start uploading forms now and get structured data in seconds
                </p>
                <Button
                    type="primary"
                    size="large"
                    icon={<UploadOutlined />}
                    style={{ height: '48px', fontSize: '16px', minWidth: '200px' }}
                >
                    <Link to="/upload" style={{ color: 'white', textDecoration: 'none' }}>
                        Upload Your First Form
                    </Link>
                </Button>
            </Card>
        </div>
    );
};

export default HomePage;
