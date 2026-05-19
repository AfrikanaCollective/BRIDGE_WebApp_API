// frontend/src/App.jsx

import React, { useEffect } from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { useDispatch } from 'react-redux';
import { ToastContainer } from 'react-toastify';
import Navbar from './components/Navbar';
import Sidebar from './components/Sidebar';
import BottomNav from './components/BottomNav';
import FaviconUpdater from './components/FaviconUpdater';
import HomePage from './pages/HomePage';
import UploadPage from './pages/UploadPage';
import HistoryPage from './pages/HistoryPage';
import { fetchStats } from './store/statsSlice';
import './styles/App.css';

const App = () => {
    const dispatch = useDispatch();
    const [collapsed, setCollapsed] = React.useState(false);

    useEffect(() => {
        dispatch(fetchStats());
        const interval = setInterval(() => dispatch(fetchStats()), 5000);
        return () => clearInterval(interval);
    }, [dispatch]);

    return (
        <>
            <FaviconUpdater />
            <div className="app-shell">
                <Navbar onMenuClick={() => setCollapsed(c => !c)} />

                <div className={`app-body${collapsed ? ' sidebar-collapsed' : ''}`}>
                    <aside className="app-sidebar desktop-sidebar" aria-label="Sidebar navigation">
                        <Sidebar collapsed={collapsed} />
                    </aside>

                    <main className="app-content">
                        <div className="page-wrapper">
                            <Routes>
                                <Route path="/" element={<HomePage />} />
                                <Route path="/upload" element={<UploadPage />} />
                                <Route path="/history" element={<HistoryPage />} />
                                <Route path="/history/:processingId" element={<HistoryPage />} />
                                <Route path="*" element={<Navigate to="/" replace />} />
                            </Routes>
                        </div>

                        <footer className="app-footer" role="contentinfo">
                            <p style={{ margin: '0 0 4px', fontWeight: 500, color: '#fff' }}>
                                the data BRIDGE project © 2026
                            </p>
                            <p style={{ margin: 0, fontSize: '0.875rem', color: '#d1d5db' }}>
                                Intelligent Clinical Form Processing with AI
                            </p>
                        </footer>
                    </main>
                </div>

                <BottomNav />
            </div>
            <ToastContainer position="bottom-right" theme="light" autoClose={3000} />
        </>
    );
};

export default App;
