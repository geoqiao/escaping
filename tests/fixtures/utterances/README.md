# Offline Utterances browser fixture

These are **unmodified official browser assets**, not a fake comments UI. They
replay the anonymous read/login-entry path through generated escaping HTML and
its copied shared `comments.js`; no test contacts Utterances or GitHub.

## Provenance and license

Captured on 2026-09-06 (+08:00) by the read-only comments investigation, then
copied from `.scratch/project-review/comments-investigation/` in the source
checkout. The investigation observed anonymous GitHub API 403 rate limiting,
subsequent recovery on the same production revision, and eight matching
old/new Quiet controlled cases. No production Issue data or credentials are
included here. The fixture's GitHub response uses synthetic `geoqiao/site`
Issues 1/2/10 with zero comments.

| File | Original URL | SHA256 |
| --- | --- | --- |
| `utterances-client.js` | https://utteranc.es/client.js | `f36e0332898e1f23f085fb5da06939f26b2fd57e99c306e9c1f4ad3b17efcf34` |
| `utterances.html` | https://utteranc.es/utterances.html | `ff4ac8ed78f1c8cd424a31a787358344930077150c7aed42c1fdcd35749aec3a` |
| `utterances-app.js` | https://utteranc.es/utterances.6ec01640.js | `373c79e86c94f0c31424633e5b225a4e9c537b8106e570835f2522f3542109a3` |
| `github-light.css` | https://utteranc.es/stylesheets/themes/github-light/utterances.css | `4be56c4af49082f20845d665dfc0051dcad7e28c9d766060b4265c00da7ef025` |
| `photon-dark.css` | https://utteranc.es/stylesheets/themes/photon-dark/utterances.css | `b534a530b6e7845c1955018bfe294f98fab25a0993de10f459dda1adc4038cae` |

Upstream: https://github.com/utterance/utterances (MIT, Jeremy Danyow).
`LICENSE.md` is copied from its `master/LICENSE.md`. CSS retains its embedded
normalize.css and GitHub syntax-theme notices; their MIT texts and sources are
in `THIRD-PARTY-NOTICES.md`. Only five runtime resources (~105 KB) are replayed:
no API service, OAuth backend, source maps, or full repository is vendored.

## What the tests prove

Run `uv run pytest -q tests/test_browser_navigation.py -k comments`.
The existing Chromium fixture is required in CI. WebKit cases run when installed
(`uv run playwright install webkit`), otherwise report explicit skips.

Four logical tests cover Theme wiring/Issue identity, success/theme/lazy behavior,
403/client-load failure, and the shared feedback message boundary. Blog wiring
also checks actual iframe height and the visible anonymous login entry in each
Theme. Idea/About callers check identity without multiplying failure/protocol
cases. Detailed shared behavior uses Quiet, including mobile success.

Success runs the real client/app/CSS, including its resize and set-theme messages.
Failure holds browser time while delivering a controlled HTTP 403, then advances
20,001 ms through the unchanged production watchdog; `fast_forward` fires repeating
timers at most once, so it does not substitute a shortened 75/100-check loop.
Client-load errors must expose a fallback even before advancing time. The fallback
is keyboard-activated into an intercepted original-Issue URL; this proves browser
navigation, **not GitHub availability or authorization**. The security case uses
blank documents only as real cross-origin/cross-window message peers.

**Known upstream boundary:** this captured official client checks resize origin
but not source. A different `utteranc.es` sibling window can change its wrapper
height (controlled reproduction: 0 → 777px). Shared `comments.js` rejects that
message for loading/error state. The feedback test does not claim that upstream
layout is source-isolated; this finding requires separate review, not weaker
shared-feedback assertions or an unapproved production patch.

This is deterministic controlled acceptance, not a fresh live-service smoke.
N7 must separately record real URL/time/browser, API status, iframe content and
height, and fallback. Playwright WebKit is not real-device Safari. No test logs
in, posts a comment, or proves App installation, OAuth, or write permission.
