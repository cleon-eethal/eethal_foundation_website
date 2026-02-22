#!/bin/bash
#
# EETHAL Foundation - Publish to Production
#
# Builds CSS, commits pending changes, pushes dev, merges to master, and deploys.
#
# Usage:
#   ./scripts/publish.sh                  # Full publish (interactive)
#   ./scripts/publish.sh --dry-run        # Preview what would be published
#   ./scripts/publish.sh -m "message"     # Publish with a custom commit message
#

set -e

# Color codes
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m'

# Ensure we're in the repo root
cd "$(dirname "$0")/.."

# Parse arguments
DRY_RUN=false
COMMIT_MSG=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        -m)
            COMMIT_MSG="$2"
            shift 2
            ;;
        --help|-h)
            echo "Usage: ./scripts/publish.sh [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --dry-run        Preview what would be deployed without making changes"
            echo "  -m \"message\"     Use a custom commit message for pending changes"
            echo "  --help           Show this help message"
            echo ""
            echo "Steps performed:"
            echo "  1. Stop CSS watcher if running"
            echo "  2. Build minified CSS"
            echo "  3. Commit any pending changes (interactive)"
            echo "  4. Push dev branch"
            echo "  5. Merge dev into master"
            echo "  6. Push master (triggers Vercel deployment)"
            echo "  7. Switch back to dev"
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Verify git repo and branch
if [ ! -d ".git" ]; then
    echo -e "${RED}Error: Not a git repository${NC}"
    exit 1
fi

CURRENT_BRANCH=$(git branch --show-current)
if [ "$CURRENT_BRANCH" != "dev" ]; then
    echo -e "${RED}Error: Must be on dev branch (currently on $CURRENT_BRANCH)${NC}"
    echo "Run: git checkout dev"
    exit 1
fi

echo -e "${BOLD}${BLUE}======================================${NC}"
echo -e "${BOLD}${BLUE}  EETHAL Foundation - Publish${NC}"
echo -e "${BOLD}${BLUE}======================================${NC}"
echo ""

# --- Step 1: Stop CSS watcher ---
CSS_WAS_RUNNING=false
if pgrep -f "tailwindcss.*watch" > /dev/null 2>&1; then
    CSS_WAS_RUNNING=true
    echo -e "${YELLOW}Stopping CSS watcher...${NC}"
    pkill -f "tailwindcss.*watch" 2>/dev/null || true
    pkill -f "npm.*watch:css" 2>/dev/null || true
    sleep 1
fi

# --- Step 2: Build minified CSS ---
echo -e "${BLUE}Step 1: Building minified CSS...${NC}"
npm run build:css 2>&1 | tail -1
echo -e "${GREEN}  ✓ CSS built${NC}\n"

# --- Step 3: Check for pending changes ---
echo -e "${BLUE}Step 2: Checking for pending changes...${NC}"

# Restore styles.css if the watcher left it unminified
if ! git diff --quiet static/css/styles.css 2>/dev/null; then
    git add static/css/styles.css
fi

HAS_CHANGES=false
if ! git diff --quiet || ! git diff --cached --quiet || [ -n "$(git ls-files --others --exclude-standard)" ]; then
    HAS_CHANGES=true

    echo -e "${YELLOW}  Pending changes:${NC}"
    git status --short | while read -r line; do
        echo "    $line"
    done
    echo ""

    if [ "$DRY_RUN" = true ]; then
        echo -e "${YELLOW}Dry run - would commit the above changes, push dev, merge to master, and push.${NC}"
        echo ""
        echo -e "${YELLOW}Recent commits on dev (not yet on master):${NC}"
        git log master..dev --oneline 2>/dev/null | head -10
        exit 0
    fi

    # Get commit message
    if [ -z "$COMMIT_MSG" ]; then
        echo -e "${YELLOW}Enter commit message (or press Enter for auto-generated):${NC} "
        read -r USER_MSG
        if [ -n "$USER_MSG" ]; then
            COMMIT_MSG="$USER_MSG"
        else
            # Auto-generate from changed files
            CHANGED_FILES=$(git diff --name-only; git diff --cached --name-only; git ls-files --others --exclude-standard)
            FILE_COUNT=$(echo "$CHANGED_FILES" | sort -u | wc -l | tr -d ' ')
            COMMIT_MSG="Update $FILE_COUNT file(s) for deployment"
        fi
    fi

    # Stage and commit
    git add -A
    git commit -m "$COMMIT_MSG

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
    echo -e "${GREEN}  ✓ Committed: $COMMIT_MSG${NC}\n"
else
    echo -e "${GREEN}  ✓ Working tree clean${NC}\n"

    if [ "$DRY_RUN" = true ]; then
        echo -e "${YELLOW}Dry run - no pending changes. Would push dev, merge to master, and push.${NC}"
        echo ""
        echo -e "${YELLOW}Commits on dev not yet on master:${NC}"
        git log master..dev --oneline 2>/dev/null | head -10
        exit 0
    fi
fi

# Check if there's anything to deploy
COMMITS_AHEAD=$(git log master..dev --oneline 2>/dev/null | wc -l | tr -d ' ')
if [ "$COMMITS_AHEAD" -eq 0 ]; then
    echo -e "${GREEN}Nothing to deploy - dev and master are in sync.${NC}"
    exit 0
fi

echo -e "${YELLOW}Commits to deploy ($COMMITS_AHEAD):${NC}"
git log master..dev --oneline | head -20
echo ""

# --- Step 4: Push dev ---
echo -e "${BLUE}Step 3: Pushing dev to origin...${NC}"
git push origin dev
echo -e "${GREEN}  ✓ Pushed dev${NC}\n"

# --- Step 5: Merge to master ---
echo -e "${BLUE}Step 4: Merging dev into master...${NC}"
git checkout master
git pull origin master --quiet
git merge dev --no-edit
echo -e "${GREEN}  ✓ Merged dev into master${NC}\n"

# --- Step 6: Push master ---
echo -e "${BLUE}Step 5: Pushing master to origin (triggers Vercel deploy)...${NC}"
git push origin master
echo -e "${GREEN}  ✓ Pushed master${NC}\n"

# --- Step 7: Switch back to dev ---
git checkout dev --quiet

# Restart CSS watcher reminder
if [ "$CSS_WAS_RUNNING" = true ]; then
    echo -e "${YELLOW}Note: CSS watcher was stopped. Restart with:${NC}"
    echo -e "${YELLOW}  npm run watch:css${NC}\n"
fi

echo -e "${BOLD}${GREEN}======================================${NC}"
echo -e "${BOLD}${GREEN}  ✓ Published to production!${NC}"
echo -e "${BOLD}${GREEN}======================================${NC}"
echo ""
echo "Vercel will build and publish automatically."
echo "Back on dev branch."
