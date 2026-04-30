// frontend/src/components/FormUploader.jsx
import React, { useState } from 'react';
import { formAPI } from '../services/api';
import ResponseDisplay from './ResponseDisplay';

const FormUploader = () => {
  const [file, setFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [response, setResponse] = useState(null);
  const [error, setError] = useState(null);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [useStreaming, setUseStreaming] = useState(false);
  const [streamingData, setStreamingData] = useState('');

  const handleFileChange = (e) => {
    const selectedFile = e.target.files[0];
    if (selectedFile) {
      setFile(selectedFile);
      setError(null);
      setResponse(null);
      setStreamingData('');
    }
  };

  const handleUpload = async (e) => {
    e.preventDefault();

    if (!file) {
      setError('Please select a file');
      return;
    }

    setLoading(true);
    setError(null);
    setResponse(null);
    setUploadProgress(0);

    try {
      let result;

      if (useStreaming) {
        result = await formAPI.uploadFormStream(file, (chunk) => {
          if (chunk.error) {
            setError(chunk.error);
          } else {
            setStreamingData((prev) =>
              prev + JSON.stringify(chunk) + '\n'
            );
          }
        });
      } else {
        result = await formAPI.uploadForm(file);
      }

      if (result.success) {
        setResponse(result.data);
        setFile(null);
        document.getElementById('fileInput').value = '';
      } else {
        setError(result.error);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
      setUploadProgress(0);
    }
  };

  return (
    <div className="max-w-4xl mx-auto p-6">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-4xl font-bold text-gray-900 mb-2">
          Form Processor
        </h1>
        <p className="text-gray-600">
          Upload and process forms with AI-powered extraction
        </p>
      </div>

      {/* Upload Form */}
      <div className="bg-white rounded-lg shadow-md p-8 mb-8">
        <form onSubmit={handleUpload}>
          {/* File Input */}
          <div className="mb-6">
            <label className="block text-sm font-semibold text-gray-700 mb-4">
              Select Form
            </label>
            <div className="relative">
              <input
                id="fileInput"
                type="file"
                onChange={handleFileChange}
                disabled={loading}
                accept=".txt,.pdf,.jpg,.jpeg,.png,.docx"
                className="block w-full text-gray-500
                  file:mr-4 file:py-2 file:px-4
                  file:rounded-md file:border-0
                  file:text-sm file:font-semibold
                  file:bg-blue-50 file:text-blue-700
                  hover:file:bg-blue-100
                  disabled:opacity-50"
              />
              {file && (
                <div className="mt-2 text-sm text-green-600">
                  ✓ {file.name} ({(file.size / 1024).toFixed(2)} KB)
                </div>
              )}
            </div>
          </div>

          {/* Options */}
          <div className="mb-6">
            <label className="flex items-center">
              <input
                type="checkbox"
                checked={useStreaming}
                onChange={(e) => setUseStreaming(e.target.checked)}
                disabled={loading}
                className="rounded"
              />
              <span className="ml-2 text-sm text-gray-700">
                Use streaming (real-time processing)
              </span>
            </label>
          </div>

          {/* Progress Bar */}
          {uploadProgress > 0 && (
            <div className="mb-6">
              <div className="w-full bg-gray-200 rounded-full h-2">
                <div
                  className="bg-blue-600 h-2 rounded-full transition-all"
                  style={{ width: `${uploadProgress}%` }}
                />
              </div>
            </div>
          )}

          {/* Submit Button */}
          <button
            type="submit"
            disabled={loading || !file}
            className="w-full bg-blue-600 text-white py-3 rounded-lg
              font-semibold hover:bg-blue-700 transition-colors
              disabled:bg-gray-400 disabled:cursor-not-allowed"
          >
            {loading ? (
              <span className="flex items-center justify-center">
                <svg
                  className="animate-spin h-5 w-5 mr-3"
                  viewBox="0 0 24 24"
                >
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
                Processing...
              </span>
            ) : (
              'Upload & Process'
            )}
          </button>
        </form>
      </div>

      {/* Error Message */}
      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-6 py-4 rounded-lg mb-8">
          <p className="font-semibold">Error</p>
          <p>{error}</p>
        </div>
      )}

      {/* Streaming Data Display */}
      {streamingData && (
        <div className="bg-gray-50 border border-gray-200 rounded-lg p-6 mb-8">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">
            Real-time Stream
          </h3>
          <pre className="bg-gray-900 text-gray-100 p-4 rounded overflow-auto max-h-96 text-sm">
            {streamingData}
          </pre>
        </div>
      )}

      {/* Response Display */}
      {response && <ResponseDisplay response={response} />}
    </div>
  );
};

export default FormUploader;
