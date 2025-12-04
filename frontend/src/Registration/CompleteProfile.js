import { useLocation, useNavigate } from "react-router-dom";
import { useEffect, useState } from "react";
import axios from "axios";

import {
    Container,
    Typography,
    Box,
    Button,
    Select,
    MenuItem,
    InputLabel,
    FormControl,
    TextField
} from "@mui/material";

export default function CompleteProfile() {
    const { state } = useLocation();
    const navigate = useNavigate();

    const [email, setEmail] = useState(state.email);

    const [formData, setFormData] = useState(state.user);
    const [hospitals, setHospitals] = useState([]);
    const [saving, setSaving] = useState(false);

    const apiUrl = process.env.REACT_APP_BRIDGE_API_URL;

    useEffect(() => {
        const fetchHospitals = async () => {
            try {
                const response = await axios.get(`${apiUrl}/hospitals/`);
                setHospitals(response.data);
            } catch (err) {
                console.error("Error fetching hospitals:", err);
            }
        };
        fetchHospitals();
    }, []);

    const handleChange = (field) => (e) => {
        setFormData((prev) => ({ ...prev, [field]: e.target.value }));
    };


    const handleSubmit = async () => {
        setSaving(true);

        try {
            await axios.post(`${apiUrl}/user/update/`, formData, {
                headers: { Authorization: `Bearer ${localStorage.getItem("access")}` },
            });
            
            
            setSaving(false);
            navigate("/awaiting-approval", {
                state: { userEmail: email }
            });
        } catch (err) {
            console.error("Update failed:", err);
        } finally {
            setSaving(false);
        }
    };

    return (
        <Container maxWidth="sm">
            <Box sx={{ mt: 4, display: "flex", flexDirection: "column", gap: 2 }}>
                <Typography variant="h5" gutterBottom>
                    Complete Your Profile
                </Typography>

                {state.update.includes("first_name") && (
                    <TextField
                        fullWidth
                        label="First Name"
                        value={formData.first_name || ""}
                        onChange={handleChange("first_name")}
                    />
                )}

                {state.update.includes("last_name") && (
                    <TextField
                        fullWidth
                        label="Last Name"
                        value={formData.last_name || ""}
                        onChange={handleChange("last_name")}
                    />
                )}

                {state.update.includes("hospital") && (
                    <FormControl fullWidth>
                        <InputLabel id="hospital-select-label">Select Hospital</InputLabel>
                        <Select
                            labelId="hospital-select-label"
                            value={formData.hospital || ""}
                            label="Select Hospital"
                            onChange={handleChange("hospital")}
                        >
                            {hospitals.map((hospital) => (
                                <MenuItem key={hospital.id} value={hospital.id}>
                                    {hospital.name}
                                </MenuItem>
                            ))}
                        </Select>
                    </FormControl>
                )}

                {state.update.includes("phone") && (
                    <TextField
                        fullWidth
                        label="Phone Number"
                        value={formData.phone || ""}
                        onChange={handleChange("phone")}
                    />
                )}

                {/* 🔐 Password */}
                <TextField
                    fullWidth
                    label="Password"
                    type="password"
                    value={formData.password || ""}
                    onChange={handleChange("password")}
                />

                {/* 🔐 Confirm Password */}
                <TextField
                    fullWidth
                    label="Confirm Password"
                    type="password"
                    value={formData.confirm_password || ""}
                    onChange={handleChange("confirm_password")}
                    error={
                        formData.confirm_password &&
                        formData.password !== formData.confirm_password
                    }
                    helperText={
                        formData.confirm_password &&
                            formData.password !== formData.confirm_password
                            ? "Passwords do not match"
                            : ""
                    }
                />

                <Button
                    variant="contained"
                    color="primary"
                    sx={{ mt: 2 }}
                    onClick={handleSubmit}
                    disabled={saving}
                >
                    {saving ? "Saving..." : "Save"}
                </Button>
            </Box>
        </Container>
    );
}
