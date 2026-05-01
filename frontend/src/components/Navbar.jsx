// frontend/src/components/Navbar.jsx
import React from 'react';
import { Layout, Menu, Button, Space } from 'antd';
import { Link } from 'react-router-dom';
import {
    HomeOutlined,
    UploadOutlined,
    HistoryOutlined,
    GithubOutlined,
} from '@ant-design/icons';
import '../styles/Navbar.css'
import faviconImage from '../assets/favicon.ico'

const { Header } = Layout;

const Navbar = () => {
    return (
        <Header
            className="navbar"
            style={{
                background: '#001529',
                color: 'white',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '0 24px',
                height: '64px',
                lineHeight: '64px',
            }}
        >
            <div className="navbar-brand">
                <div className="brand-container">
                    <img
                        src={faviconImage}
                        alt="BRIDGE Logo"
                        className="navbar-favicon"
                        title="the data BRIDGE project"
                    />
                    <h1 style={{ color: 'white', margin: 0, fontSize: '20px', lineHeight: '64px' }}>
                        the data BRIDGE project
                    </h1>
                </div>
            </div>

            <Menu
                theme="dark"
                mode="horizontal"
                defaultSelectedKeys={['home']}
                style={{
                    flex: 1,
                    justifyContent: 'center',
                    border: 'none',
                    height: '64px',
                    lineHeight: '64px',
                }}
            >
                <Menu.Item key="home" icon={<HomeOutlined />}>
                    <Link to="/">Home</Link>
                </Menu.Item>
                <Menu.Item key="upload" icon={<UploadOutlined />}>
                    <Link to="/upload">Upload</Link>
                </Menu.Item>
                <Menu.Item key="history" icon={<HistoryOutlined />}>
                    <Link to="/history">History</Link>
                </Menu.Item>
            </Menu>

            <Space>
                <Button
                    type="primary"
                    size="large"
                    icon={<UploadOutlined />}
                    style={{
                        background: '#1890ff',
                        borderColor: '#1890ff',
                        height: '40px',
                        lineHeight: '40px',
                    }}
                >
                    <Link to="/upload" style={{ color: 'white', textDecoration: 'none' }}>
                        Upload Now
                    </Link>
                </Button>
            </Space>
        </Header>
    );
};

export default Navbar;
