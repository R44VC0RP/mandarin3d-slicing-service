# Mandarin3D 3D File Slicing Service

A Flask-based microservice for processing various 3D file formats and extracting mass/dimension information using SuperSlicer with automatic file format conversion.

## Supported 3D File Formats

**Native:** STL (processed directly)

**Auto-converted to STL:** OBJ, PLY, OFF, 3MF, GLTF, GLB, DAE, X3D, WRL, VRML, STEP, STP, IGES, IGS, COLLADA, BLEND

*Conversion engines: trimesh (primary), pymeshlab (fallback)*

Baseurl: https://m3d-api.sevalla.app

## API Endpoints

### POST `/api/slice`

Process any supported 3D file format and return results via callback URL. Processing happens asynchronously in the background, and results are sent to your callback URL.

#### Request Option 1: JSON Request (File URL)

**Content-Type:** `application/json`

```typescript
{
  file_url: string;              // Required: HTTPS URL to 3D file
  callback_url: string;          // Required: HTTPS URL to receive results
  file_id?: string;              // Optional: Custom identifier for tracking
  file_name?: string;            // Optional: Filename with extension (if URL lacks it)
  max_dimensions?: {             // Optional: Max allowed dimensions in mm
    x: number;                   // Default: 300
    y: number;                   // Default: 300
    z: number;                   // Default: 300
  };
}
```

**Example:**
```json
{
  "file_url": "https://example.com/model.obj",
  "callback_url": "https://your-api.com/webhook/slice-complete",
  "file_id": "order_12345_part_A",
  "max_dimensions": {"x": 300, "y": 300, "z": 300}
}
```

**Validation Rules:**
- `file_url`: Must start with `http://` or `https://`, max 2048 characters
- `callback_url`: Must start with `http://` or `https://`, max 2048 characters
- `max_dimensions`: Each value must be > 0 and ≤ 10000mm
- File must be in a supported format (see Supported 3D File Formats)

---

#### Request Option 2: Form Data (Direct File Upload)

**Content-Type:** `multipart/form-data`

```typescript
{
  model_file: File;              // Required: 3D model file (max 500MB)
  callback_url: string;          // Required: HTTPS URL to receive results
  file_id?: string;              // Optional: Custom identifier for tracking
  max_x?: number;                // Optional: Max X dimension in mm (default: 300)
  max_y?: number;                // Optional: Max Y dimension in mm (default: 300)
  max_z?: number;                // Optional: Max Z dimension in mm (default: 300)
}
```

**Field Names:** Also accepts `stl_file`, `3d_file`, or `file` for backward compatibility.

**Example:**
```bash
curl -X POST https://m3d-api.sevalla.app/api/slice \
  -F "model_file=@model.obj" \
  -F "callback_url=https://your-api.com/webhook/slice-complete" \
  -F "file_id=order_12345_part_A" \
  -F "max_x=250" \
  -F "max_y=250" \
  -F "max_z=200"
```

**Validation Rules:**
- `model_file`: Max 500MB, must have valid file extension
- `callback_url`: Must start with `http://` or `https://`
- `max_x`, `max_y`, `max_z`: Must be > 0 and ≤ 10000mm

---

#### Immediate Response (202 Accepted)

Processing begins immediately in the background. You'll receive a `202 Accepted` response:

```typescript
{
  message: "3D file processing started";
  file_id: string | null;
  status: "processing";
  original_format: string;       // e.g., "OBJ", "STL", "3MF"
  request_processing_time: number; // Seconds to validate and queue request
}
```

**Example:**
```json
{
  "message": "3D file processing started",
  "file_id": "order_12345_part_A",
  "status": "processing",
  "original_format": "OBJ",
  "request_processing_time": 0.15
}
```

---

#### Callback Payload (Sent to Your callback_url)

Your callback URL will receive a POST request with one of these payloads:

##### Success Response

```typescript
{
  file_id: string | null;
  status: "success";
  mass_grams: number;            // Calculated mass in grams
  dimensions: {                  // Actual model dimensions in mm
    x: number;
    y: number;
    z: number;
  };
  processing_time: number;       // Total processing time in seconds
  conversion_time: number;       // File conversion time in seconds
  slicer_time: number;           // Slicer analysis time in seconds
  timestamp: number;             // Unix timestamp
}
```

**Example:**
```json
{
  "file_id": "order_12345_part_A",
  "status": "success",
  "mass_grams": 15.5,
  "dimensions": {
    "x": 50.2,
    "y": 75.1,
    "z": 25.0
  },
  "processing_time": 2.45,
  "conversion_time": 0.65,
  "slicer_time": 1.8,
  "timestamp": 1704067200.0
}
```

---

##### Error Response: Dimension Too Large

```typescript
{
  file_id: string | null;
  status: "error";
  error: string;                 // Human-readable error message
  dimensions: {                  // Actual model dimensions in mm
    x: number;
    y: number;
    z: number;
  };
  processing_time: number;       // Seconds before failure
  conversion_time?: number;      // Conversion time if applicable
  timestamp: number;             // Unix timestamp
}
```

