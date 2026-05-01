// frontend/src/components/Sidebar.jsx (update if needed)
import React from 'react';
import { Layout, Menu } from 'antd';
import { HomeOutlined, UploadOutlined, HistoryOutlined } from '@ant-design/icons';
import { Link } from 'react-router-dom';

const { Sider } = Layout;

const Sidebar = ({ collapsed }) => {
    return (
        <Sider
            width={200}
            collapsedWidth={80}
            collapsed={collapsed}
            style={{
                overflow: 'auto',
                height: 'calc(100vh - 64px)',
                position: 'fixed',
                left: 0,
                top: 64,
                bottom: 0,
                backgroundColor: '#001529',
            }}
        >
            <Menu
                theme="dark"
                defaultSelectedKeys={['1']}
                style={{ backgroundColor: '#001529' }}
            >
                <Menu.Item key="1" icon={<HomeOutlined />}>
                    <Link to="/">Home</Link>
                </Menu.Item>
                <Menu.Item key="2" icon={<UploadOutlined />}>
                    <Link to="/upload">Upload</Link>
                </Menu.Item>
                <Menu.Item key="3" icon={<HistoryOutlined />}>
                    <Link to="/history">History</Link>
                </Menu.Item>
            </Menu>
        </Sider>
    );
};

export default Sidebar;
