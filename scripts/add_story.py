#!/usr/bin/env python3
"""
EETHAL Foundation - Story Addition Script

Downloads story data from the EETHAL Foundation Google Spreadsheet and creates
Hugo content pages with front matter, cover images, and bilingual descriptions.

Usage:
    python add_story.py                    # process all stories (skip done)
    python add_story.py --rows 5-10        # process spreadsheet rows 5 through 10
    python add_story.py --rows 7           # process only spreadsheet row 7
    python add_story.py --rows 7 --force   # re-process row 7 (ignore done, re-download image)

CSV Format (from Google Sheet):
    Required columns: English Title, Tamil Title, English PDF, Tamil PDF,
                     Image, Translators, English Description, Tamil Description
    Image column should contain Google Drive share URLs
"""

import argparse
import csv
import imghdr
import re
import shutil
import ssl
import sys
import urllib.request
from datetime import date
from pathlib import Path
from typing import Optional


# Project root (parent of the scripts/ directory this file lives in)
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Default Google Sheets URL
DEFAULT_GOOGLE_SHEET_URL = "https://docs.google.com/spreadsheets/d/1zNhXLL_De8qCsk8OlORGQ_0tIk9Bw3aKi72HlSTEAOU/edit?usp=sharing"

# CSV column name mapping
CSV_COLUMNS = {
    'english_title': 'English Title',
    'tamil_title': 'Tamil Title',
    'english_pdf': 'English PDF',
    'tamil_pdf': 'Tamil PDF',
    'image': 'Image',
    'translators': 'Translators',
    'english_description': 'English Description',
    'tamil_description': 'Tamil Description',
    'status': 'Status',
    'tags': 'Tags',
}


def extract_google_sheet_id(url: str) -> Optional[str]:
    """
    Extract spreadsheet ID from Google Sheets URL.

    Args:
        url: Google Sheets URL

    Returns:
        Spreadsheet ID if found, None otherwise
    """
    pattern = r'spreadsheets/d/([a-zA-Z0-9_-]+)'
    match = re.search(pattern, url)
    if match:
        return match.group(1)
    return None


def download_google_sheet_as_csv(sheet_url: str, output_path: Path) -> None:
    """
    Download Google Sheet as CSV file.

    Args:
        sheet_url: Google Sheets URL
        output_path: Path to save CSV file

    Raises:
        Exception: If download fails or sheet ID extraction fails
    """
    # Extract spreadsheet ID
    sheet_id = extract_google_sheet_id(sheet_url)
    if not sheet_id:
        raise Exception(f"Could not extract spreadsheet ID from URL: {sheet_url}")

    # Try different export URL formats
    export_urls = [
        # Published to web format
        f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid=0",
        # Direct export format with resource key
        f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv",
        # Alternative export format
        f"https://docs.google.com/spreadsheets/d/e/{sheet_id}/pub?output=csv",
    ]

    # Download CSV
    print(f"Downloading spreadsheet as CSV...")
    # Create SSL context
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE

    last_error = None
    for export_url in export_urls:
        try:
            with urllib.request.urlopen(export_url, context=ssl_context) as response:
                with open(output_path, 'wb') as out_file:
                    out_file.write(response.read())
            print(f"✓ Downloaded to: {output_path}\n")
            return  # Success!
        except Exception as e:
            last_error = e
            continue

    # All URLs failed
    raise Exception(
        f"Failed to download Google Sheet: {last_error}\n\n"
        f"Please ensure the spreadsheet is:\n"
        f"1. Shared with 'Anyone with the link can view', OR\n"
        f"2. Published to the web (File → Share → Publish to web → CSV)\n\n"
        f"Alternatively, download the CSV manually and use --from-csv instead."
    )


def extract_gdrive_file_id(url: str) -> Optional[str]:
    """
    Extract file ID from Google Drive URL.

    Args:
        url: Google Drive share URL

    Returns:
        File ID if found, None otherwise
    """
    patterns = [
        r'drive\.google\.com/file/d/([a-zA-Z0-9_-]+)',
        r'drive\.google\.com/open\?id=([a-zA-Z0-9_-]+)',
    ]

    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)

    return None


