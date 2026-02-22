#!/usr/bin/env python3
"""
Read story data from PDFs linked in the EETHAL Foundation Google Spreadsheet.
Downloads English (column C) and Tamil (column D) PDFs from Google Drive,
extracts titles and translator names from page 1, and descriptions from the
last page of each PDF.

Only processes rows that have StoryWeaver links in columns F and G.
When using the Drive API (OAuth credentials available), automatically makes
each file publicly viewable before downloading.

Usage:
    source .venv/bin/activate
    python extract_stories.py
    python extract_stories.py -o descriptions.csv
    python extract_stories.py --rows 5-10            # process stories 5 through 10
    python extract_stories.py --rows 7               # process only story 7
    python extract_stories.py --ocr gemini           # use Gemini OCR (recommended)
    python extract_stories.py --ocr tesseract        # use Tesseract OCR (fallback)
Requirements (install via: pip install -r requirements.txt):
    - requests
    - PyMuPDF
    - gdown
    - certifi
    - google-api-python-client
    - google-auth-oauthlib
    - google-generativeai (for Gemini OCR - recommended)
    - google-cloud-translate (for Tamil translation - recommended)
    - pytesseract + Pillow (for Tesseract OCR - fallback)

Setup for Gemini OCR (recommended for better Tamil text extraction):
    1. Get your API key from: https://aistudio.google.com/app/apikey
    2. Set environment variable: export GEMINI_API_KEY='your-key-here'
    3. Note: Free tier has rate limits (5 requests/minute). The script automatically
       handles rate limiting with retries and delays between requests.

Setup for Google Cloud Translation (recommended for Tamil descriptions):
    1. Go to: https://console.cloud.google.com/
    2. Create a project (or use existing Gemini project)
    3. Enable Cloud Translation API
    4. Create a Service Account with Translation API permissions
    5. Download service account key JSON file
    6. Set environment variable: export GOOGLE_APPLICATION_CREDENTIALS='/path/to/key.json'

    Tamil descriptions are now translated from English rather than extracted from
    Tamil PDFs, avoiding font encoding issues. Falls back to Tamil PDF if needed.

Setup for Google Drive API (auto-makes files public before downloading):
    1. Go to https://console.cloud.google.com/
    2. Create a project (or select existing)
    3. Enable the Google Drive API
    4. Go to Credentials > Create Credentials > OAuth client ID
       - Application type: Desktop app
    5. Download the JSON and save as credentials.json in this directory
"""

import argparse
import certifi
import csv
import io
import os
import re
import sys
import tempfile
import time

# Fix SSL certificates for Python installations missing system certs
os.environ.setdefault("SSL_CERT_FILE", certifi.where())

import fitz  # PyMuPDF — better Tamil font handling than pdfplumber
import gdown
import requests

try:
    import pytesseract
    from PIL import Image
    HAS_TESSERACT = True
except ImportError:
    HAS_TESSERACT = False

try:
    import google.generativeai as genai
    HAS_GEMINI = True
except ImportError:
    HAS_GEMINI = False

try:
    from google.cloud import translate_v2 as translate
    HAS_TRANSLATE = True
except ImportError:
    HAS_TRANSLATE = False

HAS_OCR = HAS_TESSERACT or HAS_GEMINI

# Google Drive API (lazy-loaded, only needed for --make-public)
# Translation API scope added for OAuth-based translation
SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/cloud-translation",
    "https://www.googleapis.com/auth/spreadsheets",
]
TOKEN_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "token.json")
CREDENTIALS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "credentials.json")

# Google Spreadsheet export URL (public CSV)
SPREADSHEET_ID = "1zNhXLL_De8qCsk8OlORGQ_0tIk9Bw3aKi72HlSTEAOU"
SHEET_GID = "0"
CSV_URL = (
    f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}"
    f"/export?format=csv&gid={SHEET_GID}"
)

# Column indices (0-based)
COL_ENGLISH_TITLE = 0   # Column A
COL_TAMIL_TITLE = 1     # Column B
COL_PDF_ENG = 2          # Column C: English PDF
COL_PDF_TAM = 3          # Column D: Tamil PDF
COL_IMAGE = 4            # Column E: Image (Google Drive)
COL_SW_LINK_ENG = 5      # Column F: SW link English
COL_SW_LINK_TAM = 6      # Column G: SW link Tamil
COL_TRANSLATORS = 7      # Column H: Translators
COL_ENG_DESC = 8         # Column I: English Description
COL_TAM_DESC = 9         # Column J: Tamil Description
COL_STATUS = 10          # Column K: Status
COL_TAGS = 11            # Column L: Tags (comma-separated)

# Markers that signal the end of the description on the last page
LEVEL_MARKERS_ENG = ["This is a Level", "This book"]
LEVEL_MARKERS = LEVEL_MARKERS_ENG + ["Pratham Books"]

# Language tags that appear before the description (includes Tamil equivalents for OCR)
LANG_TAGS = ["(English)", "(Tamil)", "(தமிழ்)", "(ஆங்கிலம்)"]


