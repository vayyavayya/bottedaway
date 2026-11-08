# LoRA plan (Phase 9 — plan only, nothing trained)

**Trigger:** a brain reaches 500 real correction pairs (dashboard shows it). Until then: retrieval + rulebook + base
LLM, which needs no training and improves with every capture.

**Base model:** `Qwen3.6-27B` instruct (the model already serving the engine; strong German). Fallback if VRAM is
tight: `Qwen3.5-9B` (faster to train, weaker style transfer).

**Method:** QLoRA (4-bit NF4 base, bf16 adapters) with Unsloth or PEFT + TRL SFT on the PC; one adapter per brain
(B1/B2/B3), rank 16, alpha 32, dropout 0.05, targets q/k/v/o + gate/up/down. Training sample = prompt (rules +
draft sections) → target (final sections). Only anonymised library rows, never quarantine.

**VRAM budget (RTX 5090, 32 GB):** 27B in 4-bit ≈ 15–16 GB weights + LoRA params/optimizer ≈ 1–2 GB + activations
at seq 2048 / batch 1 with gradient checkpointing ≈ 6–9 GB → ~24–27 GB. Fits; Ollama must be stopped during
training (it holds ~18 GB for qwen3.6:27b).

**Time:** 500 pairs × ~700 tokens ≈ 350k tokens/epoch; at ~1.5–2.5k tok/s for 27B QLoRA on a 5090 ≈ 3–4 min/epoch;
3 epochs + eval ≈ 15–25 min per brain, ~1 h for all three (9B: ~3× faster).

**Serving:** merge-free — export the adapter to GGUF LoRA and load it in Ollama with a Modelfile
(`FROM qwen3.6:27b` + `ADAPTER ./b1.gguf`) → models `radbrain-b1/b2/b3`; `settings.json` maps brain → model.

**Acceptance:** the adapter replaces base+prompt for a brain only if the holdout chrF (Phase 8) beats the current
engine by ≥ 1 point and the no-new-findings guard rejection rate does not rise. Otherwise keep retrieval + rules.

**Data protection:** adapters are derived from patient reports → stay on the PC, never pushed, never synced.
