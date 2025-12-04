import React, { useEffect, useState } from 'react';
import axios from 'axios';
import ImageCanvasOCR from './ImageCanvasOCR';
import GridLoader from 'react-spinners/GridLoader';
import { Button, Box, Typography, Stack } from '@mui/material';
import { useNavigate, useLocation } from 'react-router-dom';
import { getCookie } from "../utils/csrf";
import Notification from '../UIComponents/Notification';


function VerifyDataPage({ transactionId, onNext, onBack, onCancel }) {

    const appUrl = process.env.REACT_APP_BRIDGE_URL;
    const apiUrl = process.env.REACT_APP_BRIDGE_API_URL;

    const [hospital, setHospital] = useState(null);
    const [documentType, setDocumentType] = useState(null);
    const [recordIp, setRecordIp] = useState(null);
    const [pdfId, setPdfId] = useState(null);
    const [taskId, setTaskId] = useState(null);
    const cancelRef = React.useRef(false);

    const [pages, setPages] = useState([]);
    const [currentIndex, setCurrentIndex] = useState(0);
    const [loading, setLoading] = useState(true);
    const [savedData, setSavedData] = useState(null);
    const navigate = useNavigate();
    const hasRunRef = { current: false };
    const [isDirty, setIsDirty] = useState(false);
    const [notification, setNotification] = useState({
        open: false,
        message: "",
        severity: "info",
    });

    const [seconds, setSeconds] = useState(0);
    const [viewedPages, setViewedPages] = useState(new Set());

    const waitForGroupTask = async (taskId, retries = 90, delay = 2000) => {
        const csrfToken = getCookie("csrftoken");

        for (let i = 0; i < retries; i++) {

            if (cancelRef.current) {
                console.warn("Polling stopped manually.");
                return false;  // 👈 stop polling gracefully
            }

            const res = await axios.get(`${apiUrl}/group-task-status/${taskId}`, {
                headers: {
                    "X-CSRFToken": csrfToken,
                },
                withCredentials: true
            });
            console.log('Group task status:', res.data.status);

            if (res.data.status === "SUCCESS") {
                return true;
            }
            if (res.data.status === "FAILURE") {
                const message = res.data.error || {};
                console.error(`Group task failed: ${message}`);
                throw new Error(message || "Unknown task error");
            }
            await new Promise((resolve) => setTimeout(resolve, delay));
        }
        throw new Error("Group task timed out");
    };

    const waitForTemplateSearchTask = async (taskId, retries = 90, delay = 2000) => {
        const csrfToken = getCookie("csrftoken");

        for (let i = 0; i < retries; i++) {

            if (cancelRef.current) {
                console.warn("Polling stopped manually.");
                return false;  // 👈 stop polling gracefully
            }

            const res = await axios.get(`${apiUrl}/template-match-task-status/${taskId}`, {
                headers: {
                    "X-CSRFToken": csrfToken,
                },
                withCredentials: true
            });
            console.log('Template search task status:', res.data.status);

            if (res.data.status === "SUCCESS") {
                return res.data.result;
            }
            if (res.data.status === "FAILURE") {
                const message = res.data.error || {};
                console.error(`Template search task failed: ${message}`);
                throw new Error(message || "Unknown task error");
            }
            await new Promise((resolve) => setTimeout(resolve, delay));
        }
        throw new Error("Template search task timed out");
    };

    const waitForDataExtractTask = async (taskId, retries = 30, delay = 2000) => {
        const csrfToken = getCookie("csrftoken");

        for (let i = 0; i < retries; i++) {

            if (cancelRef.current) {
                console.warn("Polling stopped manually.");
                return false;  // 👈 stop polling gracefully
            }

            const res = await axios.get(`${apiUrl}/task-status/${taskId}`, {
                headers: {
                    "X-CSRFToken": csrfToken,
                },
                withCredentials: true
            });
            console.log('Data extraction task status:', res.data.status);

            if (res.data.status === "SUCCESS") {
                return true;
            }
            if (res.data.status === "FAILURE") {
                const message = res.data.error || {};
                console.error(`Data extraction task failed: ${message}`);
                throw new Error(message || "Unknown task error");
            }
            await new Promise((resolve) => setTimeout(resolve, delay));
        }
        throw new Error("Data extraction task timed out");
    };

    const waitForTask = async (taskId, retries = 20, delay = 3000) => {
        const csrfToken = getCookie("csrftoken");

        for (let i = 0; i < retries; i++) {

            if (cancelRef.current) {
                console.warn("Polling stopped manually.");
                return false;  // 👈 stop polling gracefully
            }

            const res = await axios.get(`${apiUrl}/task-status/${taskId}`, {
                headers: {
                    "X-CSRFToken": csrfToken,
                },
                withCredentials: true
            });

            let call_result = res.data
            console.log('Page save task status:', call_result.status);

            if (call_result.status === "SUCCESS") {
                setSavedData(call_result.savedData)
                return true;
            }
            if (call_result.status === "FAILURE") {
                const message = call_result.error || {};
                console.error(`Page save task failed: ${message}`);
                throw new Error(message || "Unknown task error");
            }
            await new Promise((resolve) => setTimeout(resolve, delay));
        }
        throw new Error("Page save task timed out");
    };


    useEffect(() => {

        if (!transactionId) return;

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
        if (!pages.length || pages.length === 0) return;

        if (pages.length > 0) {
            setLoading(true); // ✅ now triggers only when currentIndex changes
        }

        setViewedPages(prevViewed => {
            if (prevViewed.has(currentIndex)) {
                return prevViewed; // No update needed
            }
            const newViewed = new Set(prevViewed);
            newViewed.add(currentIndex);
            setIsDirty(false);
            return newViewed;
        });

    }, [currentIndex, pages.length]);

    const cancelActiveTasks = async () => {
        if (!taskId) return;
        const csrfToken = getCookie("csrftoken");
        try {
            await axios.post(
                `${apiUrl}/tasks/${taskId}/revoke/`,
                {},
                {
                    headers: { "X-CSRFToken": csrfToken },
                    withCredentials: true
                }
            );
            console.log("Celery tasks revoked for task", taskId);
        } catch (err) {
            console.error("Failed to cancel Celery tasks:", err);
        }
    };




    useEffect(() => {

        if (!pdfId) return;

        if (hasRunRef.current) return; // already ran
        hasRunRef.current = true;

        setSeconds(0);
        const startTime = Date.now(); // 👈 capture start timestamp

        const timer = setInterval(() => {
            setSeconds((prev) => prev + 1);
        }, 1000);

        const fetchPages = async () => {

            try {
                const csrfToken = getCookie("csrftoken");
                const postData = {
                    pdf_id: pdfId,
                    hospital_name: hospital,
                    transaction_id: transactionId,
                };

                if (cancelRef.current) {
                    console.warn("Cancelled before running template search");
                    return;
                }

                const result = await axios.post(`${apiUrl}/pages/template/`,
                    postData,
                    {
                        headers: {
                            "X-CSRFToken": csrfToken,
                        },
                        withCredentials: true
                    } // Send cookies/session
                )


                const findTemplateTaskId = result.data.task_id;
                setTaskId(findTemplateTaskId); 
                console.log("Template find task id: ", findTemplateTaskId);
                console.log("Template find task message: ", result.data.message);
                const bestTemplateByPage = await waitForTemplateSearchTask(findTemplateTaskId);

                if (cancelRef.current) {
                    console.warn("Cancelled before running alignment step");
                    return;
                }

                try {
                    const resultAlign = await axios.post(
                        `${apiUrl}/pages/align/`,
                        {
                            pdf_id: pdfId,
                            hospital_name: hospital,
                            matches: bestTemplateByPage,
                            transaction_id: transactionId,
                        },
                        {
                            headers: {
                                "X-CSRFToken": csrfToken,
                            },
                            withCredentials: true
                        }

                    );

                    const alignTaskId = resultAlign.data.task_id;
                    setTaskId(alignTaskId); 
                    console.log("Registration task id: ", alignTaskId);
                    console.log("Registration task message: ", resultAlign.data.message);
                    const alignTaskFinished = await waitForGroupTask(alignTaskId);

                    if (cancelRef.current) {
                        console.warn("Cancelled before running extraction step");
                        return;
                    }

                    if (alignTaskFinished) {
                        try {
                            const resultExtract = await axios.post(
                                `${apiUrl}/extract_ai/`,
                                {
                                    pdf_id: pdfId,
                                    transaction_id: transactionId,
                                },
                                {
                                    headers: {
                                        "X-CSRFToken": csrfToken,
                                    },
                                    withCredentials: true
                                }

                            );
                            const extractTaskId = resultExtract.data.task_id;
                            setTaskId(extractTaskId); 
                            console.log("Data extraction task id: ", extractTaskId);
                            console.log("Data extraction task message: ", resultExtract.data.message);
                            const extractTaskFinished = await waitForDataExtractTask(extractTaskId);

                            if (cancelRef.current) {
                                console.warn("Cancelled before running data upload step");
                                return;
                            }

                            if (extractTaskFinished) {

                                const elapsed = Math.floor((Date.now() - startTime) / 1000);
                                try {
                                    const transactionResource = await axios.post(`${apiUrl}/inference-time/${pdfId}/`,
                                        {
                                            inference_time: elapsed,
                                            transaction_id: transactionId,
                                        }, {
                                        headers: {
                                            "X-CSRFToken": csrfToken,
                                        },
                                        withCredentials: true
                                    });

                                    console.log(transactionResource.data.message)

                                } catch (err) {
                                    console.error("Failed to save inference time:", err);
                                }



                                try {
                                    const resultCanvas = await axios.post(
                                        `${apiUrl}/upload_ai/`,
                                        {
                                            pdf_id: pdfId,
                                            transaction_id: transactionId,
                                        },
                                        {
                                            headers: {
                                                "X-CSRFToken": csrfToken,
                                            },
                                            withCredentials: true
                                        }

                                    );
                                    setPages(resultCanvas.data)
                                } catch (err_canvas) {
                                    console.error(err_canvas);
                                }
                            }

                        } catch (err_extract) {
                            console.error(err_extract);
                        }
                    }
                } catch (err_align) {
                    console.error(err_align);
                }

            } catch (error) {
                console.error(error);
            }

        }

        fetchPages();

        return () => {
            clearInterval(timer); // cleanup on unmount
        }

    }, [pdfId]);

    const goToNextPage = () => {
        if (currentIndex < pages.length - 1) {
            setCurrentIndex(currentIndex + 1);
        }
    };

    const goToPreviousPage = () => {
        if (currentIndex > 0) {
            setCurrentIndex(currentIndex - 1);
        }
    };

    const handleSaveData = async () => {

        try {
            const csrfToken = getCookie("csrftoken");
            const postData = {
                page_id: pages[currentIndex].id,
                field_data: pages[currentIndex].field_params,
                hospital_name: hospital
            };

            const result = await axios.post(`${apiUrl}/pages/save/`,
                postData,
                {
                    headers: {
                        "X-CSRFToken": csrfToken,
                    },
                    withCredentials: true
                }
            )

            const alignTaskId = result.data.task_id;
            console.log("Save page task id: ", alignTaskId);
            console.log("Save page task message: ", result.data.message);
            const taskFinished = await waitForTask(alignTaskId);

            if (taskFinished) {
                await axios.get(`${apiUrl}/task-status/${alignTaskId}`, {
                    headers: {
                        "X-CSRFToken": csrfToken,
                    },
                    withCredentials: true
                });

                setNotification({
                    open: true,
                    message: "Page data edit successfully saved",
                    severity: "success",
                });

                setIsDirty(false);
            }
        } catch (err) {
            console.error(err);
        }
    };


    const handleFieldUpdate = (id, value) => {

        const updatedPages = [...pages];
        updatedPages[currentIndex].field_params = updatedPages[currentIndex].field_params.map(f =>
            f.id === id ? { ...f, value } : f
        );
        setPages(updatedPages);

        // mark page data as changed
        setIsDirty(true);
    };

    return (
        <div>
            {pages.length > 0 && pages[currentIndex] && pages[currentIndex].aligned_image && pages[currentIndex].field_params ? (
                <>

                    <Box display="flex" flexDirection="column" alignItems="center" mt={4}>

                        <Typography variant="h4" mt={2}>
                            Form ID: {pages[currentIndex].form_id}
                        </Typography>

                        <Typography variant="h5" mt={2}>
                            Page {currentIndex + 1} of {pages.length}
                        </Typography>


                        <ImageCanvasOCR
                            imageUrl={pages[currentIndex].aligned_image}
                            formData={pages[currentIndex].field_params}
                            width={pages[currentIndex].width}
                            height={pages[currentIndex].height}
                            setLoading={setLoading}
                            onFieldUpdate={handleFieldUpdate}
                        />

                        <Box mt={2} mb={4}>
                            <Button
                                onClick={goToPreviousPage}
                                disabled={currentIndex === 0}
                                variant="outlined"
                                sx={{ mr: 1 }}
                            >
                                ← Prev Page
                            </Button>

                            <Button
                                onClick={goToNextPage}
                                disabled={currentIndex === pages.length - 1}
                                variant="outlined"
                                sx={{ mr: 2 }}
                            >
                                Next Page →
                            </Button>
                            {pages[currentIndex]?.field_params?.length > 0 && (
                                <Button onClick={handleSaveData}
                                    sx={{ mr: 2 }}
                                    variant="contained"
                                    color="secondary"
                                    disabled={!isDirty} // ✅ only enabled if handleFieldUpdate was called
                                >
                                    Save Page Data
                                </Button>
                            )}

                            <Notification
                                open={notification.open}
                                onClose={() => setNotification({ ...notification, open: false })}
                                message={notification.message}
                                severity={notification.severity}
                            />

                            <Stack>
                                <Box sx={{ display: "flex", justifyContent: "center", gap: 2, mt: 4 }}>
                                    <Button variant="outlined" color="error" onClick={
                                        async () => {
                                            cancelRef.current = true;    
                                            await cancelActiveTasks();
                                            onCancel(); 
                                        }}>
                                        Cancel
                                    </Button>

                                    <Button variant="outlined" color="error" onClick={
                                        async () => {
                                            cancelRef.current = true;    
                                            await cancelActiveTasks();
                                            onBack();
                                        }}>
                                        Back
                                    </Button>

                                    <Button variant="contained"
                                        onClick={onNext}
                                        disabled={(pages.length === 0) || (viewedPages.size !== pages.length)} // 👈 enable only when step is complete
                                    >
                                        Next
                                    </Button>
                                </Box>
                            </Stack>
                        </Box>
                    </Box>
                </>
            ) : (
                <div style={{ textAlign: 'center', marginTop: '40px' }}>
                    <GridLoader
                        color="#1976d2"   // MUI primary blue
                        size={20}
                        margin={4}
                    />
                    <p style={{ marginTop: '20px' }}>Loading inference...{seconds}s</p>
                    <Stack>
                        <Box sx={{ display: "flex", justifyContent: "center", gap: 2, mt: 4 }}>
                            <Button variant="outlined" color="error" onClick={
                                async () => {
                                    cancelRef.current = true;    
                                    await cancelActiveTasks();
                                    onCancel(); 
                                }}>
                                Cancel
                            </Button>

                            <Button variant="outlined" color="error" onClick={                                
                                async () => {
                                    cancelRef.current = true;    
                                    await cancelActiveTasks();
                                    onBack();
                                }}>
                                Back
                            </Button>

                            <Button variant="contained"
                                onClick={onNext}
                                disabled={(pages.length === 0) || (viewedPages.size !== pages.length)} // 👈 enable only when step is complete
                            >
                                Next
                            </Button>
                        </Box>
                    </Stack>
                </div>
            )}
        </div>
    );
}

export default VerifyDataPage;