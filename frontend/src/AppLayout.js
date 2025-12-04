import React from "react";
import AppBar from "@mui/material/AppBar";
import Toolbar from "@mui/material/Toolbar";
import Typography from "@mui/material/Typography";
import Button from "@mui/material/Button";
import Box from "@mui/material/Box";

import MenuIcon from "@mui/icons-material/Menu";
import PersonAddIcon from "@mui/icons-material/PersonAdd";
import LogoutIcon from "@mui/icons-material/Logout";
import bridgeIcon from "./assets/BRIDGE.png";


export default function AppLayout({ user, onLogout, children, view, setView }) {
  return (
    <Box sx={{ flexGrow: 1 }}>
      <AppBar position="static" color="primary">
        <Toolbar sx={{ display: "flex", justifyContent: "space-between" }}>
          <Box sx={{ display: "flex", alignItems: "center", gap: 2 }}>
            {/* LEFT: Icon + Title */}
            <img
              src={bridgeIcon}
              alt="icon"
              style={{ width: 36, height: 36 }}   // 👈 size control
            />
            {/* Title */}
            {user && (
              <Typography variant="h6" component="div">BRIDGE</Typography>
            )}
          </Box>

          {/* CENTER: Context Links (only in list mode) */}
          {user && view && view.mode === "list" && (
            <Box sx={{ display: "flex", gap: 2 }}>
              <Button
                color="inherit"
                onClick={() => setView({ mode: "menu" })}
                startIcon={<MenuIcon />}   // 👈 adds menu icon
              >
                Patients
              </Button>
              <Button
                color="inherit"
                onClick={() => setView({ mode: "add" })}
                startIcon={<PersonAddIcon />}  // 👈 adds add-patient icon
              >
                Add Patient
              </Button>
            </Box>
          )}


          {/* RIGHT: Logout */}
          {user && (
            <Button color="inherit" onClick={onLogout} startIcon={<LogoutIcon />}>
              Logout
            </Button>
          )}
        </Toolbar>
      </AppBar>

      {/* Page content */}
      <Box sx={{ p: 3 }}>{children}</Box>
    </Box>
  );
}