**Example:**
```json
{
  "file_id": "order_12345_part_A",
  "status": "error",
  "error": "Dimension X too large. Model dimensions: 350.00x200.00x100.00mm. Max allowed: 300x300x300mm.",
  "dimensions": {
    "x": 350.0,
    "y": 200.0,
    "z": 100.0
  },
  "processing_time": 1.2,
  "conversion_time": 0.5,
  "timestamp": 1704067200.0
}
```

---

##### Error Response: Processing Failure

```typescript
{
  file_id: string | null;
  status: "error";
  error: string;                 // Human-readable error message
  error_type?: string;           // Exception class name (e.g., "ValueError")
  processing_time: number;       // Seconds before failure
  conversion_time?: number;      // Conversion time if applicable
  download_time?: number;        // Download time if applicable
  timestamp: number;             // Unix timestamp
}
```

**Example (Download Failure):**
```json
{
  "file_id": "order_12345_part_A",
  "status": "error",
  "error": "Failed to download 3D file from URL",
  "download_time": 120.5,
  "processing_time": 120.5,
  "timestamp": 1704067200.0
}
```

**Example (Conversion Failure):**
```json
{
  "file_id": "order_12345_part_A",
  "status": "error",
  "error": "Failed to convert file to STL format",
  "conversion_time": 2.1,
  "processing_time": 2.1,
  "timestamp": 1704067200.0
}
```

**Example (Processing Error):**
```json
{
  "file_id": "order_12345_part_A",
  "status": "error",
  "error": "Processing error: Invalid mesh data",
  "error_type": "ValueError",
  "processing_time": 1.8,
  "timestamp": 1704067200.0
}
```

---

#### Error Responses (Immediate)

If the request fails validation, you'll receive an immediate error response:

##### 400 Bad Request
```typescript
{
  error: string;                 // Validation error message
  request_processing_time?: number;
}
```

**Examples:**
```json
{"error": "file_url and callback_url are required"}
{"error": "callback_url must start with http:// or https://"}
{"error": "Unsupported file format. Supported formats: STL, OBJ, PLY, ..."}
{"error": "File size exceeds 500MB limit"}
{"error": "max_dimensions.x must be between 0 and 10000"}
```

##### 500 Internal Server Error
```typescript
{
  error: string;                 // "Internal server error"
  message: string;               // Error details
  type: string;                  // Exception class name
  request_processing_time: number;
}
```

---

#### Callback Delivery Guarantees

The service **guarantees** callback delivery with the following reliability features:

- **3 retry attempts** with exponential backoff (2s, 4s, 8s delays)
- **Automatic retry** on: Network errors, timeouts, HTTP 5xx errors, 408, 429
- **No retry** on: HTTP 4xx client errors (except 408, 429)
- **30-second timeout** per callback attempt
- **Comprehensive logging** of all callback attempts

**Total maximum retry time:** ~14 seconds (3 attempts + backoff delays)

Your callback endpoint should:
- Respond with HTTP 200-299 for success
- Return within 30 seconds
- Be idempotent (handle duplicate deliveries)

---

### GET `/health`

Health check endpoint for monitoring service availability and configuration.

#### Response (200 OK)

```typescript
{
  status: "healthy";
  version: string;               // Service version (e.g., "4.6")
  timestamp: number;             // Unix timestamp
  supported_formats: string[];   // Array of supported file extensions
  system_info: {
    working_directory: string;
    tmp_directory_exists: boolean;
    superslicer_exists: boolean;
    config_exists: boolean;
    python_version: string;
  };
}
```

**Example:**
```json
{
  "status": "healthy",
  "version": "4.6",
  "timestamp": 1704067200.0,
  "supported_formats": [
    "STL", "OBJ", "PLY", "OFF", "3MF", "GLTF", "GLB",
    "DAE", "X3D", "WRL", "VRML", "STEP", "STP",
    "IGES", "IGS", "COLLADA", "BLEND"
  ],
  "system_info": {
    "working_directory": "/app",
    "tmp_directory_exists": true,
    "superslicer_exists": true,
    "config_exists": true,
    "python_version": "3.10.12"
  }
}
```

**Usage:**
```bash
curl https://m3d-api.sevalla.app/health
```

---

### GET `/api/formats`

Returns detailed information about all supported 3D file formats.

#### Response (200 OK)

```typescript
{
  supported_formats: Array<{
    extension: string;           // File extension (e.g., "STL", "OBJ")
    description: string;         // Format full name
    native: boolean;             // true if no conversion needed
  }>;
  conversion_info: {
    primary_engine: string;      // "trimesh"
    fallback_engine: string;     // "pymeshlab"
    note: string;                // Conversion information
  };
}
```

