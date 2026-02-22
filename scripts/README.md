# EETHAL Foundation Story Management Scripts

This folder contains Python scripts for managing EETHAL Foundation story data, including extracting metadata from PDFs and managing the story database.

## Scripts Overview

| Script | Purpose |
|--------|---------|
| `extract_stories.py` | Extract titles, translators, and descriptions from Tamil/English story PDFs |
| `add_stories.py` | Add new stories to the website |
| `delete_stories.py` | Remove stories from the website |
| `publish.sh` | Build, commit, and deploy to production |

---

## `extract_stories.py` - Story Metadata Extraction

Automatically extracts story metadata from PDFs hosted on Google Drive and outputs to CSV format.

### Features

- ✅ **Dual OCR Support**: Uses Google Gemini API (recommended) or Tesseract for Tamil text extraction
- ✅ **Smart Text Parsing**: Automatically detects and handles garbled Tamil fonts
- ✅ **Metadata Filtering**: Removes headers, footers, and reading level descriptions
- ✅ **Rate Limit Handling**: Automatic retry and delay for API rate limits
- ✅ **Google Drive Integration**: Downloads PDFs directly from Google Drive
- ✅ **Batch Processing**: Process all stories or limit to a specific number

### Quick Start

#### 1. Setup Environment

```bash
# Create and activate virtual environment (if not already done)
cd /path/to/eethal_foundation_website
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

#### 2. Configure Gemini API (Recommended)

**Get API Key:**
1. Visit https://aistudio.google.com/app/apikey
2. Create a new API key (free tier available)
3. Copy the API key

**Set Environment Variable:**
```bash
# For current session
export GEMINI_API_KEY="your-api-key-here"

# Or add to ~/.zshrc for persistence
echo 'export GEMINI_API_KEY="your-api-key-here"' >> ~/.zshrc
source ~/.zshrc
```

#### 3. Run the Script

```bash
# Extract all stories with Gemini OCR (default)
python scripts/extract_stories.py -o stories.csv

# Process first 10 stories only
python scripts/extract_stories.py -n 10 -o test.csv

# Extract Tamil descriptions only (faster)
python scripts/extract_stories.py --lang tam -o tamil_stories.csv

# Use Tesseract instead of Gemini
python scripts/extract_stories.py --ocr tesseract -o stories.csv
```

### Command-Line Options

| Option | Description | Default |
|--------|-------------|---------|
| `-o`, `--output FILE` | Output CSV file path | stdout |
| `-n`, `--limit N` | Process only first N stories | all |
| `--lang {both,eng,tam}` | Which descriptions to extract | both |
| `--ocr {gemini,tesseract}` | OCR backend to use | gemini |
| `-q`, `--quiet` | Suppress verbose logs | false |
| `--make-public` | Make Drive files publicly accessible | false |

### Examples

```bash
# Test with 5 stories
python scripts/extract_stories.py -n 5 -o test_output.csv

# Extract only English descriptions
python scripts/extract_stories.py --lang eng -o english_only.csv

# Quiet mode with Tamil only
python scripts/extract_stories.py --lang tam -q -o tamil_quiet.csv

# Batch processing for paid Gemini tier
python scripts/extract_stories.py -o all_stories.csv
```

### OCR Backends

#### Gemini API (Recommended)

**Model Used:** `gemini-2.5-pro` - Most capable model for complex Tamil fonts

**Pros:**
- ✅ **Best Tamil accuracy** - Superior multilingual support
- ✅ **Context-aware** - Understands document structure
- ✅ **No local dependencies** - Works out of the box
- ✅ **Handles complex layouts** - Multi-column, decorative fonts
- ✅ **Better with broken fonts** - Handles encoding issues well

**Cons:**
- ⚠️ **Rate limits** - Free tier: 5 requests/min, 20 requests/day
- ⚠️ **Requires API key** - Need to set up Google account

**Free Tier Limits:**
- 5 requests per minute
- 20 requests per day
- ~10 stories per day (2 OCR calls per story)

**Cost to Upgrade:**
- ~$0.00032 per image (~$0.32 per 1000 images)
- New limits: 1000 req/min, 10,000 req/day
- Process entire collection (400 images) for < $0.15

#### Tesseract OCR (Fallback)

**Pros:**
- ✅ **No rate limits** - Process unlimited stories
- ✅ **Free forever** - No API costs
- ✅ **Works offline** - No internet required

**Cons:**
- ❌ **Lower Tamil accuracy** - Often produces garbled text
- ⚠️ **Requires local install** - Must install Tesseract + Tamil language pack

**Setup Tesseract:**
```bash
# macOS
brew install tesseract tesseract-lang

