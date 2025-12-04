import logo from './logo.svg';
import './App.css';

import React, { useState, useEffect } from "react";
import {
  Container, CardContent, Card, Typography,
  Avatar, Box, Button
} from "@mui/material";
import GridLoader from 'react-spinners/GridLoader';
import { GoogleLogin } from "@react-oauth/google";
import axios from "axios";
import { Navigate, useNavigate } from "react-router-dom";
import { BrowserRouter as Router, Routes, Route } from "react-router-dom";
import { deepPurple } from "@mui/material/colors";
import { getCookie } from "./utils/csrf";



import AppLayout from "./AppLayout";
import Notification from './UIComponents/Notification';

import ApproveUser from './Registration/ApproveUser';
import AwaitingApproval from './Registration/AwaitingApproval';
import CompleteProfile from './Registration/CompleteProfile';


import DocumentAI from './DocumentAI';

function App() {

  const navigate = useNavigate();
  const [view, setView] = useState({ mode: "menu" }); // "menu" | "list" | "add" 
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(false);
  const apiUrl = process.env.REACT_APP_BRIDGE_API_URL;

  const axiosInstance = axios.create({
    baseURL: apiUrl,
    withCredentials: true
  });

  const [notification, setNotification] = useState({
    open: false,
    message: "",
    severity: "info",
  });

  useEffect(() => {
    const initCsrf = async () => {
      try {
        await axiosInstance.get('/csrf/');
        console.log("CSRF token initialized:", getCookie("csrftoken"));
      } catch (err) {
        console.error("Failed to initialize CSRF", err);
      }
    };

    const fetchUser = async () => {
      const token = localStorage.getItem("access");
      if (token) {
        try {
          const res = await axiosInstance.get("/get-session-info/");
          if (res.data && res.data.email) {
            setUser({
              email: res.data.email,
              ...res.data
            });
          }
        } catch (err) {
          console.error("Failed to fetch user session:", err);
        }
      }
    };
  
    initCsrf();
    fetchUser();
  }, []);


  const isAuthenticated = () => {
    const token = localStorage.getItem("access");
    return !!token; // true if token exists
  };


  axiosInstance.interceptors.request.use((config) => {
    if (!config.url.endsWith("/auth/google/")) {
      const token = localStorage.getItem("access");
      if (token) config.headers.Authorization = `Bearer ${token}`;
    }
    const csrftoken = getCookie("csrftoken");
    if (csrftoken) config.headers["X-CSRFToken"] = csrftoken;
    return config;
  });


  // Refresh expired token automatically
  axiosInstance.interceptors.response.use(
    (response) => response,
    async (error) => {
      if (error.response?.status === 401) {
        const refresh = localStorage.getItem("refresh");
        if (refresh) {
          try {
            const res = await axiosInstance.post('/auth/refresh/', { refresh });
            localStorage.setItem("access", res.data.access);
            if (res.data.refresh) {
              localStorage.setItem("refresh", res.data.refresh); // rotated
            }
            error.config.headers.Authorization = `Bearer ${res.data.access}`;
            return axiosInstance(error.config); // retry
          } catch (e) {
            localStorage.clear();
            window.location.href = "/login";
          }
        }
      }
      return Promise.reject(error);
    }
  );

  // PrivateRoute defined here
  const PrivateRoute = ({ children }) => {
    return isAuthenticated() ? children : <Navigate to="/login" />;
  };

  const handleGoogleSuccess = async (credentialResponse) => {

    setLoading(true);

    try {
      const response = await axiosInstance.post(
        "/auth/google/",
        { access_token: credentialResponse.credential },
      );

      localStorage.setItem("access", response.data.access);
      localStorage.setItem("refresh", response.data.refresh);

      setUser(response.data.user);

      if (response.data.update_fields && response.data.update_fields.length > 0) {
        setLoading(false);
        navigate("/complete-profile", {
          state: { 
            user: response.data.user, 
            email: response.data.user.email,
            update: response.data.update_fields 
          },
        });
      } else {

        try {
          const res = await axiosInstance.get("/get-session-info/");

          if (res.data.approved !== null && res.data.approved === false) {

            console.log("User type:", res.data.user_type);
            setLoading(false);
            navigate("/awaiting-approval", {
              state: { userEmail: res.data.email }
            });

          } else {
            setLoading(false);
            navigate("/document-ai", {
              state: {
                userType: res.data.user_type,
                hospitalId: res.data.hospital_id,
                userEmail: res.data.email
              }
            });
          }

        } catch (err) {
          setLoading(false);
          console.error("Failed to get session info:", err);
        }

      }

    } catch (err) {
      setLoading(false);
      setNotification({
        open: true,
        message: "Login failed. Please try again.",
        severity: "error",
      });
      console.error("Login failed:", err);
    }
  };

  const handleGoogleError = () => {
    setLoading(false);
    setNotification({
      open: true,
      message: "Login failed. Please try again.",
      severity: "error",
    });
  };

  const handleLogout = async () => {

    try {
      await axiosInstance.post("/logout/");

      localStorage.removeItem("access");
      localStorage.removeItem("refresh");
      setUser(null);
      setNotification({
        open: true,
        message: "You have been logged out",
        severity: "success",
      });
      navigate("/login"); // redirect to login page
    } catch (err) {

      console.error("Logout failed:", err);
      setNotification({
        open: true,
        message: "Logout failed. Please try again.",
        severity: "error",
      });

    }


  };



  return (
    <>
      <Routes>
        {/* Login page */}

        <Route
          path="/login"
          element={
            <Container
              maxWidth="sm"
              sx={{
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                height: "100vh",
                mt: -2, // margin-top (adjust value to move card higher/lower)
              }}
            >
              <Card sx={{ p: 4, borderRadius: 3, boxShadow: 6, width: "100%" }}>
                <CardContent sx={{ textAlign: "center" }}>
                  <Avatar
                    sx={{
                      bgcolor: deepPurple[500],
                      width: 72,
                      height: 72,
                      margin: "0 auto",
                      mb: 2,
                      fontSize: 32,
                    }}
                  >
                    AI
                  </Avatar>

                  <Typography variant="h5" gutterBottom>
                    Welcome to AI Clerk Portal
                  </Typography>
                  <Typography variant="body1" color="text.secondary" sx={{ mb: 3 }}>
                    Please sign in with your Google account to continue.
                  </Typography>

                  <Box sx={{ display: "flex", justifyContent: "center" }}>
                    {loading ? (
                      <div style={{ textAlign: 'center', marginTop: '40px' }}>
                        <GridLoader
                          color="#1976d2"   // MUI primary blue
                          size={20}
                          margin={4}
                        />
                        <p style={{ marginTop: '20px' }}>Processing Login, please wait...</p>
                      </div>
                    ) : <GoogleLogin
                      onSuccess={handleGoogleSuccess}
                      onError={handleGoogleError}
                      useOneTap
                      theme="filled_blue"
                      shape="pill"
                      size="large"
                      text="signin_with"
                    />
                    }
                  </Box>
                </CardContent>
              </Card>
            </Container>
          }
        />

        {/* Protected app routes */}
        <Route
          path="/complete-profile"
          element={
            <PrivateRoute user={user}>
              <AppLayout user={user} onLogout={handleLogout}>
                <CompleteProfile />
              </AppLayout>
            </PrivateRoute>
          }
        />

        <Route
          path="/awaiting-approval"
          element={
            <PrivateRoute user={user}>
              <AppLayout user={user} onLogout={handleLogout}>
                <AwaitingApproval onLogout={handleLogout} />
              </AppLayout>
            </PrivateRoute>
          }
        />

        <Route
          path="/approve-user/:userId"
          element={
            <AppLayout>
              <ApproveUser />
            </AppLayout>
          }
        />

        <Route
          path="/document-ai"
          element={
            <PrivateRoute user={user}>
              <AppLayout user={user} onLogout={handleLogout} view={view} setView={setView}>
                <DocumentAI view={view} setView={setView} />
              </AppLayout>
            </PrivateRoute>
          }
        />      

        {/* Redirect root to login */}
        <Route path="/" element={<Navigate to="/login" />} />
      </Routes>

      <Notification
        open={notification.open}
        onClose={() => setNotification({ ...notification, open: false })}
        message={notification.message}
        severity={notification.severity}
      />

    </>

  );
};


export default App;