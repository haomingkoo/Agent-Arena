# JD to Role to Test Matrix

## Purpose

Use real job demand signals to make sure each lane matches an actual job.

This document defines how AgentArena should use:

- occupational datasets
- job descriptions
- interview-style qualification prompts
- work-sample benchmark tasks

The goal is to test the right kind of agent for the right job.

## Core Principle

Do not define a role from one repo label or one prompt file.

Define it from:

1. official occupational data
2. multiple current job descriptions for the same role
3. qualification prompts
4. work-sample tasks

## Source of Truth Stack

### Level 1: Role Anchor

Use official occupational data first.

Recommended sources:

- O*NET Web Services
- U.S. Bureau of Labor Statistics Occupational Outlook Handbook

Why:

- stable role taxonomy
- recurring duties
- skills, tasks, and work activities
- useful for naming lanes and setting boundaries

References:

- O*NET Web Services: https://services.onetcenter.org/about
- Software developers duties: https://www.bls.gov/ooh/computer-and-information-technology/software-developers.htm
- Electrical and electronics engineers duties: https://www.bls.gov/ooh/architecture-and-engineering/electrical-and-electronics-engineers.htm

### Level 2: Current JD Corpus

Use multiple live job descriptions for the same role from different company sizes.

Recommended company mix per role:

- 4 enterprise companies
- 4 mid-market companies
- 4 startups or growth-stage companies

This is an inferred sampling policy, not a standard from the sources above.

Why:

- catches current tool and workflow expectations
- prevents overfitting to one company's language
- reveals common responsibilities across different environments

### Level 3: Qualification Prompts

Build short interview-style or screening-style prompts from the shared JD core.

Purpose:

- lane admission
- role-fit classification
- relabeling of misclassified candidates

### Level 4: Work-Sample Tasks

Use realistic job tasks for the public tournament.

Purpose:

- actual ranking
- trace analysis
- agent-vs-agent comparison

## Preferred Job Sources

Use ATS-backed company job boards first.

They are more stable, cleaner, and more machine-readable than arbitrary job
aggregator pages.

### Highest-Priority ATS Sources

- Greenhouse Job Board API
- Lever Postings API
- Ashby Job Postings API
- SmartRecruiters Posting API
- Workable API

References:

- Greenhouse Job Board API: https://developers.greenhouse.io/job-board.html
- Lever Postings API: https://github.com/lever/postings-api
- Ashby Job Postings API: https://developers.ashbyhq.com/docs/public-job-posting-api
- SmartRecruiters Posting API: https://developers.smartrecruiters.com/docs/posting-api
- Workable API docs: https://help.workable.com/hc/en-us/articles/115013356548-Workable-API-Documentation

## Aggregators vs ATS

Use job aggregators carefully.

### Good Uses for Aggregators

- finding candidate companies
- spotting hot roles
- estimating demand
- discovering new language and job-title variants

### Bad Uses for Aggregators

- primary JD ingestion
- canonical role definition
- source of truth for structured task extraction

Why:

- APIs may be partner-gated
- rendered pages are noisy
- duplication is common
- terms and access patterns can change

Indeed in particular has official APIs for posting management and partner
workflows, but that is not the same as a clean public search source for our use.

References:

- Indeed docs overview: https://docs.indeed.com/
- Indeed Job Sync API: https://docs.indeed.com/job-sync-api/

## MCP and Connector Strategy

Do not start by hunting for a different MCP server for every job board.

Build source adapters first.

If we want MCP later, expose our own normalized connector layer through one
internal MCP service.

### Recommended Connectors

1. `onet_source`
   - occupation tasks
   - skills
   - duties
   - title variants

2. `bls_source`
   - outlook
   - salary
   - demand context

3. `greenhouse_source`
   - published jobs
   - departments
   - locations

4. `lever_source`
   - postings
   - posting detail

5. `ashby_source`
   - published jobs
   - compensation when available

6. `smartrecruiters_source`
   - posting detail

7. `workable_source`
   - jobs and requisition metadata where available

8. `browser_fallback`
   - only for company career pages without usable APIs

### Recommendation

