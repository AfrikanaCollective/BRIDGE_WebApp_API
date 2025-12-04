import React, { useState, useEffect } from "react";
import Notification from '../UIComponents/Notification';
import {
    Typography, Paper, Table, TableBody, TableCell,
    TableContainer, TableHead, TableRow, Button, Box, Stack
} from "@mui/material";
import { getCookie } from "../utils/csrf";
import axios from 'axios';

const ViewDataPage = ({ transactionId, onBack, onFinish, onCancel }) => {

    const apiUrl = process.env.REACT_APP_BRIDGE_API_URL;

    const [hospital, setHospital] = useState(null);
    const [documentType, setDocumentType] = useState(null);
    const [recordIp, setRecordIp] = useState(null);
    const [pdfId, setPdfId] = useState(null);

    const [notification, setNotification] = useState({
        open: false,
        message: "",
        severity: "info",
    });

    const [chunked, setChunked] = useState([]);
    const [formData, setFormData] = useState(null);
    const [canFinish, setCanFinish] = useState(false)

    const hasRunRef = { current: false };

    const columns = 3;

    const waitForTask = async (taskId, retries = 20, delay = 2000) => {
        const csrfToken = getCookie("csrftoken");

        for (let i = 0; i < retries; i++) {
            const res = await axios.get(`${apiUrl}/task-status/${taskId}`, {
                headers: {
                    "X-CSRFToken": csrfToken,
                },
                withCredentials: true
            });

            let call_result = res.data
            console.log('Form save to MongoDB task status:', call_result.status);

            if (call_result.status === "SUCCESS") {
                return true;
            }
            if (call_result.status === "FAILURE") {
                const message = call_result.error || {};
                console.error(`Form save to MongoDB task failed: ${message}`);
                throw new Error(message || "Form save to MongoDB unknown task error");
            }
            await new Promise((resolve) => setTimeout(resolve, delay));
        }
        throw new Error("Form save task to MongoDB timed out");
    };

    useEffect(() => {

        if (!transactionId) return;
        if (hasRunRef.current) return; // already ran
        hasRunRef.current = true;

        const fetchTransaction = async () => {
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
                setPdfId(transactionResource.data.pdf_id)

            } catch (err) {
                console.error("Failed to fetch form data:", err);
            }
        }

        fetchTransaction();

    }, [transactionId]);

    useEffect(() => {
        
        if(!pdfId) return;
        const fetchData = async () => {
            try {
                const csrfToken = getCookie("csrftoken");
                const postData = {
                    pdf_id: pdfId,
                };

                const result = await axios.post(`${apiUrl}/form-data/`,
                    postData,
                    {
                        headers: {
                            "X-CSRFToken": csrfToken,
                        },
                        withCredentials: true
                    } // Send cookies/session
                )

                const data = result.data.form_data
                //console.log("data: ", data)
                setFormData(data)
                
                const entries = Object.entries(data);
                const newChunked = [];
                for (let i = 0; i < entries.length; i += columns) {
                    newChunked.push(entries.slice(i, i + columns));
                }
                setChunked(newChunked);

            } catch (err) {
                console.error("Form fetch data error", err)
            };
        }

        fetchData();        

    }, [pdfId]);

    const handleSaveData = async () => {

        try {
            const csrfToken = getCookie("csrftoken");
            const postData = {
                pdf_id: pdfId,
                human_readable_data: formData
            };

            const result = await axios.post(`${apiUrl}/save-data/`,
                postData,
                {
                    headers: {
                        "X-CSRFToken": csrfToken,
                    },
                    withCredentials: true
                }
            )

            const alignTaskId = result.data.task_id;
            console.log("Save form data task id: ", alignTaskId);
            console.log("Save form task message: ", result.data.message);
            const taskFinished = await waitForTask(alignTaskId);

            if (taskFinished) {
                
                setNotification({
                    open: true,
                    message: "Page data successfully saved",
                    severity: "success",
                });

                setCanFinish(true);
            }
        } catch (err) {
            console.error(err);
        }
    };

    return (
        <>
            <Box
                sx={{
                    display: "flex",
                    justifyContent: "center",  // center horizontally
                }}
            >
                <Stack spacing={2}>
                <Typography variant="h5">{documentType} data of patient IP/NO: {recordIp}</Typography>
                <Typography variant="h6">{hospital}</Typography>
                <Paper sx={{ p: 3, maxWidth: 1200 }}>
                    <TableContainer>
                        <Table size="small">
                            <TableHead>
                                <TableRow>
                                    <TableCell><strong>Field</strong></TableCell>
                                    <TableCell><strong>Value</strong></TableCell>
                                    {/* Separator column */}
                                    <TableCell
                                        sx={{
                                            borderLeft: "2px solid #ccc",
                                            width: "1px",
                                            p: 0,
                                        }}
                                    />
                                    <TableCell><strong>Field</strong></TableCell>
                                    <TableCell><strong>Value</strong></TableCell>
                                    {/* Separator column */}
                                    <TableCell
                                        sx={{
                                            borderLeft: "2px solid #ccc",
                                            width: "1px",
                                            p: 0,
                                        }}
                                    />
                                    <TableCell><strong>Field</strong></TableCell>
                                    <TableCell><strong>Value</strong></TableCell>
                                </TableRow>
                            </TableHead>
                            <TableBody>
                                {chunked.map((row, rowIndex) => (
                                    <TableRow key={rowIndex}>
                                        {/* First pair */}
                                        <TableCell>{row[0]?.[0]}</TableCell>
                                        <TableCell>{row[0] ? String(row[0]?.[1]) : ""}</TableCell>

                                        {/* Separator */}
                                        <TableCell
                                            sx={{
                                                borderLeft: "2px solid #ccc",
                                                p: 0,
                                            }}
                                        />

                                        {/* Second pair (if available) */}
                                        <TableCell>{row[1]?.[0]}</TableCell>
                                        <TableCell>{row[1] ? String(row[1]?.[1]) : ""}</TableCell>

                                        {/* Separator */}
                                        <TableCell
                                            sx={{
                                                borderLeft: "2px solid #ccc",
                                                p: 0,
                                            }}
                                        />

                                        {/* Third pair (if available) */}
                                        <TableCell>{row[2]?.[0]}</TableCell>
                                        <TableCell>{row[2] ? String(row[2]?.[1]) : ""}</TableCell>

                                    </TableRow>
                                ))}
                            </TableBody>
                        </Table>
                    </TableContainer>
                </Paper>
                </Stack>
            </Box>
            <Notification
                open={notification.open}
                onClose={() => setNotification({ ...notification, open: false })}
                message={notification.message}
                severity={notification.severity}
            />

            <Stack>
                <Box sx={{ display: "flex", justifyContent: "center", gap: 2, mt: 4 }}>
                    <Button variant="outlined" color="error" onClick={onCancel}>
                        Cancel
                    </Button>

                    <Button variant="outlined" color="error" onClick={onBack}>
                        Back
                    </Button>

                    <Button variant="contained" onClick={handleSaveData}>
                        Save Data
                    </Button>

                    <Button variant="contained" onClick={onFinish} disabled={!canFinish}>
                        Finish
                    </Button>
                </Box>
            </Stack>
        </>
    );
};

export default ViewDataPage;
