# 17 Lands GIH WR Quiz - Local Standalone Version

**The easiest way to play: Just open the HTML file in your browser!**

No server, no installation, no CSV files needed. Everything is self-contained in a single HTML file.

## Quick Start

1. Open `index.html` in any modern web browser
2. Start guessing card win rates!
3. That's it - no setup required

## How to Play

1. Select your preferred **Color** and **Rarity** filters (optional)
2. Two random cards matching your filters will appear with images from Scryfall
3. Click on the card you think has the **higher GIH WR** (Games In Hand Win Rate)
4. See the correct answer and your accuracy percentage
5. Click **Next Question** to continue

## Features

- ✅ **Works offline** - completely self-contained (just needs internet for card images from Scryfall)
- ✅ **No server needed** - works via `file://` protocol
- ✅ **Fast loading** - all card data embedded in HTML
- ✅ **Responsive design** - works on desktop, tablet, and mobile
- ✅ **Smart filtering** - filter by color and rarity
- ✅ **Real-time scoring** - track your accuracy

## Differences from the Subfolder Version

| Feature | Subfolder | Local |
|---------|-----------|-------|
| Setup required | Yes (local web server) | No |
| CSV file | Yes | No (embedded) |
| Works with `file://` | No | Yes ✓ |
| Data loading | Network fetch | Instant |
| File size | Smaller (HTML + CSV) | Larger (all data embedded) |

## Technical Details

- **Framework**: React 18 (CDN)
- **Styling**: Vanilla CSS (dark theme)
- **Card Data**: 260 cards with valid GIH WR embedded as JavaScript array
- **Card Images**: Fetched from Scryfall API on demand (with caching)
- **Total Size**: ~40 KB HTML file (includes all card data)

## Data Source

- Card ratings: 17 Lands (https://17lands.com)
- Card images: Scryfall API (https://scryfall.com)
- Dataset: Lorwyn Eclipsed limited format, current ratings

## Browser Support

Works on all modern browsers:
- Chrome 90+
- Firefox 88+
- Safari 14+
- Edge 90+

## Troubleshooting

### Card images not loading
- Check your internet connection - images are loaded from Scryfall's API
- Scryfall's API is occasionally rate-limited; wait a moment and refresh
- Some old or special card versions might not have images

### Quiz not starting
- Make sure you're opening `index.html` directly in your browser
- Try refreshing the page
- Try a different browser

## Comparison with Other Versions

**This local version** - for offline playing with no setup
**Subfolder version** (`/mtg/17lands-gih-quiz/`) - for serving via HTTP server
**GitHub Pages** - live version at https://toskicologist.github.io/MTG-draft-sets-infographics/17lands-gih-quiz/

---

**Enjoy testing your card evaluation skills!**

For issues or suggestions, see the main project: https://github.com/Toskicologist/MTG-draft-sets-infographics
