import React, { useState, useEffect } from "react";
import { default as MuiLink } from "@mui/material/Link";
import {
    Grid, Card, CardContent, Typography, Button, IconButton, Box, TextField,
    Checkbox, FormControlLabel, FormControl, Select, MenuItem,
    Dialog,
    DialogTitle,
    DialogContent,
    DialogActions,
} from "@mui/material";
import AddCircleOutlineIcon from "@mui/icons-material/AddCircleOutline";
import PeopleOutlineIcon from "@mui/icons-material/PeopleOutline";
import axios from "axios";
import { useLocation } from "react-router-dom";
import { getCookie } from "./utils/csrf";
import GridLoader from 'react-spinners/GridLoader';

import TransactionFlow from "./TransactionFlow";
import AddPatientEncounterForm from "./AddPatientEncounterForm";

function DocumentAI({ view, setView }) {

    const [patients, setPatients] = useState([]);
    const [loading, setLoading] = useState(false); // <-- spinner state

    const [open, setOpen] = useState(false);
    const [pendingParams, setPendingParams] = useState(null);

    const location = useLocation();

    const [hospitalId, setHospitalId] = useState(location.state?.hospitalId || "");
    const [userType, setUserType] = useState(location.state?.userType || "");
    const [userEmail, setUserEmail] = useState(location.state?.userEmail || "");

    const [hospitals, setHospitals] = useState([]);

    const [searchRecord, setSearchRecord] = useState("");
    const [searchHospital, setSearchHospital] = useState("");

    const processing_status = ["error", "warning", "success"]

    const [searchParams, setSearchParams] = useState({
        ipno: "",
        hospital: hospitalId ? Number(hospitalId) : null
    });

    const apiUrl = process.env.REACT_APP_BRIDGE_API_URL;

    const fetchPatients = async () => {
        const csrfToken = getCookie("csrftoken");
        setLoading(true);
        try {
            const res = await axios.get(`${apiUrl}/encounters/`, {
                params: searchParams,
                headers: {
                    "X-CSRFToken": csrfToken,
                },
                withCredentials: true,

            });
            setPatients(res.data);
        } catch (error) {
            console.error("Error fetching patients:", error);
        } finally {
            setLoading(false);
        }
    };

    const handleChange = async (event) => {

        const searchVal = event.target.value
        const searchField = event.target.name

        if (searchField === "record_ipno") {
            setSearchParams((prev) => ({
                ...prev,
                ipno: searchVal,
            }));
            setSearchRecord(searchVal)
        } else {
            setSearchParams((prev) => ({
                ...prev,
                hospital: searchVal ? Number(searchVal) : null,
            }));
            setSearchHospital(searchVal)
        }
    };

    const fetchHospitals = async () => {
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

    useEffect(() => {

        const runSearch = async () => {
            const csrfToken = getCookie("csrftoken");
            setLoading(true);
            try {
                const res = await axios.get(`${apiUrl}/encounters/`, {
                    params: searchParams,
                    headers: { "X-CSRFToken": csrfToken },
                    withCredentials: true,

                });
                setPatients(res.data);
            } catch (error) {
                console.error("Error fetching patients:", error);
            } finally {
                setLoading(false);
            }
        }

        runSearch();

    }, [searchParams]);

    useEffect(() => {
        if (view.mode === "list") {
            fetchPatients();
            fetchHospitals();
        }
    }, [view]);

    const handleCancel = () => setOpen(false);

    const handleCheckboxChange = async (event) => {

        let params = {
            is_archived: event.target.checked,
            encounter_id: event.target.name
        }
        setPendingParams(params);
        setOpen(true);
    };

    const handleConfirm = async () => {        

        if (pendingParams) {

            const csrfToken = getCookie("csrftoken");
            try {
                const response = await axios.post(`${apiUrl}/patients/archive/`,
                    pendingParams,
                    {
                        headers: { "X-CSRFToken": csrfToken },
                        withCredentials: true,

                    });

                fetchPatients(); // re-run patient_list query                
                setPendingParams(null);
            } catch (err) {
                setOpen(false);
                console.error("Failed to update selection:", err);
            }
        }

        setOpen(false);
    };



    return (

        <div style={{ padding: 20 }}>
            {/* Menu */}
            {view.mode === "menu" && (
                <Grid container spacing={2} justifyContent="center">
                    <Grid item>
                        <IconButton
                            variant="contained"
                            onClick={() => setView({ mode: "add" })}
                            sx={{ flexDirection: "column" }}
                        >
                            <AddCircleOutlineIcon sx={{ fontSize: 120 }} color="primary" />
                            <Typography>Add Patient</Typography>
                        </IconButton>
                    </Grid>
                    <Grid item>
                        <IconButton
                            variant="outlined"
                            onClick={() => setView({ mode: "list" })}
                            sx={{ flexDirection: "column" }}
                        >
                            <PeopleOutlineIcon sx={{ fontSize: 120 }} color="secondary" />
                            <Typography>View Patients</Typography>
                        </IconButton>
                    </Grid>
                </Grid>
            )}

            {/* Transaction Flow */}
            {view.mode === "transaction" && (
                <TransactionFlow
                    patientId={view.patientId}
                    documentCode={view.documentCode}
                    onCancel={() => setView({ mode: "list" })}
                    onFinish={() => {
                        setView({ mode: "list" });
                        fetchPatients(); // refresh after commit
                    }}
                />
            )}

            {/* Loading Spinner */}
            {loading && (
                <div style={{
                    display: "flex",
                    flexDirection: "column",
                    justifyContent: "center",
                    alignItems: "center",
                    height: "60vh", // adjust depending on desired vertical centering 
                }}>
                    <GridLoader
                        color="#1976d2"   // MUI primary blue
                        size={20}
                        margin={4}
                    />
                    <p style={{ marginTop: '20px' }}>Fetching patient list, please wait...</p>
                </div>
            )}

            {/* Patient List */}
            {!loading && view.mode === "list" && (
                <Grid container spacing={2}
                    sx={{ maxWidth: 960, margin: "0 auto" }}
                    justifyContent="center"
                    alignItems="flex-start">
                    {patients.length === 0 ? (
                        <Grid
                            container
                            justifyContent="center"
                            alignItems="center"
                            style={{ minHeight: "50vh" }} // or "100vh" if you want full vertical centering
                        >
                            <Grid item xs={12} sm={8} md={6} lg={4}>
                                <Card sx={{ p: 3, textAlign: "center" }}>
                                    <Typography variant="h6" color="text.secondary">
                                        No patients found
                                    </Typography>
                                    <Button
                                        variant="contained"
                                        sx={{ mt: 2 }}
                                        onClick={() => setView({ mode: "add" })}
                                    >
                                        Add First Patient
                                    </Button>
                                </Card>
                            </Grid>
                        </Grid>
                    ) : (
                        <>

                            <Grid
                                container
                                spacing={2}
                                alignItems="center"
                                justifyContent="center"
                                sx={{ maxWidth: 960, mx: "auto", mb: 2 }}
                            >

                                <Grid item>
                                    <Typography variant="h6" align="center" sx={{ whiteSpace: "nowrap" }}>
                                        Search
                                    </Typography>
                                </Grid>
                                <Grid item sx={12} sm={5}>
                                    <TextField
                                        label="Search by Record ID"
                                        variant="outlined"
                                        name="record_ipno"
                                        //size="small"
                                        sx={{ height: "56px", width: "100%" }}
                                        value={searchRecord}
                                        onChange={(e) => handleChange(e)}
                                        fullWidth
                                    />
                                </Grid>
                                <Grid item sx={12} sm={5}>

                                    <FormControl fullWidth sx={{ minWidth: 250 }}>
                                        <Select
                                            label="Search by Hospital"
                                            labelId="hospital-label"
                                            value={userType === "DM" ? searchHospital : hospitalId}
                                            name="hospital"
                                            disabled={userType !== "DM"}
                                            onChange={(e) => handleChange(e)}
                                            fullWidth
                                            displayEmpty
                                            sx={{ "& fieldset": { legend: { width: 0 } } }} // removes empty notch
                                            renderValue={(selected) => {
                                                if (!selected) {
                                                    return <span style={{ color: "#aaa" }}>All Hospitals</span>; // placeholder style
                                                }
                                                const hospital = hospitals.find((h) => h.id === selected);
                                                return hospital ? hospital.name : "All Hospitals";
                                            }}
                                        >
                                            <MenuItem value="">All Hospitals</MenuItem>
                                            {hospitals.map((h) => (
                                                <MenuItem key={h.id} value={h.id}>
                                                    {h.name}
                                                </MenuItem>
                                            ))}
                                        </Select>
                                    </FormControl>
                                </Grid>
                            </Grid>
                            {patients.map((patient) => (
                                <Grid sx={6} sm={6} key={patient.id}>

                                    <Box sx={{ position: "relative" }}>
                                        <Card>
                                            <CardContent>
                                                <>
                                                    <Box sx={{ position: "absolute", top: 8, right: 8 }}>
                                                        <FormControlLabel label="Archive?" labelPlacement="start" control={
                                                            <Checkbox
                                                                name={patient.id}
                                                                checked={patient.is_archived}
                                                                onChange={handleCheckboxChange}
                                                                disabled={userType !== "DM"}
                                                            />

                                                        }
                                                            sx={{
                                                                "& .MuiFormControlLabel-label": {
                                                                    fontSize: 14,
                                                                },
                                                            }}

                                                        />
                                                    </Box>
                                                    <Dialog open={open} onClose={handleCancel}>
                                                        <DialogTitle>Confirm Archive</DialogTitle>
                                                        <DialogContent>
                                                            Are you sure you want to archive this record?
                                                        </DialogContent>
                                                        <DialogActions>
                                                            <Button onClick={handleCancel} color="inherit">
                                                                Cancel
                                                            </Button>
                                                            <Button onClick={handleConfirm} color="error" variant="contained">
                                                                Archive
                                                            </Button>
                                                        </DialogActions>
                                                    </Dialog>
                                                </>


                                                <Typography variant="h6">
                                                    IP/No: {patient.record_ipno}
                                                </Typography>
                                                <Typography variant="body1">
                                                    Hospital: {patient.hospital_name}
                                                </Typography>
                                                <Typography variant="body2" color="text.secondary">
                                                    Admission: {patient.admission_date || "—"} | Discharge:{" "}
                                                    {patient.discharge_date || "—"}
                                                </Typography>

                                                <Button
                                                    variant="outlined"
                                                    color={processing_status[patient.itf_stage]}
                                                    sx={{ mr: 1, mt: 1 }}
                                                    onClick={() =>
                                                        setView({ mode: "transaction", patientId: patient.id, documentCode: "ITF" })
                                                    }
                                                >
                                                    Process ITF
                                                </Button>

                                                <Button
                                                    variant="outlined"
                                                    color={processing_status[patient.nar_stage]}
                                                    sx={{ mr: 1, mt: 1 }}
                                                    onClick={() =>
                                                        setView({ mode: "transaction", patientId: patient.id, documentCode: "NAR" })
                                                    }
                                                >
                                                    Process NAR
                                                </Button>

                                                <Button
                                                    variant="outlined"
                                                    color={processing_status[patient.dsc_stage]}
                                                    sx={{ mr: 1, mt: 1 }}
                                                    onClick={() =>
                                                        setView({ mode: "transaction", patientId: patient.id, documentCode: "DSC" })
                                                    }
                                                >
                                                    Process DSC
                                                </Button>

                                            </CardContent>
                                        </Card>
                                    </Box>
                                </Grid>

                            ))}

                            <Grid item xs={12}>
                                <Box sx={{ textAlign: "center", mt: 3 }}>
                                    <Typography variant="body2" color="text.secondary">
                                        Can't find the patient you're looking for?
                                    </Typography>
                                    <MuiLink
                                        component="button"
                                        variant="body2"
                                        sx={{ mt: 1 }}
                                        onClick={() => setView({ mode: "add" })}   // 👈 open AddPatientForm
                                    >
                                        Add a new patient
                                    </MuiLink>
                                </Box>
                            </Grid>



                        </>
                    )}
                </Grid>

            )}

            {/* Add Patient Form placeholder */}
            {view.mode === "add" &&
                <Grid
                    container
                    justifyContent="center"
                    alignItems="center"
                    sx={{ minHeight: "40vh" }}
                >
                    <Grid item xs={12} sm={10} md={8} lg={6}>
                        <AddPatientEncounterForm
                            hospital_id={hospitalId}
                            userType={userType}
                            userEmail={userEmail}
                            onBack={() => setView({ mode: "list" })} />
                    </Grid>
                </Grid>
            }
        </div>
    );
}

export default DocumentAI;