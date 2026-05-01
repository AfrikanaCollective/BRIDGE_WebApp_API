// frontend/src/components/FaviconUpdater.jsx

import { useEffect } from 'react';
import faviconPng from '../assets/logo.png';

const FaviconUpdater = () => {
    useEffect(() => {
        // Update favicon
        const link = document.querySelector("link[rel*='icon']") ||
            document.createElement('link');

        link.rel = 'icon';
        link.type = 'image/png';
        link.href = faviconPng;
        link.sizes = '192x192';

        if (!document.querySelector("link[rel*='icon']")) {
            document.head.appendChild(link);
        }

        // Update page title with dynamic content
        const updateTitle = () => {
            const currentPath = window.location.pathname;
            let title = 'data BRIDGE project';

            document.title = title;
        };

        updateTitle();

        // Update on navigation
        window.addEventListener('popstate', updateTitle);
        return () => window.removeEventListener('popstate', updateTitle);
    }, []);

    return null;
};

export default FaviconUpdater;
