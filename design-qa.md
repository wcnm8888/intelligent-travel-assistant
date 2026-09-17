# F-017 Design QA

- source visual truth path: `C:\Users\24696\.codex\generated_images\01a09954-7aac-7922-b02c-5007591e039a\exec-bbbdbe03-adef-4438-8ff5-591a825ceb1c.png`
- implementation screenshot paths:
  - `E:\Agent\comprehensive-cases\13-intelligent-travel-assistant\output\f017\20260915-233100-browser-recovery\desktop-advisor.png`
  - `E:\Agent\comprehensive-cases\13-intelligent-travel-assistant\output\f017\20260915-233100-browser-recovery\mobile-390-advisor.png`
- viewport: desktop `1440 × 1000` CSS px, deviceScaleFactor `1`
- source pixels: `1487 × 1058`
- implementation pixels: desktop `1440 × 1000`; mobile `390 × 4874` full-page capture at a `390 × 844` viewport
- density normalization: both treated as 1x desktop captures; composition compared at full-view scale rather than pixel overlay because the mock and live fixture use different content lengths.
- state: three selected POIs, one accepted preference suggestion, advisor expanded, synthetic/offline map.

## Full-view comparison evidence

The selected mock uses a left POI control column, central map, and visible right advisor drawer in the same above-the-fold workspace. The accepted desktop capture now has that same three-region hierarchy: list controls on the left, the largest spatial canvas in the center, and the expanded advisor at right. The accepted 390px capture reflows to list, advisor, then map without horizontal overflow.

## Focused region evidence

The accepted desktop capture visibly includes the shared-planning summary, user/advisor exchange, confirmed preference chips, quick replies, composer, and collapse control. Typography, borders, spacing and state color remain consistent with the product's paper, jade and vermilion system. The mobile capture preserves the same information and reading order without overlaying the list or map.

## Findings

- [RESOLVED P1] Advisor drawer was outside the intended desktop workspace.
  - Location: selection workspace / `.f017-advisor-workspace`.
  - Evidence: source shows the advisor beside the map; first implementation screenshot shows it below the two-column map/list region.
  - Impact: the main Agent capability remains invisible at first glance, reproducing the usability problem F-017 is meant to solve.
  - Fix verified: the three-column class and `data-advisor-open` state now belong to the selection layout; the post-fix desktop capture shows the drawer beside the map.

- [RESOLVED P2] Browser assertion checked selection-only content after leaving the selection page.
  - Location: `scripts/capture_f017_advisor.js`.
  - Evidence: the full product journey completed, then `conversation_visible` and `confirmed_preference_visible` failed because the script read the result-page body.
  - Impact: the acceptance report cannot distinguish a script timing defect from a product failure.
  - Fix verified: both booleans are captured immediately after preference acceptance; desktop and 390px journeys report them as true.

## Required fidelity surfaces

- Fonts and typography: the implementation preserves the product's existing KaiTi display heading and compact sans-serif control hierarchy; advisor labels remain readable in both captures.
- Spacing and layout rhythm: the desktop primary workspace is visibly three-column, while the mobile full-page order is stable and free of horizontal overflow.
- Colors and visual tokens: cream paper, jade actions and vermilion emphasis match the selected direction and existing product tokens; selected and confirmed states remain distinguishable by text and shape as well as color.
- Image quality and asset fidelity: the mock's POI thumbnails were intentionally omitted because the verified POI contract provides no image assets. No placeholder, CSS drawing, emoji, or invented POI photo was substituted.
- Copy and content: live copy uses user-facing terms such as “共同规划中”, “已确认偏好”, “地点建议”, “加入行程” and “旅行顾问建议”; wrapping remains contained in desktop and 390px captures.

## Comparison history

1. First pass: P1 advisor placement and P2 acceptance timing found. Both received minimal code fixes.
2. Second pass: Playwright entry parse failed before the product journey; the failure remains preserved separately.
3. Final pass: desktop and 390px complete journeys passed with revised screenshots, zero console errors, empty browser storage, no horizontal overflow and zero non-loopback requests.

## Final assessment

- Desktop composition: passed.
- 390px reflow: passed.
- Advisor visibility and hierarchy: passed.
- Conversation, preferences, quick replies and collapse affordance: passed.
- Screenshot-only accessibility limit: visual evidence cannot prove full screen-reader behavior; keyboard and semantic behavior are covered by automated tests and the browser journey, not by the screenshots alone.
- Remaining P0/P1/P2 findings: none.

final result: passed
