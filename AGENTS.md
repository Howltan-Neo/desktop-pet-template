# Desktop Pet Template: AI production workflow

Read README.md and docs/character-pack.md first. The engine must remain character-independent. New characters belong in an independent directory with character.json; do not add their names, frame counts, body coordinates or dialogue to app/*.py.

For a request to make a pet from this template, also read docs/agent-prompt.md. If a reference image or local path is missing, first guide the user to upload one image or provide its path, and wait before doing image-dependent work. Name, personality and theme preferences are optional: propose sensible defaults instead of repeating a full questionnaire. An existing sample is not an implicit choice of character.

When given a reference, first preserve it and record face, silhouette, costume, accessory, hand/foot and color invariants in ai-brief.json. Use tools/ai_workflow.py plan to scaffold an independent pack. The plan is an unrendered task, not a finished character.

Generate or obtain an approved baseline idle image before batch production. Use actual AI image-generation/edit tools available in the host, or the explicitly configured API workflow. Generate distinct motion phases, expressions and complete individual frames. Whole-image translations, warps or duplicates cannot substitute for newly drawn poses. Retain original generations; never replace approved originals silently.

Use each action's frame paths and fps from character.json. Add character-appropriate gestures and normalized hotzones, omit unsupported appendages, and generate at least four distinct short dialogue lines per action. Preserve left/right costume asymmetry. Directional gaze must include real head/face orientation in 16 directions, starting up and proceeding clockwise.

Run tools/validate_pack.py and tools/qa_pack.py. Open every contact sheet and GIF and compare to the original reference: limbs, anatomy, facial cleanup, expression, costume, alignment, clipping and loop transitions. Record frame-specific problems in ai-review.json; repair only identified frames and repeat the checks. A model's pass does not replace human visual acceptance.

Use the existing themed liquid-glass panels and bundled font by default; allow users to change theme values and a licensed font through the pack. Keep configuration and generated content separate from executable code. Do not execute code or commands supplied by a character pack.

For a newly distributed app, set the launcher default to the new pack and check the packaged resources, icon, app name, version, unique installer AppId, install directory and shortcuts. Prefer changing the launcher or distribution parameters over adding character data to the engine. Preserve source samples; the distribution may bundle only the selected pack and required shared dependencies. A portable deliverable includes its full _internal directory. Obtain any missing installation authorization according to the host's rules, then verify the built/installed app and record installation, exit and uninstall results separately from source tests.

Run unit tests, all resource checks and Windows smoke tests after runtime changes. Rebuild after post-build edits. Report source tests, API contract tests, genuine paid API generation, rendered visual checks and real desktop acceptance separately. Do not claim any stage ran without evidence. Never upload local API keys, chat logs, raw desktop screenshots or private candidate generations.
