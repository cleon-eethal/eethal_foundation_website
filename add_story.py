#!/usr/bin/env python3
"""
EETHAL Foundation - Simplified Story Addition Script

Usage:
    python add_story.py \
        --english-title "My Big Family" \
        --tamil-title "என்னுடைய பெரிய குடும்பம்" \
        --english-pdf "https://drive.google.com/file/d/FILE_ID/view" \
        --tamil-pdf "https://drive.google.com/file/d/FILE_ID/view" \
        --translators "Name1, Name2" \
        --description "A heartwarming story about..." \
        --cover-image ~/Downloads/cover.jpg
"""

import argparse
import os
import re
import shutil
from datetime import date
from pathlib import Path


def convert_gdrive_url_to_preview(url: str) -> str:
    """
    Convert Google Drive share URL to embed/preview format.

    From: https://drive.google.com/file/d/FILE_ID/view?usp=sharing
    To: https://drive.google.com/file/d/FILE_ID/preview
    """
    patterns = [
        r'drive\.google\.com/file/d/([a-zA-Z0-9_-]+)',
        r'drive\.google\.com/open\?id=([a-zA-Z0-9_-]+)',
    ]

    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            file_id = match.group(1)
            return f"https://drive.google.com/file/d/{file_id}/preview"

    return url


def create_slug(title: str) -> str:
    """Create URL-friendly slug from title."""
    slug = title.lower()
    slug = re.sub(r'[^a-z0-9]+', '-', slug)
    slug = slug.strip('-')
    return slug


def create_story_frontmatter(
    english_title: str,
    tamil_title: str,
    description: str,
    english_pdf: str,
    tamil_pdf: str,
    translators: str,
    cover_image_filename: str
) -> str:
    """Generate Hugo front matter for the story."""

    # Convert PDF URLs to preview format
    english_pdf_preview = convert_gdrive_url_to_preview(english_pdf)
    tamil_pdf_preview = convert_gdrive_url_to_preview(tamil_pdf)

    # Parse translators
    translator_list = [t.strip() for t in translators.split(',')]
    translators_yaml = '\n'.join([f'    - "{t}"' for t in translator_list])

    frontmatter = f'''---
title: "{english_title}"
description: "{description}"
date: {date.today().isoformat()}

pdfs:
  tamil: "{tamil_pdf_preview}"
  english: "{english_pdf_preview}"

titles:
  english: "{english_title}"
  tamil: "{tamil_title}"

translators:
{translators_yaml}

coverImage: "{cover_image_filename}"
draft: false
---
'''

    return frontmatter


def create_story(
    english_title: str,
    tamil_title: str,
    description: str,
    english_pdf: str,
    tamil_pdf: str,
    translators: str,
    cover_image_path: str
):
    """Create a new story directory with all necessary files."""

    # Create slug from English title
    slug = create_slug(english_title)

    # Create story directory
    content_dir = Path('content/stories') / slug
    content_dir.mkdir(parents=True, exist_ok=True)

    print(f"Creating story: {slug}")
    print(f"Directory: {content_dir}")

    # Copy cover image
    cover_image_path = Path(cover_image_path).expanduser()
    if not cover_image_path.exists():
        print(f"Error: Cover image not found at {cover_image_path}")
        return

    cover_extension = cover_image_path.suffix
    cover_filename = f"cover{cover_extension}"
    cover_dest = content_dir / cover_filename
    shutil.copy2(cover_image_path, cover_dest)
    print(f"Copied cover image: {cover_dest}")

    # Create index.md with front matter
    index_md = content_dir / 'index.md'
    frontmatter = create_story_frontmatter(
        english_title,
        tamil_title,
        description,
        english_pdf,
        tamil_pdf,
        translators,
        cover_filename
    )

    index_md.write_text(frontmatter, encoding='utf-8')
    print(f"Created story file: {index_md}")

    print("\n✅ Story created successfully!")
    print(f"\nNext steps:")
    print(f"1. Preview locally: hugo server -D")
    print(f"2. View at: http://localhost:1313/stories/{slug}/")
    print(f"3. Commit: git add content/stories/{slug} && git commit -m 'Add story: {english_title}'")


def main():
    parser = argparse.ArgumentParser(
        description='Add a new bilingual story to the EETHAL Foundation website'
    )

    parser.add_argument(
        '--english-title',
        required=True,
        help='Story title in English'
    )

    parser.add_argument(
        '--tamil-title',
        required=True,
        help='Story title in Tamil'
    )

    parser.add_argument(
        '--english-pdf',
        required=True,
        help='Google Drive URL for English PDF'
    )

    parser.add_argument(
        '--tamil-pdf',
        required=True,
        help='Google Drive URL for Tamil PDF'
    )

    parser.add_argument(
        '--translators',
        required=True,
        help='Comma-separated list of translator names'
    )

    parser.add_argument(
        '--description',
        required=True,
        help='Brief description of the story'
    )

    parser.add_argument(
        '--cover-image',
        required=True,
        help='Path to cover image file'
    )

    args = parser.parse_args()

    create_story(
        english_title=args.english_title,
        tamil_title=args.tamil_title,
        description=args.description,
        english_pdf=args.english_pdf,
        tamil_pdf=args.tamil_pdf,
        translators=args.translators,
        cover_image_path=args.cover_image
    )


if __name__ == '__main__':
    main()
