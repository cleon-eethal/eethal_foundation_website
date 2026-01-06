#!/usr/bin/env python3
"""
EETHAL Foundation - Story Addition Script
Automates the creation of bilingual story pages for the Hugo website.

Usage:
    python add_story.py --interactive
    python add_story.py --config story_config.json
    python add_story.py --storyweaver --english-dir ~/Downloads/22924-my-big-family --tamil-dir ~/Downloads/428213-ennudaya-perriya-kudumbam --english-gdrive "..." --tamil-gdrive "..." --cover-image ~/Downloads/my-big-family.jpg
"""

import argparse
import json
import os
import re
import shutil
from datetime import date
from pathlib import Path
from typing import Dict, Optional, Tuple


def convert_gdrive_url_to_preview(url: str) -> str:
    """
    Convert Google Drive share URL to embed/preview format.

    From: https://drive.google.com/file/d/FILE_ID/view?usp=sharing
    To: https://drive.google.com/file/d/FILE_ID/preview
    """
    # Extract FILE_ID from various Google Drive URL formats
    patterns = [
        r'drive\.google\.com/file/d/([a-zA-Z0-9_-]+)',
        r'drive\.google\.com/open\?id=([a-zA-Z0-9_-]+)',
    ]

    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            file_id = match.group(1)
            return f"https://drive.google.com/file/d/{file_id}/preview"

    # If already in preview format or unrecognized, return as-is
    return url


def create_slug(title: str) -> str:
    """Create URL-friendly slug from title."""
    slug = title.lower()
    slug = re.sub(r'[^a-z0-9]+', '-', slug)
    slug = slug.strip('-')
    return slug


def parse_metadata_file(filepath: str) -> Dict[str, str]:
    """
    Parse metadata from text file.

    Expected format:
        title: My Big Family
        description: A heartwarming story...
        original_author: Author Name
        translators: Name1, Name2, Name3
        age_group: 6-10 years
        genre: Family
        ...
    """
    metadata = {}

    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue

            if ':' in line:
                key, value = line.split(':', 1)
                metadata[key.strip()] = value.strip()

    return metadata


def find_pdf_in_directory(directory: str) -> Optional[str]:
    """
    Find PDF file in directory.
    Returns the first .pdf file found, or None if no PDF exists.
    """
    dir_path = Path(directory).expanduser()

    if not dir_path.exists():
        return None

    for file in dir_path.iterdir():
        if file.suffix.lower() == '.pdf':
            return str(file)

    return None


def parse_storyweaver_attribution(filepath: str) -> Tuple[str, str, str]:
    """
    Parse StoryWeaver attribution file.

    Returns: (title, attribution_text, more_info_url)

    Expected format:
        Title: My Big Family

        The CC BY 4.0 license REQUIRES...

        Attribution Text: My Big Family (English), translated by...

        [Find out more at : https://storyweaver.org.in/attributions]
    """
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Extract title
    title_match = re.search(r'^Title:\s*(.+)$', content, re.MULTILINE)
    title = title_match.group(1).strip() if title_match else ""

    # Extract attribution text
    attribution_match = re.search(r'Attribution Text:\s*(.+?)(?:\n\n|\[Find)', content, re.DOTALL)
    attribution_text = attribution_match.group(1).strip() if attribution_match else ""

    # Extract more info URL
    url_match = re.search(r'\[Find out more at\s*:\s*(.+?)\]', content)
    more_info_url = url_match.group(1).strip() if url_match else "https://storyweaver.org.in/attributions"

    return title, attribution_text, more_info_url


