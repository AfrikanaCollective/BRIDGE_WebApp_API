
import React, { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button, Box, Typography, Stack } from '@mui/material';
import GridLoader from 'react-spinners/GridLoader';
import { RadioGroup, FormControlLabel, Radio, FormLabel } from '@mui/material';
import axios from 'axios';
import { getCookie } from "../utils/csrf";

import ThresholdOptionsDropdown from '../UIComponents/ThresholdOptions';
import FiducialSizeOptionsDropdown from '../UIComponents/FiducialSizeOptions';
import AspectRatioOptionsDropdown from '../UIComponents/AspectRatioOptions';

function ProcessImagesPages({ transactionId, onNext, onBack, onCancel }) {

  const apiUrl = process.env.REACT_APP_BRIDGE_API_URL;

  const lastImageVersionPageId = useRef(null);

  const didRun = useRef(false);

  const [hospital, setHospital] = useState(null);
  const [documentType, setDocumentType] = useState(null);
  const [recordIp, setRecordIp] = useState(null);
  const [pdfId, setPdfId] = useState(null);
  const templateRef = React.useRef(null);

  const [pages, setPages] = useState([]);
  const [currentPageIndex, setCurrentPageIndex] = useState(0);
  const navigate = useNavigate();


  const currentPage = useMemo(() => {
    if (pages.length > 0 && currentPageIndex < pages.length) {
      return pages[currentPageIndex];
    }
    return null;
  }, [pages, currentPageIndex]);

  const defaultParams = {
    aspect_use: "3",
    fiducial_use: "4",
    filter_use: "1",
    gray_use: "2",
    threshold_use: "4"
  }

  const [params, setParams] = useState(defaultParams);
  const [errMessage, setErrMessage] = useState(null);
  const [successMessage, setSuccessMessage] = useState(null);
  const [saveStatus, setSaveStatus] = useState(null); // 'success' | 'error' | null
  const [taskStatus, setTaskStatus] = useState(null); // null | 'pending' | 'success' | 'error'

  const [zoomLevel, setZoomLevel] = useState(1); // 1 = 100%
  const containerRef = useRef(null);
  //const pdfId = Cookies.get('pdfId');
  const hasLoadedParamsRef = useRef({});
  const [imageVersion, setImageVersion] = useState(Date.now());
  const [viewedPages, setViewedPages] = useState(new Set());

  const allPagesViewed = pages.length > 0 && viewedPages.size === pages.length;


  const waitForTask = async (taskId, retries = 20, delay = 3000) => {
    for (let i = 0; i < retries; i++) {
      const res = await axios.get(`${apiUrl}/task-status/${taskId}`);
      console.log('Task status:', res.data.status);

      if (res.data.status === "SUCCESS") {
        return true;
      }
      if (res.data.status === "FAILURE") {
        const message = res.data.error || {};
        console.error(`Task failed: ${message}`);
        setErrMessage(message);
        setSaveStatus('error');
        setTimeout(() => setSaveStatus(null), 2000);

        throw new Error(message || "Unknown task error");
      }
      await new Promise((resolve) => setTimeout(resolve, delay));
    }
    throw new Error("Task timed out");
  };


  const handlePrev = () => {
    if (currentPageIndex > 0) {
      const newIndex = currentPageIndex - 1;
      hasLoadedParamsRef.current[pages[newIndex].id] = false;
      setCurrentPageIndex(newIndex);
    }
  };

  const handleNext = () => {
    if (currentPageIndex < pages.length - 1) {
      const newIndex = currentPageIndex + 1;
      hasLoadedParamsRef.current[pages[newIndex].id] = false;
      setCurrentPageIndex(newIndex);
    }
  };

  const handleZoomIn = () => {
    setZoomLevel((z) => Math.min(z + 0.1, 3)); // max 300%
  };

  const handleZoomOut = () => {
    setZoomLevel((z) => Math.max(z - 0.1, 0.5)); // min 50%
  };

  const handleKeyDown = useCallback((e) => {
    if (e.key === 'ArrowRight') handleNext();
    if (e.key === 'ArrowLeft') handlePrev();
    if (e.key === '+') handleZoomIn();
    if (e.key === '-') handleZoomOut();
  }, [handleNext, handlePrev]);

  const handleResetZoom = () => {
    setZoomLevel(1);
  };

  const handleWheel = useCallback((e) => {
    e.preventDefault();
    if (e.deltaY < 0) {
      handleZoomIn();
    } else if (e.deltaY > 0) {
      handleZoomOut();
    }
  }, []);


  const handleEvent = (e) => {
    const { name, type, value, checked } = e.target;
    const newValue = type === 'checkbox' ? checked : value;

    if (name === "template_version"){
      const csrfToken = getCookie("csrftoken");
      templateRef.current = value
      try {
          const transactionResource = axios.post(`${apiUrl}/template-version/${pdfId}/`,
              {
                template_version: value,
              }, {
              headers: {
                  "X-CSRFToken": csrfToken,
              },
              withCredentials: true
          });

      } catch (err) {
          console.error("Failed to save template version:", err);
      }
    }

    

    setParams((prev) => ({
      ...prev,
      [name]: type === 'number' ? Number(newValue) : newValue,
    }));
  };

  const updatePage = (updatedPage) => {
    setPages((prevPages) => {
      const newPages = prevPages.map((page, index) =>
        index === currentPageIndex ? updatedPage : page
      )
      return newPages;

    });
  };


  const sendParams = async () => {

    if (!currentPage) return;

    try {

      const postData = {
        user_params: params,
        page_id: currentPage.id,
      };

      const csrfToken = getCookie("csrftoken");

      const response_params = await axios.post(`${apiUrl}/pages/update-params/`,
        postData,
        {
          headers: { "X-CSRFToken": csrfToken },
          withCredentials: true
        } // Send cookies/session
      ).then((response) => {
        const updatedPage = response.data.updatedPage;
        updatePage(updatedPage);        // ✅ triggers re-render
        setParams(updatedPage.processing_params);

        console.log('Server response:', response.data["message"]);

        setSuccessMessage('Preprocessing parameters updated')
        setSaveStatus('success');
        setTimeout(() => setSaveStatus(null), 2000);

      }).catch((error) => {
        setTaskStatus('error');
        console.error('Error updating params:', error);
        setSaveStatus('error');
        setErrMessage('Error updating params');
        setTimeout(() => setSaveStatus(null), 2000);
      });

      setTaskStatus('pending');

      const response_reprocess = await axios.post(`${apiUrl}/pages/reprocess/`,
        postData,
        {
          headers: {
            "X-CSRFToken": csrfToken,
          },
          withCredentials: true
        } // Send cookies/session
      );

      const taskId = response_reprocess.data.task_id;
      const taskFinished = await waitForTask(taskId);

      try {

        if (taskFinished) {
          setTaskStatus('success');
          setImageVersion(Date.now());  // 🔁 Force image reload after task done
          setSuccessMessage('Updated image loaded')
          setSaveStatus('success');
          didRun.current = false;
          setTimeout(() => setSaveStatus(null), 2000);
        }
      } catch (err) {
        setTaskStatus('error');
        console.error('Task Error:', err.message);
        setSaveStatus('error');
        setErrMessage(err.message);
        setTimeout(() => setSaveStatus(null), 2000);
      }


    } catch (error) {
      setTaskStatus('error');
      console.error(error);
    }
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
        templateRef.current = transactionResource.data.template_version

      } catch (err) {
        console.error("Failed to fetch form data:", err);
      }

    }

    fetchTransaction();

    const fetchPages = async () => {
      try {
        const csrfToken = getCookie("csrftoken");
        const postData = {
          pdf_id: pdfId,
        };

        const response = await axios.post(`${apiUrl}/pages/`, postData, {
          headers: {
            "X-CSRFToken": csrfToken,
          },
          withCredentials: true,

        });

        console.log("Fetched pages:", response.data); // ✅ debug
        setPages(response.data)
      } catch (err) {
        console.error("Errot fetching pages", err);
      }
    }

    if (!pdfId) return;

    if (pdfId && !didRun.current) {
      didRun.current = true;
      fetchPages();
    }

    if (!pages.length || pages.length === 0) return;
    if (!currentPage) return;


    const pageId = currentPage.id;
    const imageUrl = currentPage.processed_image;

    if (!pageId || !imageUrl) return;

    if (!hasLoadedParamsRef.current[pageId]) {
      setParams(currentPage.processing_params || defaultParams);
      hasLoadedParamsRef.current[pageId] = true;
    }

    if (lastImageVersionPageId.current !== pageId) {
      console.log("Triggering image version refresh...");
      setImageVersion(Date.now());
      lastImageVersionPageId.current = pageId;
    }

    setViewedPages(prevViewed => {
      if (prevViewed.has(pageId)) {
        return prevViewed; // No update needed
      }
      const newViewed = new Set(prevViewed);
      newViewed.add(pageId);
      return newViewed;
    });


    /** 
    const container = containerRef.current;
    if (container) container.addEventListener('wheel', handleWheel, { passive: false });

    window.addEventListener('keydown', handleKeyDown);

    return () => {
      if (container) container.removeEventListener('wheel', handleWheel);
      window.removeEventListener('keydown', handleKeyDown);
    };
    */
  }, [pdfId, currentPage, imageVersion, handleKeyDown, handleWheel]);




  if (!pages || pages.length === 0) {
    return <Typography>No preview images available.</Typography>;
  }

  return (
    <Box display="flex" justifyContent="center" mt={4}>

      <Box textAlign="center" mt={4}>
        {currentPage ? (
          <Box
            ref={containerRef}
            onDoubleClick={handleResetZoom}
            sx={{
              overflow: 'auto',
              display: 'inline-block',
              border: '1px solid #ccc',
              p: 1,
              backgroundColor: '#fafafa',
            }}
          >

            {taskStatus === 'pending' ? (

              <div style={{ textAlign: 'center', marginTop: '40px' }}>
                <GridLoader
                  color="#1976d2"   // MUI primary blue
                  size={20}
                  margin={4}
                />
                <p style={{ marginTop: '20px' }}>Processing image, please wait...</p>
              </div>
            ) : currentPage?.processed_image ? (
              <img
                src={`${currentPage?.processed_image}`}
                alt={`Page ${currentPage.page_number}`}
                style={{
                  border: '0.5px solid #000000',
                  transform: `scale(${zoomLevel})`,
                  transformOrigin: 'center',
                  transition: 'transform 0.2s ease-in-out',
                  maxWidth: '100%',
                  maxHeight: '80vh',
                  minWidth: '1400px',     // 👈 add this
                  minHeight: '2100px',    // 👈 add this
                }}
              />

            ) : (
              <div style={{ textAlign: 'center', marginTop: '40px' }}>
                <GridLoader color="#1976d2" size={20} margin={4} />
                <p style={{ marginTop: '20px' }}>Image not processed: Update settings.</p>
              </div>
            )}
          </Box>
        ) : (

          <div style={{ textAlign: 'center', marginTop: '40px' }}>
            <GridLoader
              color="#1976d2"   // MUI primary blue
              size={20}
              margin={4}
            />
            <p style={{ marginTop: '20px' }}>Loading image, please wait...</p>
          </div>
        )}

        <Typography variant="body1" mt={2}>
          Page {currentPageIndex + 1} of {pages.length}
        </Typography>


        <Box mt={2} mb={4}>
          <Button
            onClick={handlePrev}
            disabled={currentPageIndex === 0}
            variant="outlined"
            sx={{ mr: 1 }}
          >
            ← Prev
          </Button>

          <Button
            onClick={handleNext}
            disabled={currentPageIndex === pages.length - 1}
            variant="outlined"
            sx={{ mr: 2 }}
          >
            Next →
          </Button>

          <Button onClick={handleZoomOut} sx={{ mr: 1 }} variant="contained" color="secondary" disabled={true}>
            Zoom -
          </Button>

          <Button onClick={handleZoomIn} sx={{ mr: 1 }} variant="contained" color="secondary" disabled={true}>
            Zoom +
          </Button>

          <Button onClick={handleResetZoom} variant="outlined" disabled={true}>
            Reset Zoom
          </Button>
        </Box>

        <Stack>

          <Box sx={{ display: "flex", justifyContent: "center", gap: 2, mt: 4 }}>

            <Button variant="outlined" color="error" onClick={onCancel}>
              Cancel
            </Button>

            <Button variant="outlined" color="error" onClick={onBack}>
              Back
            </Button>

            <Button variant="contained"
              onClick={onNext}
              disabled={viewedPages.size !== pages.length || !templateRef.current} // 👈 enable only when step is complete
            >
              Next
            </Button>

          </Box>

        </Stack>
      </Box>



      {/* Crop Mode Side Panel */}
      <Box sx={{ ml: 4, minWidth: 200 }}>        

        <FormLabel component="legend" sx={{ marginTop: 3}} >Reference boxes shade</FormLabel>
        <RadioGroup
          aria-label="Reference boxes shade"
          name="gray_use"
          value={params.gray_use}
          onChange={handleEvent}
        >
          <FormControlLabel value="1" control={<Radio />} label="≥45% Black" />
          <FormControlLabel value="2" control={<Radio />} label="≥55% Black" />
          <FormControlLabel value="3" control={<Radio />} label="≥65% Black" />
        </RadioGroup>


        <FiducialSizeOptionsDropdown
          name="fiducial_use"
          label="Reference boxes size"
          value={params.fiducial_use}
          onChange={handleEvent}
        />

        <AspectRatioOptionsDropdown
          name="aspect_use"
          label="Fiducial's Aspect Ratio Range"
          value={params.aspect_use}
          onChange={handleEvent}
        />

        <FormLabel component="legend" sx={{ marginTop: 3}} >Image Filter</FormLabel>
        <RadioGroup          
          aria-label="Image Filter"
          name="filter_use"
          value={params.filter_use}
          onChange={handleEvent}
        >
          <FormControlLabel value="1" control={<Radio />} label="Default" />
          <FormControlLabel value="2" control={<Radio />} label="Dilate" />
          <FormControlLabel value="3" control={<Radio />} label="Sharpen" />
          <FormControlLabel value="4" control={<Radio />} label="Faded" />
        </RadioGroup>

        <ThresholdOptionsDropdown
          name="threshold_use"
          label="Image Contrast"
          value={params.threshold_use}
          onChange={handleEvent}
        />

        {saveStatus === 'success' && <p style={{ color: 'green' }}>{successMessage}!</p>}
        {saveStatus === 'error' && <p style={{ color: 'red' }}>{errMessage}!</p>}

        <Stack direction="column" spacing={2} sx={{ marginTop: '1rem' }}>
          <Button
            onClick={sendParams}
            variant="contained"
            color="primary"
            style={{ marginTop: '1rem', marginBottom: '1rem' }}
          >
            Update Parameters
          </Button>

          <FormLabel component="legend" >Template Version</FormLabel>
            <RadioGroup
              aria-label="Template Version"
              name="template_version"
              value={templateRef.current ?? ""}
              onChange={handleEvent}
            >
              <FormControlLabel value="ver1" control={<Radio />} label="Version 1" />
              <FormControlLabel value="ver2" control={<Radio />} label="Version 2" />
            </RadioGroup>
        </Stack>
      </Box>

    </Box>
  );
}

export default ProcessImagesPages;