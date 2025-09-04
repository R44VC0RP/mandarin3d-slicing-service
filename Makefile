# Mandarin3D Slicing Service - Build and Run Commands
# Similar to package.json scripts but for Python/Docker projects

.PHONY: help build run stop clean logs shell test health dev prod push

# Variables
IMAGE_NAME := mandarin3d/mandarin3d-slicer
CONTAINER_NAME := mandarin3d-slicer
VERSION := $(shell cat version)
PORT := 5030

# Default target
help: ## Show this help message
	@echo "Mandarin3D Slicing Service - Available Commands:"
	@echo ""
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

# Development Commands
dev: ## Start development server (local Python)
	@echo "Starting development server..."
	python app.py

install: ## Install Python dependencies locally
	@echo "Installing dependencies..."
	pip install -r requirements.txt

# Docker Commands
build: ## Build Docker image
	@echo "Building Docker image: $(IMAGE_NAME):$(VERSION)"
	docker build -t $(IMAGE_NAME):latest -t $(IMAGE_NAME):$(VERSION) .

run: ## Run Docker container
	@echo "Running container: $(CONTAINER_NAME)"
	docker run -d \
		--name $(CONTAINER_NAME) \
		-p $(PORT):$(PORT) \
		-v $(PWD)/tmp:/app/tmp \
		--restart unless-stopped \
		$(IMAGE_NAME):latest

run-dev: ## Run Docker container in development mode with volume mounts
	@echo "Running development container..."
	docker run -it --rm \
		--name $(CONTAINER_NAME)-dev \
		-p $(PORT):$(PORT) \
		-v $(PWD):/app \
		-v $(PWD)/tmp:/app/tmp \
		-e FLASK_ENV=development \
		$(IMAGE_NAME):latest

stop: ## Stop and remove container
	@echo "Stopping container: $(CONTAINER_NAME)"
	-docker stop $(CONTAINER_NAME)
	-docker rm $(CONTAINER_NAME)

restart: stop run ## Restart the container

logs: ## Show container logs
	docker logs -f $(CONTAINER_NAME)

shell: ## Open shell in running container
	docker exec -it $(CONTAINER_NAME) /bin/bash

# Docker Compose Commands
up: ## Start services with docker-compose
	@echo "Starting services with docker-compose..."
	docker-compose up -d

down: ## Stop services with docker-compose
	@echo "Stopping services with docker-compose..."
	docker-compose down

up-prod: ## Start production services (including nginx)
	@echo "Starting production services..."
	docker-compose --profile production up -d

compose-logs: ## Show docker-compose logs
	docker-compose logs -f

compose-build: ## Build with docker-compose
	docker-compose build

# Maintenance Commands
clean: ## Clean up Docker resources
	@echo "Cleaning up Docker resources..."
	-docker stop $(CONTAINER_NAME)
	-docker rm $(CONTAINER_NAME)
	-docker rmi $(IMAGE_NAME):latest
	-docker system prune -f

clean-all: ## Clean all Docker resources (images, containers, volumes)
	@echo "Cleaning ALL Docker resources..."
	-docker-compose down -v
	-docker system prune -a -f
	-docker volume prune -f

# Testing & Health Commands
health: ## Check service health
	@echo "Checking service health..."
	curl -f http://localhost:$(PORT)/health | jq .

test-upload: ## Test file upload with sample STL
	@echo "Testing file upload..."
	curl -X POST http://localhost:$(PORT)/api/slice \
		-F "model_file=@test.stl" \
		-F "callback_url=http://httpbin.org/post" \
		-F "file_id=test_$(shell date +%s)"

test-url: ## Test URL processing
	@echo "Testing URL processing..."
	curl -X POST http://localhost:$(PORT)/api/slice \
		-H "Content-Type: application/json" \
		-d '{"file_url":"https://example.com/model.stl","callback_url":"http://httpbin.org/post","file_id":"url_test"}'

formats: ## Get supported formats
	@echo "Supported formats:"
	curl -s http://localhost:$(PORT)/api/formats | jq .

# Production & Deployment Commands
push: build ## Build and push to registry
	@echo "Pushing to registry..."
	docker push $(IMAGE_NAME):$(VERSION)
	docker push $(IMAGE_NAME):latest

deploy: ## Deploy to production (customize for your environment)
	@echo "Deploying to production..."
	# Add your deployment commands here
	# e.g., kubectl apply, docker stack deploy, etc.

# Version Management
version: ## Show current version
	@echo "Current version: $(VERSION)"

bump-version: ## Increment version number
	@echo "Current version: $(VERSION)"
	@read -p "Enter new version: " NEW_VERSION; \
	echo $$NEW_VERSION > version; \
	echo "Version updated to: $$NEW_VERSION"

# Monitoring Commands
stats: ## Show container stats
	docker stats $(CONTAINER_NAME)

inspect: ## Inspect container
	docker inspect $(CONTAINER_NAME) | jq .

# Development Utilities
lint: ## Run Python linting
	@echo "Running linting..."
	flake8 app.py printslicer.py --max-line-length=120

format: ## Format Python code
	@echo "Formatting code..."
	black app.py printslicer.py

# File Operations
backup: ## Backup important files
	@echo "Creating backup..."
	tar -czf backup-$(shell date +%Y%m%d-%H%M%S).tar.gz \
		app.py printslicer.py config.ini requirements.txt \
		Dockerfile docker-compose.yml version README.md docs.md

# Quick Commands (similar to npm run scripts)
start: run ## Alias for 'run'
dev-start: run-dev ## Alias for 'run-dev'  
build-start: build run ## Build and run
rebuild: stop clean build run ## Complete rebuild and run

# Examples and documentation
examples: ## Show usage examples
	@echo "Usage Examples:"
	@echo ""
	@echo "Development:"
	@echo "  make dev          # Run local Python server"
	@echo "  make run-dev      # Run in Docker with development settings"
	@echo ""
	@echo "Production:"
	@echo "  make build        # Build Docker image"
	@echo "  make run          # Run production container"
	@echo "  make up           # Start with docker-compose"
	@echo ""
	@echo "Testing:"
	@echo "  make health       # Check service health"
	@echo "  make test-upload  # Test file upload"
	@echo "  make formats      # List supported formats"
	@echo ""
	@echo "Maintenance:"
	@echo "  make logs         # View container logs"
	@echo "  make clean        # Clean up Docker resources"
	@echo "  make restart      # Restart the container"
