#!/bin/bash
#
# EETHAL Foundation - Publish Stories Script
#
# Usage:
#   ./scripts/publish_stories.sh              # Review and commit new/changed stories
#   ./scripts/publish_stories.sh --push       # Commit and push to remote
#   ./scripts/publish_stories.sh --dry-run    # Show what would be committed
#

set -e  # Exit on error

# Color codes for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Parse arguments
DRY_RUN=false
PUSH=false

for arg in "$@"; do
    case $arg in
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --push)
            PUSH=true
            shift
            ;;
        --help|-h)
            echo "Usage: ./scripts/publish_stories.sh [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --dry-run    Show what would be committed without making changes"
            echo "  --push       Commit and push to remote (origin/dev)"
            echo "  --help       Show this help message"
            echo ""
            echo "Examples:"
            echo "  ./scripts/publish_stories.sh              # Review and commit"
            echo "  ./scripts/publish_stories.sh --push       # Commit and push"
            echo "  ./scripts/publish_stories.sh --dry-run    # Preview changes"
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $arg${NC}"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Check if we're in the repository root
if [ ! -d "content/stories" ]; then
    echo -e "${RED}Error: content/stories/ directory not found${NC}"
    echo "Please run this script from the repository root"
    exit 1
fi

# Check if git repo exists
if [ ! -d ".git" ]; then
    echo -e "${RED}Error: Not a git repository${NC}"
    exit 1
fi

# Check for changes in content/stories/
echo -e "${BLUE}Checking for story changes...${NC}\n"

if ! git diff --quiet content/stories/ || [ -n "$(git ls-files --others --exclude-standard content/stories/)" ]; then
    # Get current branch
    CURRENT_BRANCH=$(git branch --show-current)

    echo -e "${YELLOW}Current branch:${NC} $CURRENT_BRANCH\n"

    # Show new/modified stories
    echo -e "${YELLOW}Changes in content/stories/:${NC}"
    git status --short content/stories/ | while read -r line; do
        echo "  $line"
    done
    echo ""

    # Count new story directories
    NEW_STORIES=$(git ls-files --others --exclude-standard content/stories/*/index.md | wc -l | tr -d ' ')
    MODIFIED_STORIES=$(git diff --name-only content/stories/*/index.md | wc -l | tr -d ' ')

    echo -e "${GREEN}Summary:${NC}"
    echo "  New stories: $NEW_STORIES"
    echo "  Modified stories: $MODIFIED_STORIES"
    echo ""

    # Dry run mode
    if [ "$DRY_RUN" = true ]; then
        echo -e "${BLUE}Dry run mode - showing what would be committed:${NC}\n"
        git diff --stat content/stories/
        echo ""
        echo -e "${YELLOW}No changes made (dry run)${NC}"
        exit 0
    fi

    # Ask for confirmation
    echo -e "${YELLOW}Do you want to commit these changes? (yes/no):${NC} "
    read -r CONFIRM

    if [[ ! "$CONFIRM" =~ ^[Yy](es)?$ ]]; then
        echo -e "${YELLOW}Cancelled${NC}"
        exit 0
    fi

    # Generate commit message
    if [ "$NEW_STORIES" -gt 0 ] && [ "$MODIFIED_STORIES" -eq 0 ]; then
        COMMIT_MSG="Add $NEW_STORIES new $([ "$NEW_STORIES" -eq 1 ] && echo "story" || echo "stories")"
    elif [ "$NEW_STORIES" -eq 0 ] && [ "$MODIFIED_STORIES" -gt 0 ]; then
        COMMIT_MSG="Update $MODIFIED_STORIES $([ "$MODIFIED_STORIES" -eq 1 ] && echo "story" || echo "stories")"
    else
        COMMIT_MSG="Add $NEW_STORIES new and update $MODIFIED_STORIES existing $([ $((NEW_STORIES + MODIFIED_STORIES)) -eq 1 ] && echo "story" || echo "stories")"
    fi

    # Stage changes
    echo -e "\n${BLUE}Staging changes...${NC}"
    git add content/stories/

    # Create commit
    echo -e "${BLUE}Creating commit...${NC}"
    git commit -m "$COMMIT_MSG

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"

    echo -e "${GREEN}✓ Committed: $COMMIT_MSG${NC}\n"

    # Push if requested
    if [ "$PUSH" = true ]; then
        echo -e "${BLUE}Pushing to origin/$CURRENT_BRANCH...${NC}"
        git push origin "$CURRENT_BRANCH"
        echo -e "${GREEN}✓ Pushed to origin/$CURRENT_BRANCH${NC}"
    else
        echo -e "${YELLOW}To push these changes, run:${NC}"
        echo "  git push origin $CURRENT_BRANCH"
        echo ""
        echo -e "${YELLOW}Or use:${NC}"
        echo "  ./scripts/publish_stories.sh --push"
    fi

else
    echo -e "${GREEN}No changes detected in content/stories/${NC}"
    echo "All stories are already committed."
fi