def parse_args():
    parser = argparse.ArgumentParser(
        description="Extract story descriptions from EETHAL Foundation story PDFs on Google Drive.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
examples:
  python extract_stories.py                      # run with defaults (Gemini OCR)
  python extract_stories.py -n 3                # only process first 3 stories
  python extract_stories.py --rows 5-10         # process stories 5 through 10
  python extract_stories.py --rows 7            # process only story 7
  python extract_stories.py --ocr tesseract     # use Tesseract instead of Gemini
  python extract_stories.py --lang eng          # English descriptions only
  python extract_stories.py -o output.csv       # save results to a CSV file
  python extract_stories.py -q                  # suppress verbose logs
""",
    )
    parser.add_argument(
        "-n", "--limit", type=int, default=0, metavar="N",
        help="only process the first N stories (default: all)",
    )
    parser.add_argument(
        "--rows", metavar="RANGE",
        help="process a specific range of stories, e.g. '5-10' or '7' "
             "(1-based index among stories with SW links)",
    )
    parser.add_argument(
        "-o", "--output", metavar="FILE",
        help="write results to a CSV file (default: console only)",
    )
    parser.add_argument(
        "--lang", choices=["both", "eng", "tam"], default="both",
        help="which descriptions to fetch (default: both)",
    )
    parser.add_argument(
        "-q", "--quiet", action="store_true",
        help="suppress verbose progress logs (only show results)",
    )
    parser.add_argument(
        "--ocr", choices=["tesseract", "gemini"], default="gemini",
        help="OCR backend to use for Tamil text extraction (default: gemini). "
             "Gemini requires GEMINI_API_KEY environment variable.",
    )
    return parser.parse_args()


QUIET = False
OCR_BACKEND = "gemini"  # Set by command-line args


def log(msg):
    """Print a timestamped log message (suppressed in quiet mode)."""
    if QUIET:
        return
    timestamp = time.strftime("%H:%M:%S")
    print(f"[{timestamp}] {msg}", flush=True)


def fetch_spreadsheet_csv():
    """Download the Google Sheet as CSV."""
    log("Fetching spreadsheet data from Google Sheets...")
    response = requests.get(CSV_URL, allow_redirects=True)
    response.raise_for_status()
    log(f"Spreadsheet fetched OK ({len(response.text)} bytes)")
    return response.text


def _get_col(row, idx):
    """Safely get a column value from a CSV row."""
    return row[idx].strip() if len(row) > idx else ""


def parse_all_rows(csv_text):
    """Parse CSV and return ALL data rows (for --make-public).

    Each row includes a 'row_num' field with its spreadsheet row number
    (row 1 = header, row 2 = first data row).
    """
    reader = csv.reader(io.StringIO(csv_text))
    next(reader)  # skip header row (row 1)

    rows = []
    row_num = 1  # header is row 1
    for row in reader:
        row_num += 1
        if not any(cell.strip() for cell in row):
            continue  # skip completely empty rows
        rows.append({
            "row_num": row_num,
            "english_title": _get_col(row, COL_ENGLISH_TITLE),
            "tamil_title": _get_col(row, COL_TAMIL_TITLE),
            "pdf_eng": _get_col(row, COL_PDF_ENG),
            "pdf_tam": _get_col(row, COL_PDF_TAM),
            "image": _get_col(row, COL_IMAGE),
            "sw_link_eng": _get_col(row, COL_SW_LINK_ENG),
            "sw_link_tam": _get_col(row, COL_SW_LINK_TAM),
            "translators": _get_col(row, COL_TRANSLATORS),
            "english_description": _get_col(row, COL_ENG_DESC),
            "tamil_description": _get_col(row, COL_TAM_DESC),
            "status": _get_col(row, COL_STATUS),
            "tags": _get_col(row, COL_TAGS),
        })
    return rows


def parse_csv(csv_text):
    """Parse CSV and extract rows that have SW links filled out."""
    all_rows = parse_all_rows(csv_text)
    return [
        row for row in all_rows
        if row["sw_link_eng"] or row["sw_link_tam"]
    ]


def extract_drive_file_id(url):
    """Extract the Google Drive file ID from a Drive URL."""
    match = re.search(r"/d/([a-zA-Z0-9_-]+)", url)
    return match.group(1) if match else None


def extract_cover_image(pdf_path, output_path):
    """Extract the largest image from page 1 of a PDF and save it as PNG.

    Selects the largest image by its rendered size on the page (not intrinsic
    pixel dimensions), so the cover illustration is chosen over high-res logos.
    Handles CMYK-to-RGB conversion for compatibility.

    Returns True if an image was successfully extracted, False otherwise.
    """
    try:
        doc = fitz.open(pdf_path)
        page = doc[0]
        images = page.get_images(full=True)

        if not images:
            log("    No images found on page 1.")
            doc.close()
            return False

        # Use get_image_info to find rendered bounding boxes on the page.
        # This tells us the actual display size, not intrinsic pixel dimensions.
        image_info_list = page.get_image_info(xrefs=True)

        best_xref = None
        best_area = 0

        for info in image_info_list:
            xref = info.get("xref", 0)
            if xref == 0:
                continue
            bbox = info.get("bbox", (0, 0, 0, 0))
            rendered_width = abs(bbox[2] - bbox[0])
            rendered_height = abs(bbox[3] - bbox[1])
            area = rendered_width * rendered_height
            if area > best_area:
                best_area = area
                best_xref = xref

        # Fallback: if get_image_info didn't work, use intrinsic pixel area
        if best_xref is None:
            for img_info in images:
                xref = img_info[0]
                width = img_info[2]
                height = img_info[3]
                area = width * height
                if area > best_area:
                    best_area = area
                    best_xref = xref

        if best_xref is None:
            doc.close()
            return False

        pix = fitz.Pixmap(doc, best_xref)

        # Convert CMYK to RGB if needed
        if pix.n - pix.alpha > 3:
            pix = fitz.Pixmap(fitz.csRGB, pix)

        pix.save(output_path)
        doc.close()

        log(f"    Extracted cover image (rendered area {best_area:.0f}): {os.path.basename(output_path)}")
        return True

    except Exception as e:
        log(f"    Failed to extract cover image: {e}")
        return False


def get_parent_folder_id(drive_service, file_id):
    """Get the parent folder ID of a file on Google Drive."""
    try:
        file_meta = drive_service.files().get(
            fileId=file_id, fields='parents'
        ).execute()
        parents = file_meta.get('parents', [])
        return parents[0] if parents else None
    except Exception as e:
        log(f"    Could not get parent folder: {e}")
        return None


def upload_image_to_drive(drive_service, local_path, filename, folder_id):
    """Upload an image file to a specific Google Drive folder.

    Returns the Drive file ID of the uploaded file, or None on failure.
    """
    from googleapiclient.http import MediaFileUpload

    try:
        file_metadata = {
            'name': filename,
            'parents': [folder_id],
        }
        media = MediaFileUpload(local_path, mimetype='image/png', resumable=True)
        uploaded = drive_service.files().create(
            body=file_metadata, media_body=media, fields='id'
        ).execute()
        file_id = uploaded.get('id')
        log(f"    Uploaded image to Drive: {filename} (ID: {file_id})")
        return file_id
    except Exception as e:
        log(f"    Failed to upload image to Drive: {e}")
        return None


def get_sheets_service(creds):
    """Build a Google Sheets API v4 service from OAuth credentials."""
    from googleapiclient.discovery import build
    return build('sheets', 'v4', credentials=creds)


def write_image_url_to_sheet(sheets_service, row_num, image_url):
    """Write an image URL to column E of the specified row in the Google Sheet."""
    try:
        sheets_service.spreadsheets().values().update(
            spreadsheetId=SPREADSHEET_ID,
            range=f"E{row_num}",
            valueInputOption='RAW',
            body={'values': [[image_url]]},
        ).execute()
        log(f"    Wrote image URL to E{row_num}")
        return True
    except Exception as e:
        log(f"    Failed to write image URL to spreadsheet: {e}")
        return False


def process_cover_image(pdf_path, story, drive_service, sheets_service, tmpdir, idx):
    """Extract cover image from PDF, upload to Drive, and update spreadsheet.

    Skips if column E already has a value or if Drive API is unavailable.
    Returns the public Drive URL of the uploaded image, or None.
    """
    if story["image"]:
        log(f"    Image already set in spreadsheet, skipping extraction.")
        return story["image"]

    if not drive_service:
        log(f"    Drive API not available, skipping image extraction.")
        return None

    # Step 1: Extract cover image from page 1
    image_path = os.path.join(tmpdir, f"cover_{idx}.png")
    if not extract_cover_image(pdf_path, image_path):
        return None

    # Step 2: Get parent folder of the English PDF
    eng_file_id = extract_drive_file_id(story["pdf_eng"])
    if not eng_file_id:
        log(f"    Could not extract file ID from English PDF URL.")
        return None

    folder_id = get_parent_folder_id(drive_service, eng_file_id)
    if not folder_id:
        log(f"    Could not determine parent folder, skipping upload.")
        return None

    # Step 3: Upload image to Drive
    title = story.get("english_title", f"story_{idx}")
    safe_title = re.sub(r'[^\w\s-]', '', title).strip().replace(' ', '_')
    upload_filename = f"{safe_title}_cover.png"

    uploaded_file_id = upload_image_to_drive(
        drive_service, image_path, upload_filename, folder_id
    )
    if not uploaded_file_id:
        return None

    # Step 4: Make the uploaded image public
    image_drive_url = f"https://drive.google.com/file/d/{uploaded_file_id}/view"
    make_file_public(drive_service, image_drive_url)

    # Step 5: Write URL to spreadsheet column E
    if sheets_service:
        write_image_url_to_sheet(sheets_service, story["row_num"], image_drive_url)

    print(f"  >> Cover image uploaded: {image_drive_url}")
    return image_drive_url


def get_drive_service():
    """Authenticate with Google Drive API and return (service, credentials) tuple.

    Returns:
        tuple: (drive_service, oauth_credentials) where credentials can be reused
               for other Google APIs like Translation
    """
    from google.auth.transport.requests import Request as GoogleRequest
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    if not os.path.exists(CREDENTIALS_PATH):
        print(
            f"Error: {CREDENTIALS_PATH} not found.\n"
            "To use OAuth with Drive/Translation APIs, you need credentials:\n"
            "  1. Go to https://console.cloud.google.com/\n"
            "  2. Create/select a project and enable Drive + Translation APIs\n"
            "  3. Credentials > Create Credentials > OAuth client ID > Desktop app\n"
            "  4. Download the JSON and save as credentials.json in this directory",
            file=sys.stderr,
        )
        sys.exit(1)

    creds = None
    if os.path.exists(TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            log("Refreshing OAuth token...")
            creds.refresh(GoogleRequest())
        else:
            log("Opening browser for OAuth authorization (Drive + Translation APIs)...")
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_PATH, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_PATH, "w") as f:
            f.write(creds.to_json())
        log("Token saved for future runs.")

    return build("drive", "v3", credentials=creds), creds


def make_file_public(drive_service, drive_url):
    """Ensure a single Drive file is publicly viewable. No-op if already public."""
    file_id = extract_drive_file_id(drive_url)
    if not file_id:
        return
    try:
        perms = drive_service.permissions().list(fileId=file_id).execute()
        already_public = any(
            p.get("type") == "anyone" for p in perms.get("permissions", [])
        )
        if already_public:
            return
        drive_service.permissions().create(
            fileId=file_id,
            body={"type": "anyone", "role": "reader"},
        ).execute()
        log(f"    Made file {file_id} publicly viewable.")
    except Exception as e:
        log(f"    Could not set public permissions for {file_id}: {e}")


def download_pdf(drive_url, dest_path, drive_service=None):
    """Download a PDF from Google Drive. Uses Drive API if available, else gdown."""
    file_id = extract_drive_file_id(drive_url)
    if not file_id:
        log(f"    Could not extract file ID from: {drive_url}")
        return False

    # Prefer Drive API (handles private files + avoids gdown confirmation issues)
    if drive_service:
        make_file_public(drive_service, drive_url)
        try:
            from googleapiclient.http import MediaIoBaseDownload
            request = drive_service.files().get_media(fileId=file_id)
            with open(dest_path, "wb") as f:
                downloader = MediaIoBaseDownload(f, request)
                done = False
                while not done:
                    _, done = downloader.next_chunk()
            return os.path.exists(dest_path) and os.path.getsize(dest_path) > 0
        except Exception as e:
            log(f"    Drive API download failed: {e}")
            return False

    # Fallback to gdown for public files with retry logic
    max_retries = 3
    for attempt in range(max_retries):
        try:
            # fuzzy=True helps with Google Drive's URL changes/redirects
            gdown.download(
                f"https://drive.google.com/uc?id={file_id}",
                dest_path, quiet=True, fuzzy=True,
            )
            if os.path.exists(dest_path) and os.path.getsize(dest_path) > 0:
                # Add small delay after successful download to avoid bot detection
                time.sleep(2)
                return True
            else:
                log(f"    Download attempt {attempt + 1} produced empty file")
        except Exception as e:
            log(f"    Download attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                wait_time = (attempt + 1) * 3  # 3s, 6s, 9s delays
                log(f"    Retrying in {wait_time} seconds...")
                time.sleep(wait_time)

    log(f"    All download attempts failed after {max_retries} tries")
    return False


def is_garbled_text(text):
    """Detect garbled text from PDFs with broken font encoding.

    Broken Tamil PDFs produce text with control characters (e.g. ^O = 0x0F)
    and stray ASCII letters mixed into Tamil Unicode. Returns True if the
    text looks garbled.
    """
    if not text:
        return True
    # Control characters (except space, newline, tab)
    if any(ord(c) < 32 and c not in ("\n", "\r", "\t") for c in text):
        return True
    # If the text contains Tamil characters, check for stray ASCII letters
    # (Tamil Unicode range: U+0B80–U+0BFF)
    has_tamil = any("\u0B80" <= c <= "\u0BFF" for c in text)
    if has_tamil:
        # Count ASCII letters that aren't part of common English words/patterns
        ascii_letters = sum(1 for c in text if "A" <= c <= "Z" or "a" <= c <= "z")
        tamil_chars = sum(1 for c in text if "\u0B80" <= c <= "\u0BFF")
        # If there's a significant mix of ASCII letters with Tamil, it's garbled
        if tamil_chars > 0 and ascii_letters > 0 and ascii_letters / (tamil_chars + ascii_letters) > 0.1:
            return True
    return False


def translate_to_tamil(text, oauth_creds=None):
    """Translate English text to Tamil using Google Cloud Translation API.

    Args:
        text: English text to translate
        oauth_creds: Optional OAuth credentials (from get_drive_service pattern)
                    If provided, uses OAuth. Otherwise tries service account via
                    GOOGLE_APPLICATION_CREDENTIALS env var.

    Returns the translated Tamil text, or None on failure.
    """
    if not text or not text.strip():
        return None

    try:
        # Method 1: Use OAuth credentials if provided (shares auth with Drive API)
        if oauth_creds:
            from googleapiclient.discovery import build
            translate_service = build('translate', 'v2', credentials=oauth_creds)

            result = translate_service.translations().list(
                q=text,
                source='en',
                target='ta'
            ).execute()

            translated_text = result['translations'][0]['translatedText']
            log(f"    ✓ Translated {len(text)} chars to Tamil (OAuth)")
            return translated_text

        # Method 2: Fall back to service account credentials
        elif HAS_TRANSLATE:
            translate_client = translate.Client()
            result = translate_client.translate(
                text,
                source_language='en',
                target_language='ta'
            )
            translated_text = result['translatedText']
            log(f"    ✓ Translated {len(text)} chars to Tamil (service account)")
            return translated_text

        else:
            log("    Google Cloud Translate unavailable (install: pip install google-cloud-translate)")
            return None

    except Exception as e:
        log(f"    Translation failed: {e}")
        return None


def ocr_pdf_page_tesseract(pdf_path, page_num, lang="tam"):
    """Render a PDF page to an image and OCR it with Tesseract.

    Used as a fallback when the PDF text layer has broken font encoding.
    Returns the OCR'd text, or empty string on failure.
    """
    if not HAS_TESSERACT:
        log("    Tesseract unavailable (install pytesseract + Pillow: pip install pytesseract Pillow)")
        return ""
    try:
        doc = fitz.open(pdf_path)
        page = doc[page_num]
        # Render at 300 DPI for good OCR quality
        pix = page.get_pixmap(dpi=300)
        doc.close()

        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        text = pytesseract.image_to_string(img, lang=lang)
        return text.strip()
    except Exception as e:
        log(f"    Tesseract OCR failed: {e}")
        return ""


def ocr_pdf_page_gemini(pdf_path, page_num, is_first_page=False, is_last_page=False):
    """Render a PDF page to an image and OCR it with Google Gemini Vision API.

    Uses Gemini's vision capabilities to extract text from Tamil PDFs.
    Requires GEMINI_API_KEY environment variable to be set.
    Returns the OCR'd text, or empty string on failure.

    Handles rate limiting (429 errors) with automatic retry and delay.
    """
    if not HAS_GEMINI:
        log("    Gemini unavailable (install: pip install google-generativeai)")
        return ""

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        log("    Error: GEMINI_API_KEY environment variable not set")
        return ""

    max_retries = 3
    retry_count = 0

    # Render PDF page to image (do this once, outside the retry loop)
    try:
        doc = fitz.open(pdf_path)
        page = doc[page_num]
        # Render at 300 DPI for good quality
        pix = page.get_pixmap(dpi=300)
        doc.close()
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    except Exception as e:
        log(f"    Failed to render PDF page: {e}")
        return ""

    # Configure Gemini
    genai.configure(api_key=api_key)

    # Use Gemini Vision to extract text
    model = genai.GenerativeModel('gemini-2.5-pro')

    # Customize prompt based on page type
    if is_first_page:
        prompt = (
            "This is the first page of a Tamil children's storybook. "
            "Extract all text from this image in reading order (top to bottom). "
            "Include the story title, author, translator, and any other text. "
            "Ignore logos, website URLs, and organization names like 'EETHAL' or 'Pratham Books'. "
            "Return only the text content, one line per text element, without any commentary."
        )
    elif is_last_page:
        prompt = (
            "This is the last page of a Tamil children's storybook. "
            "It contains a story description/summary. "
            "Extract all text from this image in reading order. "
            "Include the reading level indicator (like 'Level 2'), language tag, title, and the STORY description. "
            "DO NOT include text that describes what level of reader the book is for (like 'This is a Level 2 book for children...'). "
            "Ignore footer text like 'Pratham Books', 'StoryWeaver', website URLs, and legal text. "
            "Return only the text content, one line per text element, without any commentary."
        )
    else:
        prompt = (
            "Extract all text from this image. This is a page from a Tamil children's storybook. "
            "Please preserve the exact text layout and return only the text content without any additional commentary."
        )

    # Retry loop for rate limiting
    while retry_count <= max_retries:
        try:
            response = model.generate_content([prompt, img])
            text = response.text.strip()

            # Add a small delay after successful request to avoid rate limiting
            # Free tier: 5 requests per minute = 12 seconds between requests
            time.sleep(13)

            return text

        except Exception as e:
            error_str = str(e)

            # Check if it's a rate limit error (429)
            if "429" in error_str or "quota" in error_str.lower() or "rate" in error_str.lower():
                # Extract retry delay from error message if available
                retry_delay = 15  # Default delay
                import re
                delay_match = re.search(r'retry in (\d+\.?\d*)', error_str)
                if delay_match:
                    retry_delay = float(delay_match.group(1)) + 2  # Add 2 seconds buffer

                retry_count += 1
                if retry_count <= max_retries:
                    log(f"    Rate limit hit. Waiting {retry_delay:.0f}s before retry {retry_count}/{max_retries}...")
                    time.sleep(retry_delay)
                else:
                    log(f"    Gemini OCR failed after {max_retries} retries: Rate limit exceeded")
                    return ""
            else:
                # Other error, don't retry
                log(f"    Gemini OCR failed: {e}")
                return ""

    return ""


def ocr_pdf_page(pdf_path, page_num, lang="tam", is_first_page=False, is_last_page=False):
    """OCR a PDF page using the configured backend (Tesseract or Gemini).

    Returns the OCR'd text, or empty string on failure.
    """
    if OCR_BACKEND == "gemini":
        return ocr_pdf_page_gemini(pdf_path, page_num, is_first_page=is_first_page, is_last_page=is_last_page)
    else:
        return ocr_pdf_page_tesseract(pdf_path, page_num, lang=lang)


def _parse_page1_lines(lines):
    """Parse page 1 lines to extract title and translator.

    Skips common headers/logos that appear before the actual title.
    """
    # Common headers/logos to skip (case-insensitive)
    skip_patterns = [
        r'^EETHAL$',
        r'^Pratham\s*Books?$',
        r'^StoryWeaver$',
        r'^www\.',
        r'^http',
        r'^\d+$',  # Just numbers
        r'^```+$',  # Markdown code fences
        r'^[*#-]+$',  # Special characters only
    ]

    # Find the first line that's not a header/logo
    title = ""
    for line in lines:
        # Skip empty lines
        if not line.strip():
            continue
        # Skip lines matching skip patterns
        if any(re.match(pattern, line.strip(), re.IGNORECASE) for pattern in skip_patterns):
            continue
        # This is likely the title
        title = line.strip()
        break

    # If no title found, fall back to first non-empty line
    if not title and lines:
        title = lines[0]

    translator = ""
    for line in lines:
        m = re.match(r"(?:Translator|Translated by)[:\s]+(.+)", line, re.IGNORECASE)
        if m:
            translator = m.group(1).strip()
            break

    return {"title": title, "translator": translator}


def extract_page1_info(pdf_path, is_tamil=False):
    """
    Extract the story title and translator name from page 1 of a PDF.

    First tries PyMuPDF text extraction. For Tamil PDFs, if the result is
    garbled (broken font encoding), falls back to OCR via Tesseract.

    Returns a dict with 'title' and 'translator' keys.
    """
    try:
        doc = fitz.open(pdf_path)
        first_page = doc[0]
        text = first_page.get_text()
        doc.close()

        if not text:
            return {"title": "", "translator": ""}

        lines = [line.strip() for line in text.strip().split("\n") if line.strip()]
        result = _parse_page1_lines(lines)

        # For Tamil PDFs, check if the title is garbled and try OCR
        if is_tamil and is_garbled_text(result["title"]):
            log("    Text layer garbled — trying OCR on page 1...")
            ocr_text = ocr_pdf_page(pdf_path, 0, lang="tam", is_first_page=True)
            if ocr_text:
                ocr_lines = [l.strip() for l in ocr_text.split("\n") if l.strip()]
                ocr_result = _parse_page1_lines(ocr_lines)
                if not is_garbled_text(ocr_result["title"]):
                    return ocr_result

        return result

    except Exception as e:
        log(f"    Error reading page 1: {e}")
        return {"title": "", "translator": ""}


def _is_footer_line(line):
    """Check if a line is part of the Pratham Books footer or metadata (works with OCR typos)."""
    lower = line.lower()
    # Match "Pratham Books", "pratham books", OCR variants like "Pratham 800ks"
    if "pratham" in lower:
        return True
    if "goes digital" in lower:
        return True
    # StoryWeaver references
    if "storyweaver" in lower or "story weaver" in lower:
        return True
    # Website URLs
    if "www." in lower or "http" in lower or ".org" in lower or ".com" in lower:
        return True
    # License/legal text
    if "creative commons" in lower or "cc by" in lower:
        return True
    if "license" in lower or "copyright" in lower:
        return True
    # Tamil footer text
    if "பிரதம் புக்ஸ்" in line:
        return True
    # Tamil "StoryWeaver" transliteration
    if "ஸ்டோரி வீவர்" in line or "ஸ்டோரிவீவர்" in line:
        return True
    return False


def _is_level_marker(line):
    """Check if a line is the level/reading-level marker."""
    lower = line.lower()
    if "this is a level" in lower or "this book" in lower:
        return True
    # Tamil level markers
    if "இந்த நிலை" in line or "நிலை" in line and "கதை" in line:
        return True
    return False


def _is_level_description(line):
    """Check if a line is the reading level description (not the story description).

    These lines describe what level of reader the book is for, not the story itself.
    Example: "This is a Level 2 book for children learning to read..."
    Tamil: "இந்த நிலை 2 புத்தகம் பழகிய சொற்களை..."
    """
    lower = line.lower()
    stripped = line.strip()

    # Just "Level N" by itself (very common false positive)
    if re.match(r'^Level\s+\d+\s*$', stripped, re.IGNORECASE):
        return True

    # Just "நிலை N" in Tamil
    if re.match(r'^நிலை\s*\d+\s*$', stripped):
        return True

    # English level descriptions
    if "this is a level" in lower and "book" in lower:
        return True
    if "this book" in lower and ("reader" in lower or "children" in lower):
        return True

    # Tamil level descriptions
    # "இந்த நிலை" = "This level"
    # "புத்தகம்" = "book"
    # "குழந்தைகளுக்கானது" = "for children"
    if "இந்த நிலை" in line and "புத்தகம்" in line:
        return True
    if "நிலை" in line and ("புத்தகம்" in line or "குழந்தைகளுக்கானது" in line):
        return True

    return False


def _is_valid_description(text):
    """Check if extracted text is a valid story description.

    Returns False if text is:
    - Too short (less than 10 characters)
    - Just a level marker like "Level 4"
    - Mostly garbled (mixed ASCII and Tamil in wrong way)
    """
    if not text or len(text.strip()) < 10:
        return False

    stripped = text.strip()

    # Just level markers
    if re.match(r'^Level\s+\d+\s*$', stripped, re.IGNORECASE):
        return False
    if re.match(r'^நிலை\s*\d+\s*$', stripped):
        return False

    # Check if it's a level description (not story description)
    if _is_level_description(stripped):
        return False

    return True


def _clean_description(text):
    """Clean up extracted description text by removing trailing metadata.

    Removes common trailing words like 'StoryWeaver', URLs, etc.
    """
    if not text:
        return text

    # Remove trailing StoryWeaver references (case-insensitive)
    text = re.sub(r'\s*(?:story\s*weaver|storyweaver)\s*$', '', text, flags=re.IGNORECASE)

    # Remove trailing URLs or website references
    text = re.sub(r'\s*(?:www\.|http)[^\s]*\s*$', '', text, flags=re.IGNORECASE)

    # Remove trailing punctuation that might be left over
    text = re.sub(r'\s*[,\.\-]+\s*$', '', text)

    return text.strip()


def _parse_description_lines(lines):
    """Parse last-page lines to extract the description between language tag and footer.

    Strategy:
      1. Find the language tag line (e.g. "(Tamil)" or "(தமிழ்)")
      2. Description starts 2 lines after it (skip title)
      3. Description ends before "Pratham Books" footer

    If no language tag is found, tries a fallback: find the footer and take
    content between the level marker and the footer, skipping the first 3 lines
    (level marker + language tag + title).
    """
    # --- Primary: find language tag ---
    lang_idx = None
    for i, line in enumerate(lines):
        if any(tag in line for tag in LANG_TAGS):
            lang_idx = i
            break

    if lang_idx is not None:
        desc_start = lang_idx + 2
    else:
        # Fallback: find the level marker, description starts 3 lines after
        level_idx = None
        for i, line in enumerate(lines):
            if _is_level_marker(line):
                level_idx = i
                break
        if level_idx is not None:
            desc_start = level_idx + 3  # skip level + lang tag + title
        else:
            # Last resort: skip first 3 lines (they're usually level/tag/title)
            desc_start = min(3, len(lines))

    # Find the footer
    desc_end = len(lines)
    for i in range(desc_start, len(lines)):
        if _is_footer_line(lines[i]):
            desc_end = i
            break

    # Filter out individual lines that look like metadata or level descriptions
    desc_lines = []
    for line in lines[desc_start:desc_end]:
        # Skip lines that are just metadata
        if _is_footer_line(line):
            continue
        # Skip reading level descriptions (not story descriptions)
        if _is_level_description(line):
            continue
        desc_lines.append(line)

    if not desc_lines:
        return None

    # Join and clean up
    description = " ".join(desc_lines)
    description = _clean_description(description)

    # Validate the description before returning
    if description and not _is_valid_description(description):
        return None  # Reject invalid descriptions like "Level 4"

    return description if description else None


def extract_description_from_pdf(pdf_path, is_tamil=False):
    """
    Extract the story description from the last page of a PDF.

    First tries PyMuPDF text extraction. For Tamil PDFs, if the result is
    garbled, falls back to OCR via Tesseract.

    PyMuPDF line order on last page:
      1. Level marker line ("This is a Level..." or Tamil equivalent)
      2. (English) or (Tamil)
      3. Title
      4. Description text (one or more lines)
      5. "Pratham Books goes digital..."
    """
    try:
        doc = fitz.open(pdf_path)
        last_page = doc[-1]
        text = last_page.get_text()
        doc.close()

        if not text:
            return "[No text found on last page]"

        lines = [line.strip() for line in text.strip().split("\n") if line.strip()]
        description = _parse_description_lines(lines)

        # For Tamil PDFs, check if the description is garbled and try OCR
        if is_tamil and (description is None or is_garbled_text(description)):
            log("    Text layer garbled — trying OCR on last page...")
            page_count = fitz.open(pdf_path).page_count
            ocr_text = ocr_pdf_page(pdf_path, page_count - 1, lang="tam", is_last_page=True)
            if ocr_text:
                ocr_lines = [l.strip() for l in ocr_text.split("\n") if l.strip()]
                ocr_desc = _parse_description_lines(ocr_lines)
                if ocr_desc and not is_garbled_text(ocr_desc):
                    return ocr_desc

        if description is None:
            return "[No description found on last page]"

        return description if description else "[No description found]"

    except Exception as e:
        return f"[Error reading PDF: {e}]"



def main():
    global QUIET, OCR_BACKEND
    args = parse_args()
    QUIET = args.quiet
    OCR_BACKEND = args.ocr

    # Validate OCR backend availability
    if OCR_BACKEND == "gemini":
        if not HAS_GEMINI:
            print(
                "Error: Gemini OCR selected but google-generativeai not installed.\n"
                "Install with: pip install google-generativeai\n"
                "Or use --ocr tesseract instead.",
                file=sys.stderr,
            )
            sys.exit(1)
        if not os.environ.get("GEMINI_API_KEY"):
            print(
                "Error: Gemini OCR selected but GEMINI_API_KEY environment variable not set.\n"
                "Get your API key from: https://aistudio.google.com/app/apikey\n"
                "Then set it with: export GEMINI_API_KEY='your-key-here'\n"
                "Or use --ocr tesseract instead.",
                file=sys.stderr,
            )
            sys.exit(1)
        log("Using Gemini Vision API for OCR")
    elif OCR_BACKEND == "tesseract":
        if not HAS_TESSERACT:
            print(
                "Error: Tesseract OCR selected but pytesseract not installed.\n"
                "Install with: pip install pytesseract Pillow\n"
                "Or use --ocr gemini instead.",
                file=sys.stderr,
            )
            sys.exit(1)
        log("Using Tesseract for OCR")

    # Step 1: Fetch and parse the spreadsheet
    try:
        csv_text = fetch_spreadsheet_csv()
    except Exception as e:
        print(f"Error fetching spreadsheet: {e}", file=sys.stderr)
        sys.exit(1)

    all_rows = parse_all_rows(csv_text)
    max_row = all_rows[-1]["row_num"] if all_rows else 1

    if args.rows:
        # Parse range like "5-10" or single number like "7" (spreadsheet row numbers)
        match = re.match(r'^(\d+)(?:-(\d+))?$', args.rows)
        if not match:
            print(f"Error: invalid --rows format '{args.rows}'. Use e.g. '5-10' or '7'.",
                  file=sys.stderr)
            sys.exit(1)
        row_start = int(match.group(1))
        row_end = int(match.group(2)) if match.group(2) else row_start
        if row_start < 2:
            print(f"Error: row 1 is the header. Data rows start at 2.", file=sys.stderr)
            sys.exit(1)
        if row_end < row_start:
            print(f"Error: invalid --rows range {row_start}-{row_end}.", file=sys.stderr)
            sys.exit(1)
        if row_start > max_row:
            print(f"Error: start row {row_start} exceeds last data row ({max_row}).",
                  file=sys.stderr)
            sys.exit(1)
        # Filter to the requested spreadsheet row range, then to SW-link rows
        rows_in_range = [r for r in all_rows if row_start <= r["row_num"] <= row_end]
        stories = [r for r in rows_in_range if r["sw_link_eng"] or r["sw_link_tam"]]
        if not stories:
            print(f"No stories with SW links found in rows {row_start}-{row_end}.")
            sys.exit(0)
        log(f"Processing {len(stories)} stories from spreadsheet rows {row_start}-{row_end}.")
    else:
        stories = [r for r in all_rows if r["sw_link_eng"] or r["sw_link_tam"]]

    if not args.rows and args.limit > 0:
        stories = stories[:args.limit]
        log(f"Limited to first {args.limit} stories.")

    fetch_eng = args.lang in ("both", "eng")
    fetch_tam = args.lang in ("both", "tam")
    total_pdfs = sum((1 if fetch_eng and s["pdf_eng"] else 0) +
                     (1 if fetch_tam and s["pdf_tam"] else 0)
                     for s in stories)
    log(f"Found {len(stories)} stories with SW links, {total_pdfs} PDFs to process.")

    if not stories:
        print("No stories with SW links found.")
        sys.exit(0)

    # Step 2: Authenticate with OAuth if credentials are available (for Drive + Translation + Sheets)
    drive_service = None
    oauth_creds = None
    sheets_service = None
    if os.path.exists(TOKEN_PATH) or os.path.exists(CREDENTIALS_PATH):
        try:
            drive_service, oauth_creds = get_drive_service()
            log("Using OAuth for Drive API and Translation API.")
        except Exception as e:
            log(f"OAuth failed ({e}), falling back to public download and no translation.")
        if oauth_creds:
            try:
                sheets_service = get_sheets_service(oauth_creds)
                log("Sheets API service initialized for image URL updates.")
            except Exception as e:
                log(f"Sheets API initialization failed ({e}), image URLs will not be written to spreadsheet.")

    # Step 3: Download PDFs and extract descriptions + page 1 info
    start_time = time.time()
    results = []

    with tempfile.TemporaryDirectory() as tmpdir:
        for idx, story in enumerate(stories, 1):
            elapsed = time.time() - start_time
            print(f"\n{'='*70}")
            print(f"[{idx}/{len(stories)}] Row {story['row_num']}: {story['english_title']} / {story['tamil_title']}  (elapsed: {elapsed:.0f}s)")
            print(f"{'='*70}")

            eng_desc = ""
            tam_desc = ""
            eng_pdf_title = ""
            tam_pdf_title = ""
            translator = ""
            image_url = None

            # English PDF
            if fetch_eng and story["pdf_eng"]:
                pdf_path = os.path.join(tmpdir, f"eng_{idx}.pdf")
                log(f"    Downloading English PDF...")
                if download_pdf(story["pdf_eng"], pdf_path, drive_service):
                    page1 = extract_page1_info(pdf_path)
                    eng_pdf_title = page1["title"]
                    if page1["translator"]:
                        translator = page1["translator"]
                    print(f"  >> English title (from PDF): {eng_pdf_title}")
                    if translator:
                        print(f"  >> Translator: {translator}")

                    eng_desc = extract_description_from_pdf(pdf_path)
                    print(f"  >> English description: {eng_desc}")

                    # Extract and upload cover image
                    image_url = process_cover_image(
                        pdf_path, story, drive_service, sheets_service, tmpdir, idx
                    )
                else:
                    eng_desc = "[Download failed]"
                    print(f"  >> English: {eng_desc}")
            elif fetch_eng:
                print("  English PDF: [not available]")

            # Tamil: Always download PDF for title, but translate description from English
            if fetch_tam and story["pdf_tam"]:
                pdf_path = os.path.join(tmpdir, f"tam_{idx}.pdf")
                log(f"    Downloading Tamil PDF...")
                if download_pdf(story["pdf_tam"], pdf_path, drive_service):
                    # Always extract Tamil title from PDF
                    page1 = extract_page1_info(pdf_path, is_tamil=True)
                    tam_pdf_title = page1["title"]
                    if not translator and page1["translator"]:
                        translator = page1["translator"]
                    print(f"  >> Tamil title (from PDF): {tam_pdf_title}")

                    # For description: prefer translation, fallback to PDF extraction
                    if eng_desc and eng_desc != "[Download failed]":
                        log(f"    Translating English description to Tamil...")
                        tam_desc = translate_to_tamil(eng_desc, oauth_creds=oauth_creds)
                        if tam_desc:
                            print(f"  >> Tamil description (translated): {tam_desc[:100]}...")
                        else:
                            log(f"    Translation failed, extracting from Tamil PDF...")
                            tam_desc = extract_description_from_pdf(pdf_path, is_tamil=True)
                            print(f"  >> Tamil description (from PDF): {tam_desc}")
                    else:
                        # No English description, extract from Tamil PDF
                        tam_desc = extract_description_from_pdf(pdf_path, is_tamil=True)
                        print(f"  >> Tamil description (from PDF): {tam_desc}")
                else:
                    print(f"  >> Tamil PDF: [Download failed]")
            elif fetch_tam:
                print("  Tamil PDF: [not available]")

            # Use PDF-extracted values if available, fall back to spreadsheet values
            results.append({
                "english_title": eng_pdf_title or story["english_title"],
                "tamil_title": tam_pdf_title or story["tamil_title"],
                "pdf_eng": story["pdf_eng"],
                "pdf_tam": story["pdf_tam"],
                "image": image_url or story["image"],
                "sw_link_eng": story["sw_link_eng"],
                "sw_link_tam": story["sw_link_tam"],
                "translators": translator or story["translators"],
                "english_description": eng_desc or story["english_description"],
                "tamil_description": tam_desc or story["tamil_description"],
                "status": story["status"],
                "tags": story["tags"],
            })

    total_elapsed = time.time() - start_time
    log(f"Total time: {total_elapsed:.0f}s. Done.")

    # Step 4: Write output CSV if requested
    if args.output and results:
        fieldnames = [
            "english_title", "tamil_title",
            "pdf_eng", "pdf_tam", "image",
            "sw_link_eng", "sw_link_tam",
            "translators",
            "english_description", "tamil_description",
            "status", "tags",
        ]
        # Use human-readable headers matching the spreadsheet
        header_map = {
            "english_title": "English Title",
            "tamil_title": "Tamil Title",
            "pdf_eng": "English PDF",
            "pdf_tam": "Tamil PDF",
            "image": "Image",
            "sw_link_eng": "SW link-Eng",
            "sw_link_tam": "SW link Tamil",
            "translators": "Translators",
            "english_description": "English Description",
            "tamil_description": "Tamil Description",
            "status": "Status",
            "tags": "Tags",
        }
        with open(args.output, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            # Write custom header row
            f.write(",".join(header_map[col] for col in fieldnames) + "\n")
            writer.writerows(results)
        print(f"\nResults written to {args.output} ({len(results)} rows)")


if __name__ == "__main__":
    main()
