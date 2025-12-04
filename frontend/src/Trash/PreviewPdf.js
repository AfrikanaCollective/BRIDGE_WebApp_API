import React, { useEffect, useState } from 'react';
import Cookies from 'js-cookie';
import axios from 'axios';
import { useLocation } from "react-router-dom";
import PreprocessImages from '../ProcessImagesPage';
import { getCookie } from "../utils/csrf";

function PreviewPdf() {

  const location = useLocation();
  const [pages, setPages] = useState([]);

  const [pdfId, setPdfId] = useState(location.state?.pdfId || "");
  const [hospitalId, setHospitalId] = useState(location.state?.hospitalId || "");
  const [userType, setUserType] = useState(location.state?.userType || "");
  const [userEmail, setUserEmail] = useState(location.state?.userEmail || "");

  //const pdfId = Cookies.get('pdfId');


  const apiUrl = process.env.REACT_APP_BRIDGE_API_URL;

  useEffect(() => {

    console.log('PDF ID:', pdfId);

    const fetchPages = async () => {
      try {

        const csrfToken = getCookie("csrftoken");

        const postData = {
          pdf_id: pdfId,
        };

        const response = await axios.post(`${apiUrl}/pages/`,
          postData,
          {
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

    if (pdfId) {
      fetchPages();
    }

  }, [pdfId]);

  return <PreprocessImages
    pages={pages}
    setPages={setPages}
    pdfId={pdfId}
    hospitalId={hospitalId}
    userType={userType}
    userEmail={userEmail}
  />

}

export default PreviewPdf;