def extract_metadata_from_attribution(attribution_text: str) -> Dict[str, str]:
    """
    Extract metadata from StoryWeaver attribution text.

    Example attribution text:
    "My Big Family (English), translated by Alisha Berger, based on original story
    Nhà có đông người thì sao? (Vietnamese), written by Lưu Thị Lương,
    illustrated by Lê Thị Anh Thư, published by Room to Read (© Room to Read, 2015)
    under a CC BY 4.0 license on StoryWeaver."

    Returns dict with: translators, original_author, illustrator, publisher
    """
    metadata = {}

    # Extract translator(s)
    translator_match = re.search(r'translated by ([^,]+)', attribution_text)
    if translator_match:
        metadata['translators'] = translator_match.group(1).strip()

    # Extract original author
    author_match = re.search(r'written by ([^,]+)', attribution_text)
    if author_match:
        metadata['original_author'] = author_match.group(1).strip()

    # Extract illustrator
    illustrator_match = re.search(r'illustrated by ([^,]+)', attribution_text)
    if illustrator_match:
        metadata['illustrator'] = illustrator_match.group(1).strip()

    # Extract publisher
    publisher_match = re.search(r'published by ([^(]+)', attribution_text)
    if publisher_match:
        metadata['publisher'] = publisher_match.group(1).strip()

    # Extract original title
    original_title_match = re.search(r'based on original story ([^(]+)\s*\(', attribution_text)
    if original_title_match:
        metadata['original_title'] = original_title_match.group(1).strip()

    return metadata


def create_story_frontmatter(
    title: str,
    description: str,
    tamil_pdf_url: str,
    english_pdf_url: str,
    metadata: Dict[str, str],
    has_cover_image: bool = False,
    attribution: Optional[Dict[str, str]] = None,
    tamil_title: Optional[str] = None
) -> str:
    """Generate YAML front matter for story."""

    # Parse translators (comma-separated)
    translators = metadata.get('translators', 'Unknown').split(',')
    translators = [f'    - "{t.strip()}"' for t in translators]
    translators_yaml = '\n'.join(translators)

    # Build front matter
    frontmatter = f'''---
title: "{title}"
description: "{description}"
date: {date.today().isoformat()}

# Google Drive PDF URLs
pdfs:
  tamil: "{convert_gdrive_url_to_preview(tamil_pdf_url)}"
  english: "{convert_gdrive_url_to_preview(english_pdf_url)}"

# Story titles
titles:
  english: "{title}"
  tamil: "{tamil_title if tamil_title else title}"

# Story metadata
metadata:'''

    # Add metadata fields only if they exist
    if metadata.get('original_author'):
        frontmatter += f'\n  originalAuthor: "{metadata.get("original_author")}"'
    if metadata.get('original_url'):
        frontmatter += f'\n  originalUrl: "{metadata.get("original_url")}"'
    if metadata.get('translators'):
        frontmatter += f'\n  translators:\n{translators_yaml}'
    if metadata.get('translation_date'):
        frontmatter += f'\n  translationDate: "{metadata.get("translation_date")}"'
    if metadata.get('age_group'):
        frontmatter += f'\n  ageGroup: "{metadata.get("age_group")}"'
    if metadata.get('genre'):
        frontmatter += f'\n  genre: "{metadata.get("genre")}"'
    if metadata.get('reading_level'):
        frontmatter += f'\n  readingLevel: "{metadata.get("reading_level")}"'
    if metadata.get('illustrator'):
        frontmatter += f'\n  illustrator: "{metadata.get("illustrator")}"'
    if metadata.get('publisher'):
        frontmatter += f'\n  publisher: "{metadata.get("publisher")}"'

    frontmatter += '\n'

    # Add cover image if provided
    if has_cover_image:
        frontmatter += '\n# Cover image (relative path within page bundle)\ncoverImage: "cover.jpg"\n'

    # Add attribution if provided
    if attribution:
        frontmatter += '''
# Attribution for CC BY 4.0 licensed content
attribution:
  required: true
'''
        if attribution.get('license'):
            frontmatter += f'  license: "{attribution.get("license")}"\n'

        # Handle both new format (english_text/tamil_text) and old format (text)
        if attribution.get('english_text') or attribution.get('tamil_text'):
            if attribution.get('english_text'):
                frontmatter += f'  englishText: "{attribution.get("english_text")}"\n'
            if attribution.get('tamil_text'):
                frontmatter += f'  tamilText: "{attribution.get("tamil_text")}"\n'
        elif attribution.get('text'):
            # Backward compatibility for old format
            frontmatter += f'  text: "{attribution.get("text")}"\n'

        if attribution.get('more_info_url'):
            frontmatter += f'  moreInfoUrl: "{attribution.get("more_info_url")}"\n'

    frontmatter += '\n# Draft status - set to false when ready to publish\ndraft: false\n---\n'

    return frontmatter


