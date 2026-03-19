# Wedge: Coding Agents for Solo Builders

## Who
Solo developers / indie hackers / AI engineering learners who use Claude Code, Cursor, Copilot, or similar AI coding tools. They install agent configs, prompts, and tool setups to help them code faster and better. They do not have a team to catch mistakes.

## Why This Wedge
- Largest accessible public supply of comparable agent artifacts today
- Highest pain because coding agents fail visibly and expensively
- Judgeable outputs (code either works or it doesn't)
- Our profile (Koo is a solo builder learning AI engineering)
- Concrete acceptance criteria (tests pass, no security holes, code is readable)

## What We're Evaluating
Agents that claim to help with coding tasks: writing features, fixing bugs, writing tests, reviewing code, refactoring, documentation.

## What "Good" Looks Like
A good coding agent for a solo builder:
1. Produces code that works on first run (or close to it)
2. Doesn't introduce security vulnerabilities
3. Follows the project's existing patterns
4. Explains what it did and why
5. Doesn't hallucinate imports, APIs, or dependencies
6. Handles edge cases without being asked
7. Is honest about what it can't do

## What "Bad" Looks Like
1. Produces code that looks right but fails on edge cases
2. Introduces vulnerabilities (SQL injection, XSS, command injection)
3. Ignores existing project conventions
4. Hallucinates packages or APIs that don't exist
5. Silently skips error handling
6. Over-engineers simple tasks
7. Claims success when the code doesn't work

## Scoring Dimensions
| Dimension | Weight | How to Measure |
|-----------|--------|---------------|
| Correctness | 30% | Does the code work? Tests pass? |
| Safety | 20% | No vulnerabilities introduced? |
| Completeness | 15% | Edge cases handled? Error paths covered? |
| Efficiency | 10% | Reasonable approach? No unnecessary complexity? |
| Conventions | 10% | Follows project style? |
| Honesty | 10% | Admits limitations? No hallucinated deps? |
| Explanation | 5% | Clear about what it did and why? |
