#!/bin/bash
# PatchFlow Production Deployment Script
# Usage: ./deploy.sh [build|deploy|all]

set -e

NAMESPACE="patchflow"
REGISTRY="${DOCKER_REGISTRY:-docker.io/patchflow}"
VERSION="${VERSION:-latest}"

echo "=========================================="
echo "PatchFlow Production Deployment"
echo "=========================================="
echo "Registry: $REGISTRY"
echo "Version: $VERSION"
echo "Namespace: $NAMESPACE"
echo "=========================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Build images
build_images() {
    log_info "Building backend image..."
    docker build -t $REGISTRY/backend:$VERSION ./backend
    docker tag $REGISTRY/backend:$VERSION $REGISTRY/backend:latest
    
    log_info "Building frontend image..."
    docker build -t $REGISTRY/frontend:$VERSION ./frontend
    docker tag $REGISTRY/frontend:$VERSION $REGISTRY/frontend:latest
    
    log_info "Images built successfully!"
}

# Push images
push_images() {
    log_info "Pushing images to registry..."
    docker push $REGISTRY/backend:$VERSION
    docker push $REGISTRY/backend:latest
    docker push $REGISTRY/frontend:$VERSION
    docker push $REGISTRY/frontend:latest
    log_info "Images pushed successfully!"
}

# Deploy to Kubernetes
deploy_k8s() {
    log_info "Deploying to Kubernetes..."
    
    # Create namespace if not exists
    kubectl create namespace $NAMESPACE --dry-run=client -o yaml | kubectl apply -f -
    
    # Apply manifests in order
    log_info "Applying backend manifests..."
    kubectl apply -f k8s/backend.yaml
    
    log_info "Applying frontend manifests..."
    kubectl apply -f k8s/frontend.yaml
    
    log_info "Applying ingress manifests..."
    kubectl apply -f k8s/ingress.yaml
    
    log_info "Deployment complete!"
}

# Wait for rollout
wait_for_rollout() {
    log_info "Waiting for deployments to complete..."
    
    kubectl rollout status deployment/patchflow-backend -n $NAMESPACE --timeout=300s
    kubectl rollout status deployment/patchflow-frontend -n $NAMESPACE --timeout=300s
    
    log_info "All deployments complete!"
}

# Verify deployment
verify_deployment() {
    log_info "Verifying deployment..."
    
    # Check pods
    kubectl get pods -n $NAMESPACE
    
    # Check services
    kubectl get svc -n $NAMESPACE
    
    # Check ingress
    kubectl get ingress -n $NAMESPACE
    
    # Health check
    log_info "Testing health endpoints..."
    
    # Port forward to test
    kubectl port-forward svc/patchflow-backend 8000:8000 -n $NAMESPACE &
    PF_PID=$!
    sleep 3
    
    if curl -f http://localhost:8000/health/live; then
        log_info "Backend health check: PASSED"
    else
        log_error "Backend health check: FAILED"
    fi
    
    kill $PF_PID 2>/dev/null || true
}

# Main
case "${1:-all}" in
    build)
        build_images
        ;;
    push)
        push_images
        ;;
    deploy)
        deploy_k8s
        wait_for_rollout
        verify_deployment
        ;;
    all)
        build_images
        push_images
        deploy_k8s
        wait_for_rollout
        verify_deployment
        ;;
    *)
        echo "Usage: $0 [build|push|deploy|all]"
        exit 1
        ;;
esac

log_info "Deployment script completed!"
