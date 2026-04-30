// frontend/src/components/HistoryPanel.jsx
import React, { useState, useEffect, useCallback } from 'react';
import { Table, Space, Button, Modal, Spin, Empty, message, Tag, Tooltip } from 'antd';
import {
  DeleteOutlined,
  EyeOutlined,
  ReloadOutlined,
  DownloadOutlined,
  FileOutlined,
} from '@ant-design/icons';
import axios from 'axios';
import '../styles/HistoryPanel.css';

const HistoryPanel = () => {
  const [responses, setResponses] = useState([]);
  const [loading, setLoading] = useState(false);
  const [selectedRecord, setSelectedRecord] = useState(null);
  const [detailsVisible, setDetailsVisible] = useState(false);

  // Wrap fetchResponses in useCallback to memoize the function
  const fetchResponses = useCallback(async () => {
    setLoading(true);
    try {
      const response = await axios.get(
          `${process.env.REACT_APP_API_BASE_URL}/api/history`
      );
      setResponses(response.data || []);
    } catch (error) {
      console.error('Error fetching history:', error);
      message.error('Failed to load history');
    } finally {
      setLoading(false);
    }
  }, []); // Empty dependency array since fetchResponses doesn't depend on other state

  // Now fetchResponses can be safely included in the dependency array
  useEffect(() => {
    fetchResponses();
  }, [fetchResponses]);

  const handleDelete = async (processingId) => {
    Modal.confirm({
      title: 'Delete Record',
      content: 'Are you sure you want to delete this record?',
      okText: 'Yes',
      cancelText: 'No',
      okType: 'danger',
      onOk: async () => {
        try {
          await axios.delete(
              `${process.env.REACT_APP_API_BASE_URL}/api/history/${processingId}`
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
      const link = document.createElement('a');
      link.href = record.documentUrl;
      link.download = `${record.processingId}.pdf`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
    }
  };

  const handleRefresh = () => {
    fetchResponses();
  };

  const columns = [
    {
      title: 'Processing ID',
      dataIndex: 'processingId',
      key: 'processingId',
      width: 150,
      ellipsis: true,
      render: (text) => <Tooltip title={text}>{text?.substring(0, 8)}...</Tooltip>,
    },
    {
      title: 'Form Type',
      dataIndex: 'formType',
      key: 'formType',
      width: 100,
      render: (formType) => (
          <Tag color="blue">{formType || 'Unknown'}</Tag>
      ),
    },
    {
      title: 'Case ID',
      dataIndex: 'caseId',
      key: 'caseId',
      width: 100,
      ellipsis: true,
    },
    {
      title: 'Status',
      dataIndex: 'status',
      key: 'status',
      width: 100,
      render: (status) => {
        const colorMap = {
          completed: 'green',
          processing: 'blue',
          failed: 'red',
          pending: 'orange',
        };
        return <Tag color={colorMap[status] || 'default'}>{status || 'Unknown'}</Tag>;
      },
    },
    {
      title: 'Confidence',
      dataIndex: 'confidence',
      key: 'confidence',
      width: 100,
      render: (confidence) => {
        if (!confidence) return '-';
        const color = confidence >= 0.8 ? 'green' : confidence >= 0.5 ? 'orange' : 'red';
        return <Tag color={color}>{(confidence * 100).toFixed(0)}%</Tag>;
      },
    },
    {
      title: 'Timestamp',
      dataIndex: 'timestamp',
      key: 'timestamp',
      width: 150,
      render: (timestamp) => {
        if (!timestamp) return '-';
        return new Date(timestamp).toLocaleString();
      },
    },
    {
      title: 'Actions',
      key: 'actions',
      width: 150,
      fixed: 'right',
      render: (_, record) => (
          <Space size="small">
            <Button
                type="primary"
                size="small"
                icon={<EyeOutlined />}
                onClick={() => handleViewDetails(record)}
                title="View Details"
            />
            <Button
                type="default"
                size="small"
                icon={<DownloadOutlined />}
                onClick={() => handleDownload(record)}
                title="Download"
                disabled={!record.documentUrl}
            />
            <Button
                type="primary"
                danger
                size="small"
                icon={<DeleteOutlined />}
                onClick={() => handleDelete(record.processingId)}
                title="Delete"
            />
          </Space>
      ),
    },
  ];

  return (
      <div className="history-panel">
        <div className="history-header">
          <h2>Processing History</h2>
          <Button
              type="primary"
              icon={<ReloadOutlined />}
              onClick={handleRefresh}
              loading={loading}
          >
            Refresh
          </Button>
        </div>

        <Spin spinning={loading} tip="Loading...">
          {responses.length === 0 && !loading ? (
              <Empty description="No history records found" />
          ) : (
              <Table
                  columns={columns}
                  dataSource={responses}
                  rowKey="processingId"
                  pagination={{
                    pageSize: 10,
                    showSizeChanger: true,
                    showTotal: (total) => `Total ${total} items`,
                  }}
                  scroll={{ x: 1200 }}
                  className="history-table"
              />
          )}
        </Spin>

        {/* Details Modal */}
        <Modal
            title="Record Details"
            open={detailsVisible}
            onCancel={() => setDetailsVisible(false)}
            footer={[
              <Button key="close" onClick={() => setDetailsVisible(false)}>
                Close
              </Button>,
            ]}
            width={800}
        >
          {selectedRecord && (
              <div className="details-content">
                <pre>{JSON.stringify(selectedRecord, null, 2)}</pre>
              </div>
          )}
        </Modal>
      </div>
  );
};

export default HistoryPanel;
