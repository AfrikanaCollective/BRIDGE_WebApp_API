# Mission

## Purpose

data BRIDGE digitizes paper-based clinical and research forms using AI vision, eliminating manual transcription and bridging the gap between paper records and structured digital data.

## Dual Mission

**Clinical use** — frontline health workers (nurses, midwives) upload scanned or photographed paper forms at or near the point of care. BRIDGE extracts structured data immediately, reducing transcription burden and latency.

**Research use** — research coordinators and data managers batch-upload archived or retrospective paper records. BRIDGE accelerates cohort-building and retrospective studies without manual data entry.

## Problem Statement

Neonatal clinical records at facilities like KEMRI-Wellcome Trust are still captured on paper (ITF, NAR forms). Digitizing these records manually is slow, error-prone, and expensive. BRIDGE automates this using a Qwen Vision Language Model pipeline, producing structured JSON suitable for downstream analytics, LLMs, RAG systems, and clinical decision support.

## Target Users

| Role | Primary task |
|---|---|
| Clinical nurses / midwives | Upload individual forms from ward; view results immediately |
| Research coordinators | Batch-upload archived form sets; track job status |
| Data managers / analysts | Review extracted results, flag errors, export data |
| System admins / PIs | Monitor pipeline health, processing stats, storage |

## Guiding Principles

- **Low-resource friendly** — must work on smartphones with poor connectivity; minimize image upload size requirements
- **AI-ready storage** — output JSON structured for LLMs, RAG, vector DBs, and Elasticsearch from day one
- **Reliability over novelty** — proven, popular stack (React + Python + MongoDB); no exotic dependencies
- **Accessible design** — modern, attractive UI that works across device sizes and modern browsers

## Production Target

`https://bridge.kemri-wellcome.org`
