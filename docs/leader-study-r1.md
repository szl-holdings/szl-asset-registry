# szl-asset-registry domain leader study r1 (propose-only)

Date: 2026-11-25. Method: web-verified leader landscape + owner-direct execution (standing authority GREENLIGHT-RULING-2026-11-24-K1 rank5; the Kimi ratification seat was stood down for this cohort by explicit owner directive, disclosed; owner-direct nonce T14-OWNER-DIRECT-20261125-K1). Study pinned to szl-asset-registry HEAD d9ab57960906cee858d2e9a08ca54de9462ab33c, fetched 2026-11-25. This card is documentation only; it changes no code, CI, config, or existing PR status. All absorb actions are FUTURE PROPOSALS (non-authorizing); implementation and merges remain separately reviewed and gated. L Conjecture 1: OPEN (advisory, never a closed theorem). No speedup, energy, or proven-trust claims; upstream performance claims are labeled as upstream claims only. No unverified signing, attestation, or provenance-level claims; this study verifies nothing about this repo's artifacts.

## Domain: fail-closed discovery metadata that maps Hugging Face assets to GitHub source repositories, keeping unmapped gaps explicitly honest

## Leaders studied (web-verified 2026-11-25)
1. huggingface_hub (https://github.com/huggingface/huggingface_hub) - moat: the canonical library and API surface for Hub asset metadata and file operations that any asset-inventory approach must interoperate with.
2. syft (https://github.com/anchore/syft) - moat: a widely adopted SBOM and asset-inventory generator producing reproducible metadata from source trees and images.
3. osv-scanner (https://github.com/google/osv-scanner) - moat: evidence-driven scanning that consumes project manifests and returns sourced advisory records.

## Absorb actions (FUTURE PROPOSALS, non-authorizing)
1. (huggingface_hub) Propose a documentation-only note distinguishing Hub-listed discovery metadata from a verified source checkout, with the fail-closed mapping rule kept explicit. Cost: doc-only, with an honest estimate; limit: note only, no code, no infra changes.
2. (syft) Propose a documentation-only review of SBOM inventory conventions compared to the registry's evidence-mapped fields. Cost: doc-only, with an honest estimate; limit: note only, no code, no infra changes.
3. (osv-scanner) Propose a documentation-only note on labeling advisory evidence distinctly from verified findings in registry reports. Cost: doc-only, with an honest estimate; limit: note only, no code, no infra changes.
4. Baseline preserve honestly: a matching name, shared README URL, or curated override is discovery metadata only and never proof of the GitHub checkout that produced an asset's weights; honest-unmapped entries stay visible and fail-closed.

## Do not do (per governing seat)

Do not merge, bypass the signature wall, or claim implementation beyond this card.
