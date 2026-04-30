// frontend/src/components/ResponseDisplay.jsx
import React, { useState } from 'react';

const ResponseDisplay = ({ response }) => {
  const [expandedSections, setExpandedSections] = useState({
    response: true,
    extractedData: true,
  });

  const toggleSection = (section) => {
    setExpandedSections((prev) => ({
      ...prev,
      [section]: !prev[section],
    }));
  };

  const formatJson = (obj) => {
    return JSON.stringify(obj, null, 2);
  };

  return (
    <div className="space-y-6">
      {/* Success Banner */}
      <div className="bg-green-50 border border-green-200 rounded-lg p-6">
        <div className="flex items-start">
          <svg
            className="text-green-600 mt-0.5 mr-3"
            width="20"
            height="20"
            viewBox="0 0 20 20"
            fill="currentColor"
          >
            <path
              fillRule="evenodd"
              d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z"
              clipRule="evenodd"
            />
          </svg>
          <div>
            <h3 className="text-lg font-semibold text-green-900">
              Processing Successful
            </h3>
            <p className="text-green-700 mt-1">
              Form processed in {response.processing_time?.toFixed(2)}s
              {response.cached && ' (from cache)'}
            </p>
          </div>
        </div>
      </div>

      {/* Metadata */}
      <div className="bg-white rounded-lg shadow-md p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">
          Processing Details
        </h3>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <p className="text-sm text-gray-600">Response ID</p>
            <p className="text-base font-mono text-gray-900">
              {response.response_id?.slice(0, 16)}...
            </p>
          </div>
          <div>
            <p className="text-sm text-gray-600">Processing Time</p>
            <p className="text-base font-semibold text-blue-600">
              {response.processing_time?.toFixed(2)}s
            </p>
          </div>
        </div>
      </div>

      {/* Qwen Response */}
      <div className="bg-white rounded-lg shadow-md overflow-hidden">
        <button
          onClick={() => toggleSection('response')}
          className="w-full px-6 py-4 flex items-center justify-between
            bg-gray-50 hover:bg-gray-100 transition-colors"
        >
          <h3 className="text-lg font-semibold text-gray-900">
            AI Response
          </h3>
          <svg
            className={`w-6 h-6 text-gray-600 transition-transform ${
              expandedSections.response ? 'rotate-180' : ''
            }`}
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M19 14l-7 7m0 0l-7-7m7 7V3"
            />
          </svg>
        </button>

        {expandedSections.response && (
          <div className="px-6 py-4 bg-gray-50 border-t">
            <div className="bg-white p-4 rounded border border-gray-200">
              <p className="text-gray-700 whitespace-pre-wrap">
                {response.response}
              </p>
            </div>
          </div>
        )}
      </div>

      {/* Extracted Data */}
      <div className="bg-white rounded-lg shadow-md overflow-hidden">
        <button
          onClick={() => toggleSection('extractedData')}
          className="w-full px-6 py-4 flex items-center justify-between
            bg-gray-50 hover:bg-gray-100 transition-colors"
        >
          <h3 className="text-lg font-semibold text-gray-900">
            Extracted Data
          </h3>
          <svg
            className={`w-6 h-6 text-gray-600 transition-transform ${
              expandedSections.extractedData ? 'rotate-180' : ''
            }`}
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M19 14l-7 7m0 0l-7-7m7 7V3"
            />
          </svg>
        </button>

        {expandedSections.extractedData && (
          <div className="px-6 py-4 bg-gray-50 border-t">
            <div className="bg-gray-900 p-4 rounded overflow-auto">
              <pre className="text-green-400 text-sm font-mono">
                {formatJson(response.extracted_data)}
              </pre>
            </div>
          </div>
        )}
      </div>

      {/* Action Buttons */}
      <div className="flex gap-4">
        <button
          onClick={() => {
            navigator.clipboard.writeText(
              JSON.stringify(response, null, 2)
            );
            alert('Copied to clipboard!');
          }}
          className="flex-1 bg-blue-600 text-white py-2 rounded-lg
            hover:bg-blue-700 transition-colors font-semibold"
        >
          Copy Response
        </button>
        <button
          onClick={() => {
            const element = document.createElement('a');
            element.setAttribute(
              'href',
              'data:application/json;charset=utf-8,' +
                encodeURIComponent(JSON.stringify(response, null, 2))
            );
            element.setAttribute('download', 'response.json');
            element.style.display = 'none';
            document.body.appendChild(element);
            element.click();
            document.body.removeChild(element);
          }}
          className="flex-1 bg-green-600 text-white py-2 rounded-lg
            hover:bg-green-700 transition-colors font-semibold"
        >
          Download JSON
        </button>
      </div>
    </div>
  );
};

export default ResponseDisplay;
