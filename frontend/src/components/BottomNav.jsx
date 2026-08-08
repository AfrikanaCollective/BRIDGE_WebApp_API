// frontend/src/components/BottomNav.jsx
import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import '../styles/BottomNav.css';

const NAV_ITEMS = [
    { path: '/', label: 'Home', icon: 'bi-house-fill', exact: true },
    { path: '/upload', label: 'Upload', icon: 'bi-cloud-upload' },
    { path: '/history', label: 'History', icon: 'bi-clock-history' },
    { path: '/visualisations', label: 'Dashboard', icon: 'bi-bar-chart-fill' },
];

const BottomNav = () => {
    const { pathname } = useLocation();

    const isActive = (path, exact) => {
        if (exact) return pathname === path;
        return pathname.startsWith(path);
    };

    return (
        <nav className="bottom-nav" aria-label="Mobile navigation">
            {NAV_ITEMS.map(({ path, label, icon, exact }) => (
                <Link
                    key={path}
                    to={path}
                    className={`bottom-nav-item${isActive(path, exact) ? ' active' : ''}`}
                    aria-label={label}
                >
                    <i className={`bi ${icon} bottom-nav-icon`} aria-hidden="true" />
                    <span className="bottom-nav-label">{label}</span>
                </Link>
            ))}
        </nav>
    );
};

export default BottomNav;
