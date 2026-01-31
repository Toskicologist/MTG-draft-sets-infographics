# Analytics & Social Media Graphics

This folder contains analytics visualizations and social media graphics for MTG draft data analysis.

## Projects

### Underrated/Overrated Cards
Compare expert predictions vs actual 17 Lands performance data to identify cards that were misjudged.

**Status:** Planned (not yet implemented)

**Data Sources:**
- Expert ratings: `../data/ecl/ecl-final-data.csv`
- 17 Lands GIH WR: `../data/17lands/17 lands card-ratings-2026-01-23.csv`
- Scryfall images: `../data/scryfall/scryfall_reference.json`

**See:** `/ANALYTICS_CHART_PROMPT.md` for full implementation prompt

## Development

Create new analytics files in this directory:
```bash
# Example
mtg/analytics/underrated-overrated.html
```

Test locally:
```bash
file:///C:/Users/User/ClaudeProjects/mtg/analytics/yourfile.html
```

Deploy to GitHub Pages:
```bash
git add mtg/analytics/yourfile.html
git commit -m "Add analytics visualization"
git push origin main
```

Access at:
```
https://toskicologist.github.io/MTG-draft-sets-infographics/mtg/analytics/yourfile.html
```
