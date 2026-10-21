# iNiR / iRiS Conventions, Shell Tokens & Baseline Audit

This document establishes ground-truth conventions, exact token definitions, dynamic theming hooks, component patterns, and security/test baseline audit findings for `portfolio-widget` integrating into iNiR / iRiS.

---

## 1. W0.1 Shell Tokens & Typography (`IrisStyle.qml`)
**Source File:** `~/.config/quickshell/inir/modules/iris/style/IrisStyle.qml`

### Density & Geometry
- **Density Token:**
  - `IrisStyle.qml:76`: `readonly property real density: Math.max(0.8, Math.min(1.35, Number(root.appearance?.density ?? 1.0)))`
  - Canonical abbreviation in components: `readonly property real d: IrisStyle.density`
  - Scaled strictly for dimensions, paddings, and iconography; never for font points/pixels directly.

### Typography & Type Scale
- **Type Scale Token:**
  - `IrisStyle.qml:78`: `readonly property real typeScale: Math.max(0.75, Math.min(1.6, (Appearance.fontSizeScale ?? 1.0) * root.tweak("text", 0.85, 1.25)))`
- **Type Steps:**
  - `IrisStyle.qml:79`: `typeCaption: Math.round(10 * root.typeScale)`
  - `IrisStyle.qml:80`: `typeFootnote: Math.round(11 * root.typeScale)`
  - `IrisStyle.qml:81`: `typeMeta: Math.round(12 * root.typeScale)`
  - `IrisStyle.qml:82`: `typeLabel: Math.round(13 * root.typeScale)`
  - `IrisStyle.qml:83`: `typeBody: Math.round(14 * root.typeScale)`
  - `IrisStyle.qml:84`: `typeHeadline: Math.round(15 * root.typeScale)`
  - `IrisStyle.qml:85`: `typeTitle: Math.round(17 * root.typeScale)`
  - `IrisStyle.qml:86`: `typeTitleLarge: Math.round(21 * root.typeScale)`
  - `IrisStyle.qml:87`: `typeDisplay: Math.round(28 * root.typeScale)`
- **Optical Tracking:**
  - `IrisStyle.qml:89-91`:
    ```qml
    function tracking(px: real): int {
        return Math.round(px * (-0.0223 + 0.185 * Math.exp(-0.1745 * px)))
    }
    ```
- **Font Families:**
  - `IrisStyle.qml:191`: `faceText: "Inter"`
  - `IrisStyle.qml:192`: `faceTitle: "Inter Display"`
  - `IrisStyle.qml:193`: `faceFigures: "Rubik"`
  - `IrisStyle.qml:217`: `fontNumbers: root.face("iris.appearance.numbersFontFamily", root.appearance?.numbersFontFamily)`
- **Dynamic Weight Function (`weight()`):**
  - `IrisStyle.qml:208-215`:
    ```qml
    readonly property string weightName: String(root.theme?.weight ?? "regular")
    readonly property int weightShift: ({ light: -1, bold: 1 })[root.weightName] ?? 0
    readonly property var weightSteps: [Font.Light, Font.Normal, Font.Medium, Font.DemiBold, Font.Bold, Font.ExtraBold]
    function weight(base: int): int {
        const steps = root.weightSteps
        const at = steps.reduce((best, w, i) => Math.abs(w - base) < Math.abs(steps[best] - base) ? i : best, 0)
        return steps[Math.max(0, Math.min(steps.length - 1, at + root.weightShift))]
    }
    ```
  - Standard usage: `font.weight: IrisStyle.weight(Font.DemiBold)` or `IrisStyle.weight(Font.Medium)`.