# Verify Tamil support
tesseract --list-langs | grep tam
```

### How It Works

1. **Fetch Spreadsheet**: Downloads story metadata from Google Sheets
2. **Filter Stories**: Processes only rows with StoryWeaver links (columns F & G)
3. **Download PDFs**: Gets English & Tamil PDFs from Google Drive
4. **Extract Text**:
   - First tries direct PDF text extraction (PyMuPDF)
   - If text is garbled, falls back to OCR (Gemini or Tesseract)
5. **Parse Metadata**:
   - **Page 1**: Story title, translator name
   - **Last Page**: Story description
6. **Clean & Filter**: Removes headers, footers, level descriptions, metadata
7. **Output CSV**: Writes all data to CSV file

### Input Spreadsheet Format

The script reads from a Google Spreadsheet with these columns:

| Column | Content | Used For |
|--------|---------|----------|
| A | English Title | Fallback if PDF extraction fails |
| B | Tamil Title | Fallback if PDF extraction fails |
| C | English PDF (Drive link) | Extract English metadata |
| D | Tamil PDF (Drive link) | Extract Tamil metadata |
| E | Image (Drive link) | Story cover image |
| F | StoryWeaver link (English) | Filter criteria |
| G | StoryWeaver link (Tamil) | Filter criteria |
| H | Translators | Fallback if PDF extraction fails |
| I | English Description | Fallback if PDF extraction fails |
| J | Tamil Description | Fallback if PDF extraction fails |
| K | Status | Story status |

**Note:** Only rows with values in columns F or G (StoryWeaver links) are processed.

### Output CSV Format

The output CSV contains all columns from the input spreadsheet, with extracted values replacing empty fields:

```csv
English Title,Tamil Title,English PDF,Tamil PDF,Image,SW link-Eng,SW link Tamil,Translators,English Description,Tamil Description,Status
Lazy Anansi,சோம்பேறி அனன்சி,https://drive.google.com/...,https://drive.google.com/...,https://drive.google.com/...,https://storyweaver.org.in/...,https://storyweaver.org.in/...,Translator Name,The reason why spiders have...,சிலந்திகளுக்கு நீண்ட மெல்லிய...,Published
```

### Rate Limiting & Performance

#### Free Tier (Gemini)
- **Limit**: 5 requests/minute, 20 requests/day
- **Per story**: ~2 OCR calls (title + description)
- **Daily capacity**: ~10 stories
- **Processing time**: ~26 seconds per story needing OCR

#### Paid Tier (Gemini)
- **Cost**: < $0.001 per story
- **Limit**: 1000 requests/minute
- **Daily capacity**: Unlimited
- **Total cost for 100 stories**: < $0.10

#### Tesseract (Free, Unlimited)
- **Limit**: None
- **Processing time**: ~5 seconds per story
- **Quality**: Lower (garbled Tamil text common)

### Troubleshooting

#### Issue: "Rate limit exceeded"

```bash
# Solution 1: Process in smaller batches
python scripts/extract_stories.py -n 10 -o batch1.csv  # Day 1
python scripts/extract_stories.py -n 10 -o batch2.csv  # Day 2 (skip first 10 manually)

# Solution 2: Upgrade to paid tier (< $1 for full collection)
# Visit: https://aistudio.google.com/app/apikey

# Solution 3: Use Tesseract (lower quality)
python scripts/extract_stories.py --ocr tesseract -o stories.csv
```

#### Issue: "GEMINI_API_KEY not set"

```bash
# Check if key is set
echo $GEMINI_API_KEY

# Set for current session
export GEMINI_API_KEY="your-key-here"

# Set permanently
echo 'export GEMINI_API_KEY="your-key-here"' >> ~/.zshrc
source ~/.zshrc
```

#### Issue: Tamil text looks garbled in terminal

**This is normal!** The terminal encoding may not support Tamil characters. The actual CSV file contains correct UTF-8 Tamil text. Verify by:
1. Opening the CSV in Google Sheets
2. Opening the CSV in Excel (with UTF-8 encoding)
3. Viewing with: `less -r output.csv`

#### Issue: Wrong title extracted (shows "EETHAL")

This means the script extracted a header instead of the title. The latest version has improved header detection. If it still occurs:
1. Report the specific story number
2. The script will continue to improve header detection patterns

#### Issue: Description contains reading level text

Example: "இந்த நிலை 2 புத்தகம் பழகிய சொற்களை..."

The latest version filters these out. If you still see them:
1. Update to the latest version of the script
2. The `_is_level_description()` function filters these patterns

### Advanced Usage

#### Making Drive Files Public

If PDFs are private, you can make them public using the Drive API:

**Setup (one-time):**
1. Go to https://console.cloud.google.com/
2. Create a project and enable Google Drive API
3. Create OAuth credentials (Desktop app)
4. Download `credentials.json` to scripts folder

**Usage:**
```bash
python scripts/extract_stories.py --make-public
```

This sets "anyone with link can view" permission on all Drive files in the spreadsheet.

#### Resuming After Interruption

The script processes stories sequentially. If interrupted, use `-n` to skip already processed stories:

```bash
# First run (interrupted after 15 stories)
python scripts/extract_stories.py -o stories.csv  # Interrupted!

