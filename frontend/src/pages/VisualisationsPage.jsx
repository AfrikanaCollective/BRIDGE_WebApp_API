// frontend/src/pages/VisualisationsPage.jsx

import React from 'react';
import InfectionBarChart from '../components/charts/InfectionBarChart';
import PsbiSignCountChart from '../components/charts/PsbiSignCountChart';
import SuspectedDiagnosesChart from '../components/charts/SuspectedDiagnosesChart';
import DiagnosisVennChart from '../components/charts/DiagnosisVennChart';
import '../styles/HomePage.css';

const VisualisationsPage = () => (
    <div className="home-page">
        <article className="hero-card">
            <h1>possible Serious Bacterial Infections (pSBI) dashboard</h1>
            <p>
                Aggregated clinical indicators derived from processed patient records.
                Charts update automatically every two minutes.
            </p>
        </article>

        <article className="statistics-card">
            <SuspectedDiagnosesChart />
        </article>

        <article className="statistics-card">
            <DiagnosisVennChart />
        </article>

        <article className="statistics-card">
            <PsbiSignCountChart />
        </article>

        <article className="statistics-card">
            <InfectionBarChart />
        </article>
    </div>
);

export default VisualisationsPage;