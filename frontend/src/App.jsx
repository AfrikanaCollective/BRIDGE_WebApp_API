// frontend/src/App.jsx

import React, { useEffect } from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { useDispatch } from 'react-redux';
import { Layout, ConfigProvider } from 'antd';
import Navbar from './components/Navbar';
import Sidebar from './components/Sidebar';
import HomePage from './pages/HomePage';
import UploadPage from './pages/UploadPage';
import HistoryPage from './pages/HistoryPage';
import { fetchStats } from './store/statsSlice';
import './styles/App.css';

const { Content } = Layout;

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
            <Layout style={{ minHeight: '100vh' }}>
                <Navbar onMenuClick={() => setCollapsed(!collapsed)} />
                <Layout style={{ marginTop: '64px' }}>
                    <Sidebar collapsed={collapsed} />
                    <Layout style={{ marginLeft: collapsed ? '80px' : '200px' }}>
                        <Content style={{ padding: '0', background: '#fff' }}>
                            <Routes>
                                <Route path="/" element={<HomePage />} />
                                <Route path="/upload" element={<UploadPage />} />
                                <Route path="/history" element={<HistoryPage />} />
                                <Route path="/history/:processingId" element={<HistoryPage />} />
                                <Route path="*" element={<Navigate to="/" replace />} />
                            </Routes>
                        </Content>
                    </Layout>
                </Layout>
            </Layout>
        </ConfigProvider>
    );
};

export default App;