### Semantic Color Roles & Identity Tokens
- **Identity Palette (`IrisStyle.qml:758-772`):**
  ```qml
  readonly property QtObject identity: QtObject {
      readonly property color blue: Qt.color(root.identitySet.blue ?? "#0a84ff")
      readonly property color sky: Qt.color(root.identitySet.sky ?? "#64d2ff")
      readonly property color teal: Qt.color(root.identitySet.teal ?? "#30b0c7")
      readonly property color green: Qt.color(root.identitySet.green ?? "#34c759")
      readonly property color yellow: Qt.color(root.identitySet.yellow ?? "#e0a800")
      readonly property color orange: Qt.color(root.identitySet.orange ?? "#ff9f0a")
      readonly property color red: Qt.color(root.identitySet.red ?? "#ff453a")
      readonly property color pink: Qt.color(root.identitySet.pink ?? "#ff375f")
      readonly property color indigo: Qt.color(root.identitySet.indigo ?? "#5e5ce6")
      readonly property color purple: Qt.color(root.identitySet.purple ?? "#bf5af2")
      readonly property color lavender: Qt.color(root.identitySet.lavender ?? "#b4a0ff")
      readonly property color gray: Qt.color(root.identitySet.gray ?? "#8e8e93")
  }
  ```
- **Text & Ink Roles:**
  - `IrisStyle.qml:395`: `text: root.role("text", "#f5f5f7")`
  - `IrisStyle.qml:397`: `subtext: ColorUtils.applyAlpha(root.quietInk, root.inkLevel(Math.max(0.78, root.preset.textStrong - 0.02), 0.9))`
  - `IrisStyle.qml:398`: `muted: ColorUtils.applyAlpha(root.quietInk, root.inkLevel(Math.max(0.64, root.preset.textSecondary + 0.04), 0.8))`
  - `IrisStyle.qml:400`: `label: root.subtext`
- **Status & Badges:**
  - `IrisStyle.qml:534`: `success: root.role("success", "#8de0a3")`
  - `IrisStyle.qml:535`: `warning: root.role("warning", "#ffb340")`
  - `IrisStyle.qml:536`: `danger: root.role("danger", "#ff6961")`
  - `IrisStyle.qml:524`: `badge: root.badgeStyle === "accent" ? root.accent : ...`
  - `IrisStyle.qml:531`: `badgeInk: ...`
- **Surface Elevation & Containers:**
  - `IrisStyle.qml:282`: `surfaceOpaque: root.role("surface", "#000000")`
  - `IrisStyle.qml:285`: `surfaceHighOpaque: root.role("surfaceHigh", "#1c1c1e")`
  - `IrisStyle.qml:286`: `surfaceHighestOpaque: root.role("surfaceHighest", "#2c2c2e")`
  - `IrisStyle.qml:385`: `surfaceHigh: root.glassy || root.afterglow ? ... : root.tinted(root.surfaceHighOpaque, 0.16)`
  - `IrisStyle.qml:388`: `surfaceHighest: root.glassy || root.afterglow ? ... : root.tinted(root.surfaceHighestOpaque, 0.2)`
  - `IrisStyle.qml:392`: `raised: root.light ? ColorUtils.applyAlpha(root.litLayer, root.glassy ? 0.86 : 1) : root.fillHover`
  - `IrisStyle.qml:393`: `field: root.surfaceHighest`
  - `IrisStyle.qml:752`: `readingPlate: ColorUtils.applyAlpha(root.surfaceOpaque, root.placePlate)`
  - `IrisStyle.qml:753`: `readingCard: root.glassy ? Lume.stack(root.readingPlate, root.surfaceHigh) : root.surfaceHigh`
- **Fills & Interaction States:**
  - `IrisStyle.qml:565`: `fillQuiet: ColorUtils.applyAlpha(root.fillInk, root.fillAlpha(0.08))`
  - `IrisStyle.qml:566`: `fill: ColorUtils.applyAlpha(root.fillInk, root.fillAlpha(0.12))`
  - `IrisStyle.qml:567`: `fillHover: ColorUtils.applyAlpha(root.fillInk, root.fillAlpha(0.18))`
  - `IrisStyle.qml:568`: `fillActive: ColorUtils.applyAlpha(root.fillInk, root.fillAlpha(0.26))`
  - `IrisStyle.qml:572`: `fillStrong: ...`
  - `IrisStyle.qml:574`: `tintFill(tint: color): color`
  - `IrisStyle.qml:576`: `trackOf(tint: color): color`
  - `IrisStyle.qml:577`: `tintFillHover(tint: color): color`
  - `IrisStyle.qml:551`: `hairline`
  - `IrisStyle.qml:553`: `hairlineStrong`

