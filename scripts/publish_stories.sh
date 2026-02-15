#!/bin/bash
#
# EETHAL Foundation - Publish Stories Script
#
# Usage:
#   ./scripts/publish_stories.sh              # Review and commit new/changed stories
#   ./scripts/publish_stories.sh --push       # Commit and push to remote
#   ./scripts/publish_stories.sh --deploy     # Merge dev to master and deploy
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
DEPLOY=false

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
        --deploy)
            DEPLOY=true
            shift
            ;;
        --help|-h)
            echo "Usage: ./scripts/publish_stories.sh [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --dry-run    Show what would be committed without making changes"
            echo "  --push       Commit and push to remote (origin/dev)"
            echo "  --deploy     Merge dev to master and push (for production deployment)"
            echo "  --help       Show this help message"
            echo ""
            echo "Examples:"
            echo "  ./scripts/publish_stories.sh              # Review and commit"
            echo "  ./scripts/publish_stories.sh --push       # Commit and push to dev"
            echo "  ./scripts/publish_stories.sh --deploy     # Deploy to production (master)"
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

# Deploy mode: Merge dev to master and push
if [ "$DEPLOY" = true ]; then
    echo ""
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}  Deploying to Production (master)${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""

    # Check current branch
    CURRENT_BRANCH=$(git branch --show-current)

    if [ "$CURRENT_BRANCH" != "dev" ]; then
        echo -e "${RED}Error: Deploy must be run from dev branch${NC}"
        echo "Current branch: $CURRENT_BRANCH"
        echo ""
        echo "Switch to dev first:"
        echo "  git checkout dev"
        exit 1
    fi

    # Check if there are uncommitted changes
    if ! git diff --quiet || [ -n "$(git ls-files --others --exclude-standard)" ]; then
        echo -e "${RED}Error: You have uncommitted changes${NC}"
        echo "Please commit or stash your changes first:"
        echo "  git status"
        exit 1
    fi

    # Push dev to origin first
    echo -e "${BLUE}Step 1: Pushing dev to origin...${NC}"
    git push origin dev
    echo -e "${GREEN}✓ Pushed dev to origin${NC}\n"

    # Switch to master
    echo -e "${BLUE}Step 2: Switching to master branch...${NC}"
    git checkout master
    echo -e "${GREEN}✓ Switched to master${NC}\n"

    # Pull latest master
    echo -e "${BLUE}Step 3: Pulling latest master from origin...${NC}"
    git pull origin master
    echo -e "${GREEN}✓ Updated master${NC}\n"

    # Show what will be merged
    echo -e "${YELLOW}Commits that will be merged from dev:${NC}"
    git log master..dev --oneline --decorate | head -10
    echo ""

    # Ask for confirmation
    echo -e "${YELLOW}Do you want to merge dev to master and deploy? (yes/no):${NC} "
    read -r CONFIRM

    if [[ ! "$CONFIRM" =~ ^[Yy](es)?$ ]]; then
        echo -e "${YELLOW}Cancelled - switching back to dev${NC}"
        git checkout dev
        exit 0
    fi

    # Merge dev into master
    echo -e "\n${BLUE}Step 4: Merging dev into master...${NC}"
    git merge dev --no-edit -m "Merge dev to master for deployment"
    echo -e "${GREEN}✓ Merged dev into master${NC}\n"

    # Push master to origin
    echo -e "${BLUE}Step 5: Pushing master to origin...${NC}"
    git push origin master
    echo -e "${GREEN}✓ Pushed master to origin${NC}\n"

    # Switch back to dev
    echo -e "${BLUE}Step 6: Switching back to dev branch...${NC}"
    git checkout dev
    echo -e "${GREEN}✓ Back on dev${NC}\n"

    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}  ✓ Deployment Complete!${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo ""
    echo -e "${GREEN}Your changes are now live on master.${NC}"
    echo ""
    echo "Next steps:"
    echo "  - Check your deployment pipeline/CI"
    echo "  - Verify the production site"
    echo "  - Continue development on dev branch"
fi
