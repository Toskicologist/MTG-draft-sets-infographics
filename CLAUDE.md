# Project Notes for LLM Assistants

## Privacy & Personal Information

**CRITICAL:** This is a public GitHub repository. NEVER include:
- Personal names, usernames, or identifying information
- Local file paths (e.g., `C:\Users\...` or `/home/username/...`)
- Email addresses (except the generic noreply@anthropic.com for co-authoring)
- Any other personally identifiable information

When referencing local development:
- Use generic placeholders like "the repository directory" instead of full paths
- Use relative paths instead of absolute paths when possible
- Keep commit messages generic and professional

## GitHub Pages Deployment

**IMPORTANT:** The file served by GitHub Pages is `index.html`, NOT the versioned files.

When the user asks to update the live/deployed site:
- Edit `index.html` (this is what GitHub Pages serves)
- The versioned files (e.g., `lorwyn-color-wheel-v12.23-beta.1.html`) are working copies/archives
- After editing `index.html`, commit and push to deploy changes

## Git Repository

The git repo root is this folder (`extracted/`). To push changes:
```bash
# Navigate to the repository directory
git add index.html
git commit -m "Your message"
git push
```

## File Structure

- `index.html` - **DEPLOYED FILE** (GitHub Pages serves this)
- `lorwyn-color-wheel-v*.html` - Version history / working copies
- `*.jsx` - Earlier React component versions (not directly usable in browser)
