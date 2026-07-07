# ADR 0001: PostgreSQL + PostGIS over MongoDB with geo-indexes

Status: TODO — fill this in once you've actually made the call, not before.
Writing this before you've weighed the trade-off yourself defeats the point.

## Context

What does the project need from its database? (e.g., radius queries around a
point, historical time-series per station, relational integrity between
stations and readings.)

## Options considered

- PostgreSQL + PostGIS
- MongoDB with `2dsphere` geo-indexes
- (Any other option you genuinely considered)

## Decision

State which you chose.

## Reasoning

This is the section that actually matters. Don't write "Postgres is more
popular" — write the specific trade-off that mattered for *this* project:
query patterns you needed, consistency guarantees, how you're already using
relational data (stations to readings), or anything else that was a real
factor in your decision. If you can't fill this in honestly, it means you
haven't actually thought through the choice yet — do that before writing it
down.

## Consequences

What did this choice cost you? (e.g., PostGIS has a steeper learning curve
than a plain lat/lon field; migrations are more rigid than a schemaless
document store.) A believable ADR names real trade-offs, not just upsides.
