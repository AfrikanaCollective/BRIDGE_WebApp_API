import React from "react";
import { Container, Card, CardContent, Typography, Box, Button } from "@mui/material";
import { WarningAmber } from "@mui/icons-material";
import { useLocation } from "react-router-dom";

const AwaitingApproval = ({ onLogout }) => {

    const location = useLocation();
    const { userEmail } = location.state || {}; // get email from nav

    return (
        <Container
            maxWidth="sm"
            sx={{
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                height: "100vh",
            }}
        >
            <Card sx={{ p: 4, borderRadius: 3, boxShadow: 6, textAlign: "center" }}>
                <CardContent>
                    <Box sx={{ display: "flex", justifyContent: "center", mb: 2 }}>
                        <WarningAmber sx={{ fontSize: 48, color: "orange" }} />
                    </Box>

                    <Typography variant="h5" gutterBottom>
                        Account Pending Approval
                    </Typography>
                    <Typography variant="body1" color="text.secondary" sx={{ mb: 3 }}>
                        Your account (<strong>{userEmail}</strong>) is awaiting approval by the administrator.
                        You will be notified once your access is granted.
                    </Typography>

                    <Button
                        variant="contained"
                        color="secondary"
                        onClick={onLogout}
                    >
                        Logout
                    </Button>
                </CardContent>
            </Card>
        </Container>
    );
};

export default AwaitingApproval;