// frontend/src/pages/VisualisationsPage.jsx

import React from 'react';
import InfectionBarChart from '../components/charts/InfectionBarChart';
import '../styles/HomePage.css';

const VisualisationsPage = () => (
    <div className="home-page">
        <article className="hero-card">
            <h1>Dashboard</h1>
            <p>
                Aggregated clinical indicators derived from processed patient records.
                Charts update automatically every two minutes.
            </p>
        </article>

        <article className="statistics-card">
            <InfectionBarChart />
        </article>
    </div>
);

export default VisualisationsPage;