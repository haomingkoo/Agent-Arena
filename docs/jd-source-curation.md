# JD Source Curation

## Why This Exists

The ATS/JD pipeline is only useful if the source list is good.

Bad source curation gives us:

- empty corpora
- noisy role definitions
- hand-wavy tournament tasks
- fake confidence that a lane is "market-backed"

Good source curation gives us:

- a live role corpus
- real role blueprints
- better qualification prompts
- better tournament task packs

## What We Confirmed

On 2026-03-18, the first live SWE refresh succeeded:

- `fetched=26`
- `new=20`
- `deduped=6`
- one dead source: `lever/flex` returned `404`

After the refresh:

- `jd_postings_total = 27`
- `jd_postings_swe = 25`
- `jd_corpus_versions_total = 2`

So the pipeline is real now, but source curation still matters.

## Current Rule

For a lane to claim JD backing, its source list should be:

- same-role only
- public and currently reachable
- spread across multiple ATSes
- spread across multiple companies
- not dominated by one mirror, recruiter, or aggregator

## How To Pick Good SWE Sources

For `software-engineering/software-engineer-agent`, prefer boards that:

- publish titles containing `Software Engineer`
- come from direct company boards, not generic relay sites
- span enterprise, mid-market, and startup employers
- are hosted on ATSes we already support: `Greenhouse`, `Lever`, `Ashby`

Avoid as primary sources:

- staffing relays
- multi-company reposting farms
- aggregator job mirrors
- boards that only expose unrelated subroles and never match the active title filter

## Current SWE Config

The starter config is in:

- `data/jd_sources.swe.json`

It currently uses:

- `Greenhouse`
  - `canonical`
  - `databricks`
  - `appliedintuition`
  - `array`
- `Lever`
  - `applydigital`
  - `aledade`
  - `civitech`
  - `granicus`
- `Ashby`
  - `ashby`
  - `flowengineering`
  - `upvest`

`flex` was removed after returning `404` in the first live refresh.

## Research-Backed ATS Notes

The currently most useful public ATS surfaces are:

- `Greenhouse Job Board API`
  - public GET access to board jobs
  - official docs: https://developers.greenhouse.io/job-board.html
- `Lever Postings API`
  - public job postings endpoint by site slug
  - official docs: https://github.com/lever/postings-api
- `Ashby Public Job Posting API`
  - public board endpoint by job board name
  - official docs: https://developers.ashbyhq.com/docs/public-job-posting-api

Useful next ATS targets:

- `SmartRecruiters`
  - public posting API exists, but we do not yet have an adapter
  - official docs: https://developers.smartrecruiters.com/docs/posting-api
- `Workable`
  - useful, but requires authenticated access and is not a drop-in public scrape target
  - docs: https://help.workable.com/hc/en-us/articles/115012771647-Using-the-Workable-API-to-create-a-careers-page

## Operational Loop

Per lane:

1. curate the ATS board list
2. run `agentarena jd-refresh --config ...`
3. verify postings actually land
4. inspect corpus quality
5. only then claim the lane is JD-backed

## Claude Follow-Up

Claude should:

1. maintain one curated JD source config per target lane
2. remove dead boards after each refresh
3. avoid aggregator-heavy boards as the primary role corpus
4. expand ATS coverage only when the new adapter is actually useful for same-role sourcing
5. tie standardized tournaments to the latest live corpus version
