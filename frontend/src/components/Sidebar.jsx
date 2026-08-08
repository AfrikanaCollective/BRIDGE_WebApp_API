// frontend/src/components/Sidebar.jsx
import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import '../styles/Sidebar.css';

const NAV_ITEMS = [
    { path: '/', label: 'Home', icon: 'bi-house-fill', exact: true },
    { path: '/upload', label: 'Upload', icon: 'bi-cloud-upload' },
    { path: '/history', label: 'History', icon: 'bi-clock-history' },
    { path: '/visualisations', label: 'Dashboard', icon: 'bi-bar-chart-fill' },
];

const Sidebar = ({ collapsed }) => {
    const { pathname } = useLocation();

    const isActive = (path, exact) =>
        exact ? pathname === path : pathname.startsWith(path);

    return (
        <nav className={`sidebar-nav${collapsed ? ' collapsed' : ''}`} aria-label="Sidebar navigation">
            <ul>
                {NAV_ITEMS.map(({ path, label, icon, exact }) => (
                    <li key={path}>
                        <Link
                            to={path}
                            className={`sidebar-link${isActive(path, exact) ? ' active' : ''}`}
                            title={collapsed ? label : undefined}
                        >
                            <i className={`bi ${icon} sidebar-icon`} aria-hidden="true" />
                            {!collapsed && <span className="sidebar-label">{label}</span>}
                        </Link>
                    </li>
                ))}
            </ul>
        </nav>
    );
};

export default Sidebar;
