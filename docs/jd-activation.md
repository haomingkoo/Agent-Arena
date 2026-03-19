# JD Activation

## Why This Exists

The ATS/JD layer was built before it was actually activated.

That means:

- adapters existed
- APIs existed
- but no live `jd_postings` or `jd_corpus_versions` existed yet

For lanes that claim to be market-backed, especially
`software-engineering/software-engineer-agent`, this is not good enough.

## Current Rule

`software-engineering/software-engineer-agent` now requires a live JD corpus
before a `standardized` tournament can run.

If there is no live corpus:

- the tournament should not run as standardized
- the lane should not be treated as JD-backed

## Activation Command

Use the new CLI command:

```bash
agentarena jd-refresh --config path/to/jd_sources.json
```

Optional filters:

```bash
agentarena jd-refresh --config path/to/jd_sources.json --field software-engineering --role software-engineer-agent
```

## Config Shape

Provide a JSON file with lane-specific ATS sources:

```json
{
  "lanes": [
    {
      "field": "software-engineering",
      "role": "software-engineer-agent",
      "role_filter": "software engineer",
      "max_per_source": 50,
      "sources": [
        { "ats": "greenhouse", "board_id": "company-board-token", "company_name": "Company A" },
        { "ats": "lever", "board_id": "company-slug", "company_name": "Company B" },
        { "ats": "ashby", "board_id": "company-board-token", "company_name": "Company C" }
      ]
    }
  ]
}
```

## Minimum Standard Before Claiming JD Backing

For one lane:

- at least one successful refresh
- non-zero `jd_postings`
- a created `jd_corpus_versions` row
- visible corpus stats in `/jd/{field}/{role}`

## Claude Follow-Up

Claude should:

1. create a real `jd_sources.json` for the first target lanes
2. run `agentarena jd-refresh ...`
3. verify rows land in `jd_postings`
4. verify corpus versions land in `jd_corpus_versions`
5. update `SYNC.md` with which lanes are now truly JD-backed