def create_story_content(
    about_text: str = "",
    translator_notes: str = "",
    custom_sections: Optional[Dict[str, str]] = None
) -> str:
    """Generate markdown content for story."""

    content = ""

    if about_text:
        content += f"\n## About This Story\n\n{about_text}\n"

    if translator_notes:
        content += f"\n## Translator Notes\n\n{translator_notes}\n"

    if custom_sections:
        for heading, text in custom_sections.items():
            content += f"\n## {heading}\n\n{text}\n"

    return content


def create_story(
    title: str,
    description: str,
    tamil_pdf_url: str,
    english_pdf_url: str,
    metadata_file: str,
    cover_image_path: Optional[str] = None,
    about_text: str = "",
    translator_notes: str = "",
    attribution: Optional[Dict[str, str]] = None,
    tamil_title: Optional[str] = None,
    content_dir: str = "content/stories"
) -> str:
    """
    Create a new story in the Hugo site.

    Returns the path to the created story directory.
    """

    # Parse metadata
    metadata = parse_metadata_file(metadata_file)

    # Override with any metadata from arguments
    if not metadata.get('title'):
        metadata['title'] = title
    if not metadata.get('description'):
        metadata['description'] = description

    # Create slug for directory name
    slug = create_slug(title)
    story_dir = Path(content_dir) / slug

    # Create directory
    story_dir.mkdir(parents=True, exist_ok=True)
    print(f"✓ Created directory: {story_dir}")

    # Copy cover image if provided
    has_cover = False
    if cover_image_path and os.path.exists(cover_image_path):
        cover_ext = Path(cover_image_path).suffix
        cover_dest = story_dir / f"cover{cover_ext}"
        shutil.copy2(cover_image_path, cover_dest)
        print(f"✓ Copied cover image: {cover_dest}")
        has_cover = True

        # Update frontmatter to use correct extension
        if cover_ext != '.jpg':
            has_cover = f"cover{cover_ext}"

    # Generate front matter
    frontmatter = create_story_frontmatter(
        title=title,
        description=description,
        tamil_pdf_url=tamil_pdf_url,
        english_pdf_url=english_pdf_url,
        metadata=metadata,
        has_cover_image=has_cover,
        attribution=attribution,
        tamil_title=tamil_title
    )

    # Generate content
    content = create_story_content(
        about_text=about_text or metadata.get('about', ''),
        translator_notes=translator_notes or metadata.get('translator_notes', '')
    )

    # Write index.md
    index_path = story_dir / "index.md"
    with open(index_path, 'w', encoding='utf-8') as f:
        f.write(frontmatter)
        f.write(content)

    print(f"✓ Created story file: {index_path}")
    print(f"\n✅ Story '{title}' created successfully!")
    print(f"📁 Location: {story_dir}")
    print(f"🌐 Will be available at: /stories/{slug}/")

    return str(story_dir)