### Corner Radii & Spacing
- **Corner Token Scale (`IrisStyle.qml:778-792`):**
  ```qml
  function corner(px: real): int {
      const cap = px >= 18 ? 1.3 : px >= 10 ? 1.4 : 1.6
      return Math.max(2, Math.round(px * Math.min(root.shapeScale, cap) * root.density))
  }
  readonly property int radiusPanel: root.corner(30)   // Control Center, Settings frame
  readonly property int radiusSheet: root.corner(26)   // Spotlight, media card, wallpaper picker
  readonly property int radiusPlate: root.corner(22)   // widget and lock plates, dialogs, blocks
  readonly property int radiusCard: root.corner(18)    // side-panel sections, menus
  readonly property int radiusTile: root.corner(14)    // grouped cards, tiles, results
  readonly property int radiusRow: root.corner(10)     // list rows, menu items, small buttons
  readonly property int radiusChip: root.corner(7)     // chips, thumbnails, small marks
  readonly property int radiusMicro: root.corner(4)    // bars inside skeletons, swatches
  ```
- **Base Geometry Radii (`IrisStyle.qml:155-157`):**
  - `radius: Math.round(Math.max(16, Math.min(40, Number(root.appearance?.expandedRadius ?? 28))) * root.density)`
  - `radiusSmall: Math.max(4, Math.round(root.radius * 0.58))`
  - `radiusTiny: Math.max(3, Math.round(root.radius * 0.36))`
  - `iconRadius(size)`: `IrisStyle.qml:843`
- **Spacing Steps (`IrisStyle.qml:158-162`):**
  - `gap`: `Math.max(4, Math.round(8 * root.density))`
  - `gapLarge`: `Math.max(8, Math.round(14 * root.density))`
  - `spaceSmall`: `Math.max(4, Math.round(6 * root.density))`
  - `spaceMedium`: `Math.max(6, Math.round(10 * root.density))`
  - `spaceLarge`: `Math.max(10, Math.round(16 * root.density))`
  - `cardPad`: `IrisStyle.qml:146` (`Math.round(16 * root.density * ...)`)

---

## 2. W0.2 Native Pieces & Cards Reference
**Inspected Components:**
- `~/.config/quickshell/inir/modules/iris/stage/IrisWatchingCard.qml`
- `~/.config/quickshell/inir/modules/iris/components/IrisMediaCard.qml`
- `~/.config/quickshell/inir/modules/iris/stage/CardHeader.qml`
- `~/.config/quickshell/inir/modules/iris/stage/IrisCardContent.qml`
- `~/.config/quickshell/inir/modules/iris/components/IrisBubbleFace.qml`
- `~/.config/quickshell/inir/modules/iris/components/IrisNumber.qml`

### Morph & Spring Animations
- **Spring Solver (`IrisSpring.qml` & `IrisStyle.qml:923-966`):**
  - Curves: `expressive: [0.16, 1, 0.3, 1]`, `standard: [0.2, 0, 0, 1]`, `gentle: [0.4, 0, 0.2, 1]`, `swift: [0.3, 0.9, 0.2, 1]`, `fold: [0.3, 0, 0.2, 1]`.
  - Morph Presets: `direct`, `liquid`, `glide`, `snap`, `elastic`, `instant`.
  - Intent Spring: `IrisStyle.springFor(intent: "move" | "emerge" | "recede", surface: string)`.
  - Standard Durations:
    - `morphDuration`: `moveDuration`
    - `settleDuration`: `emergeDuration`
    - `revealDuration`: `duration(140)`
    - `feedbackDuration`: `duration(100)`
    - `feedbackEasing`: `Easing.OutCubic`
    - `morphCurve`: `root.moveCurve`

### Pill-to-Card Continuity Pattern
- In `IrisStage.qml`, pieces/bubbles expand into stage cards maintaining origin and visual weight continuity.
- In `CardHeader.qml`, every card leads with an icon chip matching the piece's glyph:
  - Implicit size: `Math.round(24 * IrisStyle.density)`
  - Radius: `IrisStyle.iconRadius(width)`
  - Gradient: `GradientStop { position: 0; color: IrisStyle.tileTop(header.tint) }; GradientStop { position: 1; color: header.tint }`
  - Symbol: `MaterialSymbol { iconSize: Math.round(15 * IrisStyle.density); color: IrisStyle.onTint }`
  - Header Title: `IrisText { font.weight: IrisStyle.weight(Font.DemiBold); font.pixelSize: IrisStyle.typeBody }`
  - Header Detail: `IrisText { role: IrisText.Meta }`

