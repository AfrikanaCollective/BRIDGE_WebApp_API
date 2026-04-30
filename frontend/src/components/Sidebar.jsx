// frontend/src/components/Sidebar.jsx
import React, { useState } from 'react';
import { Layout, Menu } from 'antd';
import { Link, useLocation } from 'react-router-dom';
import {
    HomeOutlined,
    UploadOutlined,
    HistoryOutlined,
    FileOutlined,
} from '@ant-design/icons';
import '../styles/Navbar.css';

const { Sider } = Layout;

const Sidebar = () => {
    const [collapsed, setCollapsed] = useState(false);
    const location = useLocation();

    const getSelectedKey = () => {
        const path = location.pathname;
        if (path === '/') return 'home';
        if (path === '/upload') return 'upload';
        if (path === '/history') return 'history';
        return 'home';
    };

    return (
        <Sider
            collapsible
            collapsedWidth={0}
            onCollapse={setCollapsed}
            breakpoint="lg"
            className="sidebar"
            style={{
                background: '#f0f2f5',
                minHeight: '100vh',
            }}
        >
            <Menu
                mode="inline"
                selectedKeys={[getSelectedKey()]}
                style={{ height: '100%', borderRight: '1px solid #d9d9d9' }}
            >
                <Menu.Item key="home" icon={<HomeOutlined />}>
                    <Link to="/">Home</Link>
                </Menu.Item>

                <Menu.ItemGroup title="Processing">
                    <Menu.Item key="upload" icon={<UploadOutlined />}>
                        <Link to="/upload">Upload Form</Link>
                    </Menu.Item>
                    <Menu.Item key="batch" icon={<FileOutlined />}>
                        <Link to="/upload?mode=batch">Batch Upload</Link>
                    </Menu.Item>
                </Menu.ItemGroup>

                <Menu.Item key="history" icon={<HistoryOutlined />}>
                    <Link to="/history">View History</Link>
                </Menu.Item>
            </Menu>
        </Sider>
    );
};

export default Sidebar;