def interactive_mode():
    """Run script in interactive mode with prompts."""

    print("\n" + "="*60)
    print("  EETHAL Foundation - Story Addition Tool")
    print("="*60 + "\n")

    # Basic info
    print("📖 BASIC INFORMATION\n")
    title = input("Story Title: ").strip()
    description = input("Short Description: ").strip()

    # PDF URLs
    print("\n📄 PDF FILES (Google Drive URLs)\n")
    tamil_pdf = input("Tamil PDF URL: ").strip()
    english_pdf = input("English PDF URL: ").strip()

    # Metadata file
    print("\n📋 METADATA\n")
    metadata_file = input("Path to metadata file: ").strip()

    if not os.path.exists(metadata_file):
        print(f"❌ Error: Metadata file not found: {metadata_file}")
        return

    # Cover image
    print("\n🖼️  COVER IMAGE (optional)\n")
    cover_image = input("Path to cover image (press Enter to skip): ").strip()

    # Additional content
    print("\n✍️  STORY CONTENT (optional)\n")
    print("Enter 'About This Story' text (press Enter twice when done):")
    about_lines = []
    while True:
        line = input()
        if not line:
            break
        about_lines.append(line)
    about_text = '\n'.join(about_lines)

    print("\nEnter 'Translator Notes' text (press Enter twice when done):")
    notes_lines = []
    while True:
        line = input()
        if not line:
            break
        notes_lines.append(line)
    translator_notes = '\n'.join(notes_lines)

    # Attribution
    print("\n📜 ATTRIBUTION (optional)\n")
    has_attribution = input("Does this story require CC BY attribution? (y/n): ").strip().lower()

    attribution = None
    if has_attribution == 'y':
        attribution = {
            'license': input("License (e.g., CC BY 4.0): ").strip(),
            'text': input("Full attribution text: ").strip(),
            'more_info_url': input("More info URL: ").strip()
        }

    # Confirm
    print("\n" + "="*60)
    print("📝 SUMMARY")
    print("="*60)
    print(f"Title: {title}")
    print(f"Slug: {create_slug(title)}")
    print(f"Tamil PDF: {tamil_pdf[:50]}...")
    print(f"English PDF: {english_pdf[:50]}...")
    print(f"Metadata: {metadata_file}")
    print(f"Cover Image: {cover_image or 'None'}")
    print(f"Attribution: {'Yes' if attribution else 'No'}")
    print("="*60 + "\n")

    confirm = input("Create this story? (y/n): ").strip().lower()

    if confirm == 'y':
        create_story(
            title=title,
            description=description,
            tamil_pdf_url=tamil_pdf,
            english_pdf_url=english_pdf,
            metadata_file=metadata_file,
            cover_image_path=cover_image if cover_image else None,
            about_text=about_text,
            translator_notes=translator_notes,
            attribution=attribution
        )
    else:
        print("❌ Story creation cancelled.")


def config_mode(config_file: str):
    """Run script with JSON config file."""

    with open(config_file, 'r', encoding='utf-8') as f:
        config = json.load(f)

    create_story(
        title=config['title'],
        description=config['description'],
        tamil_pdf_url=config['tamil_pdf_url'],
        english_pdf_url=config['english_pdf_url'],
        metadata_file=config['metadata_file'],
        cover_image_path=config.get('cover_image'),
        about_text=config.get('about_text', ''),
        translator_notes=config.get('translator_notes', ''),
        attribution=config.get('attribution'),
        content_dir=config.get('content_dir', 'content/stories')
    )


