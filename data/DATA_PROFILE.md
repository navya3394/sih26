# AyuSetu Terminology Data Profile

The interactive index contains 6,000 terminology records for the local presentation environment. Every record has a NAMASTE-style code, an ICD-11 TM2-style target, a biomedical ICD-11-style target, and a confidence score so the complete clinical workflow can be exercised without external API credentials.

The source-backed seed records are retained where available. Additional linked records are generated from the seed terminology to provide broad search coverage and deterministic mapping behavior for the interface. Generated mapping fields are marked internally with `syntheticMapping: true` and must not be represented as official WHO or Ministry mappings in a production deployment.

The application UI intentionally presents the workflow rather than exposing internal data-provenance fields. The production data pipeline should replace generated mappings with the authoritative NAMASTE/WHO/ICD-11 datasets and validated crosswalks.
