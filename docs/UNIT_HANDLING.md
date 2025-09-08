# Normalizing Heterogeneous Scientific Units in PostgreSQL (postgresql-unit)

The data mixes unit spellings and ambiguous symbols. Normalize at ingest with `to_unit(val, unit_text)`, which converts legacy strings into the `unit` type from the postgresql-unit extension. The function returns NULL for unsupported/unknown or context-dependent units. Important policy: "A" is interpreted as Ångström (length). For electric current, use mA/µA/etc. or explicit words like "ampere".

## Problem

Many datasets contain inconsistent unit labels and context-dependent meanings, for example:
- Temperature: "°C", "C", "degC", "oC", "celsius", "K", "k", "Kelvin"
- Length and resolution: "Å", "A", "AA", "Ang", "ang", "angstrom", "nm", "um", "µm", "mm", "cm", "m"
- Reciprocal areas: "1/Å²"
- Magnetic field: "G", "Gauss"
- Energy: "eV", "keV", "MeV", "meV", "ueV"
- Dose and rate: "Gy/s", "kGy"
- Frequency/time: "hertz", "Hz", "s^-1", "s", "ms", "ns", "seconds"
- Mass/concentration: "g", "mg", "kg", "mg/ml", "kDa"
- Percent: "%"
- Pressure/voltage/current: "Pa", "kV", "mA"
- Context-dependent: "rlu" (reciprocal lattice units)

Direct casting like `'value unit'::unit` can fail or misinterpret data when:
- "C" is treated by the extension as Coulomb (charge) instead of Celsius (temperature).
- "A" is Ampere in base SI, but must be Ångström in these records.
- Aliases like "hertz", "um", "angstrom", "Bytes" are not always parsed by default.

## Goals

- Normalize all unit/value pairs into a consistent, comparable, indexable representation.
- Preserve scientific correctness across mixed units (e.g., mm vs Å vs nm, Hz vs s^-1).
- Return NULL instead of raising an error for unsupported or context-dependent inputs (so ingest can continue).

## Solution Overview

1. Use the postgresql-unit extension to store values in a `unit`-typed column.
2. Convert legacy pairs `(value, unit_text)` with `to_unit(val, unit_text)`.
   - Handles ambiguous tokens and common synonyms.
   - Converts non-SI labels to SI-compatible forms (e.g., Å → m, G → T, mg/ml → kg/m³, eV → J).
   - Converts Celsius inputs to Kelvin for internal consistency.
   - Returns NULL for context-dependent tokens like `rlu` and for anything the extension cannot parse.
3. Query with equality/range semantics across units; combine with pgvector by filtering on `unit` first and ordering by vector distance (optional).

## Key Decisions

- Temperature: "C", "degC", "°C", "oC", "celsius" are treated as Celsius and converted to Kelvin. "K", "k", "Kelvin" remain Kelvin.
- Ångström family: "Å", "A", "AA", "Ang", "ang", "angstrom" are mapped to meters via 1 Å = 1e-10 m.
  - Plain "A" is Ångström in this normalization. For electric current, use "mA"/"µA" or explicit "ampere".
- 1/Å²: converted to m^-2 using 1/Å² = 1e20 m^-2.
- Magnetic field: "G", "Gauss" → Tesla via 1 G = 1e-4 T. Lowercase "g" remains gram.
- Energy: eV family converted to Joules using the exact SI factor.
- Concentration: 1 mg/mL → 1 kg/m³ exactly.
- kDa: converted to kg using 1 Da = 1.66053906660e-27 kg.
- Time: "years" converted to seconds using 365.25 days.
- rlu: returns NULL because conversion requires lattice parameters.

## Edge cases and notes

- The base postgresql-unit parser treats "A" as Ampere. This normalization intentionally maps "A" to Ångström; use "mA"/"µA" or explicit words ("ampere") for current.
- "C" in the base extension is Coulomb; the helper interprets "C" as Celsius and converts to Kelvin.
- The degree symbol "°" requires proper encoding; ASCII-safe "degC" is supported.
- "rlu" depends on lattice parameters; to normalize it, enrich records with lattice metadata and handle conversion upstream or in a key-aware function.
- For complete disambiguation, consider a key-aware function variant (e.g., `to_unit_keyed(value, unit_text, key_text)`).

## Why this works

- postgresql-unit provides a dimensioned type with arithmetic, comparison, and indexing.
- Normalizing inputs through one function avoids inconsistent labels while keeping storage and queries simple and robust.
- Returning NULL keeps ingestion resilient; data quality checks can target NULL rows for remediation.