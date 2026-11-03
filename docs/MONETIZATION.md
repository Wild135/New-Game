# Monetization: what's in the game and how to take real money

## What players can buy

**Real-money Store** (Shop → Store tab), configured in `config/store.json`:

| Product | Price | What you get |
|---|---|---|
| Starter Pack (one time) | $2.99 | 300 gems + Rare manager Kai + 2 h of instant income |
| Golden Investor (one time, permanent) | $7.99 | Rockets worth +50%, +4 h offline cap, +20% offline efficiency (kept through Space Legacy resets) |
| Galaxy Bundle (one time) | $3.99 | Exclusive paint, exhaust and launch effect, plus 50 gems |
| Gem packs | $0.99 – $24.99 | 80 / 450 / 1,000 / 2,800 gems (bigger packs give bonus gems) |

**Gem spends** (gems can be bought or earned free from missions, achievements, daily rewards and gifts):
- Boosts: Turbo ×2 / ×3 income, 1 h and 8 h Time Warps, a Research Grant, and a Manager Pep Talk that resets every ability cooldown.
- **Collect ×2** on the Welcome Back screen (20 gems).
- Epic and Legendary managers.
- Cosmetics: rocket paints, decals, exhaust colours, launch effects, factory themes, worker hats.

Fairness: everything except the exclusive cosmetics and the Golden Investor perk can be earned
without paying. The economy simulation is tuned for free players, so paying makes the game
faster, not mandatory.

## Test mode (current build)

`"test_mode": true` in `config/store.json` means every purchase goes through `TestProvider`.
It **pretends** the payment worked and charges nothing. The Store tab shows a yellow
"TEST MODE" banner, and each purchase asks for confirmation first. Change `"enabled": false`
to hide the Store completely.

## Going live: connecting real payments

A plain Python/pygame `.exe` can't charge cards by itself. Money has to go through a payment
platform, and each store **requires its own system for digital items**:

| Where you publish | Required payment system |
|---|---|
| iPhone / iPad (App Store) | Apple In-App Purchase (StoreKit) |
| Android (Google Play) | Google Play Billing |
| Steam (Windows) | Steamworks microtransactions |
| Your own website / itch.io | A web payment provider, e.g. Stripe or Paddle, which needs a small server |

Steps:
1. Create the products with the **same ids** (`gems_small`, `starter_pack`, …) in that
   platform's dashboard. The platform sets the real local prices.
2. Write a provider class in `game/shop/store.py` that implements
   `begin(product, callback)`. It opens the platform's checkout and, when the platform confirms,
   calls `callback(True, transaction_id, "")`. The `Store` class already grants items exactly
   once per transaction id and saves immediately.
3. Ideally, verify receipts on a server before granting, so people can't fake purchases.
4. Set `test_mode` to `false`.

The mobile route (see `MOBILE_PUBLISHING.md`) ports the UI to an engine such as Godot. Godot has
official StoreKit and Google Play Billing plugins, and the same product ids and grant rules carry
over.

## Rules to follow before charging anyone

- Platform rules: no misleading offers, show the price clearly, offer "restore purchases" for
  one-time items on iOS, and disclose odds for anything random. This game has no loot boxes, so
  there are no odds to disclose.
- Age rating and privacy forms must mention in-app purchases.
- Tax and payouts are handled through each store's developer account (banking and tax forms).
- Check the current Apple App Store and Google Play policies before publishing. They change often.
