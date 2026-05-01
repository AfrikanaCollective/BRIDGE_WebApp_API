// frontend/src/App.jsx

import React, { useEffect } from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { useDispatch } from 'react-redux';
import { Layout, ConfigProvider } from 'antd';
import Navbar from './components/Navbar';
import Sidebar from './components/Sidebar';
import FaviconUpdater from './components/FaviconUpdater';
import HomePage from './pages/HomePage';
import UploadPage from './pages/UploadPage';
import HistoryPage from './pages/HistoryPage';
import { fetchStats } from './store/statsSlice';
import './styles/App.css';

const { Content , Footer} = Layout;

const App = () => {
    const dispatch = useDispatch();
    const [collapsed, setCollapsed] = React.useState(false);

    useEffect(() => {
        // Fetch initial stats
        dispatch(fetchStats());

        // Set up polling interval (5 seconds)
        const interval = setInterval(() => {
            dispatch(fetchStats());
        }, 5000);

        return () => clearInterval(interval);
    }, [dispatch]);

    return (
        <ConfigProvider>
            <FaviconUpdater />
            <Layout style={{ minHeight: '100vh',  display: 'flex', flexDirection: 'column' }}>
                <Navbar onMenuClick={() => setCollapsed(!collapsed)} />
                <Layout style={{ flex: 1, overflow: 'hidden', marginTop: '64px'}}>
                    <Sidebar collapsed={collapsed} />
                    <Layout style={{
                        flex: 1,
                        marginLeft: collapsed ? '80px' : '200px',
                        overflow: 'hidden',
                        display: 'flex',
                        flexDirection: 'column',
                        transition: 'margin-left 0.2s ease'
                    }}>
                        <Content style={{
                            flex: 1,
                            overflow: 'auto',
                            display: 'flex',
                            flexDirection: 'column',
                            padding: '24px',
                            background: '#ffffff'
                        }}>
                            <div style={{ flex: 1 }}>
                            <Routes>
                                <Route path="/" element={<HomePage />} />
                                <Route path="/upload" element={<UploadPage />} />
                                <Route path="/history" element={<HistoryPage />} />
                                <Route path="/history/:processingId" element={<HistoryPage />} />
                                <Route path="*" element={<Navigate to="/" replace />} />
                            </Routes>
                            </div>
                            {/* Footer - Sticky */}
                            <Footer
                                style={{
                                    textAlign: 'center',
                                    background: 'linear-gradient(90deg, #001529 0%, #0a2647 100%)',
                                    color: 'white',
                                    padding: '32px 24px',
                                    flex: 'none',
                                    fontSize: 'var(--fs-base)',
                                    fontFamily: 'var(--font-primary)',
                                }}
                            >
                                <p style={{ margin: '0 0 8px 0', fontWeight: 500 }}>
                                    the data BRIDGE project © 2026
                                </p>
                                <p style={{ margin: 0, fontSize: 'var(--fs-sm)', color: '#d1d5db' }}>
                                    Intelligent Clinical Form Processing with AI
                                </p>
                            </Footer>
                        </Content>
                    </Layout>
                </Layout>
            </Layout>
        </ConfigProvider>
    );
};

export default App;