# Continue from story 16 (manually edit spreadsheet or use different approach)
# Note: Built-in resume feature not yet implemented
```

---

## `add_stories.py` - Add New Stories

Automates the process of adding bilingual stories to the Hugo website. Supports three modes: Google Sheets, CSV file, or individual CLI arguments.

### Features

- ✅ **Batch Processing**: Add multiple stories from Google Sheets or CSV
- ✅ **Automatic Downloads**: Fetches cover images from Google Drive
- ✅ **Smart Caching**: Skips re-downloading existing images
- ✅ **Status Tracking**: Processes only rows without "done" status
- ✅ **Validation**: Checks for required fields before processing
- ✅ **URL Conversion**: Automatically converts Google Drive URLs to embed format

### Usage

#### 1. From Google Sheets (Recommended)

```bash
# Use default configured Google Sheet
python scripts/add_stories.py --from-google-sheet

# Or specify a different Google Sheet
python scripts/add_stories.py --from-google-sheet "https://docs.google.com/spreadsheets/d/SHEET_ID/edit"
```

**Requirements:**
- Google Sheet must be shared with "Anyone with the link can view" OR
- Published to web (File → Share → Publish to web → CSV)

#### 2. From Local CSV File

```bash
python scripts/add_stories.py --from-csv ~/Downloads/stories.csv
```

**CSV Format:**
Must include these columns:
- English Title
- Tamil Title
- English PDF (Google Drive URL)
- Tamil PDF (Google Drive URL)
- Image (Google Drive URL)
- Translators
- English Description
- Tamil Description
- Status (optional - rows with "done" are skipped)

#### 3. Single Story via CLI

```bash
python scripts/add_stories.py \
    --english-title "My Big Family" \
    --tamil-title "என்னுடைய பெரிய குடும்பம்" \
    --english-pdf "https://drive.google.com/file/d/FILE_ID/view" \
    --tamil-pdf "https://drive.google.com/file/d/FILE_ID/view" \
    --translators "Name1, Name2" \
    --english-description "A heartwarming story about..." \
    --tamil-description "குடும்பத்தைப் பற்றிய ஒரு அன்பான கதை..." \
    --cover-image ~/Downloads/cover.jpg
```

### How It Works

1. **Validates** all required fields for each story
2. **Creates slug** from English title (e.g., "My Story" → "my-story")
3. **Downloads cover image** from Google Drive (or uses cached version)
4. **Creates story directory** at `content/stories/{slug}/`
5. **Copies cover image** to story directory
6. **Generates index.md** with Hugo front matter
7. **Reports results** with success/failure counts

### Story Directory Structure

```
content/stories/my-story/
├── index.md          # Hugo front matter with metadata
└── cover.jpg         # Cover image
```

### Output Summary

```
=================================================
CSV Processing Complete
=================================================
Total rows:     15
Successful:     14
Failed:         1

Failed stories:
  - Row 8: "The Lost Key" - Image download failed: Invalid URL
```

### Error Handling

The script handles these common errors:
- Missing required fields
- Invalid Google Drive URLs
- Image download failures
- Invalid image file types

Failed stories are reported at the end with specific error messages.

### Tips

- **Status Column**: Add a "Status" column to your CSV/Sheet and mark completed stories as "done" to skip them on subsequent runs
- **Caching**: If a story directory already exists with a cover image, the script reuses it instead of re-downloading
- **Translators**: Can be comma-separated or newline-separated
- **Google Drive URLs**: Both `/view` and `/open` formats are supported

---

## `delete_stories.py` - Remove Stories

Safely removes story directories from the website with confirmation prompts.

### Features

- ✅ **List Stories**: View all available stories with titles
- ✅ **Preview Deletion**: Shows files that will be deleted
- ✅ **Confirmation**: Asks for confirmation before deletion (unless --force)
- ✅ **Git Integration**: Provides git commands for committing deletion

### Usage

#### List All Stories

```bash
python scripts/delete_stories.py --list
```

**Output:**
```
Available stories (14):
  - my-big-family              (My Big Family)
  - the-lost-key               (The Lost Key)
  - sharing-is-caring          (Sharing is Caring)
  ...
