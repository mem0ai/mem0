#!/bin/bash
# Install git hooks for the deploy branch

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$(dirname "${SCRIPT_DIR}")")"
GIT_HOOKS_DIR="${REPO_ROOT}/.git/hooks"

echo "Installing git hooks..."

# Create pre-commit hook
cat > "${GIT_HOOKS_DIR}/pre-commit" << 'EOF'
#!/bin/bash
# Pre-commit hook for deploy branch
# Runs security checks before allowing commits on deploy branch

BRANCH=$(git rev-parse --abbrev-ref HEAD)

if [ "${BRANCH}" = "deploy" ]; then
    echo "Running security check on deploy branch..."

    SCRIPT_DIR="$(git rev-parse --show-toplevel)/deploy-fly-io/hooks"
    if [ -x "${SCRIPT_DIR}/security-check.sh" ]; then
        "${SCRIPT_DIR}/security-check.sh"
        if [ $? -ne 0 ]; then
            echo "Security check failed. Commit aborted."
            exit 1
        fi
    fi
fi

exit 0
EOF

chmod +x "${GIT_HOOKS_DIR}/pre-commit"

# Create pre-push hook
cat > "${GIT_HOOKS_DIR}/pre-push" << 'EOF'
#!/bin/bash
# Pre-push hook
# Warns before pushing to deploy branch

while read local_ref local_sha remote_ref remote_sha; do
    if [[ "${remote_ref}" == *"deploy"* ]]; then
        echo ""
        echo "⚠️  You are pushing to the deploy branch!"
        echo ""
        echo "Make sure you have:"
        echo "  1. Run the pre-merge security check"
        echo "  2. Tested locally"
        echo "  3. Deployed to test environment first"
        echo ""
        read -p "Continue with push? (yes/no): " CONFIRM
        if [ "${CONFIRM}" != "yes" ]; then
            echo "Push aborted."
            exit 1
        fi
    fi
done

exit 0
EOF

chmod +x "${GIT_HOOKS_DIR}/pre-push"

echo "Git hooks installed successfully!"
echo ""
echo "Hooks installed:"
echo "  - pre-commit: Runs security check on deploy branch commits"
echo "  - pre-push: Warns before pushing to deploy branch"