def download_gdrive_image(gdrive_url: str, temp_dir: Path, slug: str, story_dir: Path, force: bool = False) -> Path:
    """
    Download cover image from Google Drive URL to local temp file (with caching).

    Args:
        gdrive_url: Google Drive share URL
        temp_dir: Directory to save downloaded image
        slug: Story slug for filename
        story_dir: Story directory to check for existing cover image
        force: If True, always re-download even if a cached image exists

    Returns:
        Path to downloaded or cached image file

    Raises:
        Exception: If download fails or file ID extraction fails
    """
    # Check if story directory exists and has cover image (skip re-download)
    if not force and story_dir.exists():
        for cover_file in story_dir.glob('cover.*'):
            print(f"  ✓ Using existing image: {cover_file.name}")
            return cover_file

    # Extract file ID from Google Drive URL
    file_id = extract_gdrive_file_id(gdrive_url)
    if not file_id:
        raise Exception(f"Could not extract file ID from URL: {gdrive_url}")

    # Build direct download URL
    download_url = f"https://drive.google.com/uc?export=download&id={file_id}&confirm=t"

    # Create temp directory if it doesn't exist
    temp_dir.mkdir(parents=True, exist_ok=True)

    # Download to temp file
    temp_file = temp_dir / f"{slug}_cover_temp"

    try:
        print(f"  ⬇ Downloading image from Google Drive...")
        # Create SSL context that doesn't verify certificates (needed for some systems)
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE

        # Download using urlopen with SSL context
        with urllib.request.urlopen(download_url, context=ssl_context) as response:
            with open(temp_file, 'wb') as out_file:
                out_file.write(response.read())
    except Exception as e:
        raise Exception(f"Failed to download image: {e}")

    # Detect image type and rename with correct extension
    img_type = imghdr.what(temp_file)
    if not img_type:
        temp_file.unlink()  # Clean up invalid file
        raise Exception("Downloaded file is not a valid image")

    # Rename with correct extension
    final_file = temp_dir / f"{slug}_cover.{img_type}"
    temp_file.rename(final_file)

    print(f"  ✓ Downloaded image: {final_file.name}")
    return final_file


def validate_csv_row(row: dict) -> tuple[bool, str]:
    """
    Check if CSV row has all required fields.

    Args:
        row: Dictionary from CSV DictReader

    Returns:
        Tuple of (is_valid, error_message)
    """
    required_fields = [
        CSV_COLUMNS['english_title'],
        CSV_COLUMNS['tamil_title'],
        CSV_COLUMNS['english_pdf'],
        CSV_COLUMNS['tamil_pdf'],
        CSV_COLUMNS['image'],
        CSV_COLUMNS['translators'],
        CSV_COLUMNS['english_description'],
        CSV_COLUMNS['tamil_description'],
    ]

    for field in required_fields:
        if not row.get(field, '').strip():
            return False, f"Missing required field: {field}"

    return True, ""


