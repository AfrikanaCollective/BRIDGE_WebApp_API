// frontend/src/components/Navbar.jsx
import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import '../styles/Navbar.css';
import faviconImage from '../assets/favicon.ico';

const NAV_LINKS = [
    { path: '/', label: 'Home', icon: 'bi-house-fill', exact: true },
    { path: '/upload', label: 'Upload', icon: 'bi-cloud-upload' },
    { path: '/history', label: 'History', icon: 'bi-clock-history' },
    { path: '/visualisations', label: 'Charts', icon: 'bi-bar-chart-fill' },
];

const Navbar = ({ onMenuClick }) => {
    const { pathname } = useLocation();

    const isActive = (path, exact) =>
        exact ? pathname === path : pathname.startsWith(path);

    return (
        <header className="app-header" role="banner">
            <div className="navbar-inner">
                <button
                    className="hamburger-btn navbar-hamburger"
                    onClick={onMenuClick}
                    aria-label="Toggle sidebar"
                    type="button"
                >
                    <i className="bi bi-list" aria-hidden="true" />
                </button>

                <Link to="/" className="navbar-brand">
                    <img src={faviconImage} alt="" className="navbar-favicon" />
                    <span className="brand-text">the data BRIDGE project</span>
                </Link>

                <nav className="navbar-nav" aria-label="Main navigation">
                    <ul>
                        {NAV_LINKS.map(({ path, label, icon, exact }) => (
                            <li key={path}>
                                <Link
                                    to={path}
                                    className={isActive(path, exact) ? 'active' : ''}
                                >
                                    <i className={`bi ${icon}`} aria-hidden="true" />
                                    <span>{label}</span>
                                </Link>
                            </li>
                        ))}
                    </ul>
                </nav>

                <Link to="/upload" className="navbar-cta-btn">
                    <i className="bi bi-cloud-upload" aria-hidden="true" />
                    <span>Upload Now</span>
                </Link>
            </div>
        </header>
    );
};

export default Navbar;
