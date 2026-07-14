# Geode Community Input Boundary

## Status

This document replaces an older community-workspace plan. The active Geode
architecture is a backend regulatory intelligence database and orchestration
layer.

## Rule

External commentary, annotations, review notes, partner feedback, or downstream
user content must never become canonical legal truth.

## Allowed Use

External input may be useful as review evidence or issue reporting when it is
kept outside the canonical corpus. A correction may enter Geode only through the
normal backend path:

1. identify the official source
2. preserve source evidence
3. validate the proposed normalized record
4. snapshot any replaced canonical file
5. write through atomic storage helpers
6. update indexes, crosswalks, timelines, and logs
7. record provenance and reviewer approval

## Current Product Boundary

Geode serves AI systems, agents, APIs, search, retrieval, ingestion, and legal
data analysis. Community input is a possible upstream signal, not a product
surface and not a source of legal authority.
