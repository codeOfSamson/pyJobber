# LinkedIn Easy Apply Scraper — Design Spec

**Date:** 2026-08-07
**Status:** Approved

---

## Goal

Add a third scraper module, `LinkedInScraper`, that applies to LinkedIn "Easy Apply" jobs, following the same `BaseScraper` interface as `CakeResumeScraper` and `Job104Scraper` so it plugs into the existing `main.py` orchestration with no changes to the shared run loop.

LinkedIn's Easy Apply flow is more variable than either existing site — the number of intermediate form pages and the presence of screening questions differs per job posting. This spec scopes the first version to what real recon confirmed exists (text-based screening questions, a variable-length "Continue" step sequence) rather than guessing at untested field types (radio/dropdown/file upload).

---

## Recon Findings

Captured live via `patchright codegen` across 3 real job applications:

- Entry point is consistent: `get_by_role("link", name="Easy Apply to this job")`.
- Number of "Continue to next step" clicks before reaching submit varies per job (1 vs. 2 observed across 3 jobs) — no fixed step count.
- Screening question fields are self-describing: the textbox's accessible name **is** the question text, e.g. `get_by_role("textbox", name="How many years of work experience do you have with Core Java?*")`. A trailing `*` marks a required field.
- The post-submit confirmation modal's dismiss button label is inconsistent — observed both "Dismiss" and "Not now" across different jobs.
- A reliable success signal exists: "Application submitted" text appears after a successful submit.
- Radio buttons, dropdowns, and file-upload fields were not encountered in this recon session — no verified selector exists for them yet. Out of scope for this version (see below).

---

## Architecture

No changes to `main.py`'s orchestration loop. `LinkedInScraper` is added to `SCRAPER_MAP` under `"linkedin"` and to `config.example.json`'s `sites` list, exactly like the existing two entries.

```
scrapers/
├── base.py            # unchanged
├── cakeresume.py       # unchanged
├── job104.py           # unchanged — auth persistence pattern reused
└── linkedin.py         # new
tests/
└── test_linkedin.py    # new — mirrors test_cakeresume.py's mocking pattern
```

---

## Auth — Session Persistence (follows the 104 pattern)

LinkedIn is more sensitive to repeated automated logins than CakeResume. `login()` follows `job104.py`'s existing pattern exactly, retargeted:

- On start, attempt to load a saved session: `auth_linkedin.json` (local file, or downloaded from S3 in production via the same `_download_auth`/`_upload_auth` helper shape already in `job104.py`).
- If the saved session is valid (checked via presence/absence of a logged-out-only element), skip login entirely.
- Otherwise, perform a full login and save the resulting `context.storage_state()` to `auth_linkedin.json` (uploaded to S3 in production).

New secrets: `LINKEDIN_EMAIL`, `LINKEDIN_PASSWORD`, added to `secrets/loader.py`'s `_load_from_env()` required-keys list (and expected in the production Secrets Manager JSON blob).

---

## collect_links()

Same shape as the existing two scrapers: navigate to a LinkedIn job search URL with the Easy Apply filter applied (`f_AL=true`), extract and dedupe job URLs from the search results, respecting `pages` and `remote_only` the same way `cakeresume.py`/`job104.py` do.

**Randomized cap — isolated to this scraper, not `main.py`:** after gathering the full result set for a run, shuffle and slice to `random.randint(15, 25)` before returning. This keeps LinkedIn's "look human, vary the daily count" behavior contained entirely inside `LinkedInScraper.collect_links()`. `main.py`'s existing `max_links_per_site` truncation is untouched and continues to apply uniformly across all sites as it does today — for LinkedIn specifically, the random 15–25 cap is applied first, upstream of that shared logic.

---

## apply() — Step Loop (Approach A)

```
1. Navigate to job URL.
2. Find "Easy Apply to this job" — if absent, return skipped (external application, same as
   CakeResume's external-ATS handling).
3. Click it to open the Easy Apply modal.
4. Loop (capped at 10 iterations, same safety-valve style as the CakeResume Next-loop fix):
     a. Scan the current step for any field NOT matching "textbox whose accessible name
        ends in '?' or '?*'". If found (radio, dropdown, file input, or anything
        unrecognized) → close modal, return skipped with the link flagged
        (screening_links), same fallback convention as both existing scrapers.
     b. For each matching textbox found, pass its accessible-name text into the existing
        answer_screening_questions() (ai/screening.py) and fill in the answer — only when
        ai_screening is enabled; otherwise skipped + flagged, matching existing convention.
     c. If a "Continue to next step" button exists, click it and loop back to (a).
        Otherwise, exit the loop.
5. Click "Review your application" if present (optional step, some flows may skip straight
   to submit — same optional-step handling as CakeResume's resume-template step).
6. Click "Submit application".
7. Best-effort dismiss of whatever post-submit modal appears — match button text via
   regex (e.g. "Dismiss|Not now|Done") with a short timeout; proceed regardless of whether
   one was found.
8. Verify success: wait for "Application submitted" text to appear within a timeout.
   Found → return applied. Not found → return failed with an explanatory error — same
   verification convention as 104's "應徵成功" check and the CakeResume post-submit fix.
```

All of it wrapped in the same top-level `try/except → failed with str(exception)` pattern already used by both existing scrapers.

---

## Data Model Changes

`db/models.py` — `JobApplication.site` enum gains a value:

```python
site = Column(SAEnum("cakeresume", "104", "linkedin"), nullable=False)
```

No other schema changes.

---

## Config & Secrets Changes

`config.example.json` — `sites` list gains `"linkedin"`.

`secrets/loader.py` — `_load_from_env()` gains `LINKEDIN_EMAIL`, `LINKEDIN_PASSWORD`. Production Secrets Manager blob (`autojobber/production`) needs the same two keys added manually via the AWS console/CLI before first production run.

`main.py` — `SCRAPER_MAP` gains `"linkedin": LinkedInScraper`. No other change.

---

## Testing

`tests/test_linkedin.py`, mirroring `tests/test_cakeresume.py`'s approach: `MagicMock`-based `page`/`ap` objects, no real network/browser calls. Covers:

- `login()` navigates correctly and fills credentials when no saved session exists
- `collect_links()` extracts and dedupes links, and caps the returned list to the `random.randint(15, 25)` range
- `apply()` returns `skipped` when no "Easy Apply to this job" link is present (external application)
- `apply()` loops through multiple "Continue to next step" pages before reaching submit (same style as the CakeResume multi-page-Next test)
- `apply()` answers a text screening question via the mocked `answer_screening_questions` and fills it in
- `apply()` returns `skipped` (flagged) when an unrecognized field type is encountered on a step
- `apply()` returns `applied` when "Application submitted" text appears after submit
- `apply()` returns `failed` when that success text never appears (mirrors the CakeResume post-submit-verification test)

---

## Out of Scope (this version)

- Radio button, dropdown/select, and file-upload (resume selection) question types — no verified DOM structure exists yet. A follow-up recon session targeting a job with a yes/no or work-authorization question would be needed before extending the field-type handling.
- Resume tailoring per job.
- Any LinkedIn feature beyond Easy Apply (e.g. jobs requiring an external application).