Start with adapters, not MCP.

Then optionally wrap the normalized adapter layer in one MCP service for:

- role research
- Claude/Codex query access
- JD corpus inspection

## Role-Building Workflow

1. Pick a candidate lane.
2. Pull O*NET and BLS role anchors.
3. Collect 12 current JDs across company sizes.
4. Extract repeated responsibilities, tools, and outputs.
5. Write a role-core matrix:
   - responsibilities
   - artifacts produced
   - tools used
   - evaluation outcomes
6. Build qualification prompts.
7. Build work-sample tasks.
8. Validate that tasks reflect the JD core rather than one company's quirks.

## Role Matrices

### Software Engineering -> Software Engineer Agent

JD core usually includes:

- understand requirements
- design or modify systems
- implement code
- debug defects
- test and maintain systems
- document changes
- reason about security and reliability

Qualification prompts should test:

- debugging
- implementation planning
- test design
- system tradeoffs
- maintenance reasoning

Work-sample tasks should include:

- implement a feature from a spec
- fix a failing defect
- add or repair tests
- review a risky change
- analyze a production issue

Important note:

Current BLS duties for software developers are broader than the current repo's
code-review-heavy task pack.

Reference:

- https://www.bls.gov/ooh/computer-and-information-technology/software-developers.htm

### Software Engineering -> Code Review Agent

JD proxy sources often come from application security or product security roles.

JD core usually includes:

- inspect changes for vulnerabilities and correctness issues
- recommend mitigations
- communicate severity and impact
- reason about architecture and operational risks

Qualification prompts should test:

- vulnerability identification
- correctness review
- risk prioritization
- remediation quality

Work-sample tasks should include:

- review a diff for security flaws
- review a PR for correctness risks
- review test adequacy
- review operational or privacy impact

Proxy references:

- https://jobs.lever.co/palantir/205c3184-4272-41a9-a1e2-5352d4d00910
- https://jobs.lever.co/lendbuzz/3b4f0488-7f7d-4732-b1d1-016c70649ad9

### Semiconductor -> Verification Debug Agent

JD core usually includes:

- build or use testbenches
- debug assertion failures
- analyze protocol behavior
- inspect coverage gaps
- triage regressions
- work with SystemVerilog or UVM environments

Qualification prompts should test:

- assertion reasoning
- reset and handshake analysis
- log and waveform interpretation
- coverage reasoning

Work-sample tasks should include:

- root-cause a failing assertion
- debug reset sequencing bug
- explain a coverage hole
- triage a regression failure
- analyze a protocol or CDC issue

References:

- https://careers.synopsys.com/job/bengaluru/senior-design-verification-engineer-ddr/44408/90948502240
- https://careers.synopsys.com/job/noida/staff-design-verification-engineer/44408/91940192160
- https://careers.synopsys.com/job/zapopan/pre-silicon-design-verification-engineer-sr-staff/44408/90667798096

## Role-Fit Scoring

Each candidate should receive three scores:

- `jd_fit_score`
- `qualification_fit_score`
- `work_sample_fit_score`

Suggested use:

- high JD fit + high qualification fit -> lane admission
- low JD fit but high work-sample fit -> relabel review
- low qualification fit -> reject from public lane

## Mislabeled Agents

Mislabeled agents are not a problem if the routing system is strong.

Policy:

- self-label is a hint
- qualification and work-sample fit can override the self-label

Example:

- repo says `software engineer agent`
- qualification and performance say `code-review-agent`
- route it to the review lane

## Immediate Build Tasks

1. Add JD corpus support to the role-definition workflow.
2. Create lane-specific JD extraction templates.
3. Add `jd_fit_score` fields to role-classification output.
4. Build qualification prompt sets for:
   - `software-engineer-agent`
   - `code-review-agent`
   - `verification-debug-agent`
5. Align current task packs to the role matrix above.

## Acceptance Criteria

- each lane has an explicit role-core matrix derived from JD evidence
- each public lane has qualification prompts and work-sample tasks
- tasks can be traced back to common JD duties, not just repo labels
- off-role agents are routed or rejected before public ranking
