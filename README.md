# AH Oracle

A community-driven Auction House intelligence platform for WoW Classic Era. 
This project collects auction data via the AHDB addon, processes it into a local SQLite/PostgreSQL database, and serves a real-time dashboard with market depth, price histories, and crafting profitability.

## 🏗️ Architecture

- **Data Source:** `AuctionDB` (AHDB) addon running in-game. It uses Blizzard's native `C_AuctionHouse` API to capture 20,000+ items in seconds.
- **ETL Pipeline:** Python script that parses the `AuctionDB.lua` file, diffs the data against the previous scan to find vanished items, and calculates hourly OHLCV bars.
- **Database:** SQLite (default for local dev) or PostgreSQL.
- **Backend:** FastAPI serving read-only REST endpoints.
- **Frontend:** Nuxt 3 (Vue 3) with Tailwind CSS and Chart.js.

## 📋 Prerequisites

- Python 3.10+
- Node.js 18+
- The **AHDB** addon installed in WoW Classic Era.

## 🚀 Setup & Installation

### 1. Backend (ETL & API)
Open a terminal in the `ahoracle-etl` folder:
```bash
python -m venv .venv
# Activate venv:
# Windows: .venv\Scripts\activate
# Mac/Linux: source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Frontend (Nuxt)
Open a terminal in the `frontend` folder:
```bash
npm install
```

## 🏃‍♂️ How to Run (Development)

To run the entire stack (Watcher, API, and Frontend) with one command, run this from the root folder:

```bash
python start_dev.py
```

This will start:
1. The ETL Watcher (monitors `AuctionDB.lua` for new scans).
2. FastAPI on `http://localhost:8000`.
3. Nuxt on `http://localhost:3000`.

### How to Scan (In-Game)
1. Open the Auction House.
2. Type `/ahdb scan` to take a full scan (takes ~1 second).
3. Log out or `/reload` to save the file to disk.
4. The Watcher will automatically ingest it into the database.

## 🗄️ Database Schema

- `live_auction_book`: The current cheapest listings (overwritten on every full scan).
- `scan_snapshots`: An append-only history of every listing ever seen.
- `auction_event_log`: Items that vanished between scans (SOLD/EXPIRED).
- `ohlcv_session`: Compressed hourly price data for charting.
- `dim_items`: Static item metadata.

## 🧪 Modules

- **Market Dashboard:** Browse unique items with min/max prices and total supply.
- **Item Detail:** Chart price/volume over time, view cumulative order book depth, and see current listings.
- **Consumables Tracker:** Calculates the exact cost to craft raid consumables based on current AH reagent prices (Order Book matching).

## 🛠️ Configuration
Copy `.env.example` to `.env` in the `ahoracle-etl` folder to configure your database URL or custom WoW installation path.

---

## 🗺️ Planned Features (Roadmap)

We are moving away from relying on AHDB and building a fully integrated AHOracle ecosystem.

### 1. The AHOracle Addon (Replacing AHDB & TSM)
- **Standalone Scanning:** Remove the dependency on AHDB (which forces annoying tooltips on users). AHOracle will natively use `C_AuctionHouse` for clean, fast scanning.
- **TSM Replacement:** Feature comprehensive accounting, shopping lists, and custom tooltips that pull directly from our up-to-date, community-driven database (rather than TSM's hours-late app data).
- **Fragmented Scanning:** Passively collect data as users browse the AH, filling gaps between full scans.
- **Smart Prompts:** If a user is browsing a category with stale data, the addon will prompt them to run a full scan to share with the network.

### 2. Dual Scan Modes
- **Fast Scan:** A quick, names-less snapshot of the entire AH for immediate price updates.
- **Long Scan:** Captures seller names and listing durations. This enables advanced analytics to pinpoint:
  - Frequent AH "dumpers" and undercutters.
  - Big market players and whales.
  - Cancel/relist behaviors.

### 3. AHOracle Desktop Client (EXE)
- A lightweight background executable for users to install alongside the game.
- Automatically uploads SavedVariables data to the central API the moment a user logs out, ensuring the community database is *always* up-to-the-minute (unlike TSM).
- Zero-configuration setup for non-technical users.
- Asks for where the wow installtion is, then finds the SavedVar file from there, needs a unique footprint to prevent false data uploads.

### 4. Advanced Market Intelligence
- **Crafting & Arbitrage:** Factor in auction house cut, vendor mats, and cross-faction arbitrage.
- **Bounty Board / Procurement:** A web interface to request bulk materials and have players fulfill them.
- **Chat bot**: Helps you to optimize trade patterns, example, you want to get more gold on Ally, it'll tell you certain farms for highly sought after items (troll necklaces), or items that cost more on Ally rather than horde.

### 5. Web page features
- **Big ticket item pages**
- **Raid consumes page**