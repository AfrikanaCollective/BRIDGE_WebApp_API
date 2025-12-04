import React, { useState } from 'react';
import {
  Box,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
} from '@mui/material';

function FiducialSizeOptionsDropdown({ value, name, label, onChange}) {
  
  const fiducialSizeRanges = [
    { value: '1', label: '(Tiny) 1200 and 4400' },
    { value: '2', label: '(Extra Small) 1500 and 4400' },
    { value: '3', label: '(Small) 1800 and 4400' },
    { value: '4', label: '(Default) 2200 and 4400' },
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
          {fiducialSizeRanges.map((mode) => (
            <MenuItem key={mode.value} value={mode.value}>
              {mode.label}
            </MenuItem>
          ))}
        </Select>
      </FormControl>
    </Box>
  );
}

export default FiducialSizeOptionsDropdown;