def process_csv_row(row: dict, row_number: int, temp_dir: Path, force: bool = False) -> dict:
    """
    Process a single CSV row.

    Args:
        row: Dictionary from CSV DictReader
        row_number: Row number for reporting
        temp_dir: Temporary directory for downloads
        force: If True, re-download images even if cached

    Returns:
        Status dictionary with row, title, status, and optional error
    """
    try:
        # Validate row
        is_valid, error_msg = validate_csv_row(row)
        if not is_valid:
            return {
                'row': row_number,
                'title': row.get(CSV_COLUMNS['english_title'], 'Unknown'),
                'status': 'failed',
                'error': error_msg
            }

        # Map CSV columns to story parameters
        english_title = row[CSV_COLUMNS['english_title']].strip()
        tamil_title = row[CSV_COLUMNS['tamil_title']].strip()
        english_pdf = row[CSV_COLUMNS['english_pdf']].strip()
        tamil_pdf = row[CSV_COLUMNS['tamil_pdf']].strip()
        image_url = row[CSV_COLUMNS['image']].strip()
        translators = row[CSV_COLUMNS['translators']].strip()
        english_description = row[CSV_COLUMNS['english_description']].strip()
        tamil_description = row[CSV_COLUMNS['tamil_description']].strip()
        tags = row.get(CSV_COLUMNS['tags'], '').strip()

        # Create slug and determine story directory
        slug = create_slug(english_title)
        story_dir = PROJECT_ROOT / 'content' / 'stories' / slug

        # Download cover image (with caching)
        try:
            cover_image_path = download_gdrive_image(image_url, temp_dir, slug, story_dir, force=force)
        except Exception as e:
            return {
                'row': row_number,
                'title': english_title,
                'status': 'failed',
                'error': f"Image download failed: {e}"
            }

        # Create story
        success = create_story(
            english_title=english_title,
            tamil_title=tamil_title,
            english_description=english_description,
            tamil_description=tamil_description,
            english_pdf=english_pdf,
            tamil_pdf=tamil_pdf,
            translators=translators,
            cover_image_path=str(cover_image_path),
            tags=tags,
        )

        # Clean up: Delete downloaded temp image ONLY if it was newly downloaded
        # (not from cache, i.e., not in story_dir)
        if cover_image_path.parent == temp_dir and cover_image_path.exists():
            cover_image_path.unlink()

        if success:
            return {
                'row': row_number,
                'title': english_title,
                'status': 'success'
            }
        else:
            return {
                'row': row_number,
                'title': english_title,
                'status': 'failed',
                'error': 'Story creation failed'
            }

    except Exception as e:
        return {
            'row': row_number,
            'title': row.get(CSV_COLUMNS['english_title'], 'Unknown'),
            'status': 'failed',
            'error': str(e)
        }


def process_csv(csv_path: str, row_start: int = 0, row_end: int = 0, force: bool = False) -> dict:
    """
    Main CSV processing orchestrator.

    Args:
        csv_path: Path to CSV file
        row_start: First spreadsheet row to process (0 = no filter)
        row_end: Last spreadsheet row to process (0 = no filter)
        force: If True, re-download images and skip 'done' status filter

    Returns:
        Summary dictionary with total, successful, failed counts and details
    """
    print(f"Processing stories from CSV: {csv_path}\n")

    # Read CSV file
    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
    except Exception as e:
        print(f"Error reading CSV file: {e}")
        return {'total': 0, 'successful': 0, 'failed': 0, 'details': []}

    if not rows:
        print("No rows found in CSV file (or only header row)")
        return {'total': 0, 'successful': 0, 'failed': 0, 'details': []}

    # Create temp directory
    temp_dir = Path.home() / '.eethal_temp'

    # Build list of (row_number, row_dict) tuples, filtering by --rows if set
    eligible = []
    for idx, row in enumerate(rows, start=2):  # row 1 is header
        if row_start and idx < row_start:
            continue
        if row_end and idx > row_end:
            continue

        # Skip rows with Status = 'done' (unless force is set)
        status = row.get(CSV_COLUMNS['status'], '').strip().lower()
        if status == 'done' and not force:
            continue

        # Skip empty rows
        is_valid, _ = validate_csv_row(row)
        if not is_valid:
            continue

        eligible.append((idx, row))

    if not eligible:
        range_desc = f" in rows {row_start}-{row_end}" if row_start else ""
        print(f"No eligible stories found{range_desc}.")
        return {'total': 0, 'successful': 0, 'failed': 0, 'details': []}

    if row_start:
        print(f"Processing spreadsheet rows {row_start}-{row_end} ({len(eligible)} eligible stories)\n")

    # Process each row
    results = []
    for i, (idx, row) in enumerate(eligible, 1):
        english_title = row.get(CSV_COLUMNS['english_title'], 'Unknown').strip()
        print(f"[{i}/{len(eligible)}] Row {idx}: Creating: {english_title}")

        result = process_csv_row(row, idx, temp_dir, force=force)
        results.append(result)

        if result['status'] == 'success':
            print(f"  ✓ SUCCESS\n")
        else:
            print(f"  ✗ FAILED: {result.get('error', 'Unknown error')}\n")

    # Clean up temp directory
    try:
        if temp_dir.exists():
            shutil.rmtree(temp_dir)
    except Exception:
        pass  # Ignore cleanup errors

    # Calculate statistics
    successful = sum(1 for r in results if r['status'] == 'success')
    failed = sum(1 for r in results if r['status'] == 'failed')

    # Print summary
    print("=" * 50)
    print("CSV Processing Complete")
    print("=" * 50)
    print(f"Total processed: {len(results)}")
    print(f"Successful:      {successful}")
    print(f"Failed:          {failed}")

    if failed > 0:
        print("\nFailed stories:")
        for r in results:
            if r['status'] == 'failed':
                print(f"  - Row {r['row']}: \"{r['title']}\" - {r.get('error', 'Unknown error')}")

    return {
        'total': len(results),
        'successful': successful,
        'failed': failed,
        'details': results
    }


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


