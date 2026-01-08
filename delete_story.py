#!/usr/bin/env python3
"""
EETHAL Foundation - Story Deletion Script

Usage:
    # List all stories
    python delete_story.py --list

    # Delete a story
    python delete_story.py portrai-of-life

    # Delete without confirmation
    python delete_story.py portrai-of-life --force
"""

import argparse
import shutil
import sys
from pathlib import Path


def list_stories() -> list[str]:
    """
    List all stories in the content/stories directory.

    Returns:
        List of story slugs
    """
    stories_dir = Path('content/stories')
    if not stories_dir.exists():
        return []

    stories = []
    for item in stories_dir.iterdir():
        if item.is_dir() and item.name != '.' and not item.name.startswith('_'):
            stories.append(item.name)

    return sorted(stories)


def delete_story(slug: str, force: bool = False) -> bool:
    """
    Delete a story by its slug.

    Args:
        slug: Story slug (directory name)
        force: Skip confirmation if True

    Returns:
        True if deleted, False otherwise
    """
    story_dir = Path('content/stories') / slug

    # Check if story exists
    if not story_dir.exists():
        print(f"Error: Story '{slug}' not found")
        print(f"\nAvailable stories:")
        for s in list_stories():
            print(f"  - {s}")
        return False

    # Show what will be deleted
    files = list(story_dir.glob('*'))
    print(f"Story to delete: {slug}")
    print(f"Location: {story_dir}")
    print(f"Files to be removed:")
    for f in files:
        print(f"  - {f.name}")

    # Confirm deletion
    if not force:
        response = input(f"\nAre you sure you want to delete '{slug}'? (yes/no): ")
        if response.lower() not in ['yes', 'y']:
            print("Deletion cancelled")
            return False

    # Delete the directory
    try:
        shutil.rmtree(story_dir)
        print(f"\n✅ Story '{slug}' deleted successfully")

        # Check if git repo exists
        git_dir = Path('.git')
        if git_dir.exists():
            print(f"\nNext steps:")
            print(f"1. Commit the deletion:")
            print(f"   git add content/stories/{slug}")
            print(f"   git commit -m 'Delete story: {slug}'")

        return True

    except Exception as e:
        print(f"Error deleting story: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description='Delete a story from the EETHAL Foundation website'
    )

    parser.add_argument(
        'slug',
        nargs='?',
        help='Story slug (directory name) to delete'
    )

    parser.add_argument(
        '--list',
        action='store_true',
        help='List all available stories'
    )

    parser.add_argument(
        '--force',
        action='store_true',
        help='Delete without confirmation'
    )

    args = parser.parse_args()

    # List mode
    if args.list or not args.slug:
        stories = list_stories()
        if not stories:
            print("No stories found in content/stories/")
            sys.exit(0)

        print(f"Available stories ({len(stories)}):")
        for story in stories:
            story_dir = Path('content/stories') / story
            index_md = story_dir / 'index.md'

            # Try to read title from index.md
            title = story
            if index_md.exists():
                try:
                    content = index_md.read_text(encoding='utf-8')
                    for line in content.split('\n'):
                        if line.startswith('title:'):
                            title = line.split('title:')[1].strip().strip('"')
                            break
                except Exception:
                    pass

            print(f"  - {story:30} ({title})")

        if not args.slug:
            print("\nUsage: python delete_story.py <slug>")
            sys.exit(0)

    # Delete mode
    else:
        success = delete_story(args.slug, args.force)
        sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