**Example:**
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
    },
    {
      "extension": "3MF",
      "description": "3D Manufacturing Format",
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

**Usage:**
```bash
curl https://m3d-api.sevalla.app/api/formats
```

---

## Dependencies
- SuperSlicer binary (`slicersuper`)
- Configuration file (`config.ini`)
- Python dependencies in `requirements.txt`

## Docker Usage

### Quick Start (Recommended)

```bash
# Using the docker script (easiest)
./docker.sh build
./docker.sh run

# Or using npm-style commands
npm run build
npm start

# Or using make commands
make build
make run
```

### Manual Docker Commands

```bash
docker build -t mandarin3d-slicer .
docker run -p 5030:5030 mandarin3d-slicer
```

### Docker Compose

```bash
# Development
docker-compose up -d

# Production (with nginx)
docker-compose --profile production up -d
```

## Usage Examples

### Upload OBJ file
```bash
curl -X POST http://localhost:5030/api/slice \
  -F "model_file=@model.obj" \
  -F "callback_url=https://your-api.com/callback" \
  -F "file_id=test_obj_123" \
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
    "callback_url": "https://your-api.com/callback",
    "file_id": "test_3mf_456",
    "max_dimensions": {"x": 300, "y": 300, "z": 300}
  }'
```

### Check supported formats
```bash
curl -X GET http://localhost:5030/api/formats
```

## Build & Development Tools

This project includes multiple ways to build and run the service, similar to Node.js package.json scripts:

### 🔧 Available Tools

| Tool | Purpose | Usage |
|------|---------|--------|
| `docker.sh` | Simple Docker management script | `./docker.sh build` |
| `Makefile` | GNU Make commands | `make build` |  
| `package.json` | npm-style scripts | `npm run build` |
| `docker-compose.yml` | Multi-container orchestration | `docker-compose up` |

### 🚀 Common Commands

```bash
# Build and run (choose your preferred method)
./docker.sh build && ./docker.sh run
make build-start
npm run build && npm start

# Development mode
./docker.sh dev
make run-dev  
npm run docker:run-dev

# View logs
./docker.sh logs
make logs
npm run logs

# Health check
./docker.sh health
make health
npm run health

# Stop and clean
./docker.sh clean
make clean
npm run clean
```

## Recent Updates

### Version 4.6 - Robustness & Reliability (Latest)
- **NEW:** Download timeout protection (30s connection, 120s read) prevents worker deaths
- **NEW:** Callback retry logic with exponential backoff (3 attempts, 2s/4s/8s delays)
- **NEW:** Comprehensive error handling - callbacks **guaranteed** in all scenarios
- **NEW:** Request validation (URLs, file sizes, dimensions) with early failure detection
- **NEW:** Background thread safety wrapper catches catastrophic failures
- **NEW:** Global error handlers for 404, 405, and unhandled exceptions
- **NEW:** File size limits (500MB) and dimension limits (10000mm) validation
- **Enhanced:** Full traceback logging for all errors
- **Enhanced:** Automatic cleanup of temporary files on errors
- **Enhanced:** Progress monitoring for long downloads (logs every 8MB)
- **Enhanced:** Detailed timing metrics (download_time, conversion_time, slicer_time)
- **Enhanced:** Error responses include error_type for better debugging

### Version 4.x - Multi-Format Support
- **NEW:** Support for 17 different 3D file formats (OBJ, STEP, 3MF, etc.)
- **NEW:** Automatic file format conversion using trimesh + pymeshlab
- **NEW:** `/api/formats` endpoint to list supported formats
- **NEW:** Multiple build/run tools: `docker.sh`, `Makefile`, `package.json`, `docker-compose.yml`
- **NEW:** Comprehensive documentation in `docs.md`
- **Enhanced:** Better error handling for conversion failures
- **Enhanced:** Format validation before processing
- **Enhanced:** Production-ready Docker setup with health checks
- Removed MongoDB dependency
- Removed Cloudflare R2 dependency
- Simplified to callback-based architecture
- Supports both URL downloads and direct file uploads
- Backward compatibility with existing STL-only API calls

---

## Reliability Features

### Callback Guarantees
- **3 automatic retries** with exponential backoff
- **Smart retry logic**: Retries on transient errors (5xx, timeouts, connection errors)
- **No retry** on permanent client errors (4xx except 408, 429)
- **Emergency callbacks** sent even on catastrophic thread crashes
- **Comprehensive logging** of all callback attempts and failures

### Timeout Protection
- **Connection timeout**: 30 seconds
- **Read timeout**: 120 seconds (for large file downloads)
- **Callback timeout**: 30 seconds per attempt
- **Progress monitoring**: Logs every 8MB during downloads

### Error Handling
- **Global exception handlers** catch all unhandled errors
- **Background thread safety** wrapper prevents silent failures
- **Automatic file cleanup** removes temporary files on errors
- **Detailed error types** and tracebacks in logs
- **Validation before processing** fails fast on invalid inputs

### Resource Limits
- **Max file size**: 500MB
- **Max URL length**: 2048 characters
- **Max dimensions**: 10,000mm per axis
- **Request timeout**: Based on Gunicorn worker timeout (configurable)
