import React, { useState, useEffect } from "react";
import {
    TextField, Button, Box, Stack,
    FormControl,
    InputLabel,
    Select,
    MenuItem,
} from "@mui/material";
import axios from "axios";
import { getCookie } from "./utils/csrf";

import Notification from './UIComponents/Notification';

import { LocalizationProvider } from '@mui/x-date-pickers/LocalizationProvider';
import { DatePicker } from '@mui/x-date-pickers/DatePicker';
import { AdapterDayjs } from '@mui/x-date-pickers/AdapterDayjs';
import dayjs from "dayjs";
import 'dayjs/locale/en-gb';

function AddPatientForm({
    hospital_id,
    userType,
    userEmail,
    onBack
}) {

    const apiUrl = process.env.REACT_APP_BRIDGE_API_URL;

    const [hospitalId, setHospitalId] = useState(hospital_id || "");
    const [hospitals, setHospitals] = useState([]);

    const [formData, setFormData] = useState({
        record_ipno: "",
        admission_date: null,
        discharge_date: null,
        hospital: hospital_id || "",
        userEmail: userEmail
    });

    const [notification, setNotification] = useState({
        open: false,
        message: "",
        severity: "info",
    });

    let hasFetched = false;

    useEffect(() => {


        const fetchData = async () => {

            if (hasFetched) return;
            hasFetched = true;

            const csrfToken = getCookie("csrftoken");

            try {
                const [hospitalsRes] = await Promise.all([
                    axios.get(`${apiUrl}/hospitals/`,
                        {
                            headers: {
                                "X-CSRFToken": csrfToken,
                            },
                            withCredentials: true //the browser will NOT send cookies by default.
                        })
                ]);

                setHospitals(hospitalsRes.data);
            } catch (err) {
                console.error("Failed to fetch form data:", err);
            }


        }

        if (userType !== "DM" && hospital_id) {
            setFormData((prev) => ({ ...prev, hospital: hospital_id }));
        }

        fetchData();
    }, [userType, hospital_id]);

    const handleChange = (field, value) => {
        setFormData((prev) => {
            let updated = { ...prev, [field]: value };
            return updated;
        });

        if (field === "hospital") {
            setHospitalId(value); // update hospitalId when hospital changes
        }
    };

    const handleSubmit = (e) => {
        e.preventDefault();
        const csrfToken = getCookie("csrftoken");

        axios.post(`${apiUrl}/patients/add`,
            formData, {
            headers: {
                "X-CSRFToken": csrfToken,
            },
            withCredentials: true //the browser will NOT send cookies by default.
        }).then(() => {
            setNotification({
                open: true,
                message: "Patient successfully added",
                severity: "success",
            });
            onBack();
        })
            .catch(err => console.error(err));
    };

    return (
        <Box component="form" onSubmit={handleSubmit} sx={{ mt: 2 }}>
            <Stack spacing={3}>

                <TextField
                    fullWidth
                    label="Record IP/No"
                    name="record_ipno"
                    value={formData.record_ipno}
                    variant="outlined"
                    onChange={(e) => handleChange("record_ipno", e.target.value)}
                    sx={{ mb: 3 }}
                    required
                />


                <LocalizationProvider dateAdapter={AdapterDayjs} adapterLocale="en-gb">
                    <DatePicker
                        label="Admission Date"
                        name="admission_date"
                        value={formData.admission_date}
                        format="DD/MM/YYYY"
                        maxDate={dayjs()}   // 👈 Admission cannot be after today
                        onChange={(newValue) => handleChange("admission_date", newValue)}
                        slotProps={{ textField: { fullWidth: true, required: true } }}
                    />

                    <DatePicker
                        label="Discharge Date"
                        name="discharge_date"
                        value={formData.discharge_date}
                        format="DD/MM/YYYY"
                        minDate={formData.admission_date} // 👈 ensures discharge ≥ admission
                        maxDate={dayjs()}   // 👈 Admission cannot be after today
                        onChange={(newValue) => handleChange("discharge_date", newValue)}
                        slotProps={{ textField: { fullWidth: true, required: true } }}
                    />
                </LocalizationProvider>

                <FormControl fullWidth sx={{ mt: 2 }}>
                    <InputLabel id="hospital-label">Hospital</InputLabel>
                    <Select
                        labelId="hospital-label"
                        label="Hospital"
                        value={formData.hospital}
                        disabled={userType !== "DM"}
                        onChange={(e) => handleChange("hospital", e.target.value)}
                        required
                    >
                        {hospitals.map((h) => (
                            <MenuItem key={h.id} value={h.id}>
                                {h.name}
                            </MenuItem>
                        ))}
                    </Select>
                </FormControl>

            </Stack>

            <Box sx={{ mt: 2 }}>
                <Button type="submit" variant="contained" color="primary">Save</Button>
                <Button onClick={onBack} sx={{ ml: 2 }}>Cancel</Button>
            </Box>
            <Notification
                open={notification.open}
                onClose={() => setNotification({ ...notification, open: false })}
                message={notification.message}
                severity={notification.severity}
            />
        </Box>

    );
}

export default AddPatientForm;