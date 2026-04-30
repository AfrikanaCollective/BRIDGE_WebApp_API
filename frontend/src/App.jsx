// frontend/src/App.jsx
import React, { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Link } from 'react-router-dom';
import FormUploader from './components/FormUploader';
import HistoryPanel from './components/HistoryPanel';
import { formAPI } from './services/api';

function App() {
  const [healthStatus, setHealthStatus] = useState(null);

  useEffect(() => {
    checkHealth();
    const interval = setInterval(checkHealth, 30000); // Check every 30s
    return () => clearInterval(interval);
  }, []);

  const checkHealth = async () => {
    const result = await formAPI.healthCheck();
    setHealthStatus(result.success);
  };

  return (
    <Router>
      <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100">
        {/* Header */}
        <header className="bg-white shadow">
          <div className="max-w-7xl mx-auto px-6 py-4 flex justify-between items-center">
            <Link to="/" className="flex items-center gap-2">
              <svg
                className="w-8 h-8 text-blue-600"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z"
                />
              </svg>
              <span className="text-2xl font-bold text-gray-900">
                FormAI
              </span>
            </Link>

            <nav className="flex items-center gap-6">
              <Link
                to="/"
                className="text-gray-700 hover:text-blue-600 transition-colors"
              >
                Upload
              </Link>
              <Link
                to="/history"
                className="text-gray-700 hover:text-blue-600 transition-colors"
              >
                History
              </Link>

              {/* Health Status */}
              <div className="flex items-center gap-2">
                <div
                  className={`w-3 h-3 rounded-full ${
                    healthStatus === true
                      ? 'bg-green-500'
                      : healthStatus === false
                      ? 'bg-red-500'
                      : 'bg-gray-400'
                  }`}
                />
                <span className="text-sm text-gray-600">
                  {healthStatus === true
                    ? 'Online'
                    : healthStatus === false
                    ? 'Offline'
                    : 'Checking...'}
                </span>
              </div>
            </nav>
          </div>
        </header>

        {/* Main Content */}
        <main className="py-12">
          <Routes>
            <Route path="/" element={<FormUploader />} />
            <Route path="/history" element={<HistoryPanel />} />
          </Routes>
        </main>

        {/* Footer */}
        <footer className="bg-white border-t mt-12">
          <div className="max-w-7xl mx-auto px-6 py-8 text-center text-gray-600">
            <p>
              Form Processor v1.0.0 • Powered by Qwen AI
            </p>
          </div>
        </footer>
      </div>
    </Router>
  );
}

export default App;
