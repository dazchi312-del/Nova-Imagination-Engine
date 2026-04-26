# Project Nova — Memory Substrate Implementation Plan
**Document:** PLAN-S29-001  
**Status:** Approved  
**Date:** 2026-04-25  

## 1. Purpose
Define the implementation order for the Nova memory substrate (ADR-134) and the single-writer constraint (ADR-135).

## 2. Guiding Principles
* **Tier 1 is sacred:** Episodes are immutable historical facts.
* **Tier 2 is disposable:** Beliefs are a derived, regenerable cache.
* **Atomic writes:** One cycle = one row.
* **Single writer:** Only one process owns the SQLite file; others use HTTP.

## 3. Phased Delivery
* **Phase 1:** Episode Store (Tier 1), single-node.
* **Phase 1.5:** Memory Service (HTTP wrapper).
* **Phase 2:** Beliefs and Deltas (Tier 2).
* **Phase 3:** Real models in the loop.