def _yaml_safe(value: str) -> str:
    """Escape a string for use inside a YAML double-quoted value.

    Replaces smart/curly quotes with single quotes, escapes any remaining
    double quotes with a backslash, and strips HTML entities like &quot;.
    """
    # Replace smart/curly double quotes with single quotes
    value = value.replace('\u201c', "'").replace('\u201d', "'")
    # Replace HTML-encoded quotes
    value = value.replace('&quot;', "'")
    # Escape any remaining literal double quotes
    value = value.replace('"', '\\"')
    return value


def create_story_frontmatter(
    english_title: str,
    tamil_title: str,
    english_description: str,
    tamil_description: str,
    english_pdf: str,
    tamil_pdf: str,
    translators: str,
    cover_image_filename: str,
    tags: str = "",
) -> str:
    """Generate Hugo front matter for the story."""

    # Sanitise text fields for YAML double-quoted strings
    english_title = _yaml_safe(english_title)
    tamil_title = _yaml_safe(tamil_title)
    english_description = _yaml_safe(english_description)
    tamil_description = _yaml_safe(tamil_description)

    # Convert PDF URLs to preview format
    english_pdf_preview = convert_gdrive_url_to_preview(english_pdf)
    tamil_pdf_preview = convert_gdrive_url_to_preview(tamil_pdf)

    # Parse translators (handle both comma-separated and newline-separated)
    # First split by newlines, then by commas
    translator_list = []
    for line in translators.split('\n'):
        for name in line.split(','):
            name = name.strip()
            if name:
                translator_list.append(name)
    translators_yaml = '\n'.join([f'    - "{t}"' for t in translator_list])

    # Parse tags (comma-separated)
    tag_list = [t.strip() for t in tags.split(',') if t.strip()] if tags else []
    tags_yaml = '\n'.join([f'    - "{t}"' for t in tag_list])

    frontmatter = f'''---
title: "{english_title}"
date: {date.today().isoformat()}

descriptions:
  english: "{english_description}"
  tamil: "{tamil_description}"

pdfs:
  tamil: "{tamil_pdf_preview}"
  english: "{english_pdf_preview}"

titles:
  english: "{english_title}"
  tamil: "{tamil_title}"

translators:
{translators_yaml}

tags:
{tags_yaml}

coverImage: "{cover_image_filename}"
draft: false
---
'''

    return frontmatter


def create_story(
    english_title: str,
    tamil_title: str,
    english_description: str,
    tamil_description: str,
    english_pdf: str,
    tamil_pdf: str,
    translators: str,
    cover_image_path: str,
    tags: str = "",
) -> bool:
    """
    Create a new story directory with all necessary files.

    Returns:
        True if successful, False otherwise
    """
    try:
        # Create slug from English title
        slug = create_slug(english_title)

        # Create story directory
        content_dir = PROJECT_ROOT / 'content' / 'stories' / slug
        content_dir.mkdir(parents=True, exist_ok=True)

        print(f"  Creating story: {slug}")
        print(f"  Directory: {content_dir}")

        # Copy cover image
        cover_image_path = Path(cover_image_path).expanduser()
        if not cover_image_path.exists():
            print(f"  Error: Cover image not found at {cover_image_path}")
            return False

        cover_extension = cover_image_path.suffix
        cover_filename = f"cover{cover_extension}"
        cover_dest = content_dir / cover_filename

        # Only copy if source and destination are different
        if cover_image_path.resolve() != cover_dest.resolve():
            shutil.copy2(cover_image_path, cover_dest)
            print(f"  Copied cover image: {cover_dest}")
        else:
            print(f"  Cover image already in place: {cover_filename}")

        # Create index.md with front matter
        index_md = content_dir / 'index.md'
        frontmatter = create_story_frontmatter(
            english_title,
            tamil_title,
            english_description,
            tamil_description,
            english_pdf,
            tamil_pdf,
            translators,
            cover_filename,
            tags=tags,
        )

        index_md.write_text(frontmatter, encoding='utf-8')
        print(f"  Created story file: {index_md}")

        return True

    except Exception as e:
        print(f"  Error creating story: {e}")
        return False


