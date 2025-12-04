import { useEffect, useState } from "react";
import { useParams, useNavigate, useLocation } from "react-router-dom";
import axios from "axios";
import {
  Container,
  Typography,
  Button,
  Box,
  Paper,
  CircularProgress,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
} from "@mui/material";

export default function ApproveUser() {
  const { userId } = useParams();
  const navigate = useNavigate();
  const location = useLocation();

  const [user, setUser] = useState(null);
  const [hospitals, setHospitals] = useState([]);
  const [userTypes, setUserTypes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [approving, setApproving] = useState(false);
  const [form, setForm] = useState({ hospital: "", user_type: "" });
  const token = new URLSearchParams(location.search).get("token");

  const apiUrl = process.env.REACT_APP_BRIDGE_API_URL;

  useEffect(() => {
    setApproving(false);
    const fetchData = async () => {

      try {
        const [hospitalsRes, userTypesRes] = await Promise.all([
          axios.get(`${apiUrl}/hospitals/`),
          axios.get(`${apiUrl}/user-types/`),
        ]);


        setHospitals(hospitalsRes.data);
        setUserTypes(userTypesRes.data);


        let userRes;

        if (token) {

          userRes = await axios.get(
            `${apiUrl}/users/${userId}/?token=${token}`
          );
        }
        console.log("User: ", userRes.data)

        setUser(userRes.data);

        


        setForm({
          hospital: userRes.data.hospital_id || "",
          user_type: userRes.data.user_type_id || "",
        });
      } catch (err) {
        console.error("Failed to fetch approval data:", err);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, [apiUrl, userId]);

  const handleChange = (field, value) => {
    setForm((prev) => {
      let updated = { ...prev, [field]: value };
  
      // If user_type is DM, clear hospital
      if (field === "user_type") {
        const selectedType = userTypes.find((ut) => ut.id === value);
        if (selectedType?.code === "DM") {
          updated.hospital = ""; // or null, depending on your backend
        }
      }
  
      return updated;
    });
  };
  

  const handleApprove = async () => {
    setApproving(true);
    try {
      await axios.post(
        `${apiUrl}/users/${userId}/approve/`,
        {
          token,
          hospital: form.hospital,
          user_type: form.user_type,
        },
      );
      navigate("/login");
    } catch (err) {
      console.error("Approval failed:", err);
    } finally {
      setApproving(false);
    }
  };

  if (loading) return <CircularProgress />;

  return (
    <Container maxWidth="sm" sx={{ mt: 4 }}>
      <Paper sx={{ p: 3 }}>
        <Typography variant="h5" gutterBottom>
          Approve User
        </Typography>
        {user ? (
          <>
            <Typography>Name: {user.full_name}</Typography>
            <Typography>Phone number: {user.phone}</Typography>
            <Typography>Email: {user.email}</Typography>

            <FormControl fullWidth sx={{ mt: 2 }}>
              <InputLabel id="user-type-label">User Type</InputLabel>
              <Select
                labelId="user-type-label"
                label="User Type"
                value={form.user_type}
                onChange={(e) => handleChange("user_type", e.target.value)}
              >
                {userTypes.map((ut) => (
                  <MenuItem key={ut.id} value={ut.id}>
                    {ut.description}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>

            <FormControl fullWidth sx={{ mt: 2 }}>
              <InputLabel id="hospital-label">Hospital</InputLabel>
              <Select
                labelId="hospital-label"
                label="Hospital"
                value={form.hospital}
                disabled={
                  userTypes.find((ut) => ut.id === form.user_type)?.code === "DM"
                }
                onChange={(e) => handleChange("hospital", e.target.value)}
              >
                {hospitals.map((h) => (
                  <MenuItem key={h.id} value={h.id}>
                    {h.name}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>

            

            <Box sx={{ mt: 3 }}>
              <Button
                variant="contained"
                color="success"
                onClick={handleApprove}
                disabled={
                  approving ||
                  !form.user_type ||
                  (
                    userTypes.find((ut) => ut.id === form.user_type)?.code !== "DM" &&
                    !form.hospital
                  )
                }
              >
                {approving ? "Approving..." : "Approve"}
              </Button>
            </Box>
          </>
        ) : (
          <Typography color="error">User not found</Typography>
        )}
      </Paper>
    </Container>
  );
}
