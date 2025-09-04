# Mandarin3D 3D File Slicing Service - API Documentation

## Table of Contents

- [Overview](#overview)
- [Supported File Formats](#supported-file-formats)
- [API Endpoints](#api-endpoints)
  - [POST /api/slice](#post-apislice)
  - [GET /health](#get-health)
  - [GET /api/formats](#get-apiformats)
- [Request Examples](#request-examples)
- [Response Format](#response-format)
- [Error Handling](#error-handling)
- [Installation & Deployment](#installation--deployment)
- [Technical Details](#technical-details)
- [Troubleshooting](#troubleshooting)

## Overview

The Mandarin3D 3D File Slicing Service is a Flask-based microservice that processes various 3D file formats and extracts crucial manufacturing information including mass, dimensions, and volume. The service automatically converts non-STL formats to STL using advanced mesh processing libraries before analysis with SuperSlicer.

**Key Features:**
- Support for 17+ 3D file formats
- Automatic format conversion with dual-engine fallback
- Callback-based asynchronous processing
- Dimension validation and size constraints
- Mass calculation for material estimation
- Docker containerization for easy deployment

## Supported File Formats

### Native Processing
| Format | Extension | Description |
|--------|-----------|-------------|
| STL | `.stl` | Stereolithography - processed directly without conversion |

### Auto-Converted Formats
| Format | Extensions | Description | Primary Engine |
|--------|------------|-------------|----------------|
| Wavefront OBJ | `.obj` | Common 3D model format | trimesh |
| Polygon File Format | `.ply` | Stanford 3D scanning format | trimesh |
| Object File Format | `.off` | Simple 3D mesh format | trimesh |
| 3D Manufacturing | `.3mf` | Microsoft 3D printing format | trimesh |
| GL Transmission | `.gltf`, `.glb` | Khronos 3D web format | trimesh |
| COLLADA | `.dae`, `.collada` | Digital Asset Exchange | trimesh |
| X3D/VRML | `.x3d`, `.wrl`, `.vrml` | 3D web standards | trimesh |
| CAD Formats | `.step`, `.stp` | Standard for Exchange of Product Data | pymeshlab |
| CAD Formats | `.iges`, `.igs` | Initial Graphics Exchange | pymeshlab |
| Blender | `.blend` | Blender 3D files | trimesh |

**Conversion Process:**
1. **Primary**: trimesh library (fast, handles most formats)
2. **Fallback**: pymeshlab (robust, handles complex CAD formats)
3. **Mesh Repair**: Removes duplicates, fills holes, fixes degenerate faces

## API Endpoints

### POST /api/slice

Process a 3D file and return results via callback URL.

**URL:** `POST /api/slice`

**Content-Type Options:**
- `application/json` - For URL-based file processing
- `multipart/form-data` - For file uploads

#### JSON Request (File URL)

```json
{
  "file_url": "https://example.com/model.obj",
  "callback_url": "https://your-api.com/callback",
  "file_id": "optional_identifier",
  "max_dimensions": {
    "x": 300,
    "y": 300, 
    "z": 300
  }
}
```

**Parameters:**
- `file_url` (required): Direct URL to the 3D file
- `callback_url` (required): URL to receive processing results
- `file_id` (optional): Custom identifier for tracking
- `max_dimensions` (optional): Maximum allowed dimensions in mm

#### Form Data Request (File Upload)

**Form Fields:**
- `model_file` (required): The 3D file to process
- `callback_url` (required): URL to receive results
- `file_id` (optional): Custom identifier
- `max_x` (optional): Maximum X dimension in mm (default: 300)
- `max_y` (optional): Maximum Y dimension in mm (default: 300)  
- `max_z` (optional): Maximum Z dimension in mm (default: 300)

**Alternative Field Names** (for backward compatibility):
- `stl_file`, `3d_file`, `file` instead of `model_file`

#### Response

```json
{
  "message": "3D file processing started",
  "file_id": "your_identifier",
  "status": "processing",
  "original_format": "OBJ"
}
```

**Status Codes:**
- `202 Accepted` - Processing started successfully
- `400 Bad Request` - Invalid request or unsupported format
- `500 Internal Server Error` - Server error

### GET /health

Health check endpoint with service status and capabilities.

**URL:** `GET /health`

**Response:**
```json
{
  "status": "healthy",
  "version": "4.6",
  "timestamp": 1704067200.0,
  "supported_formats": [
    "STL", "OBJ", "PLY", "OFF", "3MF", "GLTF", "GLB", 
    "DAE", "X3D", "WRL", "VRML", "STEP", "STP", 
    "IGES", "IGS", "COLLADA", "BLEND"
  ]
}
```

### GET /api/formats

Detailed information about supported file formats.

**URL:** `GET /api/formats`

**Response:**
```json
{
  "supported_formats": [
    {
      "extension": "STL",
      "description": "Stereolithography", 
      "native": true
    },
    {
      "extension": "OBJ",
      "description": "Wavefront OBJ",
      "native": false
    }
  ],
  "conversion_info": {
    "primary_engine": "trimesh",
    "fallback_engine": "pymeshlab",
    "note": "Files are automatically converted to STL before slicing. Native STL files are processed directly."
  }
}
```

## Request Examples

### Process OBJ File Upload

```bash
curl -X POST http://localhost:5030/api/slice \
  -F "model_file=@chair.obj" \
  -F "callback_url=https://myapi.com/webhook" \
  -F "file_id=chair_001" \
  -F "max_x=250" \
  -F "max_y=250" \
  -F "max_z=200"
```

### Process 3MF from URL

```bash
curl -X POST http://localhost:5030/api/slice \
  -H "Content-Type: application/json" \
  -d '{
    "file_url": "https://example.com/model.3mf",
    "callback_url": "https://myapi.com/webhook",
    "file_id": "model_3mf_456",
    "max_dimensions": {"x": 300, "y": 300, "z": 300}
  }'
```

### Process STEP File

```bash
curl -X POST http://localhost:5030/api/slice \
  -F "model_file=@mechanical_part.step" \
  -F "callback_url=https://myapi.com/webhook" \
  -F "file_id=part_step_789"
```

### Check Service Health

```bash
curl -X GET http://localhost:5030/health
```

### Get Supported Formats

```bash
curl -X GET http://localhost:5030/api/formats
```

## Response Format

### Callback Payload

The service sends results to your callback URL with one of these payloads:

#### Success Response

```json
{
  "file_id": "your_identifier",
  "status": "success",
  "mass_grams": 15.5,
  "dimensions": {
    "x": 50.2,
    "y": 75.1, 
    "z": 25.0
  },
  "processing_time": 2.45,
  "slicer_time": 1.8,
  "timestamp": 1704067200.0
}
```

**Fields:**
- `file_id`: Your provided identifier
- `status`: "success"
- `mass_grams`: Calculated mass in grams (assuming PLA density 1.25 g/cm³)
- `dimensions`: Model dimensions in millimeters
- `processing_time`: Total processing time in seconds
- `slicer_time`: SuperSlicer execution time in seconds
- `timestamp`: Unix timestamp

#### Error Response - Conversion Failure

```json
{
  "file_id": "your_identifier",
  "status": "error",
  "error": "Failed to convert file to STL format",
  "processing_time": 1.2,
  "timestamp": 1704067200.0
}
```

#### Error Response - Dimension Violation

```json
{
  "file_id": "your_identifier",
  "status": "error",
  "error": "Dimension X too large. Model dimensions: 350.00x200.00x100.00mm. Max allowed: 300x300x300mm.",
  "dimensions": {
    "x": 350.0,
    "y": 200.0,
    "z": 100.0
  },
  "processing_time": 2.1,
  "timestamp": 1704067200.0
}
```

#### Error Response - Slicing Failure

```json
{
  "file_id": "your_identifier",
  "status": "error", 
  "error": "Objects could not fit on the bed",
  "processing_time": 3.2,
  "timestamp": 1704067200.0
}
```

## Error Handling

### HTTP Status Codes

| Code | Meaning | Description |
|------|---------|-------------|
| 202 | Accepted | Processing started successfully |
| 400 | Bad Request | Invalid parameters or unsupported format |
| 500 | Internal Server Error | Server-side processing error |

### Common Error Scenarios

#### Unsupported File Format
```json
{
  "error": "Unsupported file format. Supported formats: STL, OBJ, PLY, OFF, 3MF, GLTF, GLB, DAE, X3D, WRL, VRML, STEP, STP, IGES, IGS, COLLADA, BLEND"
}
```

#### Missing Required Fields
```json
{
  "error": "file_url and callback_url are required"
}
```

#### File Download Failed
```json
{
  "error": "Failed to download 3D file"
}
```

### Callback Error Types

1. **Conversion Errors**: File format couldn't be converted to STL
2. **Dimension Errors**: Model exceeds specified size limits
3. **Slicing Errors**: SuperSlicer couldn't process the file
4. **Processing Errors**: General processing failures

## Installation & Deployment

### Docker Deployment (Recommended)

1. **Build the image:**
   ```bash
   docker build -t mandarin3d-slicer .
   ```

2. **Run the container:**
   ```bash
   docker run -p 5030:5030 mandarin3d-slicer
   ```

3. **With environment variables:**
   ```bash
   docker run -p 5030:5030 \
     -e PORT=5030 \
     mandarin3d-slicer
   ```

### Local Development

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Ensure SuperSlicer binary is executable:**
   ```bash
   chmod +x slicersuper
   ```

3. **Run the application:**
   ```bash
   python app.py
   ```

### Production Deployment

The service is designed to run with Gunicorn in production:

```bash
gunicorn --bind 0.0.0.0:5030 app:app
```

### System Requirements

**Minimum:**
- Python 3.10+
- 2GB RAM
- 1GB disk space
- Linux/Unix environment (for SuperSlicer binary)

**Recommended:**
- 4GB+ RAM for large file processing
- SSD storage for temp file operations
- Multi-core CPU for faster conversion

## Technical Details

### Processing Pipeline

1. **Request Validation**: Check file format and required parameters
2. **File Acquisition**: Download from URL or save uploaded file
3. **Format Detection**: Identify file type by extension
4. **Conversion** (if needed): Convert to STL using trimesh/pymeshlab
5. **Slicing Analysis**: Run SuperSlicer to extract mass/dimensions
6. **Dimension Validation**: Check against size constraints
7. **Callback Delivery**: Send results to provided URL
8. **Cleanup**: Remove temporary files

### Conversion Engines

#### Trimesh (Primary)
- **Strengths**: Fast, handles most common formats
- **Formats**: OBJ, PLY, OFF, 3MF, GLTF, GLB, DAE, X3D, WRL, VRML, BLEND
- **Features**: Scene handling, mesh repair, efficient processing

#### PyMeshLab (Fallback)  
- **Strengths**: Robust, handles complex CAD formats
- **Formats**: STEP, STP, IGES, IGS, and fallback for failed trimesh conversions
- **Features**: Advanced mesh processing, hole filling, cleaning

### SuperSlicer Configuration

The service uses `config.ini` with optimized settings for:
- Mass calculation accuracy
- Dimension extraction
- Processing speed
- Error handling

### File Management

- **Temporary Storage**: Files stored in `tmp/` directory
- **Automatic Cleanup**: Files removed after processing
- **Unique Naming**: Timestamped filenames prevent conflicts
- **Security**: Uses `secure_filename()` for uploads

### Callback Reliability

- **Timeout**: 30-second timeout for callback requests
- **Retry Logic**: Single attempt (implement retries in your application)
- **Error Logging**: Failed callbacks logged for debugging

## Troubleshooting

### Common Issues

#### "Failed to convert file to STL format"
- **Cause**: File corruption or unsupported geometry
- **Solution**: Verify file integrity, try re-exporting from source application

#### "Dimension X too large"
- **Cause**: Model exceeds specified maximum dimensions
- **Solution**: Scale model down or increase `max_dimensions` parameters

#### "Objects could not fit on the bed"
- **Cause**: Model too large for SuperSlicer's bed configuration
- **Solution**: Check model dimensions and bed settings in `config.ini`

#### "No extrusions were generated"
- **Cause**: Model too small or incorrect units
- **Solution**: Service auto-scales by 25.4x for inch-based models

### Debug Information

Enable debug logging by checking:
1. **Application logs**: Container stdout/stderr
2. **Slicer logs**: `slicer.log`, `slicer_output.txt`, `slicer_error.txt`
3. **Temporary files**: Check `tmp/` directory for conversion artifacts

### Performance Optimization

1. **Memory**: Increase container memory for large files
2. **CPU**: Multi-core systems improve conversion speed
3. **Storage**: Use SSD for better I/O performance
4. **Network**: Ensure stable connection for URL downloads

### File Size Limits

- **Recommended**: < 100MB per file
- **Maximum**: Depends on available memory
- **Large files**: May require increased processing time

---

## Support & Contributing

For issues, feature requests, or contributions, please refer to the project repository or contact the development team.

**Version**: 4.6  
**Last Updated**: January 2024
