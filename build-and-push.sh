#!/bin/bash
# Build and push u-mem0 container images to GitHub Container Registry
# Usage: ./build-and-push.sh [version]
# Example: ./build-and-push.sh v1.0.0

set -e

# Configuration
REGISTRY="ghcr.io"
ORG="Ushadow-io"  # GitHub org name
VERSION="${1:-latest}"

# Image names (must be lowercase for GHCR)
ORG_LOWERCASE=$(echo "${ORG}" | tr '[:upper:]' '[:lower:]')
API_IMAGE="${REGISTRY}/${ORG_LOWERCASE}/u-mem0-api"
UI_IMAGE="${REGISTRY}/${ORG_LOWERCASE}/u-mem0-ui"

echo "Building and pushing u-mem0 containers version: ${VERSION}"
echo "Registry: ${REGISTRY}/${ORG}"
echo ""

# Ensure we're using a multi-platform capable builder
if ! docker buildx ls | grep -q "multiarch.*docker-container"; then
    echo "Creating multi-arch builder..."
    docker buildx create --name multiarch --use
    docker buildx inspect --bootstrap
else
    echo "Using existing multi-arch builder"
    docker buildx use multiarch
fi
echo ""

# Check if logged into GHCR
# Note: This check may not work with all Docker implementations (e.g., OrbStack)
# If you've already logged in successfully, the push will work
if [ -f ~/.docker/config.json ] && grep -q "ghcr.io" ~/.docker/config.json 2>/dev/null; then
    echo "✓ Detected GHCR credentials"
else
    echo "⚠️  Could not verify GHCR login. If not logged in, the push will fail."
    echo "   Login with: echo \$GITHUB_TOKEN | docker login ghcr.io -u USERNAME --password-stdin"
    echo ""
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Build and push API
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Building u-mem0 API (Backend)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

docker buildx build \
    --platform linux/amd64,linux/arm64 \
    --tag "${API_IMAGE}:${VERSION}" \
    --tag "${API_IMAGE}:latest" \
    --file openmemory/api/Dockerfile \
    --push \
    openmemory/api/

echo "✓ API image pushed: ${API_IMAGE}:${VERSION}"
echo ""

# Build and push UI
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Building u-mem0 UI (Frontend)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

docker buildx build \
    --platform linux/amd64,linux/arm64 \
    --tag "${UI_IMAGE}:${VERSION}" \
    --tag "${UI_IMAGE}:latest" \
    --file openmemory/ui/Dockerfile \
    --push \
    openmemory/ui/

echo "✓ UI image pushed: ${UI_IMAGE}:${VERSION}"
echo ""

# Make images public
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Making images public..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Check if gh CLI is available
if ! command -v gh &> /dev/null; then
    echo "⚠️  GitHub CLI (gh) not found. Skipping visibility change."
    echo "   Install gh CLI: https://cli.github.com/"
    echo "   Or manually change visibility at: https://github.com/orgs/${ORG}/packages"
else
    echo "Setting u-mem0-api to public..."
    if gh api \
        --method PATCH \
        -H "Accept: application/vnd.github+json" \
        "/orgs/${ORG_LOWERCASE}/packages/container/u-mem0-api" \
        -f visibility='public' 2>/dev/null; then
        echo "✓ u-mem0-api is now public"
    else
        echo "⚠️  Could not set u-mem0-api visibility (may already be public or require different permissions)"
    fi

    echo "Setting u-mem0-ui to public..."
    if gh api \
        --method PATCH \
        -H "Accept: application/vnd.github+json" \
        "/orgs/${ORG_LOWERCASE}/packages/container/u-mem0-ui" \
        -f visibility='public' 2>/dev/null; then
        echo "✓ u-mem0-ui is now public"
    else
        echo "⚠️  Could not set u-mem0-ui visibility (may already be public or require different permissions)"
    fi
fi
echo ""

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✓ All images published successfully!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Public images available at:"
echo "  - ${API_IMAGE}:${VERSION}"
echo "  - ${API_IMAGE}:latest"
echo "  - ${UI_IMAGE}:${VERSION}"
echo "  - ${UI_IMAGE}:latest"
echo ""
echo "Anyone can now pull with (no authentication required):"
echo "  docker pull ${API_IMAGE}:latest"
echo "  docker pull ${UI_IMAGE}:latest"
echo ""
echo "Or use docker-compose-prod.yml to run the entire stack"
echo ""
echo "View packages at:"
echo "  - https://github.com/orgs/${ORG_LOWERCASE}/packages/container/package/u-mem0-api"
echo "  - https://github.com/orgs/${ORG_LOWERCASE}/packages/container/package/u-mem0-ui"
