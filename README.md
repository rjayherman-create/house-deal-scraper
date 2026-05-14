house-deal-scraper

## Required production data source

Set this in Railway so the analyzer has reliable live listing and valuation data:

```env
RENTCAST_API_KEY=your_rentcast_key
RENTCAST_API_BASE_URL=https://api.rentcast.io/v1
DISTRESSIQ_DB_PATH=/tmp/distressiq.db
```

The app still keeps Redfin, Realtor, Craigslist, Zillow, and Facebook as best-effort fallback scrapers, but those sources can return zero results from hosted servers because they are HTML pages with changing markup and anti-bot controls.

Useful production diagnostics:

- `/data-sources` shows configured and missing data sources.
- `/debug/scrapers?city=Detroit&state=MI` tests each source and returns counts.
- `/analyze?city=Detroit&state=MI` runs the full analysis pipeline.
