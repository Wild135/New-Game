# Mobile Publishing Roadmap (iOS and Android)

> Store rules change often. **Check the current official requirements** (Apple Developer /
> App Store Review Guidelines, Google Play Console Help) before submitting. Nothing has been
> submitted, and nothing will be without your approval.

## The honest situation

* **pygame-ce has no official, supported iOS export.** Community experiments exist (for example
  via kivy-ios-style toolchains), but they are fragile and not a reasonable base for an App Store
  release.
* **Android with pygame** is possible with community tools (e.g. `pygame-ce` + Buildozer /
  python-for-android recipes), but this is also community-maintained. Expect setup work and
  test on real devices.
* **Recommended path for both stores:** port the *presentation layer* to a mobile-first engine
  and keep the game rules and data.

## Recommended plan: keep the rules, replace the renderer

The code was designed for this:

| Keep as-is (portable) | Re-implement per engine |
|---|---|
| `config/*.json` (all balance data) | Rendering (`game/rendering`) |
| Economy formulas & tests (as a spec) | UI screens (`game/ui`) |
| Save format (JSON) | Audio playback |
| Offline/mission/prestige rules | Input & platform services |

Options:

1. **Godot 4 (free, open source, exports to iOS + Android + Windows).** Port `game/core`,
   `economy`, `factories`, … to GDScript (they are plain classes and functions, about 2,000 lines).
   Use the pytest suite and `tools/economy_sim.py` output as the reference: write the same tests in
   Godot (GUT) and compare numbers. Load the same JSON configs. *This is the recommended option.*
2. **Kivy + python-for-android / kivy-ios.** Keeps Python and the logic modules unchanged; only the
   UI is rewritten with Kivy widgets. Uses fewer languages, but the toolchains are more fragile.
3. **Unity (C#).** Also mature, but brings licensing terms and a heavier toolchain.

## Touch controls and screens

The UI already uses touch-sized targets (≥ 80 px on a 1080×1920 canvas), drag scrolling with
inertia, and no hover-only actions. On mobile:

* Lay out against **safe areas** (notch, home indicator). Keep the 1080-wide design and add
  top/bottom insets.
* Support aspect ratios from 16:9 to about 20:9 by extending the factory view vertically. The
  top bar and navigation stay anchored to the edges.
* Use the platform's lifecycle events (pause/resume) instead of window focus to save and to
  compute offline time.

## iOS step by step

1. **You need macOS with Xcode.** iOS apps cannot be built or signed on Windows alone. Options:
   a Mac (a Mac mini works), or a cloud Mac service (e.g. MacStadium, AWS EC2 Mac,
   MacinCloud).
2. Join the **Apple Developer Program** (paid yearly membership).
3. In Godot: install the iOS export templates and set the bundle id (e.g.
   `com.yourname.rocketempire`), icons and launch screen.
4. Export an Xcode project. Open it in Xcode, select your Team, and let Xcode manage
   **signing certificates and provisioning profiles**.
5. Test on a **real iPhone** (connect by USB, select it as the run target) and on several screen
   sizes in the Simulator.
6. In **App Store Connect**: create the app record, fill in metadata, age rating, privacy details
   ("Data Not Collected" applies to the current offline build) and screenshots for the required
   device sizes. `tools/screenshot_tour.py` helps prepare these.
7. Archive in Xcode → upload → test through **TestFlight** → submit for review.

## Android step by step

1. Install Android Studio (SDK + platform tools) and a JDK. Godot's Android export uses these.
2. Create an **upload keystore** (`keytool -genkey …`). Back it up, because losing it is serious.
3. Configure the Android export (package name, version code, min/target SDK). **Google Play
   requires targeting a recent API level**, so check the current minimum.
4. Build an **Android App Bundle (.aab)**. Play requires AAB for new apps.
5. Test on real devices (USB debugging) at different resolutions and aspect ratios.
6. Create a **Google Play Console** developer account (one-time fee) and the app. Complete the
   content rating, Data safety form, target audience and store listing (icon, feature graphic,
   screenshots, description).
7. Upload to **internal testing**, then closed testing. New personal accounts may have to run a
   closed test with a minimum number of testers for a set period before production. Check the
   current rule. Then roll out to production.

## Monetization (future, only with your approval)

The current build has no ads or purchases. If you add them later: use the platform billing
systems (StoreKit / Google Play Billing), disclose the odds of anything random (or avoid loot
boxes altogether, as now), follow age-rating and privacy requirements, and keep the game
winnable without paying.
