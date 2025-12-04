import React, { useState } from 'react';
import {
  Box,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
} from '@mui/material';

function AspectRatioOptionsDropdown({ value, name, label, onChange }) {
  
  const aspectRatioSizeRanges = [
    { value: '1', label: '(Extra Strict) 0.9 and 1.1' },
    { value: '2', label: '(Strict) 0.8 and 1.2' },
    { value: '3', label: '(Default) 0.725 and 1.35' },
    { value: '4', label: '(Lax) 0.65 and 1.35' },
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
          {aspectRatioSizeRanges.map((mode) => (
            <MenuItem key={mode.value} value={mode.value}>
              {mode.label}
            </MenuItem>
          ))}
        </Select>
      </FormControl>
    </Box>
  );
}

export default AspectRatioOptionsDropdown;