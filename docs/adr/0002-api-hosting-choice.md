# ADR 0002: Render over AWS App Runner / Elastic Beanstalk for API hosting

Status: Decided and shipped. The API has been live on Render since Week 4,
verified end-to-end multiple times including the full Week 5 alert pipeline.

## Context

By Week 4 the database decision (ADR 0001) was made and RDS was live. What
remained was choosing where the stateless FastAPI process itself runs.
Unlike the database, the hosting platform for the API doesn't need to
provide any capability the project specifically requires — it just needs to
run a Python process and be reachable at a public URL.

## Options considered

- AWS App Runner
- AWS Elastic Beanstalk
- Render
- Fly.io

## Decision

Render, free tier.

## Reasoning

The key realization: **the specific claims this project needs evidence for
— "real AWS RDS," "real PostGIS," "a real benchmarked spatial index" — are
fully satisfied by the database living on AWS.** The API process hosting
platform doesn't carry any of that weight. Once that was clear, the decision
became a much lower-stakes "what's the fastest path to a reliable public
URL" question, not a "which platform proves more resume keywords" question.

Against that framing:

- **AWS App Runner has no free tier at all** — it bills per vCPU/memory-hour
  from the first minute. For a small always-on FastAPI service that's a real,
  ongoing cost with no corresponding benefit, since the AWS-specific claims
  were already earned by the database.
- **Elastic Beanstalk** would have meant managing an actual EC2 instance
  (sizing, security groups, environment configuration) for what is
  functionally a single Python process — more operational surface than the
  app justifies, and still not free.
- **Render** deploys directly from the GitHub repo via a committed
  `render.yaml` Blueprint (infrastructure as code, not just dashboard
  clicks), costs nothing on the free tier, and needed close to zero
  AWS-style setup (no VPC, no security groups, no IAM role for the compute
  itself).
- **Fly.io** was a reasonable alternative but its free-allowance terms have
  shifted more over time and, per the earlier research into this decision,
  weren't as clearly documented as Render's at decision time — not worth the
  extra diligence for a choice this low-stakes.

## Consequences

- **Render's free tier sleeps after ~15 minutes of inactivity.** This is a
  real, observed cost: the first request after a quiet period times out on
  a normal timeout window and needs a longer one — confirmed directly during
  verification, not a theoretical caveat. A live demo link clicked cold can
  feel briefly broken on the first hit. Worth mentioning proactively in an
  interview rather than letting someone discover it.
- **Two vendors instead of one** for infrastructure (AWS for the database,
  Render for the API) means two dashboards, two auth stories, two places
  something could go wrong — a small real complexity cost against the
  single-vendor alternative, accepted because neither AWS hosting option was
  free and the app didn't need anything AWS-specific beyond the database.
- **Secrets management became slightly more involved** as a direct
  consequence of the two-vendor split: `DATABASE_URL` needed to be set in
  three separate places (local `.env`, Render's environment variables, and
  GitHub Actions secrets for the ingestion cron), each a manual step with
  its own chance to be missed — which is exactly what happened once (a
  GitHub secret silently failed to save, causing the scheduled ingestion job
  to fail every run until caught and fixed). A single-vendor setup wouldn't
  eliminate this class of problem, but it would reduce the number of places
  the same secret has to be kept in sync.