def storyweaver_mode(
    english_dir: str,
    tamil_dir: str,
    english_gdrive_url: str,
    tamil_gdrive_url: str,
    cover_image_path: str,
    translator: Optional[str] = None,
    description: Optional[str] = None,
    original_url: Optional[str] = None,
    content_dir: str = "content/stories"
):
    """
    Create story from StoryWeaver download directories.

    Args:
        english_dir: Path to English StoryWeaver download directory
        tamil_dir: Path to Tamil StoryWeaver download directory
        english_gdrive_url: Google Drive URL for English PDF
        tamil_gdrive_url: Google Drive URL for Tamil PDF
        cover_image_path: Path to cover image file
        translator: Name(s) of translator(s) for this version (overrides attribution)
        description: Story description (optional, auto-generated if not provided)
        original_url: URL to original story (optional, defaults to StoryWeaver)
        content_dir: Hugo content directory for stories
    """
    print("\n" + "="*60)
    print("  EETHAL Foundation - StoryWeaver Import")
    print("="*60 + "\n")

    # Expand paths
    english_dir = os.path.expanduser(english_dir)
    tamil_dir = os.path.expanduser(tamil_dir)
    cover_image_path = os.path.expanduser(cover_image_path)

    # Find attribution files
    print("🔍 Looking for StoryWeaver attribution files...\n")

    english_attr_file = None
    tamil_attr_file = None

    # Find English attribution file
    for file in Path(english_dir).iterdir():
        if file.name.startswith('StoryWeaverAttribution') and file.suffix == '.txt':
            english_attr_file = str(file)
            print(f"✓ Found English attribution: {file.name}")
            break

    # Find Tamil attribution file
    for file in Path(tamil_dir).iterdir():
        if file.name.startswith('StoryWeaverAttribution') and file.suffix == '.txt':
            tamil_attr_file = str(file)
            print(f"✓ Found Tamil attribution: {file.name}")
            break

    if not english_attr_file:
        print(f"❌ Error: No StoryWeaver attribution file found in {english_dir}")
        return

    if not tamil_attr_file:
        print(f"❌ Error: No StoryWeaver attribution file found in {tamil_dir}")
        return

    # Parse English attribution (use as primary metadata source)
    print("\n📖 Parsing attribution files...\n")

    english_title, english_attribution, more_info_url = parse_storyweaver_attribution(english_attr_file)
    tamil_title, tamil_attribution, _ = parse_storyweaver_attribution(tamil_attr_file)

    print(f"English Title: {english_title}")
    print(f"Tamil Title: {tamil_title}")

    # Extract metadata from English attribution text
    metadata = extract_metadata_from_attribution(english_attribution)

    # Override translator if provided via command line
    if translator:
        metadata['translators'] = translator

    # Override original URL if provided
    if original_url:
        metadata['original_url'] = original_url
    elif not metadata.get('original_url'):
        metadata['original_url'] = 'https://storyweaver.org.in'

    print(f"\n📋 Extracted Metadata:")
    if metadata.get('original_author'):
        print(f"  Original Author: {metadata.get('original_author')}")
    if metadata.get('translators'):
        print(f"  Translator: {metadata.get('translators')}")
    if metadata.get('illustrator'):
        print(f"  Illustrator: {metadata.get('illustrator')}")
    if metadata.get('publisher'):
        print(f"  Publisher: {metadata.get('publisher')}")
    if metadata.get('original_url'):
        print(f"  Original URL: {metadata.get('original_url')}")

    # Create temporary metadata file (for create_story function compatibility)
    # Only include fields that have values
    import tempfile
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt', encoding='utf-8') as tmp:
        for key, value in metadata.items():
            if value:  # Only write non-empty values
                tmp.write(f"{key}: {value}\n")
        temp_metadata_file = tmp.name

    # Use provided description or auto-generate
    if not description:
        description = f"A bilingual story translated by EETHAL students - {english_title}"

    # Build attribution dict for both languages
    attribution = {
        'license': 'CC BY 4.0',
        'english_text': english_attribution,
        'tamil_text': tamil_attribution,
        'more_info_url': more_info_url
    }

    # Verify cover image exists
    if not os.path.exists(cover_image_path):
        print(f"\n⚠️  Warning: Cover image not found: {cover_image_path}")
        cover_image_path = None

    # Summary
    print("\n" + "="*60)
    print("📝 IMPORT SUMMARY")
    print("="*60)
    print(f"Title: {english_title}")
    print(f"Slug: {create_slug(english_title)}")
    print(f"English Attribution File: {os.path.basename(english_attr_file)}")
    print(f"Tamil Attribution File: {os.path.basename(tamil_attr_file)}")
    print(f"Cover Image: {cover_image_path or 'None'}")
    print(f"Attribution License: CC BY 4.0")
    print("="*60 + "\n")

    # Create story
    try:
        create_story(
            title=english_title,
            description=description,
            tamil_pdf_url=tamil_gdrive_url,
            english_pdf_url=english_gdrive_url,
            metadata_file=temp_metadata_file,
            cover_image_path=cover_image_path,
            about_text="",
            translator_notes="",
            attribution=attribution,
            tamil_title=tamil_title,
            content_dir=content_dir
        )
    finally:
        # Clean up temp file
        if os.path.exists(temp_metadata_file):
            os.unlink(temp_metadata_file)