### Numeric Roll Pattern (`IrisNumber.qml`)
- Tabular figures: `font.features: ({ "tnum": 1 })`
- Slot-based character animation with `travel: slot.height * 0.7 * (root.countDown ? -1 : 1)`.
- Gated strictly by:
  ```qml
  if (!IrisStyle.motionEnabled || IrisStyle.morphDuration <= 0 || !root.visible) return
  ```

### Press & Hover Feedback Idioms
- Scale feedback: `pressScale(base): 1 - (1 - base) * root.tweak("press", 0, 2)` (`IrisStyle.qml:967`).
- Hover backgrounds: `IrisStyle.fillHover` or `IrisStyle.tintFillHover(tint)`.
- Smooth transition on hover using `duration: IrisStyle.feedbackDuration` and `easing.type: IrisStyle.feedbackEasing`.

---

## 3. W0.3 Dynamic Theming, Matugen & Lifecycle Hooks

### Matugen Palette Ingestion
- `Appearance.colors` (`colPrimary`, `colSecondary`, `colTertiary`, `m3colors.m3background`, `wallpaperDominantColor`) are extracted in `IrisWashi.qml:45-56`.
- `IrisWashi.qml` coordinates with `scripts/colors/washi` to solve accessible contrast ratios against paper materials, outputting to `${Directories.stateUserPath}/generated/iris-washi.json`.
- `IrisStyle.qml:249-252` queries `IrisWashi.palette(root.scheme)` via `root.role(name, fallback)`:
  ```qml
  readonly property var washi: IrisWashi.palette(root.scheme)
  function role(name: string, fallback: string): color { return Qt.color(root.washi?.[name] ?? fallback) }
  ```
- Three schemes are supported: `"dark"`, `"ink"`, and `"light"`.

### Reduce-Motion Hook
- Token: `IrisStyle.qml:858`:
  ```qml
  readonly property bool motionEnabled: (root.appearance?.motion ?? true) && Appearance.animationsEnabled
  ```
- Duration function: `IrisStyle.qml:884-886`:
  ```qml
  function duration(ms: int): int {
      return root.motionEnabled ? Appearance.calcEffectiveDuration(ms) : 0
  }
  ```
- Any QML transition must bind `enabled: IrisStyle.motionEnabled` or use `IrisStyle.duration(ms)`.

### Idle & OLED Care Hooks
- `services/Idle.qml` runs `swayidle` watching user activity and battery profiles.
- Native background widgets gate expensive shaders/animations on `!root.visible` or pause updates after idle timeout.
- To prevent OLED burn-in, static high-contrast digits (like Hero numerals) fade/desaturate or shift slightly after idle timeout.

### Localization (`Translation.tr`)
- Invoked throughout iRiS via: `Translation.tr("Text")` and `Translation.tr("Template %1 of %2").arg(a).arg(b)`.
- Sourced from `qs.services.Translation`.

---

## 4. W0.4 Registration Mechanism (Feeds P1)

### Discovery Audit
- Examination of `IrisPieces.qml`, `IrisBubbleFace.qml`, `IrisCardContent.qml`, and `services/qmldir` confirms:
  **iNiR has no dynamic runtime plugin/piece discovery system.**
- All pieces and cards are explicitly hardcoded:
  1. `modules/iris/pieces/IrisPieces.qml`: Listed in `readonly property var extras: [...]` and `function defaultGlyph(kind)`.
  2. `modules/iris/components/IrisBubbleFace.qml`: Evaluated via `switch (root.kind)` / `root.kind === "..."`.
  3. `modules/iris/stage/IrisCardContent.qml`: Evaluated via `switch (root.kind)` returning card component.
  4. Module registries: `services/qmldir`, `modules/iris/pieces/qmldir`, `modules/iris/stage/qmldir`.

