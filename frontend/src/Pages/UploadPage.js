import { useNavigate } from 'react-router-dom';
import React, { useState, useEffect } from 'react';
import GridLoader from 'react-spinners/GridLoader';

import {
    Container,
    Typography,
    Stack,
    Button,
    Box
} from '@mui/material';


import axios from 'axios';
import { getCookie } from "../utils/csrf";
import { useLocation } from "react-router-dom";


function UploadPage({ transactionId, onNext, onCancel }) {

    const apiUrl = process.env.REACT_APP_BRIDGE_API_URL;

    axios.defaults.withCredentials = true;

    const ALLOWED_TYPES = ['application/pdf'];
    const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10MB

    const [file, setFile] = useState(null);
    const [uploadMsg, setUploadMsg] = useState("");


    const [pdfId, setPdfId] = useState(null);
    const [loading, setLoading] = useState(false);

    const [hospital, setHospital] = useState(null);
    const [documentType, setDocumentType] = useState(null);
    const [recordIp, setRecordIp] = useState(null);

    const [isComplete, setIsComplete] = useState(false);

    const location = useLocation();

    const [userEmail, setUserEmail] = useState(location.state?.userEmail || "");

    const navigate = useNavigate();

    const waitForTask = async (taskId, retries = 10, delay = 2000) => {
        for (let i = 0; i < retries; i++) {
            const res = await axios.get(`${apiUrl}/task-status/${taskId}`);
            console.log('Upload task status:', res.data.status);

            if (res.data.status === "SUCCESS") {
                return true;
            }
            if (res.data.status === "FAILURE") {
                console.error('Upload task failed:', res.data.error);
                throw new Error('Upload task failed');
            }
            await new Promise((resolve) => setTimeout(resolve, delay));
        }
        throw new Error("Upload task timed out");
    };


    const handleSubmit = async (e) => {
        e.preventDefault();
        setUploadMsg("");
        setLoading(true);

        if (!file) {
            setUploadMsg("No file selected");
            setLoading(false);
            return;
        }

        if (!ALLOWED_TYPES.includes(file.type)) {
            setUploadMsg("Invalid file type. Only PDF allowed.");
            setLoading(false);
            return;
        }

        if (file.size > MAX_FILE_SIZE) {
            setUploadMsg("File too large. Max 10MB allowed.");
            setLoading(false);
            return;
        }

        const formData = new FormData();

        formData.append("file", file);
        formData.append("transactionId", transactionId);    
        formData.append("userEmail", userEmail);   

        try {
            const csrfToken = getCookie("csrftoken");
            const result = await axios.post(
                `${apiUrl}/upload_pdf/`,
                formData,
                {
                    headers: {
                        "X-CSRFToken": csrfToken,
                    },
                    withCredentials: true //the browser will NOT send cookies by default.
                });


            const taskId = result.data.task_id;
            const taskFinished = await waitForTask(taskId);

            try {
                if (taskFinished) {
                    const pdfId = result.data.pdf_id;
                    setPdfId(pdfId);
                }
            } catch (error) {
                console.error("Upload error", error);
                setLoading(false);
            }

        } catch (err) {
            setUploadMsg(
                err.response?.data?.error || "Upload failed. Check console for details."
            );
            console.error("Error: ", err);
            setLoading(false);
        }
    };

    useEffect(() => {

        if(!transactionId) return;

        const fetchData = async () => {
            const csrfToken = getCookie("csrftoken");
            try {
                const transactionResource = await axios.post(`${apiUrl}/transactions/details/${transactionId}/`,
                    {}, {
                    headers: {
                        "X-CSRFToken": csrfToken,
                    },
                    withCredentials: true
                });

                setHospital(transactionResource.data.hospital)
                setDocumentType(transactionResource.data.document)
                setRecordIp(transactionResource.data.record)

            } catch (err) {
                console.error("Failed to fetch form data:", err);
            }
        }

        fetchData();

        let intervalId;

        if (pdfId) {
            intervalId = setInterval(async () => {
                const csrfToken = getCookie("csrftoken");
                try {
                    const response = await axios.get(
                        `${apiUrl}/pdf_status/${pdfId}/`,
                        {
                            headers: {
                                "X-CSRFToken": csrfToken,
                                "Content-Type": "multipart/form-data",
                            },
                            withCredentials: true //the browser will NOT send cookies by default.
                        });
                    const status = response.data.status;

                    console.log(`[Polling] PDF status: ${status}`);

                    if (status === 'processing') {

                        clearInterval(intervalId);
                        setLoading(false);
                        setIsComplete(true);
                    }
                } catch (err) {
                    console.error('[Polling] Status check failed:', err);
                    clearInterval(intervalId);
                    setLoading(false);
                }
            }, 2000); // poll every 2 seconds
        }

        // Clear interval on unmount
        return () => clearInterval(intervalId);
    }, [pdfId, navigate, transactionId]);

    return (

        <Container maxWidth="sm">
            <Box component="form" onSubmit={handleSubmit} sx={{ mt: 4 }}>
                <Typography variant="h4">Upload PDF Form Step</Typography>


                <Stack spacing={2}>

                    <Typography variant="h6" display="block">Hospital: {hospital}</Typography>
                    <Typography variant="h6" display="block">Record: {recordIp}</Typography>
                    <Typography variant="h6" display="block">Form: {documentType}</Typography>


                    <Button variant="contained" component="label" sx={{ mb: 3 }}>
                        Choose PDF File
                        <input
                            type="file"
                            hidden
                            accept="application/pdf"
                            onChange={(e) => setFile(e.target.files[0])}
                        />
                    </Button>

                    {file && <Typography variant="body2" sx={{ mb: 2 }}>Selected: {file.name}</Typography>}
                    {uploadMsg && <Typography variant="body1" color="error" sx={{ mb: 3 }}>{uploadMsg}</Typography>}


                    {loading && (
                        <div style={{ textAlign: 'center', marginTop: '40px' }}>
                            <GridLoader
                                color="#1976d2"   // MUI primary blue
                                size={20}
                                margin={4}
                            />
                            <p style={{ marginTop: '20px' }}>Processing PDF, please wait...</p>
                        </div>
                    )}

                    <Button
                        type="submit"
                        variant="contained"
                        color="primary"
                    >
                        Upload PDF
                    </Button>

                </Stack>

                <Box sx={{ display: "flex", justifyContent: "center", gap: 2, mt: 4 }}>

                    <Button variant="contained" 
                    onClick={onNext} 
                    disabled={!isComplete} // 👈 enable only when step is complete
                    >
                        Next
                    </Button>
                    <Button variant="outlined" color="error" onClick={onCancel}>
                        Cancel
                    </Button>
                </Box>



            </Box>
        </Container>

    );
}

export default UploadPage;