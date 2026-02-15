#!/usr/bin/env python3
"""
EETHAL Foundation - Simplified Story Addition Script

Usage:

1. Process stories from default Google Sheets (auto-downloads CSV):
    python add_story.py --from-google-sheet

   Or specify a different Google Sheets URL:
    python add_story.py --from-google-sheet "https://docs.google.com/spreadsheets/d/SHEET_ID/edit"

2. Process stories from local CSV file:
    python add_story.py --from-csv ~/Downloads/stories.csv

3. Add a single story via CLI arguments:
    python add_story.py \
        --english-title "My Big Family" \
        --tamil-title "என்னுடைய பெரிய குடும்பம்" \
        --english-pdf "https://drive.google.com/file/d/FILE_ID/view" \
        --tamil-pdf "https://drive.google.com/file/d/FILE_ID/view" \
        --translators "Name1, Name2" \
        --english-description "A heartwarming story about..." \
        --tamil-description "குடும்பத்தைப் பற்றிய ஒரு அன்பான கதை..." \
        --cover-image ~/Downloads/cover.jpg

CSV Format:
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


def download_gdrive_image(gdrive_url: str, temp_dir: Path, slug: str, story_dir: Path) -> Path:
    """
    Download cover image from Google Drive URL to local temp file (with caching).

    Args:
        gdrive_url: Google Drive share URL
        temp_dir: Directory to save downloaded image
        slug: Story slug for filename
        story_dir: Story directory to check for existing cover image

    Returns:
        Path to downloaded or cached image file

    Raises:
        Exception: If download fails or file ID extraction fails
    """
    # Check if story directory exists and has cover image (caching)
    if story_dir.exists():
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


def process_csv_row(row: dict, row_number: int, temp_dir: Path) -> dict:
    """
    Process a single CSV row.

    Args:
        row: Dictionary from CSV DictReader
        row_number: Row number for reporting
        temp_dir: Temporary directory for downloads

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

        # Create slug and determine story directory
        slug = create_slug(english_title)
        story_dir = Path('content/stories') / slug

        # Download cover image (with caching)
        try:
            cover_image_path = download_gdrive_image(image_url, temp_dir, slug, story_dir)
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
            cover_image_path=str(cover_image_path)
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