def _parse_tags(tags_str: str) -> list[str]:
    """Parse comma-separated tags string into a list of trimmed tag names."""
    if not tags_str:
        return []
    return [t.strip() for t in tags_str.split(',') if t.strip()]


def update_story_tags(story_dir: Path, tag_list: list[str]) -> bool:
    """Update the tags in an existing story's index.md front matter.

    Reads the YAML front matter, adds or replaces the `tags:` block,
    and writes the file back. Preserves all other front matter and body content.

    Returns True if updated, False on error.
    """
    index_md = story_dir / "index.md"
    if not index_md.exists():
        return False

    content = index_md.read_text(encoding="utf-8")

    # Split into front matter and body
    # Front matter is between the first two '---' lines
    parts = content.split("---", 2)
    if len(parts) < 3:
        print(f"  Could not parse front matter in {index_md}")
        return False

    front_matter = parts[1]
    body = parts[2]

    # Remove existing tags block if present
    # Match "tags:\n    - ...\n    - ...\n" (with possible variations in indentation)
    front_matter = re.sub(
        r'\ntags:\n(?:\s+- [^\n]+\n)*',
        '\n',
        front_matter,
    )

    # Build tags YAML block
    tags_yaml = "\ntags:\n"
    for tag in tag_list:
        tags_yaml += f'    - "{tag}"\n'

    # Insert tags at end of front matter (before closing ---)
    front_matter = front_matter.rstrip('\n') + '\n'
    front_matter += tags_yaml

    # Reconstruct the file
    new_content = "---" + front_matter + "---" + body
    index_md.write_text(new_content, encoding="utf-8")
    return True


def process_tags_only(csv_path: str, row_start: int = 0, row_end: int = 0) -> dict:
    """Process only tags from the spreadsheet and update existing story files.

    Skips image download and story creation. Reads tags from the Tags column
    and updates front matter of matching stories in content/stories/.

    Returns summary dict with updated/skipped/no_tags counts.
    """
    print(f"Updating tags from CSV: {csv_path}\n")

    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
    except Exception as e:
        print(f"Error reading CSV file: {e}")
        return {'updated': 0, 'skipped': 0, 'no_tags': 0}

    if not rows:
        print("No rows found in CSV file")
        return {'updated': 0, 'skipped': 0, 'no_tags': 0}

    updated = 0
    skipped = 0
    no_tags = 0

    for idx, row in enumerate(rows, start=2):  # row 1 is header
        if row_start and idx < row_start:
            continue
        if row_end and idx > row_end:
            continue

        english_title = row.get(CSV_COLUMNS['english_title'], '').strip()
        if not english_title:
            skipped += 1
            continue

        tags_str = row.get(CSV_COLUMNS['tags'], '').strip()
        tag_list = _parse_tags(tags_str)

        if not tag_list:
            print(f"  Row {idx}: {english_title} -- no tags, skipping.")
            no_tags += 1
            continue

        slug = create_slug(english_title)
        story_dir = PROJECT_ROOT / 'content' / 'stories' / slug

        if not story_dir.exists():
            print(f"  Row {idx}: {english_title} -- story dir not found ({slug}/), skipping.")
            skipped += 1
            continue

        if update_story_tags(story_dir, tag_list):
            print(f"  Row {idx}: {english_title} -- updated tags: {', '.join(tag_list)}")
            updated += 1
        else:
            print(f"  Row {idx}: {english_title} -- failed to update tags.")
            skipped += 1

    # Print summary
    print(f"\nTags update complete: {updated} updated, {skipped} skipped, {no_tags} had no tags.")
    return {'updated': updated, 'skipped': skipped, 'no_tags': no_tags}


