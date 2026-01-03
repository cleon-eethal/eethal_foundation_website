# EETHAL Foundation Website

A modern static website built with Hugo for the EETHAL Foundation.

## Quick Start

### Development

```bash
# Start Hugo development server with live reload
hugo server -D

# In a separate terminal, watch CSS changes
npm run watch:css
```

Visit http://localhost:1313/ to view the site.

### Build for Production

```bash
# Build CSS
npm run build:css

# Build Hugo site (outputs to public/)
hugo --minify
```

## Project Structure

```
eethal/
├── config.toml           # Site configuration
├── content/              # Markdown content files (edit these!)
│   ├── _index.md        # Homepage
│   ├── young-translators/
│   ├── donate/
│   └── contact/
├── layouts/              # HTML templates
│   ├── _default/
│   ├── partials/
│   └── shortcodes/
├── static/               # Static assets
│   ├── css/
│   ├── js/
│   └── images/
└── assets/               # Source files (CSS, JS)
```

## Adding Content

### Create a New Page

```bash
hugo new young-translators/new-page.md
```

### Edit Content

Just edit the markdown files in `content/` and save. Hugo will auto-reload!

### Use Shortcodes

**Call to Action:**
```markdown
{{< cta title="Get Involved" link="/young-translators/" buttonText="Sign Up" >}}
Join our program today!
{{< /cta >}}
```

**Stats:**
```markdown
{{< stats number="100+" label="Students Served" >}}
```

**Form:**
```markdown
{{< form action="https://formspree.io/f/YOUR_FORM_ID" >}}
  <!-- Form fields here -->
{{< /form >}}
```

## Next Steps

### 1. Set up Forms (Formspree)

1. Go to https://formspree.io/ and create a free account
2. Create forms for:
   - Contact
   - Student Signup
   - Adult Signup
   - Newsletter
3. Update form action URLs in content files (search for `YOUR_FORM_ID`)

### 2. Add Images

- Place your logo at `static/images/logo.png`
- Add hero background at `static/images/hero-background.jpg`
- Add team photos to `static/images/team/`

### 3. Migrate Content

Copy content from https://www.eethalfoundation.org/ into the markdown files in `content/`.

Refer to the CLAUDE.md file for the complete content migration checklist.

### 4. Deploy

**Option 1: Netlify (Recommended)**
1. Push code to GitHub
2. Connect repository to Netlify
3. Build command: `npm run build:css && hugo`
4. Publish directory: `public`
5. Add environment variable: `HUGO_VERSION` = `0.154.2`

**Option 2: Vercel**
1. Push code to GitHub
2. Import to Vercel
3. Framework: Hugo
4. Build command: `npm run build:css && hugo`
5. Output directory: `public`

## Customization

### Colors

Edit `tailwind.config.js` to change the purple brand colors.

### Navigation

Edit the `[menu]` sections in `config.toml`.

### Templates

Modify files in `layouts/` to change the HTML structure.

## Commands Reference

```bash
# Install dependencies
npm install

# Build CSS once
npm run build:css

# Watch CSS for changes
npm run watch:css

# Start dev server
hugo server -D

# Build production site
hugo --minify

# Full build
npm run build:css && hugo --minify
```

## Support

For questions about Hugo, visit https://gohugo.io/documentation/

For site-specific help, refer to CLAUDE.md