### Requirements for Non-Destructive Packaging (`P1`, `P2`)
- Since dynamic discovery is absent upstream in iNiR, registration requires declarative hooks into these files.
- The installer must:
  1. Create atomic backup markers before modifying files.
  2. Apply idempotent regex/string patches that do not mutate unrelated lines.
  3. Provide `make uninstall` / `./install.sh --uninstall` that cleanly strips the patches and restores exact byte-for-byte upstream files.

---

## 5. W0.5 Security & Baseline Audit

### Code Audit: Unencrypted Disk Writes
1. **`src/indmoney_sync/cli.py` (lines 30, 34, 253-288):**
   - Writes `sips_cache.json` in plaintext to `~/.cache/inir/indmoney/sips_cache.json`.
   - Contains raw upcoming SIP amounts, fund names, and deduction dates.
2. **`src/indmoney_sync/inspector.py` (lines 9-10, 48-52):**
   - Writes `raw_dump.json` in plaintext to `~/.cache/inir/indmoney/raw_dump.json`.
   - Dumps entire unscrubbed IndMoney portfolio, account holdings, bank balances, and ISINs.
3. **`install.sh` (line 13):**
   - Creates `mkdir -p "$HOME/.cache/inir/indmoney"`.
4. **`systemd/inir-indmoney-sync.service` (line 12):**
   - Exposes `%h/.cache/inir/indmoney` in `ReadWritePaths`.

### Live Disk Scan Output (`find ~/.cache/inir -type f`)
```
/home/rakeshpc/.cache/inir/abi-check
/home/rakeshpc/.cache/inir/region-sampling/71b997af2fcb66da252abdb1ac0ed4d336ce74e5.lock
/home/rakeshpc/.cache/inir/region-sampling/71b997af2fcb66da252abdb1ac0ed4d336ce74e5.npy
/home/rakeshpc/.cache/inir/region-sampling/beb0fbfbf8ba4a5ff286f9b325f2fae895c5573b.lock
/home/rakeshpc/.cache/inir/region-sampling/0debe16951c8703c0620b32508197f5eb8ec532d.lock
/home/rakeshpc/.cache/inir/region-sampling/0debe16951c8703c0620b32508197f5eb8ec532d.npy
/home/rakeshpc/.cache/inir/region-sampling/beb0fbfbf8ba4a5ff286f9b325f2fae895c5573b.npy
/home/rakeshpc/.cache/inir/region-sampling/4341a98396590019b013907492860adc04cd76ca.lock
/home/rakeshpc/.cache/inir/region-sampling/4341a98396590019b013907492860adc04cd76ca.npy
/home/rakeshpc/.cache/inir/region-sampling/9294d1f3ab51a25d83d1c158f5d5fdf45a4bdf7f.lock
/home/rakeshpc/.cache/inir/region-sampling/9294d1f3ab51a25d83d1c158f5d5fdf45a4bdf7f.npy
/home/rakeshpc/.cache/inir/region-sampling/6619d60408b383c90ca2b37570486e29d2083530.lock
/home/rakeshpc/.cache/inir/region-sampling/6619d60408b383c90ca2b37570486e29d2083530.npy
/home/rakeshpc/.cache/inir/region-sampling/dfd0a4629bc308b933de34aa04d462f5393c070c.lock
/home/rakeshpc/.cache/inir/region-sampling/dfd0a4629bc308b933de34aa04d462f5393c070c.npy
/home/rakeshpc/.cache/inir/region-sampling/dc2a481ad3e8efcaf94a9c739e3d8c36a1fe17be.lock
/home/rakeshpc/.cache/inir/region-sampling/dc2a481ad3e8efcaf94a9c739e3d8c36a1fe17be.npy
/home/rakeshpc/.cache/inir/thumbgen.log
/home/rakeshpc/.cache/inir/window-previews/.niri-session
/home/rakeshpc/.cache/inir/indmoney/sips_cache.json
/home/rakeshpc/.cache/inir/indmoney/raw_dump.json
/home/rakeshpc/.cache/inir/last-boot.json
```
**Finding:** Both `~/.cache/inir/indmoney/sips_cache.json` and `~/.cache/inir/indmoney/raw_dump.json` are present on disk in plaintext.

