# HaLoWave PitchPulse × Pascal

An order-book-free European Football 1X2 trading terminal built on [Pascal](https://pascal.trade) ([Solana](https://solana.com)) that pairs **1-second continuous Sub-GHz Wi-Fi HaLow (IEEE 802.11ah) stadium weather telemetry** from the [HaLoWave DePIN Network](https://halowave.io) with permissionless builder fee routing (`builder_info`) to reward physical HaLoWave Miner hosts.

Built for the **[Superteam Italy — Vitruvium Hackathon (Pascal Track)](https://it.superteam.fun/vitruvium)**.

---

## Official Links & Live Infrastructure

- **HaLoWave Official Website:** https://halowave.io
- **HaLoWave IoT Devices & Miner Console:** https://console.halowave.io
- **HaLoWave Live Global Network Explorer (100+ Active Nodes):** https://explorer.halowave.io
- **Pascal Prediction Market Exchange:** https://pascal.trade
- **Pascal Trading Web App:** https://app.pascal.trade
- **Pascal Technical API Documentation:** https://docs.pascal.trade
- **Solana Blockchain:** https://solana.com
- **Superteam Italy Vitruvium Portal:** https://it.superteam.fun/vitruvium
- **Public GitHub Repository:** https://github.com/HaLoWaveNetwork/halowave-pascal

---

## 1. What is HaLoWave (IoT 2.0 on Solana) & Why Connect It to Pascal?

**[HaLoWave](https://halowave.io)** is building the first global decentralized Sub-GHz **Wi-Fi HaLow (IEEE 802.11ah)** DePIN network on the [Solana](https://solana.com) blockchain. With over 100 physical nodes deployed globally (visible live on [explorer.halowave.io](https://explorer.halowave.io)), HaLoWave provides long-range, high-throughput **IoT 2.0** IP connectivity up to 3 kilometers for industrial sensors, weather stations, and cameras registered via the **IoT Devices** portal on [console.halowave.io](https://console.halowave.io).

### The Protocol Latency Mismatch: Wi-Fi HaLow (1 Second) vs. LoRaWAN (5–10 Minutes)

- **Pascal's Matching Engine Speed:** Pascal (`pascal.trade`) operates a high-speed off-chain order book that clears matching rounds every **50 milliseconds** (`50 ms batch rounds`), broadcasting every matched trade to Solana for non-custodial USDC settlement.
- **The Legacy LoRaWAN Bottleneck:** Traditional first-generation IoT weather stations rely on **LoRaWAN**, which is constrained by strict 1% sub-band duty-cycle limits and ultra-narrow bandwidth. As a result, a LoRaWAN weather sensor can only transmit a data packet every **5 to 10 minutes**. In live sports prediction markets, a 5-to-10-minute delay is unusable: by the time a LoRaWAN packet arrives, the market odds have already moved.
- **The HaLoWave Wi-Fi HaLow Advantage:** Operating in the Sub-GHz band (`868 MHz` in Europe / `915 MHz` in North America) using **Morse Micro MM8108** silicon and high-gain 8 dBi outdoor antennas, Wi-Fi HaLow delivers multi-megabit native TCP/IP throughput over kilometer distances. A **Wi-Fi HaLow Stadium Weather Station** connected to a local **HaLoWave Miner** streams wind, rain, temperature, and humidity data **every single second (`1-Sec Continuous TCP/IP`)**, matching the real-time execution speed of Pascal.

---

## 2. Tactical Football Use Case: Newcastle United vs. Arsenal (1 · X · 2)

Following the Vitruvium Pascal Track specification (*"A trading app for one kind of market... three buttons: home, draw, away with prices as probabilities, no order book"*), **PitchPulse** eliminates complex order books and exposes three direct 1-tap cards: **`1 · HOME WIN`**, **`X · DRAW OUTCOME`**, and **`2 · AWAY WIN`**.

### How Real-Time Stadium Weather Shifts 1X2 Probabilities

In our flagship live match **Newcastle United vs Arsenal** (`EPL_26NOV21_NEWARS_ML`):
- **Pre-Storm Baseline (Overcast & Foggy):** The stadium weather station reports overcast and foggy conditions (`14.2 km/h` wind, `0.0 mm/h` rain, `13.6 °C`, `74%` relative humidity). On Pascal's order book, **Arsenal (`2 · AWAY`)** is the clear favorite at **`63%`** (`Bid: $0.62 | Ask: $0.63`), **Draw (`X`)** is at **`23%`** (`Bid: $0.22 | Ask: $0.23`), and **Newcastle United (`1 · HOME`)** is at **`17%`** (`Bid: $0.16 | Ask: $0.17`).
- **Tactical Impact of a Playable Heavy Downpour:** When the Wi-Fi HaLow Stadium Weather Station detects a sudden transition from overcast clouds to a **Heavy Playable Downpour (`28.4 mm/h` precipitation, `54.2 km/h` wind gusts, `11.2 °C`, `96%` saturated humidity)**:
  - **Playability Verification:** Modern European stadium drainage systems handle up to 45–50 mm/h of rain and matches are only suspended when wind gusts exceed 75–80 km/h. At `28.4 mm/h` rain and `54.2 km/h` wind, **the match is 100% playable and not suspended**, but pitch physics change dramatically.
  - **Disruption of Technical Possession Play:** Arsenal is a technical possession-based team that relies on fast, short ground passes. Waterlogged, heavy turf slows ball roll and cross-pitch gusts disrupt passing accuracy, reducing overall Expected Goals (`xG`).
  - **Automated 1X2 Repricing Model:** PitchPulse processes the 1-second Wi-Fi HaLow telemetry stream and reprices the three outcomes in real time (`+6% + 3% - 9% = 0%` balanced delta):
    1. **Arsenal (`2 · AWAY` Favorite):** Drops by **`-9%`** (from **`63%` to `54%`**).
    2. **Draw (`X · DRAW`):** Increases by **`+6% Edge`** (from **`23%` to `29%`**), as lower expected scoring directly increases tie probability.
    3. **Newcastle United (`1 · HOME` Underdog):** Increases by **`+3% Edge`** (from **`17%` to `20%`**), favoring direct physical home play.

---

## 3. Two-Wallet Permissionless Builder Code Architecture (`builder_info`)

Pascal allows any third-party interface to attach `builder_info: {builder_pubkey, builder_fee_rate}` to orders and earn a permissionless fee share on every fill. Under Pascal's protocol rules (`docs.pascal.trade`):
1. The **Builder Wallet (`builder_pubkey`)** must hold at least **$100.00 USDC** of free collateral on Pascal (`BUILDER_COLLATERAL_BELOW_MINIMUM` otherwise).
2. The **Trader Wallet (`owner`)** and **Builder Wallet (`builder_pubkey`)** must be two separate accounts (Pascal rejects self-referred builder orders where `owner == builder_pubkey` with `BUILDER_INVALID`).

To comply 100% with Pascal Mainnet rules, PitchPulse operates with two distinct funded Solana accounts on Pascal:
- **Wallet 1 — HaLoWave Builder Account (`builder_pubkey`):** `EzUhshaBxGPnNEYeG7FEhKkGGTsDMC3wb7S6KeBt69Rt` — Funded with **$109.00 USDC** of free collateral on Pascal.
- **Wallet 2 — Trader Account (`owner`):** `HHyHJD9zBN9riw3yn38AM7Suy5riu7YXCreGhEW4zUn8` — Funded with **$3.01 USDC** of trading collateral and authorized via delegated Ed25519 Session/Trading Key `J3FKdxfuQg3pYYb3aNHzsexacr2pqmcEYr6YwEiZDvhp`.

### Direct DePIN Miner USDC Reward Pool
Every order routed through PitchPulse calculates the builder fee according to Pascal's formula:

    builder_fee_usd = size * price * (1 - price) * 0.020000

When a trade fills on Pascal, the USDC builder fee settles on Solana into the HaLoWave Builder Pool (`EzUh...69Rt`) and is **allocated directly to reward the specific HaLoWave Miner providing Sub-GHz Wi-Fi HaLow radio coverage to that Stadium Weather Station**.

---

## 4. What It Does on Pascal (API & WebSocket Endpoints)

- **Read API (`https://data.pascal.trade`):**
  - `GET /api/v1/markets` — Downloads the live unresolved catalog (cached locally to respect rate limits), filtering strictly for `sport == "soccer"` head-to-head 1X2 matches (`Home`, `Draw`, `Away`) while excluding season futures and player props.
  - `GET /api/v1/books?symbols=<HOME_SYM>,<DRAW_SYM>,<AWAY_SYM>` — Reads live Best Bid, Best Ask, and resting contract liquidity for all three match outcomes.
  - `GET /api/v1/top-holders?symbols=<HOME_SYM>,<DRAW_SYM>,<AWAY_SYM>&limit=10` — Displays public on-chain whale positions (`LONG` vs `SHORT`) and order book depth.
  - `GET /api/v1/accounts/HHyHJD9zBN9riw3yn38AM7Suy5riu7YXCreGhEW4zUn8` — Reads live free collateral and active positions (`"You hold 1 Draw"`).
- **Market Data & Account WebSocket (`wss://data.pascal.trade/ws`):**
  - Subscribes live to `{"channel": "book", "symbol": "..."}` for the 3 match symbols and `{"channel": "account", "owner": "HHyHJD9zBN9riw3yn38AM7Suy5riu7YXCreGhEW4zUn8"}`, sending `{"type": "ping"}` every 25 seconds and streaming real-time fill events with `builder_fee_paid_usd`.
- **Write API (`https://trade.pascal.trade`):**
  - `POST /api/v1/orders` — Places Ed25519 binary-permit signed limit orders (`Instant Fill at Best Ask` or `post_only: true`, plus `reduce_only: true` for 1-click position closing) with `builder_info: {"builder_pubkey": "EzUhshaBxGPnNEYeG7FEhKkGGTsDMC3wb7S6KeBt69Rt", "builder_fee_rate": "0.020000"}`.
  - `POST /api/v1/cancels` — Cancels resting open orders via 144-byte signed cancel permits.
- **Honesty Disclosure (What is Real vs. Simulated):**
  - **100% Real & Live:** All 1X2 football markets, live Bid/Ask prices, order book depth, public on-chain holder positions, WebSocket `book` and `account` subscriptions, Ed25519 binary permit signing, live Mainnet order execution and fills on `trade.pascal.trade`, the `$109.00 USDC` funded Builder account (`EzUh...69Rt`), the funded Trader account (`HHyH...zUn8`), and the physical HaLoWave Sub-GHz Miner hardware, 8 dBi outdoor antenna, and [console.halowave.io](https://console.halowave.io) / [explorer.halowave.io](https://explorer.halowave.io) infrastructure.
  - **Simulated for Demo Trigger:** The *"Simulate Stadium Weather Shift (Live HaLow Radar)"* button triggers a 10-second animated telemetry transition (from overcast/foggy baseline to a `28.4 mm/h` downpour with `54.2 km/h` wind gusts) so judges can observe the live 1X2 probability repricing and execute a real Pascal Mainnet order on demand without waiting for live stadium rain.

---

## 5. How to Run It

1. Clone the repository and install the 3 lightweight dependencies:

    git clone https://github.com/HaLoWaveNetwork/halowave-pascal
    cd halowave-pascal
    pip install requests pynacl base58

2. Create a local `.env` file in the root folder (never committed to Git; only the delegated Session/Trading key is used, never the wallet owner private key):

    PASCAL_OWNER_PUBLIC_KEY=HHyHJD9zBN9riw3yn38AM7Suy5riu7YXCreGhEW4zUn8
    PASCAL_TRADING_PRIVATE_KEY=your_delegated_session_key_from_app_pascal_trade
    HALOWAVE_BUILDER_PUBKEY=EzUhshaBxGPnNEYeG7FEhKkGGTsDMC3wb7S6KeBt69Rt

3. Start the server and open `http://localhost:8080`:

    python app.py

---

## 6. Built for Superteam Italy Vitruvium (Pascal Track)

- **Team:** Built in Italy by **Osvaldo Ruscitti** (Co-Founder, [HaLoWave](https://halowave.io)).
- **Vitruvium Edition:** Rome, Italy.
- **Pre-existing Code & Infrastructure:** HaLoWave Sub-GHz hardware miners, [console.halowave.io](https://console.halowave.io), and [explorer.halowave.io](https://explorer.halowave.io). The `app.py` HaLoWave PitchPulse × Pascal terminal was built from scratch specifically for the Superteam Italy Vitruvium Pascal Track.
