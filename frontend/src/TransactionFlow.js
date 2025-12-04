// TransactionFlow.js
import React, { useState, useEffect } from "react";
import UploadPage from "./Pages/UploadPage";
import ProcessImagesPage from "./Pages/ProcessImagesPage";
import VerifyDataPage from "./Pages/VerifyDataPage";
import ViewDataPage from "./Pages/ViewDataPage";
import { getCookie } from "./utils/csrf";

import axios from "axios";


const TransactionFlow = ({ patientId, documentCode, onCancel, onFinish }) => {
  const [step, setStep] = useState(0); // Upload=0, Preprocess=1...
  const [transactionId, setTransactionId] = useState(null);

  let didRun = false;

  const apiUrl = process.env.REACT_APP_BRIDGE_API_URL;

  // Start transaction on mount
  useEffect(() => {

    const initTransaction = async () => {
      if (didRun) return;   // 👈 prevent 2nd call in dev StrictMode
      didRun = true;
      try {
        const csrfToken = getCookie("csrftoken");
        const res = await axios.post(`${apiUrl}/transactions/start/${patientId}/${documentCode}/`,
          {}, {
          headers: {
            "X-CSRFToken": csrfToken,
          },
          withCredentials: true,

        });
        setTransactionId(res.data.transaction_id);
        setStep(res.data.current_step); // 👈 resume where left off

      } catch (err) {
        console.error("Failed to start/resume transaction:", err);
        onCancel(); // fallback: bail out
      } finally {
        console.log("Successfully started/resumed transaction");
      }
    };
    initTransaction();
  }, [patientId, documentCode, onCancel]);


  const updateProgress = async (nextStep) => {
    if (!transactionId) return;
    const csrfToken = getCookie("csrftoken");
    try {
      const res = await axios.post(
        `${apiUrl}/transactions/save_step/${transactionId}/`,
        { step: nextStep }, // tell backend what stage we reached
        {
          headers: { "X-CSRFToken": csrfToken },
          withCredentials: true,
        }
      );

    } catch (err) {
      console.error("Failed to update progress:", err);
    }
  };


  const rollback = async () => {
    if (!transactionId) {
      onCancel();
      return;
    }
    const csrfToken = getCookie("csrftoken");
    try {
      await axios.post(
        `${apiUrl}/transactions/rollback/${transactionId}/`,
        {},
        {
          headers: {
            "X-CSRFToken": csrfToken,
          },
          withCredentials: true,
        }
      );
    } catch (err) {
      console.error("Failed to rollback transaction:", err);
    } finally {
      // Always return to parent view
      onCancel();
    }
  };

  const commit = async () => {
    if (!transactionId) return;
    const csrfToken = getCookie("csrftoken");
    try {
      await axios.post(
        `${apiUrl}/transactions/commit/${transactionId}/`,
        {},
        {
          headers: {
            "X-CSRFToken": csrfToken,
          },
          withCredentials: true,
        }
      );
      onFinish();
    } catch (err) {
      console.error("Failed to commit transaction:", err);
    }
  };

  return (
    <div>
      {step === 0 && <UploadPage
        transactionId={transactionId}
        onNext={async () => {
          await updateProgress(1);
          setStep(1);
        }}
        onCancel={rollback} />}
      {step === 1 && <ProcessImagesPage
        transactionId={transactionId}
        onNext={async () => {
          await updateProgress(2);
          setStep(2)
        }}
        onBack={() => setStep(0)}
        onCancel={rollback} />}
      {step === 2 && <VerifyDataPage
        transactionId={transactionId}
        onNext={async () => {
          await updateProgress(3);
          setStep(3);
        }}
        onBack={() => setStep(1)}
        onCancel={rollback} />}
      {step === 3 && (
        <ViewDataPage
          transactionId={transactionId}
          onBack={() => setStep(2)}
          onFinish={commit}
          onCancel={rollback}
        />
      )}
    </div>
  );
};

export default TransactionFlow;