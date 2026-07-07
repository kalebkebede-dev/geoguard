# Setup Checklist

Work through this before/during Week 1. Everything here is free.

## Accounts to create

- [ ] **AirNow API key** — https://docs.airnowapi.org — instant signup, this is your
      primary data source.
- [ ] **AWS account (free tier)** — https://aws.amazon.com/free
      - Immediately after signup: go to Billing → Budgets and set a $1 budget alert.
        This takes 2 minutes and means you'll never get a surprise charge.
      - You'll use RDS (Postgres) and App Runner or Elastic Beanstalk (API hosting),
        both of which have meaningful free tiers for 12 months.
- [ ] **GitHub repo** — create a new **public** repo, e.g. `wildfire-risk-platform`.
      Public matters — this needs to be visible on your profile.
- [ ] **NASA FIRMS API key (optional)** — https://firms.modaps.eosdis.nasa.gov/api/
      — adds active fire/hotspot data alongside AQI. Nice-to-have, not required for
      the MVP.
- [ ] **SendGrid free tier (optional)** — https://sendgrid.com — only if you get to
      the alerting stretch goal in Week 5.

## Local machine setup

- [ ] Python 3.11+ installed (`python3 --version`)
- [ ] Git installed and an SSH key added to your GitHub account
- [ ] A code editor (VS Code recommended — free, and has good Python + Docker
      extensions)
- [ ] Docker Desktop installed (optional but recommended) — lets you run
      Postgres+PostGIS locally in Week 2 without touching AWS RDS until deployment
      week. Saves you from burning AWS free-tier hours before you actually need to.

## Python environment

From inside the project folder:

```bash
python3 -m venv venv
source venv/bin/activate        # on Windows: venv\Scripts\activate
pip install fastapi uvicorn psycopg2-binary sqlalchemy requests pytest python-dotenv pandas
pip freeze > requirements.txt
```

## Engineering judgment note

Don't reach for PySpark on the live ingestion path — each AirNow API pull is a
small payload, and using a big-data tool there is a red flag to a sharp
interviewer, not a green one. Plain Python + pandas is the right tool for that
job. Save PySpark for the optional Week 5 stretch: a batch job aggregating your
*accumulated* historical readings for trend analysis. That's a dataset that
actually grows over time, which is where a tool like PySpark is genuinely
justified rather than just resume-keyword-stuffed in.

## First real milestone

By the end of Week 1, you should be able to run one script locally that calls the
AirNow API with your key and prints real AQI readings to your terminal. That's it —
resist the urge to build the database or API before that works end to end.
