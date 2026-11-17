# Closing prices for the share cards

Each `<TICKER>.csv` holds daily closes (`date,close`) for the 90 calendar days ending on that bank's release date. `scripts/og.py` draws the card's price line from it and computes the % change from the first to the last close in the window.

Close is the split-adjusted daily close as shown on Yahoo Finance's historical prices page (not dividend-adjusted). Stooq, Yahoo's chart API and Nasdaq's historical page were also tried but refused or rate-limited automated reads, so each series has one source.

| File | Window | Read from | Read on |
|---|---|---|---|
| PNC.csv | Jul 17 to Oct 15, 2026 | https://finance.yahoo.com/quote/PNC/history/ | Nov 14, 2026 |
| PNBK.csv | Aug 14 to Nov 12, 2026 | https://finance.yahoo.com/quote/PNBK/history/ | Nov 14, 2026 |
| OPHC.csv | Aug 14 to Nov 12, 2026 | https://finance.yahoo.com/quote/OPHC/history/ | Nov 14, 2026 |
| WSBF.csv | Aug 17 to Nov 13, 2026 | https://finance.yahoo.com/quote/WSBF/history/ | Nov 14, 2026 |
| BYFC.csv | Aug 17 to Nov 13, 2026 | https://finance.yahoo.com/quote/BYFC/history/ | Nov 14, 2026 |
| TYCB.csv | Aug 19 to Nov 16, 2026 | https://stockanalysis.com/quote/otc/TYCB/history/ | Nov 17, 2026 |

TYCB trades thinly over the counter and Yahoo Finance could not be read for it, so its closes come from stockanalysis.com's history page (unadjusted close). Days with no trade carry the last traded price forward, starting from the Jul 30, 2026 trade at $58.05; 12 days in the window had trades.

Add a row here whenever you add a CSV.
