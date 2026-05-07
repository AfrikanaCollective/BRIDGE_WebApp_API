// frontend/src/components/HistoryPanel.jsx
import React, { useState, useEffect, useCallback } from 'react';
import { Table, Space, Button, Modal, Spin, Empty, message, Tag, Tooltip, Drawer, Descriptions, Row, Col, Card } from 'antd';
import {
  DeleteOutlined,
  EyeOutlined,
  ReloadOutlined,
  DownloadOutlined,
  CopyOutlined,
  ExclamationCircleOutlined,
} from '@ant-design/icons';
import axios from 'axios';
import '../styles/HistoryPanel.css';

const HistoryPanel = () => {
  const [responses, setResponses] = useState([]);
  const [loading, setLoading] = useState(false);
  const [selectedRecord, setSelectedRecord] = useState(null);
  const [detailsVisible, setDetailsVisible] = useState(false);
  const [refreshing, setRefreshing] = useState(false);

  // Wrap fetchResponses in useCallback to memoize the function
  const fetchResponses = useCallback(async () => {
    setLoading(true);
    try {
      const response = await axios.get(
          `${process.env.REACT_APP_API_URL}/api/history`
      );
      setResponses(response.data || []);
    } catch (error) {
      console.error('Error fetching history:', error);
      message.error('Failed to load history');
    } finally {
      setLoading(false);
    }
  }, []);

  // Now fetchResponses can be safely included in the dependency array
  useEffect(() => {
    fetchResponses();
  }, [fetchResponses]);

  const handleDelete = async (processingId) => {
    Modal.confirm({
      title: 'Delete Record',
      icon: <ExclamationCircleOutlined />,
      content: 'Are you sure you want to delete this record? This action cannot be undone.',
      okText: 'Delete',
      cancelText: 'Cancel',
      okType: 'danger',
      onOk: async () => {
        try {
          await axios.delete(
              `${process.env.REACT_APP_API_URL}/api/history/${processingId}`
          );
          message.success('Record deleted successfully');
          fetchResponses(); // Refresh the list
        } catch (error) {
          console.error('Error deleting record:', error);
          message.error('Failed to delete record');
        }
      },
    });
  };

  const handleViewDetails = (record) => {
    setSelectedRecord(record);
    setDetailsVisible(true);
  };

  const handleDownload = (record) => {
    if (record.documentUrl) {
      try {
        const link = document.createElement('a');
        link.href = record.documentUrl;
        link.download = `${record.processingId}.pdf`;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        message.success('Download started');
      } catch (error) {
        console.error('Error downloading file:', error);
        message.error('Failed to download file');
      }
    }
  };

  const handleRefresh = async () => {
    setRefreshing(true);
    await fetchResponses();
    setRefreshing(false);
  };

  const handleCopyId = (processingId) => {
    navigator.clipboard.writeText(processingId);
    message.success('Processing ID copied to clipboard');
  };

  // Status badge renderer with improved styling
  const renderStatus = (status) => {
    const statusConfig = {
      completed: {
        color: 'success',
        className: 'status-badge completed',
        label: 'Completed',
      },
      processing: {
        color: 'processing',
        className: 'status-badge processing',
        label: 'Processing',
      },
      failed: {
        color: 'error',
        className: 'status-badge failed',
        label: 'Failed',
      },
      pending: {
        color: 'warning',
        className: 'status-badge pending',
        label: 'Pending',
      },
    };

    const config = statusConfig[status] || { color: 'default', label: 'Unknown' };
    return (
        <Tag color={config.color} className={config.className}>
          {config.label}
        </Tag>
    );
  };

  // Confidence renderer with visual indicator
  const renderConfidence = (confidence) => {
    if (!confidence && confidence !== 0) return <span className="confidence-empty">-</span>;

    const percentage = confidence * 100;
    let className = 'confidence-high';

    if (percentage < 50) {
      className = 'confidence-low';
    } else if (percentage < 80) {
      className = 'confidence-medium';
    }

    return (
        <div className="confidence-wrapper">
          <div className="confidence-bar">
            <div className={`confidence-fill ${className}`} style={{ width: `${percentage}%` }} />
          </div>
          <span className={`confidence-text ${className}`}>{percentage.toFixed(0)}%</span>
        </div>
    );
  };

  const columns = [
    {
      title: 'Processing ID',
      dataIndex: 'processingId',
      key: 'processingId',
      width: 140,
      ellipsis: true,
      render: (text) => (
          <Tooltip title={text}>
          <span className="processing-id-cell">
            {text?.substring(0, 8)}...
            <CopyOutlined
                className="copy-icon"
                onClick={() => handleCopyId(text)}
                style={{ marginLeft: '8px', cursor: 'pointer' }}
            />
          </span>
          </Tooltip>
      ),
    },
    {
      title: 'Form Type',
      dataIndex: 'formType',
      key: 'formType',
      width: 110,
      render: (formType) => (
          <Tag color="blue" className="form-type-tag">
            {formType || 'Unknown'}
          </Tag>
      ),
    },
    {
      title: 'Case ID',
      dataIndex: 'caseId',
      key: 'caseId',
      width: 110,
      ellipsis: true,
      render: (caseId) => caseId || <span className="text-muted">-</span>,
    },
    {
      title: 'Status',
      dataIndex: 'status',
      key: 'status',
      width: 110,
      render: (status) => renderStatus(status),
      filters: [
        { text: 'Completed', value: 'completed' },
        { text: 'Processing', value: 'processing' },
        { text: 'Failed', value: 'failed' },
        { text: 'Pending', value: 'pending' },
      ],
      onFilter: (value, record) => record.status === value,
    },
    {
      title: 'Confidence',
      dataIndex: 'confidence',
      key: 'confidence',
      width: 130,
      render: (confidence) => renderConfidence(confidence),
      sorter: (a, b) => (a.confidence || 0) - (b.confidence || 0),
    },
    {
      title: 'Timestamp',
      dataIndex: 'timestamp',
      key: 'timestamp',
      width: 160,
      render: (timestamp) => {
        if (!timestamp) return <span className="text-muted">-</span>;
        return (
            <Tooltip title={new Date(timestamp).toLocaleString()}>
              <span>{new Date(timestamp).toLocaleDateString()} {new Date(timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
            </Tooltip>
        );
      },
      sorter: (a, b) => new Date(a.timestamp) - new Date(b.timestamp),
      defaultSortOrder: 'descend',
    },
    {
      title: 'Actions',
      key: 'actions',
      width: 140,
      fixed: 'right',
      render: (_, record) => (
          <Space size="small" className="actions-space">
            <Tooltip title="View Details">
              <Button
                  type="primary"
                  size="small"
                  icon={<EyeOutlined />}
                  onClick={() => handleViewDetails(record)}
                  className="action-btn-view"
              />
            </Tooltip>
            <Tooltip title={record.documentUrl ? 'Download' : 'No document available'}>
              <Button
                  type="default"
                  size="small"
                  icon={<DownloadOutlined />}
                  onClick={() => handleDownload(record)}
                  disabled={!record.documentUrl}
                  className="action-btn-download"
              />
            </Tooltip>
            <Tooltip title="Delete">
              <Button
                  type="primary"
                  danger
                  size="small"
                  icon={<DeleteOutlined />}
                  onClick={() => handleDelete(record.processingId)}
                  className="action-btn-delete"
              />
            </Tooltip>
          </Space>
      ),
    },
  ];

  return (
      <div className="history-panel">
        <div className="history-header">
          <div className="history-header-left">
            <h1 className="history-title">Processing History</h1>
            <span className="history-count">{responses.length} record{responses.length !== 1 ? 's' : ''}</span>
          </div>
          <div className="history-actions">
            <Button
                type="primary"
                icon={<ReloadOutlined />}
                onClick={handleRefresh}
                loading={refreshing}
                className="refresh-btn"
            >
              Refresh
            </Button>
          </div>
        </div>

        <div className="history-content">
          <Spin spinning={loading} tip="Loading history records...">
            {responses.length === 0 && !loading ? (
                <Empty
                    description="No history records found"
                    className="history-empty"
                    style={{ paddingTop: '60px' }}
                />
            ) : (
                <Table
                    columns={columns}
                    dataSource={responses}
                    rowKey="processingId"
                    pagination={{
                      pageSize: 10,
                      showSizeChanger: true,
                      showTotal: (total, range) => `${range[0]}-${range[1]} of ${total} records`,
                      pageSizeOptions: ['5', '10', '20', '50'],
                    }}
                    scroll={{ x: 1200 }}
                    className="history-table"
                    size="middle"
                />
            )}
          </Spin>
        </div>

        {/* Details Drawer (better UX than Modal) */}
        <Drawer
            title="Record Details"
            placement="right"
            onClose={() => setDetailsVisible(false)}
            open={detailsVisible}
            width={600}
            className="details-drawer"
        >
          {selectedRecord && (
              <div className="details-content">
                <Descriptions
                    column={1}
                    bordered
                    size="small"
                    className="details-descriptions"
                >
                  <Descriptions.Item label="Processing ID">
                    <div className="details-id-row">
                      <code>{selectedRecord.processingId}</code>
                      <CopyOutlined
                          onClick={() => handleCopyId(selectedRecord.processingId)}
                          style={{ cursor: 'pointer', marginLeft: '8px' }}
                      />
                    </div>
                  </Descriptions.Item>
                  <Descriptions.Item label="Form Type">
                    <Tag color="blue">{selectedRecord.formType || 'Unknown'}</Tag>
                  </Descriptions.Item>
                  <Descriptions.Item label="Case ID">
                    {selectedRecord.caseId || '-'}
                  </Descriptions.Item>
                  <Descriptions.Item label="Status">
                    {renderStatus(selectedRecord.status)}
                  </Descriptions.Item>
                  <Descriptions.Item label="Confidence">
                    {renderConfidence(selectedRecord.confidence)}
                  </Descriptions.Item>
                  <Descriptions.Item label="Timestamp">
                    {selectedRecord.timestamp ? new Date(selectedRecord.timestamp).toLocaleString() : '-'}
                  </Descriptions.Item>
                  {selectedRecord.documentUrl && (
                      <Descriptions.Item label="Document">
                        <Button
                            type="primary"
                            size="small"
                            icon={<DownloadOutlined />}
                            onClick={() => handleDownload(selectedRecord)}
                        >
                          Download
                        </Button>
                      </Descriptions.Item>
                  )}
                </Descriptions>

                {/* Raw JSON Data */}
                <Card
                    title="Raw Data"
                    size="small"
                    style={{ marginTop: '20px' }}
                    className="details-raw-card"
                >
                  <pre className="details-json">{JSON.stringify(selectedRecord, null, 2)}</pre>
                </Card>
              </div>
          )}
        </Drawer>
      </div>
  );
};

export default HistoryPanel;
