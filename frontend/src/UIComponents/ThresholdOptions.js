import React, { useState } from 'react';
import {
  Box,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
} from '@mui/material';

function ThresholdOptionsDropdown({ value, name, label, onChange }) {
  
  const threshModes = [
    { value: '1', label: 'Extremely Low' },
    { value: '2', label: 'Very Low' },
    { value: '3', label: 'Low' },
    { value: '4', label: 'Neutral' },
    { value: '5', label: 'High' },
    { value: '6', label: 'Very High' },
  ];
  
  return (
    <Box sx={{ mt: 4, minWidth: 200 }}>
      <FormControl fullWidth>
        <InputLabel>{label}</InputLabel>
        <Select
         value={value}
         name={name}
         label={label}
         onChange={onChange}
        >
          {threshModes.map((mode) => (
            <MenuItem key={mode.value} value={mode.value}>
              {mode.label}
            </MenuItem>
          ))}
        </Select>
      </FormControl>
    </Box>
  );
}

export default ThresholdOptionsDropdown;