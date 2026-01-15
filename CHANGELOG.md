# Changelog

## v12.34 (Current Stable)

**Release Date**: 2026-01-15

### Features Added
- **Text Size Slider**: Added adjustable text size control (50%-200%) in main version to match beta features
  - Automatically scales label font sizes and recalculates label box dimensions
  - Uses `getBBox()` for responsive label box sizing
  - Updates configuration on resize or slider change

### UI Improvements
- Renamed "Simple" toggle to "B&W" for clarity
- Integrated experimental `labelbox-v2.html` features into main `index.html`

### Bug Fixes
- Fixed export image function to render mana symbols (W/U/B/R/G) correctly
  - Previous issue: SVG `foreignObject` elements with web fonts didn't serialize properly
  - Solution: Draw mana symbol letters directly on canvas after SVG render
  - Preserves original web font display on live page while fixing export functionality

### Changes Made
- Updated `getConfig()` function to accept optional `textSizeMultiplier` parameter
- Added `textSize` state and effects for reactive configuration updates
- Disabled export image button on main version (still active on beta `labelbox-v2.html`)
- Version updated from v12.33 to v12.34

### Files Modified
- `index.html` (main): v12.33 → v12.34
- `labelbox-v2.html` (beta): v13.0-labelbox-v2 → v13.2-labelbox-v2

---

## v12.33

**Release Date**: 2026-01-15

### Features Added
- Initial export image function fix attempt with canvas-based mana symbol rendering

---

## v12.32 and Earlier

Previous versions maintained the core Lorwyn Eclipsed MTG color wheel visualization with responsive design and label box auto-sizing functionality.