```

#### Delete a Story

```bash
python scripts/delete_stories.py my-big-family
```

**Interactive Prompt:**
```
Story to delete: my-big-family
Location: content/stories/my-big-family
Files to be removed:
  - index.md
  - cover.jpg

Are you sure you want to delete 'my-big-family'? (yes/no): yes

✅ Story 'my-big-family' deleted successfully

Next steps:
1. Commit the deletion:
   git add content/stories/my-big-family
   git commit -m 'Delete story: my-big-family'
```

#### Force Delete (No Confirmation)

```bash
python scripts/delete_stories.py my-big-family --force
```

### Parameters

| Option | Description |
|--------|-------------|
| `slug` | Story slug (directory name) to delete |
| `--list` | List all available stories |
| `--force` | Skip confirmation prompt |

### Safety Features

- **Verification**: Checks if story exists before deletion
- **Preview**: Shows all files that will be removed
- **Confirmation**: Requires "yes" or "y" to proceed (unless --force)
- **Clear Feedback**: Shows exactly what was deleted
- **Git Guidance**: Provides commands for committing the change

### Finding Story Slugs

Story slugs are the directory names in `content/stories/`. To find them:

1. **Using the script:**
   ```bash
   python scripts/delete_stories.py --list
   ```

2. **Manually:**
   ```bash
   ls content/stories/
   ```

3. **From URL:**
   If the story URL is `https://eethalfoundation.org/stories/my-big-family/`, the slug is `my-big-family`

---

## `publish.sh` - Publish to Production

Builds CSS, commits pending changes, pushes dev, merges to master, and triggers Vercel deployment.

### Features

- ✅ **Full Pipeline**: CSS build → commit → push dev → merge to master → push master
- ✅ **Interactive Prompts**: Asks for commit message and shows pending changes
- ✅ **Dry Run Mode**: Preview without making any changes
- ✅ **CSS Watcher Handling**: Automatically stops watcher and reminds you to restart
- ✅ **Safety Checks**: Verifies git repo, branch, and shows commits before deploying

### Usage

```bash
# Full publish (interactive)
./scripts/publish.sh

# Preview what would be published
./scripts/publish.sh --dry-run

# Publish with a custom commit message
./scripts/publish.sh -m "Add new stories"
```

### Options

| Option | Description |
|--------|-------------|
| _(no options)_ | Interactive mode: build, commit, and deploy |
| `--dry-run` | Preview changes without making any |
| `-m "message"` | Use a custom commit message |
| `--help`, `-h` | Show help message |

### How It Works

1. **Stops CSS watcher** if running
2. **Builds minified CSS** (`npm run build:css`)
3. **Commits pending changes** (interactive prompt for message)
4. **Pushes dev** to origin
5. **Merges dev into master** and pushes (triggers Vercel deploy)
6. **Switches back to dev**

### Common Workflows

#### Add Stories from CSV, Then Publish

```bash
# Step 1: Add stories from CSV
python scripts/add_stories.py --from-csv stories.csv

# Step 2: Preview what would be published
./scripts/publish.sh --dry-run

# Step 3: Publish to production
./scripts/publish.sh
```

#### Quick Publish with Message

```bash
./scripts/publish.sh -m "Add 3 new stories"
```

---

## Dependencies

Install all dependencies with:

```bash
pip install -r requirements.txt
```

### Required Packages

```
requests>=2.31.0          # HTTP requests for spreadsheet & Drive
PyMuPDF>=1.24.0          # PDF text extraction
gdown>=5.0.0             # Google Drive downloads
certifi>=2023.0.0        # SSL certificates
google-api-python-client>=2.100.0    # Google Drive API
google-auth-oauthlib>=1.0.0          # OAuth authentication
pytesseract>=0.3.10      # Tesseract OCR (optional)
Pillow>=10.0.0           # Image processing
google-generativeai>=0.3.0           # Gemini API (recommended)
```

---

## Contributing

When adding new stories or modifying extraction logic:

1. **Test with small batches first**: Use `-n 5` to test changes
2. **Check both languages**: Verify English and Tamil extraction
3. **Inspect output CSV**: Open in Google Sheets to verify formatting
4. **Document rate limits**: Note any API usage when testing

---

## License

These scripts are part of the EETHAL Foundation website project.

---

## Support

For issues or questions:
1. Check the troubleshooting section above
2. Review the script's inline help: `python scripts/extract_stories.py --help`
3. Contact the EETHAL Foundation tech team
