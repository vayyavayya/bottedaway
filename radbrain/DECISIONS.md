# DECISIONS — RadBrain

1. **Codes only (B1/B2/B3).** Names live only in `signers.json` in the data dir; the anonymiser replaces a signer's
   name anywhere in the text with the code, Ajit's own name with `[AA]`, listed staff with `[NAME]`.
2. **Data dir outside the repo** (`%LOCALAPPDATA%\RadBrain` on the PC). The repo is public: code + synthetic data only.
   `.gitignore` excludes sqlite/json/quarantine/rulebooks/images.
3. **No Triage for RadBrain (deviation from Ajit's 01.11.2026 "use Triage for everything").** Triage routes to
   Claude in the cloud; this project's hard rule is that report text never leaves the PC. The engine talks only to
   the PC's own Ollama on 127.0.0.1; `llm._base()` raises for any other host (tested).
4. **Anonymiser = structure first, then scrub, then fail-closed residual check.** The PACS header (name, DOB, PID,
   exam date) is dropped wholesale because only Fragestellung/Technik/Befund/Beurteilung are kept. Inside those:
   regex + name lists + context rules (titles, communication sentences). Residual check: any date/time/long number,
   listed name or capitalised word the lexicon cannot explain → quarantine. Lexicon = wordfreq (de) + compound
   splitting + medical suffix morphology + `lexicon_med.txt` + eponyms + abbreviations + the local allowlist that
   grows when Ajit releases a quarantined capture.
   Known residual risk: a surname that is also a frequent German word ("Trautwein", "Vogel"), written in the body
   **without** any cue (no title, no Herr/Frau, no "mitgeteilt an/Rücksprache mit"), passes. Mitigation: staff names
   in `signers.json`; Ajit checks the first captures and the quarantine.
5. **Synthetic recall test is necessary, not sufficient.** The generator draws half its names from a held-out list
   the anonymiser has never seen, and a hand-written adversarial set (tests/test_core.py::ADVERSARIAL) covers
   formats the generator never produces. Result 08.11.2026: 0 leaks in 1,040 synthetic texts + 12/12 adversarial;
   quarantine rate on clean synthetic text 0 % (real text will be higher at first: OCR noise, rare words).
6. **Embedding model: `bge-m3`** (multilingual, strong German retrieval, 1.2 GB, free via Ollama). Fallback when
   Ollama is down: character-trigram similarity, so Correct still runs (rules only).
7. **LLM: `qwen3.6:27b`** on the PC (already installed, 17.8 GB, fits the 5090 with room for bge-m3). Mac test box:
   `qwen3.5:9b`. The LLM output is accepted per section only if the guard finds no new/changed numbers, sides,
   asserted entities or content words (`engine.guard`); otherwise the rules-only version is kept and flagged.
8. **Rule = recurring, consistent edit:** count ≥ max(3, 3 % of the signer's pairs) and changed in ≥ 30 % of the
   pairs where it could apply. HOUSE STANDARD if ≥ 2 of 3 signers have it. Correct auto-applies rules with
   consistency ≥ 50 %; lower ones appear only in Predict.
9. **Saturation:** an entity is saturated for a brain when its last 20 pairs brought no rule "birth" (the capture at
   which a rule crossed the threshold).
10. **Dashboard:** stdlib HTTP server bound to 127.0.0.1:8650, Host-header check (DNS rebinding), POST requires
    `X-RadBrain: 1`, CSP self-only, no CDN — charts are inline SVG.
11. **Demo data never mixes with real data:** `python -m radbrain.demo` writes to `<data dir>-demo` and refuses a dir
    that contains real captures. The hotkey end-to-end test on the PC runs against the demo dir.
12. **Eval on synthetic data (08.11.2026, Mac, rules only):** chrF draft→engine B1 96.7→97.9, B2 89.7→96.4,
    B3 97.4→97.7; predict recall 52/73/67 %. Synthetic — proves the pipeline, says nothing about real performance.
13. **Phase 1 result (VERIFIED on the PC, 08.11.2026 22:56–22:58, real Citrix session open):** the Citrix window
    (`wfica32.exe`, class "Transparent Windows Client", 3840×2088) is NOT black. `mss` screen grab + Tesseract deu
    read 335 words (260 German) in 5.4 s. PrintWindow and Windows Graphics Capture return blank frames. **Clipboard
    route is blocked**: Ctrl+A/Ctrl+C sent into the focused Citrix panel never changed the local clipboard (Citrix
    clipboard redirection off). → Route = **mss + OCR** (`recommended_route: ocr`).
14. **OCR backend = Tesseract (deu, tessdata_best) with preprocessing**, measured on 30 synthetic panels (11–20 px,
    dark/light, JPEG q35–55 + blur): CER 0.67 % (median 0), abbreviations 95 %, umlauts/ß 100 %, 0.16 s/image.
    qwen3-vl:8b (Mac): 0.24 % CER when it answers but 2/22 empty (thinking runs out of tokens), ~50 s/image →
    not used; qwen3.6:27b as a second pass only after checking it honours think:false. Preprocessing was tuned on
    the same set (optimistic). Tesseract runs via stdin/stdout — pytesseract wrote temp PNGs, which would break the
    no-image-on-disk rule.
15. **OCR punctuation noise is not a correction:** `re.`↔`re,`, `V.a.`↔`V.a,` between the two panels are dropped by
    the miner (`miner.ocr_noise`).
16. **PC lifeline (08.11.2026):** the OpenSSH service had vanished (package still registered in winget); reinstalled,
    sshd Automatic + restart-on-failure, firewall rule for LAN + tailnet on all profiles, profiles forced Private,
    Tailscale unattended, SYSTEM watchdog every 5 min (`C:\ProgramData\RadLifeline`), Fast Startup off, WoL armed.
