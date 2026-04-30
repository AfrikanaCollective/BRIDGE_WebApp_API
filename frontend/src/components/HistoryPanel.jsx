// frontend/src/components/HistoryPanel.jsx
import React, { useState, useEffect } from 'react';
import { formAPI } from '../services/api';

const HistoryPanel = () => {
  const [responses, setResponses] = useState([]);
  const [loading, setLoading] = useState(false);
  const [pagination, setPagination] = useState({
    skip: 0,
    limit: 10,
    total: 0,
  });
  const [error, setError] = useState(null);
  const [selectedResponse, setSelectedResponse] = useState(null);

  useEffect(() => {
    fetchResponses();
  }, [pagination.skip]);

  const fetchResponses = async () => {
    setLoading(true);
    setError(null);

    const result = await formAPI.getResponses(
      pagination.skip,
      pagination.limit
    );

    if (result.success) {
      setResponses(result.data.data);
      setPagination((prev) => ({
        ...prev,
        total: result.data.pagination.total,
      }));
    } else {
      setError(result.error);
    }

    setLoading(false);
  };

  const handleDelete = async (responseId) => {
    if (window.confirm('Are you sure?')) {
      const result = await formAPI.deleteResponse(responseId);
      if (result.success) {
        fetchResponses();
      } else {
        alert('Delete failed: ' + result.error);
      }
    }
  };

  const totalPages = Math.ceil(pagination.total / pagination.limit);
  const currentPage = Math.floor(pagination.skip / pagination.limit) + 1;

  return (
    <div className="max-w-6xl mx-auto p-6">
      <div className="mb-8">
        <h2 className="text-3xl font-bold text-gray-900 mb-2">
          Processing History
        </h2>
        <p className="text-gray-600">
          View and manage all processed forms
        </p>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded mb-6">
          {error}
        </div>
      )}

      {loading && (
        <div className="flex justify-center py-8">
          <svg className="animate-spin h-8 w-8 text-blue-600" viewBox="0 0 24 24">
            <circle
              className="opacity-25"
              cx="12"
              cy="12"
              r="10"
              stroke="currentColor"
              strokeWidth="4"
              fill="none"
            />
            <path
              className="opacity-75"
              fill="currentColor"
              d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
            />
          </svg>
        </div>
      )}

      {!loading && responses.length === 0 && (
        <div className="bg-gray-50 border border-gray-200 rounded-lg p-8 text-center">
          <p className="text-gray-600">No responses yet</p>
        </div>
      )}

      {!loading && responses.length > 0 && (
        <>
          {/* Responses Table */}
          <div className="bg-white rounded-lg shadow-md overflow-hidden mb-6">
            <table className="w-full">
              <thead className="bg-gray-50 border-b">
                <tr>
                  <th className="px-6 py-3 text-left text-sm font-semibold text-gray-900">
                    Filename
                  </th>
                  <th className="px-6 py-3 text-left text-sm font-semibold text-gray-900">
                    Created
                  </th>
                  <th className="px-6 py-3 text-left text-sm font-semibold text-gray-900">
                    Time (s)
                  </th>
                  <th className="px-6 py-3 text-left text-sm font-semibold text-gray-900">
                    Confidence
                  </th>
                  <th className="px-6 py-3 text-right text-sm font-semibold text-gray-900">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody>
                {responses.map((response) => (
                  <tr key={response._id} className="border-b hover:bg-gray-50">
                    <td className="px-6 py-4 text-sm font-medium text-gray-900">
                      {response.filename}
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-600">
                      {new Date(response.created_at).toLocaleString()}
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-600">
                      {response.processing_time?.toFixed(2)}
                    </td>
                    <td className="px-6 py-4 text-sm">
                      <span
                        className={`px-3 py-1 rounded-full text-xs font-semibold ${
                          (response.confidence_score || 0) > 0.8
                            ? 'bg-green-100 text-green-800'
                            : (response.confidence_score || 0) > 0.5
                            ? 'bg-yellow-100 text-yellow-800'
                            : 'bg-red-100 text-red-800'
                        }`}
                      >
                        {((response.confidence_score || 0) * 100).toFixed(0)}%
                      </span>
                    </td>
                    <td className="px-6 py-4 text-sm text-right space-x-2">
                      <button
                        onClick={() => setSelectedResponse(response)}
                        className="text-blue-600 hover:text-blue-900"
                      >
                        View
                      </button>
                      <button
                        onClick={() => handleDelete(response._id)}
                        className="text-red-600 hover:text-red-900"
                      >
                        Delete
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          <div className="flex items-center justify-between">
            <div className="text-sm text-gray-600">
              Page {currentPage} of {totalPages} ({pagination.total} total)
            </div>
            <div className="flex gap-2">
              <button
                onClick={() =>
                  setPagination((prev) => ({
                    ...prev,
                    skip: Math.max(0, prev.skip - prev.limit),
                  }))
                }
                disabled={pagination.skip === 0}
                className="px-4 py-2 border rounded hover:bg-gray-50 disabled:opacity-50"
              >
                Previous
              </button>
              <button
                onClick={() =>
                  setPagination((prev) => ({
                    ...prev,
                    skip: prev.skip + prev.limit,
                  }))
                }
                disabled={currentPage >= totalPages}
                className="px-4 py-2 border rounded hover:bg-gray-50 disabled:opacity-50"
              >
                Next
              </button>
            </div>
          </div>
        </>
      )}

      {/* Detailed View Modal */}
      {selectedResponse && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-lg shadow-xl max-w-2xl w-full max-h-96 overflow-auto">
            <div className="sticky top-0 bg-gray-50 border-b px-6 py-4 flex justify-between items-center">
              <h3 className="font-semibold text-gray-900">
                {selectedResponse.filename}
              </h3>
              <button
                onClick={() => setSelectedResponse(null)}
                className="text-gray-500 hover:text-gray-700"
              >
                ✕
              </button>
            </div>
            <div className="px-6 py-4">
              <pre className="bg-gray-900 text-green-400 p-4 rounded text-sm overflow-auto">
                {JSON.stringify(selectedResponse, null, 2)}
              </pre>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default HistoryPanel;
