# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Hugo-based static website for the EETHAL Foundation (Education and Empowerment THrough Applied Languages), a non-profit organization focused on Tamil language preservation and youth education programs.

**Tech Stack:**
- **Hugo v0.154.2** - Static site generator
- **Tailwind CSS v3.4** - Utility-first CSS framework with custom EETHAL brand colors
- **PostCSS with Autoprefixer** - CSS processing pipeline
- **No Hugo theme** - Custom layouts built from scratch

## Development Commands

### Setup
```bash
npm install
```

### Development Workflow
```bash
# Start Hugo dev server with live reload (port 1313)
hugo server -D

# In a separate terminal: watch and rebuild CSS on changes
npm run watch:css
```

Visit http://localhost:1313/ to view the site during development.

### Building for Production
```bash
# Build optimized CSS
npm run build:css

# Build minified Hugo site (outputs to public/)
hugo --minify

# Or combine both steps
npm run build:css && hugo --minify
```

### Other Commands
```bash
# Build CSS once without watching
npm run build:css

# Create new content page
hugo new young-translators/new-page.md

# Check Hugo version
hugo version
```

## Architecture

### Site Structure

The Hugo site lives in the repository root:

```
eethal_foundation_website/
├── config.toml           # Site config, menus, params
├── content/              # Markdown content (edit here!)
├── layouts/              # HTML templates
│   ├── _default/
│   │   ├── baseof.html   # Base template with header/footer
│   │   ├── list.html     # Section list pages
│   │   └── single.html   # Individual pages
│   ├── index.html        # Homepage template
│   ├── partials/         # Reusable components
│   │   ├── header.html   # Navigation with dropdown
│   │   ├── footer.html   # Footer with social links
│   │   └── meta.html     # SEO meta tags
│   └── shortcodes/       # Custom content components
│       ├── cta.html      # Call-to-action boxes
│       ├── form.html     # Form wrapper
│       └── stats.html    # Statistics display
├── assets/
│   └── css/main.css      # Tailwind source (input)
└── static/
    ├── css/styles.css    # Compiled CSS (output)
    ├── images/           # Images and logo
    └── js/               # JavaScript files
```

### Template Hierarchy

Hugo follows a specific template lookup order:

1. **Homepage** → `layouts/index.html`
2. **Section pages** (e.g., /young-translators/) → `layouts/_default/list.html`
3. **Individual pages** → `layouts/_default/single.html`
4. **All pages inherit from** → `layouts/_default/baseof.html`

The `baseof.html` template defines the overall structure and loads partials for header/footer.

### Tailwind Configuration

Custom EETHAL brand colors are defined in `tailwind.config.js`:

```javascript
colors: {
  'eethal': {
    600: '#741f8a',  // Primary brand purple
    // ... other shades
  }
}
```

Custom utility classes in `assets/css/main.css`:
- `.btn-primary` / `.btn-secondary` - Branded buttons
- `.section-container` - Max-width container with responsive padding
- `.prose-eethal` - Typography styling

**Important**: Tailwind scans `layouts/**/*.html` and `content/**/*.md` for class names. After adding new Tailwind classes, rebuild CSS with `npm run build:css`.

### Navigation System

Navigation is configured in `config.toml` under `[menu]` sections:

- **Main menu** (`[menu.main]`) - Top-level navigation
- **Young Translators submenu** (`[menu.youngTranslators]`) - Dropdown items

The header partial (`layouts/partials/header.html`) renders a desktop navigation with a dropdown for "Young Translators" and a mobile hamburger menu.

### Content Management

Content uses Hugo's front matter (YAML) for metadata and markdown for body:

```yaml
---
title: "Page Title"
description: "SEO description"
hero:
  title: "Hero heading"
  subtitle: "Hero subheading"
---
Markdown content here...
```

**Shortcodes** allow embedding reusable components in markdown:

```markdown
{{< cta title="Join Us" link="/signup/" buttonText="Sign Up" >}}
Call to action content here.
{{< /cta >}}

{{< stats number="100+" label="Students Served" >}}

{{< form action="https://formspree.io/f/FORM_ID" >}}
  <!-- Form fields -->
{{< /form >}}
```

### Forms Integration

Forms use Formspree for submission handling. Form action URLs containing `YOUR_FORM_ID` are placeholders that need to be replaced with actual Formspree form IDs.

### CSS Build Pipeline

1. Source: `assets/css/main.css` (Tailwind directives)
2. Processing: Tailwind CLI → PostCSS → Autoprefixer
3. Output: `static/css/styles.css` (compiled CSS)
4. Referenced in `baseof.html`: `<link rel="stylesheet" href="/css/styles.css">`

The `watch:css` script monitors changes and rebuilds automatically during development.

## Deployment

The site is configured for deployment to Netlify or Vercel:

**Build command**: `npm run build:css && hugo --minify`
**Publish directory**: `public`
**Environment variable**: `HUGO_VERSION=0.154.2`

The base URL is set to `https://www.eethalfoundation.org/` in `config.toml`.

## Key Conventions

- **All paths are absolute from root** - Use `/images/logo.png`, not `images/logo.png`
- **Working directory is repository root** - Run all commands from `eethal_foundation_website/`
- **Draft pages** - Use `draft: true` in front matter; view with `hugo server -D`
- **Menu weights** - Lower numbers appear first in navigation
- **Brand color** - Use `eethal-600` class for primary purple (#741f8a)
- **Responsive design** - Mobile-first with Tailwind breakpoints (sm, md, lg)

## Important Notes

- The site has no Hugo theme installed - all templates are custom-built
- Markdown rendering allows unsafe HTML (`unsafe = true` in config.toml)
- Google Analytics is configured but currently empty (add ID in config.toml)
- Social media links (Facebook, YouTube) are in config.toml params
- The Lato font family is loaded from Google Fonts
- Mobile menu toggle functionality requires JavaScript in `/js/main.js`