### Baseline Test Suite Audit Output
**Command:** `pytest -v` (version: `pytest 9.1.1` on Python `3.14.8`)
```
============================= test session starts ==============================
platform linux -- Python 3.14.8, pytest-9.1.1, pluggy-1.7.0 -- /usr/bin/python
cachedir: .pytest_cache
rootdir: /home/rakeshpc/Projects/portfolio-widget
configfile: pyproject.toml
testpaths: tests
plugins: anyio-4.15.1, platformdirs-4.13.0
collecting ... collected 21 items

tests/test_governor.py::TestGovernor::test_dynamic_holiday_lookup_with_holidays_mock PASSED [  4%]
tests/test_governor.py::TestGovernor::test_dynamic_holiday_lookup_without_holidays_pkg PASSED [  9%]
tests/test_governor.py::TestGovernor::test_force_always_fetches PASSED   [ 14%]
tests/test_governor.py::TestGovernor::test_indian_market_hours_normal_day PASSED [ 19%]
tests/test_governor.py::TestGovernor::test_market_closed_off_hours PASSED [ 23%]
tests/test_governor.py::TestGovernor::test_no_hardcoded_year_constants_in_governor PASSED [ 28%]
tests/test_governor.py::TestGovernor::test_opening_bell_window_transition_resets_streak_and_fetches PASSED [ 33%]
tests/test_governor.py::TestGovernor::test_unchanged_streak_auto_backoff_in_market PASSED [ 38%]
tests/test_governor.py::TestGovernor::test_unchanged_streak_auto_backoff_us_market PASSED [ 42%]
tests/test_governor.py::TestGovernor::test_us_market_hours_normal_day PASSED [ 47%]
tests/test_governor.py::TestGovernor::test_weekend_hours PASSED          [ 52%]
tests/test_normalizer.py::TestNormalizer::test_build_normalized_state_integrates_sparkline PASSED [ 57%]
tests/test_normalizer.py::TestNormalizer::test_build_normalized_state_unchanged_streak FAILED [ 61%]
tests/test_normalizer.py::TestNormalizer::test_build_normalized_state_window_transition_resets_streak FAILED [ 66%]
tests/test_normalizer.py::TestNormalizer::test_normalize_allocation PASSED [ 71%]
tests/test_normalizer.py::TestNormalizer::test_normalize_holdings_and_top_movers_with_rupee_attribution PASSED [ 76%]
tests/test_normalizer.py::TestNormalizer::test_normalize_sips_with_liquidity_coverage PASSED [ 80%]
tests/test_normalizer.py::TestNormalizer::test_normalize_summary_standard PASSED [ 85%]
tests/test_normalizer.py::TestNormalizer::test_normalize_summary_strings_with_commas PASSED [ 90%]
tests/test_normalizer.py::TestNormalizer::test_normalize_with_markdown_fences_and_string_json PASSED [ 95%]
tests/test_normalizer.py::TestNormalizer::test_update_sparkline_ring_buffer PASSED [100%]

=================================== FAILURES ===================================
_________ TestNormalizer.test_build_normalized_state_unchanged_streak __________
AssertionError: 'US_OPEN' != 'IN_OPEN'
- US_OPEN
+ IN_OPEN

__ TestNormalizer.test_build_normalized_state_window_transition_resets_streak __
AssertionError: 'US_OPEN' != 'IN_OPEN'
- US_OPEN
+ IN_OPEN
=========================== short test summary info ============================
FAILED tests/test_normalizer.py::TestNormalizer::test_build_normalized_state_unchanged_streak
FAILED tests/test_normalizer.py::TestNormalizer::test_build_normalized_state_window_transition_resets_streak
========================= 2 failed, 19 passed in 0.06s =========================
```

**Root Cause Analysis:**
`build_normalized_state()` calls `get_market_state(unchanged_streak=unchanged_streak)` on line 521 of `normalizer.py`. The tests only patched `indmoney_sync.normalizer.get_nominal_market_state`, but `get_market_state` evaluates real system clock time (`datetime.datetime.now(IST)`). When tests run during US trading hours (20:48 IST), `get_market_state` returns `"US_OPEN"` instead of `"IN_OPEN"`, causing assertion failures due to unmocked clock state.