def main():
    parser = argparse.ArgumentParser(
        description='Add a new bilingual story to the EETHAL Foundation website'
    )

    parser.add_argument(
        '--rows', metavar='RANGE',
        help="process a specific range of spreadsheet rows, e.g. '5-10' or '7' "
             "(row 1 is header, data rows start at 2)",
    )
    parser.add_argument(
        '--force', action='store_true',
        help="re-process stories even if marked 'done'; re-download images "
             "instead of using cached copies",
    )
    parser.add_argument(
        '--tags-only', action='store_true',
        help="only update tags in existing story front matter from the spreadsheet. "
             "Skips image download and story creation. Best used with --rows.",
    )

    # # CSV mode arguments (unused — all data comes from default Google Sheet)
    # parser.add_argument(
    #     '--from-csv',
    #     help='Path to CSV file (processes ALL rows in CSV)'
    # )
    #
    # parser.add_argument(
    #     '--from-google-sheet',
    #     nargs='?',
    #     const=DEFAULT_GOOGLE_SHEET_URL,
    #     help=f'Google Sheets URL (defaults to configured spreadsheet if URL not provided)'
    # )
    #
    # # Traditional CLI arguments
    # parser.add_argument(
    #     '--english-title',
    #     help='Story title in English'
    # )
    #
    # parser.add_argument(
    #     '--tamil-title',
    #     help='Story title in Tamil'
    # )
    #
    # parser.add_argument(
    #     '--english-pdf',
    #     help='Google Drive URL for English PDF'
    # )
    #
    # parser.add_argument(
    #     '--tamil-pdf',
    #     help='Google Drive URL for Tamil PDF'
    # )
    #
    # parser.add_argument(
    #     '--translators',
    #     help='Comma-separated list of translator names'
    # )
    #
    # parser.add_argument(
    #     '--english-description',
    #     help='Brief description of the story in English'
    # )
    #
    # parser.add_argument(
    #     '--tamil-description',
    #     help='Brief description of the story in Tamil'
    # )
    #
    # parser.add_argument(
    #     '--cover-image',
    #     help='Path to cover image file'
    # )

    args = parser.parse_args()

    # Parse --rows range
    row_start = 0
    row_end = 0
    if args.rows:
        match = re.match(r'^(\d+)(?:-(\d+))?$', args.rows)
        if not match:
            print(f"Error: invalid --rows format '{args.rows}'. Use e.g. '5-10' or '7'.",
                  file=sys.stderr)
            sys.exit(1)
        row_start = int(match.group(1))
        row_end = int(match.group(2)) if match.group(2) else row_start
        if row_start < 2:
            print("Error: row 1 is the header. Data rows start at 2.", file=sys.stderr)
            sys.exit(1)
        if row_end < row_start:
            print(f"Error: invalid --rows range {row_start}-{row_end}.", file=sys.stderr)
            sys.exit(1)

    # Always download from the default Google Sheet
    temp_csv = Path.home() / '.eethal_temp' / 'downloaded_sheet.csv'
    temp_csv.parent.mkdir(parents=True, exist_ok=True)

    try:
        download_google_sheet_as_csv(DEFAULT_GOOGLE_SHEET_URL, temp_csv)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

    # --tags-only mode: update tags in existing story front matter and exit
    if args.tags_only:
        process_tags_only(str(temp_csv), row_start=row_start, row_end=row_end)
        try:
            temp_csv.unlink()
        except Exception:
            pass
        sys.exit(0)

    result = process_csv(str(temp_csv), row_start=row_start, row_end=row_end, force=args.force)

    # Clean up temp CSV
    try:
        temp_csv.unlink()
    except Exception:
        pass

    # Print next steps
    print("\nNext steps:")
    print("1. Preview: hugo server -D")
    print("2. Commit: git add content/stories/ && git commit -m 'Add stories from Google Sheet'")

    sys.exit(0 if result['failed'] == 0 else 1)


if __name__ == '__main__':
    main()