def process_csv(csv_path: str) -> dict:
    """
    Main CSV processing orchestrator (processes ALL rows in CSV).

    Args:
        csv_path: Path to CSV file

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

    # Process each row
    results = []
    total_rows = len(rows)

    for idx, row in enumerate(rows, start=2):  # Start at 2 because row 1 is header
        # Skip rows with Status = 'done'
        status = row.get(CSV_COLUMNS['status'], '').strip().lower()
        if status == 'done':
            continue

        # Skip empty rows
        is_valid, _ = validate_csv_row(row)
        if not is_valid:
            continue

        english_title = row.get(CSV_COLUMNS['english_title'], 'Unknown').strip()
        print(f"[{len(results)+1}/{total_rows}] Creating: {english_title}")

        result = process_csv_row(row, idx, temp_dir)
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
    print(f"Total rows:     {total_rows}")
    print(f"Successful:     {successful}")
    print(f"Failed:         {failed}")

    if failed > 0:
        print("\nFailed stories:")
        for r in results:
            if r['status'] == 'failed':
                print(f"  - Row {r['row']}: \"{r['title']}\" - {r.get('error', 'Unknown error')}")

    return {
        'total': total_rows,
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


def create_story_frontmatter(
    english_title: str,
    tamil_title: str,
    english_description: str,
    tamil_description: str,
    english_pdf: str,
    tamil_pdf: str,
    translators: str,
    cover_image_filename: str
) -> str:
    """Generate Hugo front matter for the story."""

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
    cover_image_path: str
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
        content_dir = Path('content/stories') / slug
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
            cover_filename
        )

        index_md.write_text(frontmatter, encoding='utf-8')
        print(f"  Created story file: {index_md}")

        return True

    except Exception as e:
        print(f"  Error creating story: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description='Add a new bilingual story to the EETHAL Foundation website'
    )

    # CSV mode arguments
    parser.add_argument(
        '--from-csv',
        help='Path to CSV file (processes ALL rows in CSV)'
    )

    parser.add_argument(
        '--from-google-sheet',
        nargs='?',
        const=DEFAULT_GOOGLE_SHEET_URL,
        help=f'Google Sheets URL (defaults to configured spreadsheet if URL not provided)'
    )

    # Traditional CLI arguments
    parser.add_argument(
        '--english-title',
        help='Story title in English'
    )

    parser.add_argument(
        '--tamil-title',
        help='Story title in Tamil'
    )

    parser.add_argument(
        '--english-pdf',
        help='Google Drive URL for English PDF'
    )

    parser.add_argument(
        '--tamil-pdf',
        help='Google Drive URL for Tamil PDF'
    )

    parser.add_argument(
        '--translators',
        help='Comma-separated list of translator names'
    )

    parser.add_argument(
        '--english-description',
        help='Brief description of the story in English'
    )

    parser.add_argument(
        '--tamil-description',
        help='Brief description of the story in Tamil'
    )

    parser.add_argument(
        '--cover-image',
        help='Path to cover image file'
    )

    args = parser.parse_args()

    # Google Sheets Mode
    if args.from_google_sheet:
        # Download Google Sheet as CSV to temp file
        temp_csv = Path.home() / '.eethal_temp' / 'downloaded_sheet.csv'
        temp_csv.parent.mkdir(parents=True, exist_ok=True)

        try:
            download_google_sheet_as_csv(args.from_google_sheet, temp_csv)
        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1)

        result = process_csv(str(temp_csv))

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

    # CSV Mode
    elif args.from_csv:
        csv_path = Path(args.from_csv).expanduser()
        if not csv_path.exists():
            print(f"Error: CSV file not found: {csv_path}")
            sys.exit(1)

        result = process_csv(str(csv_path))

        # Print next steps
        print("\nNext steps:")
        print("1. Preview: hugo server -D")
        print("2. Commit: git add content/stories/ && git commit -m 'Add stories from CSV'")

        sys.exit(0 if result['failed'] == 0 else 1)

    # Traditional CLI Mode
    else:
        # Validate required arguments for CLI mode
        required_args = [
            ('english_title', 'Story title in English'),
            ('tamil_title', 'Story title in Tamil'),
            ('english_pdf', 'Google Drive URL for English PDF'),
            ('tamil_pdf', 'Google Drive URL for Tamil PDF'),
            ('translators', 'Comma-separated list of translator names'),
            ('english_description', 'Brief description in English'),
            ('tamil_description', 'Brief description in Tamil'),
            ('cover_image', 'Path to cover image file'),
        ]

        missing_args = []
        for arg_name, arg_desc in required_args:
            if not getattr(args, arg_name):
                missing_args.append(f"--{arg_name.replace('_', '-')}: {arg_desc}")

        if missing_args:
            print("Error: Missing required arguments for CLI mode:\n")
            for missing in missing_args:
                print(f"  {missing}")
            print("\nUse --from-csv <path> to process stories from CSV file instead.")
            sys.exit(1)

        success = create_story(
            english_title=args.english_title,
            tamil_title=args.tamil_title,
            english_description=args.english_description,
            tamil_description=args.tamil_description,
            english_pdf=args.english_pdf,
            tamil_pdf=args.tamil_pdf,
            translators=args.translators,
            cover_image_path=args.cover_image
        )

        if success:
            slug = create_slug(args.english_title)
            print("\n✅ Story created successfully!")
            print(f"\nNext steps:")
            print(f"1. Preview locally: hugo server -D")
            print(f"2. View at: http://localhost:1313/stories/{slug}/")
            print(f"3. Commit: git add content/stories/{slug} && git commit -m 'Add story: {args.english_title}'")
            sys.exit(0)
        else:
            sys.exit(1)


if __name__ == '__main__':
    main()
