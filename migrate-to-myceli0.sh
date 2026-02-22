#!/bin/bash

# migrate-to-myceli0.sh
# Script to migrate your mem0 fork to the new myceli0 repository

set -e  # Exit on error

echo "========================================="
echo "  myceli0 Migration Script"
echo "========================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Step 1: Verify we're in the right directory
echo -e "${YELLOW}[1/7] Verifying repository...${NC}"
if [ ! -d ".git" ]; then
    echo -e "${RED}Error: Not in a git repository${NC}"
    exit 1
fi

if ! git remote -v | grep -q "thestumonkey/mem0"; then
    echo -e "${RED}Error: This doesn't appear to be your mem0 fork${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Repository verified${NC}"
echo ""

# Step 2: Check for uncommitted changes
echo -e "${YELLOW}[2/7] Checking for uncommitted changes...${NC}"
if [[ -n $(git status -s) ]]; then
    echo -e "${YELLOW}You have uncommitted changes. Committing them now...${NC}"

    # Add the new files
    git add NOTICE
    git add README-MYCELI0.md
    git add GRAPH_FIXES.md GRAPH_VISUALIZATION.md

    # Commit all changes
    git add -A
    git commit -m "Prepare for myceli0 migration

- Add NOTICE file with Apache 2.0 attribution
- Add README-MYCELI0.md with new branding
- Add migration script
- Include graph documentation

🍄 Migrating to myceli0 - Enterprise memory layer for AI agents

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"

    echo -e "${GREEN}✓ Changes committed${NC}"
else
    echo -e "${GREEN}✓ No uncommitted changes${NC}"
fi
echo ""

# Step 3: Add myceli0 remote
echo -e "${YELLOW}[3/7] Adding myceli0 remote...${NC}"
MYCELI0_REPO="git@github.com:chronicler-ai/myceli0.git"

# Remove existing myceli0 remote if it exists
if git remote | grep -q "^myceli0$"; then
    echo "  Removing existing myceli0 remote..."
    git remote remove myceli0
fi

git remote add myceli0 "$MYCELI0_REPO"
echo -e "${GREEN}✓ myceli0 remote added${NC}"
echo ""

# Step 4: Show current remotes
echo -e "${YELLOW}[4/7] Current remotes:${NC}"
git remote -v
echo ""

# Step 5: Replace README
echo -e "${YELLOW}[5/7] Updating README for myceli0 branding...${NC}"
if [ -f "README-MYCELI0.md" ]; then
    # Backup original README
    cp README.md README-MEM0-ORIGINAL.md

    # Replace with myceli0 README
    cp README-MYCELI0.md README.md

    git add README.md README-MEM0-ORIGINAL.md
    git commit -m "Update README for myceli0 branding

- Replace README with myceli0-specific content
- Backup original mem0 README
- Add myceli0 logo and branding
- Document enterprise features

🍄 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"

    echo -e "${GREEN}✓ README updated${NC}"
else
    echo -e "${RED}Error: README-MYCELI0.md not found${NC}"
    exit 1
fi
echo ""

# Step 6: Push to myceli0
echo -e "${YELLOW}[6/7] Ready to push to myceli0${NC}"
echo ""
echo "The repository has been prepared. To complete the migration:"
echo ""
echo "1. Create the repository on GitHub:"
echo "   Go to: https://github.com/organizations/chronicler-ai/repositories/new"
echo "   Repository name: myceli0"
echo "   Visibility: Public or Private (your choice)"
echo "   Do NOT initialize with README"
echo ""
echo "2. Once created, run:"
echo "   ${GREEN}git push myceli0 stufork:main${NC}"
echo ""
echo "   Or to push all branches:"
echo "   ${GREEN}git push myceli0 --all${NC}"
echo ""
echo "   Or to set myceli0 as default and push:"
echo "   ${GREEN}git remote rename origin thestumonkey${NC}"
echo "   ${GREEN}git remote rename myceli0 origin${NC}"
echo "   ${GREEN}git push origin stufork:main${NC}"
echo ""

# Step 7: Summary
echo -e "${YELLOW}[7/7] Migration Summary${NC}"
echo ""
echo "Files added:"
echo "  ✓ NOTICE - Apache 2.0 attribution"
echo "  ✓ README.md - Updated with myceli0 branding"
echo "  ✓ README-MEM0-ORIGINAL.md - Backup of original"
echo "  ✓ migrate-to-myceli0.sh - This script"
echo ""
echo "Remotes configured:"
echo "  • origin     → thestumonkey/mem0 (your fork)"
echo "  • upstream   → mem0ai/mem0 (original)"
echo "  • myceli0    → chronicler-ai/myceli0 (new home)"
echo ""
echo -e "${GREEN}=========================================${NC}"
echo -e "${GREEN}  Migration Preparation Complete!${NC}"
echo -e "${GREEN}=========================================${NC}"
echo ""
echo "Next steps:"
echo "1. Create GitHub repository (chronicler-ai/myceli0)"
echo "2. Push code: git push myceli0 stufork:main"
echo "3. Set up branch protection rules"
echo "4. Update Chakra integration to use myceli0"
echo ""
