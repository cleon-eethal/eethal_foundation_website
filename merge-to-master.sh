#!/bin/bash
set -e

# Push dev branch to remote
git push origin dev

# Switch to master and pull latest
git checkout master
git pull origin master

# Merge dev into master
git merge dev

# Push master to remote
git push origin master

# Switch back to dev
git checkout dev

echo "Done! Merged dev into master and returned to dev branch."
