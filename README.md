# Mandarin3D STL Slicing Service

A simplified Flask-based microservice for processing STL files and extracting mass/dimension information using SuperSlicer.

## API Endpoints

### POST `/api/slice`

Process an STL file and return results via callback URL.

#### Option 1: JSON Request (STL URL)
```json
{
  "stl_url": "https://example.com/model.stl",
  "callback_url": "https://your-api.com/callback",
  "file_id": "optional_file_identifier",
  "max_dimensions": {"x": 300, "y": 300, "z": 300}
}
```

#### Option 2: Form Data (File Upload)
- `stl_file`: STL file (required)
- `callback_url`: Callback URL (required)  
- `file_id`: Optional file identifier
- `max_x`, `max_y`, `max_z`: Optional dimension limits (default: 300mm)

#### Response
```json
{
  "message": "STL processing started",
  "file_id": "your_file_id",
  "status": "processing"
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

On error:
```json
{
  "file_id": "your_file_id", 
  "status": "error",
  "error": "Dimension X too large. Model dimensions: 350.00x200.00x100.00mm. Max allowed: 300x300x300mm.",
  "processing_time": 1.2,
  "timestamp": 1704067200.0
}
```

### GET `/health`
Health check endpoint returning service status and version.

## Dependencies
- SuperSlicer binary (`slicersuper`)
- Configuration file (`config.ini`)
- Python dependencies in `requirements.txt`

## Docker Usage
```bash
docker build -t mandarin3d-slicer .
docker run -p 5030:5030 mandarin3d-slicer
```

## Changes from Previous Version
- Removed MongoDB dependency
- Removed Cloudflare R2 dependency  
- Simplified to callback-based architecture
- Supports both URL downloads and direct file uploads
