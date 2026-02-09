import React, { useRef, useEffect, useState } from 'react';
import { Canvas, Rect, Text, FabricImage } from 'fabric';
import { Box } from '@mui/material';
import { Dialog, DialogTitle, DialogContent, DialogActions, Button, TextField, Typography } from '@mui/material';


const ImageCanvasOCR = ({ imageUrl, formData, width = 600, height = 800, setLoading, onFieldUpdate }) => {

  const canvasRef = useRef(null);
  const fabricCanvas = useRef(null);

  const [openDialog, setOpenDialog] = useState(false);
  const [currentField, setCurrentField] = useState(null);
  const [newValue, setNewValue] = useState('');
  const [errorMessage, setErrorMessage] = useState('');
  


  // overlaying results live without reloading the image each time.

  useEffect(() => {

    if (!canvasRef.current) return;
    if (!imageUrl) return;

    const canvas = new Canvas(canvasRef.current, {
      width,
      height
    });

    fabricCanvas.current = canvas; // ✅ Store Fabric canvas instance

    const img = new Image();
    img.src = imageUrl;
    img.crossOrigin = 'use-credentials';  //'anonymous'; // This enables CORS

    img.onload = () => {
      const imgInstance = new FabricImage(img, {
        left: 0,
        top: 0,
        scaleX: width / img.width,
        scaleY: height / img.height,
        selectable: false,
      });
      canvas.backgroundImage = imgInstance;


      if (!Array.isArray(formData) || formData.length === 0) {
        console.error("formData is empty or invalid");
        if (setLoading) setLoading(false);
        canvas.renderAll();
        return;
      }

      // Draw ROIs
      formData.forEach((item) => {
        const { xmin, ymin, xmax, ymax, id, variable, roi_type, value } = item;

        if (id.includes('combined')) return;

        const rect = new Rect({
          left: xmin - 1,
          top: ymin - 1,
          width: xmax - xmin,
          height: ymax - ymin,
          fill: roi_type === 'checkbox' ? '' : 'rgba(255, 0, 0, 0.2)',
          stroke: roi_type === 'checkbox' ? (value === 0 ? '#FFA500' : '#00D100') : '#00D1D1',
          strokeWidth: 3,
          selectable: true,
          hasControls: false,
          hasBorders: false,
          objectCaching: false,
          hoverCursor: roi_type === 'checkbox' ? 'pointer' : 'default',
          lockMovementX: true,
          lockMovementY: true,
        });

        rect.set('fieldId', id);
        rect.set('roiType', roi_type);
        rect.set('currentValue', value);

        canvas.add(rect);

        // Optional: text overlay for freetext
        if (roi_type !== 'checkbox') {
          let textValue = String(value);

          if (textValue === '@') {
            textValue = '';
          }

          const text = new Text(textValue, {
            left: xmin + 5,
            top: ymin + 5,
            fontSize: 18,
            fill: 'red',
            fontWeight: 'bold',
            selectable: false,
            evented: false,
          });

          canvas.add(text);

          rect.set('linkedText', text);

          rect.on('mousedown', (opt) => {
            const e = opt.e;
            
            setCurrentField({
              rect,
              fieldId: id,
              variable, // store variable name
            });
            setNewValue(text.text);
            setErrorMessage(''); // ✅ Reset old error message
            setOpenDialog(true);
          });
        }


        canvas.renderAll();

        // Add click event listener for checkboxes
        if (roi_type === 'checkbox') {
          rect.on('mousedown', (opt) => {
            const e = opt.e;
            if (e.button !== 0) return; // Only respond to left-click

            const newValue = rect.get('currentValue') === 0 ? 1 : 0;
            rect.set('currentValue', newValue);
            rect.set('stroke', newValue === 0 ? '#FFA500' : '#00D100');
            canvas.renderAll();

            if (onFieldUpdate) {
              onFieldUpdate(id, newValue);
            }
          });
        }
      });

    }

    if (setLoading) setLoading(false);
    return () => canvas.dispose();

  }, [imageUrl, width, height]);

  const handleSave = () => {

    if (!currentField) return;

    const { rect, fieldId } = currentField;
    const twoCharFields = ["apgar", "rbs"];
    const allowsTwoChars = twoCharFields.some(key => fieldId.includes(key));
    
    if (newValue.length > 1 && !allowsTwoChars ) {
      setErrorMessage('Please enter not more than one character.');
      return;
    }

    if (newValue.length > 2 && allowsTwoChars ) {
      setErrorMessage('Please enter not more than two characters.');
      return;
    }

    
    const textObj = rect.get('linkedText');   // you set this earlier with rect.set('linkedText', text)

    textObj.set('text', newValue);
    rect.canvas.renderAll();                  // render via the Fabric canvas instance
    onFieldUpdate?.(fieldId, newValue);    
    setOpenDialog(false);
    setErrorMessage('');    
  };



  return (

    <>
    <Box
      sx={{
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        padding: 0,
        margin: 0,
        border: 'none',
      }}
    >
      <canvas
        ref={canvasRef}
        width={width}
        height={height}
        style={{ border: '1px solid #ccc' }}
      />
    </Box>

    <Dialog open={openDialog} onClose={() => setOpenDialog(false)}>
        <DialogTitle>
        Edit value for {currentField?.variable || 'Field'}
        </DialogTitle>
        <DialogContent>
          <TextField
            value={newValue}
            onChange={(e) => setNewValue(e.target.value)}
            label="Enter Value"
            fullWidth
            variant="outlined"
            margin="dense"
            sx={{ shrink: true }}
          />
          {errorMessage && (
            <Typography color="error" variant="body2">
              {errorMessage}
            </Typography>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setOpenDialog(false)}>Cancel</Button>
          <Button onClick={handleSave} color="primary" variant="contained">
            Save
          </Button>
        </DialogActions>
      </Dialog>

    </>
  );
};


export default ImageCanvasOCR;
