# Technical Project: ReviewLens AI

## Business Context

Imagine a consultancy that specializes in Online Reputation Management (ORM). Their business model relies on analyzing massive amounts of fragmented customer feedback to offer strategic services to brands.

Currently, their analysts spend hours manually reading reviews to identify "pain points." They need a rapid prototype of a Review Intelligence Portal that can ingest a product's digital footprint and allow an analyst to "talk" to that data to find specific trends—without the AI drifting into generalities or competitor data.

## The Mission

Develop ReviewLens AI: A secure, web-based portal that enables a user to track a product or entity from a single review platform (Amazon, Google Maps, G2, Capterra, or a similar publicly accessible platform) and analyze those reviews using a guardrailed Q&A interface.

Whichever platform you choose, it should:

- Be publicly accessible — open to browse without authentication
- Feature user-generated content — customer-written text reviews and ratings
- Ready to be deployed to production—build the system such that we can deploy to production

## Our Review Approach

We value your ability to build great software, including your use of AI tools (Claude Code, Cursor, Codex, Copilot, etc.), which is expected.

As we review this project, we'll focus on the professional quality and speed of delivery, the judgment you use when working with AI, and the engineering instincts you demonstrate—all vital traits for a senior member of our team.

## Core Requirements

1. **Ingestion & Scraping Result Summary**
   - **Ingestion Module:** The application should accept a target URL from the chosen platform and extract the relevant review data, or otherwise allow the user to supply the data in a practical format for analysis
   - **Ingestion Result Summary:** Give the user a clear summary of what was successfully ingested — whether that's text-based, tabular, or a visual. The goal is to give confidence that the data is accurate, sufficiently complete, and ready for analysis
2. **Guardrailed Q&A Interface**
   - **Interactive Chat:** Build a user-facing interface where users can pose questions exclusively about the ingested reviews
   - **Scope Guard Enforcement:** This is one we care a lot about. If a user asks about an external platform or general world knowledge, the AI should gracefully and explicitly decline (e.g., if tracking Google Maps, it shouldn't discuss Amazon reviews or the current weather). This should be primarily driven by your system prompt configuration
3. **Deployment**
   - **Hosting:** We'd like to see the application hosted publicly and accessible via a URL
   - **Code:** Please share the full source code in a GitHub Repository

## Make This Your Own

This project is your canvas. The core requirements above set the baseline, but this is where you can go above and beyond to stand out. Take this project in whatever direction proves your unique value — whether that's through sophisticated prompt engineering, an elegant UI, a particularly clever architectural choice, or engineering practices that show how you'd operate on a production team. Surprise us!

## Project Guardrails and Scope

- **Self-Funded Project:** To maintain simplicity in our review process, we do not have a mechanism for expense reimbursement
- You're welcome to use any tools, LLMs, or platforms
- **No User Auth:** The application should be directly accessible via its URL without a login

## Project Review Items

1. **GitHub Repository:** A link to the complete code, shared with the hiring team
2. **AI Session Transcripts:** Include your full AI session transcripts (Claude Code session logs, Cursor Composer history, Copilot chat exports, etc.) in the repo under an `/ai-transcripts` directory. This is a first-class deliverable. Don't clean them up or cherry-pick — we want the real working session, including dead ends
3. **Live URL:** A direct link to your deployed application
4. **Loom Demo (under 3 minutes):** Walk us through what you built:
   - Demo the full flow end-to-end (scraping → summary → Q&A → scope guard)
   - Talk through your key design decisions and tradeoffs
   - Call out anything you're proud of, and anything you'd do differently
5. **README.md:** Setup instructions, architecture overview, and any assumptions you made

## Final Instructions

- **Assumptions:** We encourage you to use your best professional judgment for any detail not explicitly covered. Please approach anything not mentioned as you would when building production-grade software.
- To simulate a real-world rapid deployment environment, we won't be providing additional clarifications
- **Time:** We suggest 5 hours as a planning target. This is not a strict limit — if you want to invest more time to go deeper, that's your call