def main():
    parser = argparse.ArgumentParser(
        description='Add a new bilingual story to the EETHAL Foundation website'
    )

    parser.add_argument(
        '--interactive', '-i',
        action='store_true',
        help='Run in interactive mode with prompts'
    )

    parser.add_argument(
        '--config', '-c',
        type=str,
        help='Path to JSON config file'
    )

    parser.add_argument(
        '--storyweaver',
        action='store_true',
        help='Import from StoryWeaver download directories'
    )

    parser.add_argument(
        '--english-dir',
        type=str,
        help='Path to English StoryWeaver download directory'
    )

    parser.add_argument(
        '--tamil-dir',
        type=str,
        help='Path to Tamil StoryWeaver download directory'
    )

    parser.add_argument(
        '--english-gdrive',
        type=str,
        help='Google Drive URL for English PDF'
    )

    parser.add_argument(
        '--tamil-gdrive',
        type=str,
        help='Google Drive URL for Tamil PDF'
    )

    parser.add_argument(
        '--translator',
        type=str,
        help='Translator name(s) for this story (overrides attribution file)'
    )

    parser.add_argument(
        '--story-description',
        type=str,
        help='Story description (for StoryWeaver mode, overrides auto-generated)'
    )

    parser.add_argument(
        '--original-url',
        type=str,
        help='URL to original story (defaults to StoryWeaver if not provided)'
    )

    parser.add_argument(
        '--title', '-t',
        type=str,
        help='Story title'
    )

    parser.add_argument(
        '--description', '-d',
        type=str,
        help='Story description'
    )

    parser.add_argument(
        '--tamil-pdf',
        type=str,
        help='Google Drive URL for Tamil PDF'
    )

    parser.add_argument(
        '--english-pdf',
        type=str,
        help='Google Drive URL for English PDF'
    )

    parser.add_argument(
        '--metadata',
        type=str,
        help='Path to metadata file'
    )

    parser.add_argument(
        '--cover-image',
        type=str,
        help='Path to cover image'
    )

    args = parser.parse_args()

    if args.interactive:
        interactive_mode()
    elif args.config:
        config_mode(args.config)
    elif args.storyweaver:
        # StoryWeaver mode - import from downloaded directories
        if not all([args.english_dir, args.tamil_dir, args.english_gdrive, args.tamil_gdrive, args.cover_image]):
            print("❌ Error: StoryWeaver mode requires:")
            print("  --english-dir (path to English StoryWeaver directory)")
            print("  --tamil-dir (path to Tamil StoryWeaver directory)")
            print("  --english-gdrive (Google Drive URL for English PDF)")
            print("  --tamil-gdrive (Google Drive URL for Tamil PDF)")
            print("  --cover-image (path to cover image)")
            print("\nOptional parameters:")
            print("  --translator (translator name, overrides attribution)")
            print("  --story-description (custom description, otherwise auto-generated)")
            print("  --original-url (URL to original story, defaults to StoryWeaver)")
            print("\nExample:")
            print("  python add_story.py --storyweaver \\")
            print("    --english-dir ~/Downloads/22924-my-big-family \\")
            print("    --tamil-dir ~/Downloads/428213-ennudaya-perriya-kudumbam \\")
            print("    --english-gdrive 'https://drive.google.com/file/d/...' \\")
            print("    --tamil-gdrive 'https://drive.google.com/file/d/...' \\")
            print("    --cover-image ~/Downloads/my-big-family.jpg \\")
            print("    --translator 'Student Name' \\")
            print("    --story-description 'A heartwarming tale about family' \\")
            print("    --original-url 'https://storyweaver.org.in/stories/12345'")
            return

        storyweaver_mode(
            english_dir=args.english_dir,
            tamil_dir=args.tamil_dir,
            english_gdrive_url=args.english_gdrive,
            tamil_gdrive_url=args.tamil_gdrive,
            cover_image_path=args.cover_image,
            translator=args.translator,
            description=args.story_description,
            original_url=args.original_url
        )
    elif args.title and args.tamil_pdf and args.english_pdf and args.metadata:
        create_story(
            title=args.title,
            description=args.description or "",
            tamil_pdf_url=args.tamil_pdf,
            english_pdf_url=args.english_pdf,
            metadata_file=args.metadata,
            cover_image_path=args.cover_image
        )
    else:
        parser.print_help()
        print("\n💡 Tips:")
        print("  - Use --interactive for guided story creation")
        print("  - Use --storyweaver to import from StoryWeaver downloads")


if __name__ == '__main__':
    main()
