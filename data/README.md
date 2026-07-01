# Tempus Sales Copilot — Mock Data

> **Disclaimer:** All data in this directory is synthetic and fabricated for demo and case-study purposes only. No real patients, providers, or clinical statistics are represented.

## Contents

| File / folder | Description |
|---------------|-------------|
| `providers.csv` | Market intelligence — one row per provider (join key: `provider_id`) |
| `product_knowledge_base.md` | Product descriptions for xT CDx, xR, and xF+ |
| `product_fit_table.json` | Editorial specialty → product fit scores (0–100) |
| `product_fit_rationale.md` | One-sentence justification per specialty's top-scoring product |
| `crm_notes/` | Informal rep notes, one file per provider (`crm_notes_{provider_id}.txt`) |

## Provider count

7 providers in `providers.csv`. CRM notes exist for 6 providers; **P007 has no CRM file** (intentional missing-data test case).
