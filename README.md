# Mandarin3D 3D File Slicing Service

A Flask-based microservice for processing various 3D file formats and extracting mass/dimension information using SuperSlicer with automatic file format conversion.

## Supported 3D File Formats

**Native:** STL (processed directly)

**Auto-converted to STL:** OBJ, PLY, OFF, 3MF, GLTF, GLB, DAE, X3D, WRL, VRML, STEP, STP, IGES, IGS, COLLADA, BLEND

*Conversion engines: trimesh (primary), pymeshlab (fallback)*

Baseurl: https://m3d-api.sevalla.app

## API Endpoints

### POST `/api/slice`

Process any supported 3D file format and return results via callback URL.

#### Option 1: JSON Request (File URL)
```json
{
  "file_url": "https://example.com/model.obj",
  "callback_url": "https://your-api.com/callback",
  "file_id": "optional_file_identifier",
  "max_dimensions": {"x": 300, "y": 300, "z": 300}
}
```

#### Option 2: Form Data (File Upload)
- `model_file`: 3D model file in any supported format (required)
- `callback_url`: Callback URL (required)  
- `file_id`: Optional file identifier
- `max_x`, `max_y`, `max_z`: Optional dimension limits (default: 300mm)

*Note: Also accepts `stl_file`, `3d_file`, or `file` field names for backward compatibility.*

#### Response
```json
{
  "message": "3D file processing started",
  "file_id": "your_file_id",
  "status": "processing",
  "original_format": "OBJ"
}
```

#### Callback Payload
On success:
```json
{
  "file_id": "your_file_id",
  "status": "success",
  "mass_grams": 15.5,
  "dimensions": {"x": 50.2, "y": 75.1, "z": 25.0},
  "processing_time": 2.45,
  "slicer_time": 1.8,
  "timestamp": 1704067200.0
}
```

On error (conversion failure):
```json
{
  "file_id": "your_file_id",
  "status": "error", 
  "error": "Failed to convert file to STL format",
  "processing_time": 1.2,
  "timestamp": 1704067200.0
}
```

On error (dimension check):
```json
{
  "file_id": "your_file_id", 
  "status": "error",
  "error": "Dimension X too large. Model dimensions: 350.00x200.00x100.00mm. Max allowed: 300x300x300mm.",
  "dimensions": {"x": 350.0, "y": 200.0, "z": 100.0},
  "processing_time": 1.2,
  "timestamp": 1704067200.0
}
```

### GET `/health`
Health check endpoint returning service status, version, and supported formats.

### GET `/api/formats`
Returns detailed list of all supported 3D file formats with descriptions and conversion information.

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

## Changes from Previous Version
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
