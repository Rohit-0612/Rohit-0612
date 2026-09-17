# Rohit Kumar

**AI Engineer — retrieval, multi-agent systems, and the evaluation that keeps them honest.**

I build LLM systems that are held to a measurable standard: every answer cited, every
claim checked by something other than the model that made it, and the numbers published
in the README even when they are unflattering. Most of what I ship runs end to end —
retrieval, orchestration, API, and interface — rather than stopping at a notebook.

Final-year B.E. Computer Science student at **Atria Institute of Technology**, Bangalore
(7th semester, graduating 2027) · Open to AI engineering roles and internships.

---

## Selected work

### [ARIA](https://github.com/Rohit-0612/aria) — evidence-grounded clinical pharmacotherapy
[**Live demo**](https://mohitrks-aria.hf.space) · LangGraph · Qdrant · Cohere rerank · FastAPI/SSE · React

A multi-agent assistant that answers pharmacotherapy questions strictly from two reference
texts, with page-level citations behind every claim. A separate **Judge agent** scores
groundedness and relevance before an answer is allowed to reach the user, and each response
carries a graded evidence tier and a visible confidence gauge. The interesting problem here
was refusal: making the system decline rather than improvise when the retrieved passages
do not support an answer.

### [BirdID](https://github.com/Rohit-0612/birdid) — local-first species identification
PyTorch · EfficientNetV2-S · BioCLIP · BirdNET · Grad-CAM

Identifies a bird from a photo or a call, entirely offline. A 200-way classifier cannot say
"none of the above" — it renormalises over the classes it has — so a photo of a frog came
back as a confident nightjar. I added an **open-set gate** over the raw logits, then a second
identifier (BioCLIP) that scores images against species *names* rather than a fixed class
list, extending reach from 200 species to 6,423. Measured on 130 photos of 26 species outside
the trained set: **79% top-1**, **91.5% precision** among committed answers. When neither
model is confident, it files nothing and says why.

### [Multilingual Voice RAG](https://github.com/Rohit-0612/HHGoa26-Voice-Rag) — 14 Indic languages
Sarvam STT · Qdrant hybrid (dense + BM25, server-side RRF) · guardrails

Voice in, grounded answer out, across all 14 Indic languages in `ai4bharat/MSMARCO-XI` —
27,958 passages, 29,582 indexed points. Two guardrails, a provider fallback chain, and
latency instrumented at every stage. **recall@5 0.58** against MSMARCO gold labels,
**P50 6.0s** end to end, 65 tests, and 35 design decisions written up with the alternatives
I rejected and why.

### [FinStock Research Assistant](https://github.com/Rohit-0612/finstock-research-assistant) — multi-agent market research
LangGraph (supervisor + parallel fanout) · RAG · FastAPI/SSE · React

Five-node graph covering NSE/BSE and US markets: a guardrail and query analyser routes to
parallel market-data, news, and knowledge-RAG agents, then a synthesis node with an output
guardrail. It cites a source for every data point and **refuses to produce predictive or
advisory output** — the constraint that shaped the whole design.

### [CI Failure Triage Agent](https://github.com/Rohit-0612/CI-Failure-Triage-Agent) — agentic developer tooling
Python 3.11 · uv · ruff · pytest

Investigates failed GitHub Actions runs: collects logs, diffs and history, forms and verifies
a root-cause hypothesis, and proposes a fix a human must approve. Built on a mined dataset of
**real** CI failures from public repositories — 50-case dev split and a held-out 25-case test
split — each paired with the commit that made CI green again, with a deterministic rule
baseline to beat. Built in phases, with the README stating plainly what is not implemented yet.

### [Olist E-Commerce Analysis](https://github.com/Rohit-0612/olist-ecommerce-analysis) — 100k orders, 2016–2018
PostgreSQL · SQL · pandas · Streamlit

End-to-end analysis of the Brazilian e-commerce dataset: relational modelling, six analytical
SQL queries, a chart suite, EDA notebook and a Streamlit dashboard.

---

## Also here

[medbot-rag](https://github.com/Rohit-0612/medbot-rag) — Flask + Qdrant hybrid retrieval over pharmacology case reports ·
[multi-agent-codegen](https://github.com/Rohit-0612/multi-agent-codegen) — prompt to running full-stack app, with a self-repair loop on local Ollama ·
[forecasting-project](https://github.com/Rohit-0612/forecasting-project) — ARIMA/Prophet/XGBoost/LSTM per state, best model selected on a strict out-of-sample window

---

## Tools

**LLM systems** LangGraph · RAG (dense, BM25, hybrid RRF) · Qdrant · Cohere rerank · open-set and refusal handling · LLM-as-judge evaluation
**ML** PyTorch · scikit-learn · XGBoost · Prophet · transfer learning · Grad-CAM
**Backend** Python · FastAPI · Flask · SSE streaming · PostgreSQL · pytest · uv · ruff
**Frontend** TypeScript · React · Next.js · Tailwind

---

## Contact

**[LinkedIn](https://www.linkedin.com/in/rohit-kumar-857b38360/)** — the fastest way to reach me.

If a project here is relevant to something you are hiring for, open an issue on that repo
or message me on LinkedIn and I will walk you through the design decisions behind it.
