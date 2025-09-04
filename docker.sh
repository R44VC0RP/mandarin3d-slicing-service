#!/bin/bash

# Mandarin3D Slicing Service - Docker Management Script
# Simple script for building and running the Docker container

set -e

# Configuration
IMAGE_NAME="mandarin3d/mandarin3d-slicer"
CONTAINER_NAME="mandarin3d-slicer"
PORT="5030"
VERSION=$(cat version 2>/dev/null || echo "latest")

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Helper functions
log() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if Docker is running
check_docker() {
    if ! docker info > /dev/null 2>&1; then
        error "Docker is not running. Please start Docker and try again."
        exit 1
    fi
}

# Show usage
usage() {
    echo "Mandarin3D Slicing Service - Docker Management"
    echo ""
    echo "Usage: $0 {build|run|dev|stop|restart|logs|shell|clean|health|test|help}"
    echo ""
    echo "Commands:"
    echo "  build     - Build Docker image"
    echo "  run       - Run container in production mode"
    echo "  dev       - Run container in development mode"
    echo "  stop      - Stop and remove container"
    echo "  restart   - Restart container"
    echo "  logs      - Show container logs"
    echo "  shell     - Open shell in running container"
    echo "  clean     - Clean up Docker resources"
    echo "  health    - Check service health"
    echo "  test      - Run basic tests"
    echo "  status    - Show container status"
    echo "  help      - Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 build && $0 run    # Build and run"
    echo "  $0 dev                # Quick development setup"
    echo "  $0 logs               # Monitor logs"
}

# Build Docker image
build() {
    log "Building Docker image: ${IMAGE_NAME}:${VERSION}"
    docker build -t "${IMAGE_NAME}:latest" -t "${IMAGE_NAME}:${VERSION}" .
    log "Build complete!"
}

# Run container in production mode
run() {
    log "Starting container: ${CONTAINER_NAME}"
    
    # Stop existing container if running
    if docker ps -a --format "table {{.Names}}" | grep -q "^${CONTAINER_NAME}$"; then
        warn "Container ${CONTAINER_NAME} already exists. Stopping..."
        docker stop "${CONTAINER_NAME}" || true
        docker rm "${CONTAINER_NAME}" || true
    fi
    
    # Create tmp directory if it doesn't exist
    mkdir -p ./tmp
    
    # Run new container
    docker run -d \
        --name "${CONTAINER_NAME}" \
        -p "${PORT}:${PORT}" \
        -v "$(pwd)/tmp:/app/tmp" \
        --restart unless-stopped \
        "${IMAGE_NAME}:latest"
    
    log "Container started successfully!"
    log "Service available at: http://localhost:${PORT}"
    log "Health check: http://localhost:${PORT}/health"
}

# Run container in development mode
dev() {
    log "Starting development container..."
    
    # Stop existing dev container if running
    docker stop "${CONTAINER_NAME}-dev" 2>/dev/null || true
    docker rm "${CONTAINER_NAME}-dev" 2>/dev/null || true
    
    # Create tmp directory
    mkdir -p ./tmp
    
    # Run in development mode with volume mounts
    docker run -it --rm \
        --name "${CONTAINER_NAME}-dev" \
        -p "${PORT}:${PORT}" \
        -v "$(pwd):/app" \
        -v "$(pwd)/tmp:/app/tmp" \
        -e FLASK_ENV=development \
        "${IMAGE_NAME}:latest"
}

# Stop container
stop() {
    log "Stopping container: ${CONTAINER_NAME}"
    docker stop "${CONTAINER_NAME}" 2>/dev/null || warn "Container not running"
    docker rm "${CONTAINER_NAME}" 2>/dev/null || warn "Container not found"
    log "Container stopped"
}

# Restart container
restart() {
    log "Restarting container..."
    stop
    run
}

# Show logs
logs() {
    log "Showing logs for ${CONTAINER_NAME}..."
    docker logs -f "${CONTAINER_NAME}"
}

# Open shell in container
shell() {
    log "Opening shell in ${CONTAINER_NAME}..."
    docker exec -it "${CONTAINER_NAME}" /bin/bash
}

# Clean up Docker resources
clean() {
    log "Cleaning up Docker resources..."
    docker stop "${CONTAINER_NAME}" 2>/dev/null || true
    docker rm "${CONTAINER_NAME}" 2>/dev/null || true
    docker rmi "${IMAGE_NAME}:latest" 2>/dev/null || true
    docker system prune -f
    log "Cleanup complete"
}

# Check service health
health() {
    log "Checking service health..."
    if curl -f -s "http://localhost:${PORT}/health" > /dev/null; then
        log "Service is healthy! ✓"
        curl -s "http://localhost:${PORT}/health" | jq . 2>/dev/null || curl -s "http://localhost:${PORT}/health"
    else
        error "Service is not responding ✗"
        exit 1
    fi
}

# Run basic tests
test() {
    log "Running basic tests..."
    
    # Test health endpoint
    if ! health; then
        error "Health check failed"
        exit 1
    fi
    
    # Test formats endpoint
    log "Testing formats endpoint..."
    if curl -f -s "http://localhost:${PORT}/api/formats" > /dev/null; then
        log "Formats endpoint working ✓"
    else
        error "Formats endpoint failed ✗"
        exit 1
    fi
    
    log "All tests passed! ✓"
}

# Show container status
status() {
    log "Container status:"
    if docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | grep -q "${CONTAINER_NAME}"; then
        docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | grep "${CONTAINER_NAME}"
        log "Container is running ✓"
    else
        warn "Container is not running"
    fi
}

# Main script logic
main() {
    check_docker
    
    case "${1}" in
        build)
            build
            ;;
        run)
            run
            ;;
        dev)
            dev
            ;;
        stop)
            stop
            ;;
        restart)
            restart
            ;;
        logs)
            logs
            ;;
        shell)
            shell
            ;;
        clean)
            clean
            ;;
        health)
            health
            ;;
        test)
            test
            ;;
        status)
            status
            ;;
        help|--help|-h)
            usage
            ;;
        *)
            error "Unknown command: ${1}"
            echo ""
            usage
            exit 1
            ;;
    esac
}

# Run main function with all arguments
main "$@"
