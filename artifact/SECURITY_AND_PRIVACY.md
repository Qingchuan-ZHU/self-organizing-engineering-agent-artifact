# Security and privacy

## Credentials and private endpoints

- No `.env` file or credential value is included. The packaged `.env.example` has an empty `DEEPSEEK_API_KEY` field; its provider endpoint is public.
- The package scan must report zero credential-pattern hits and zero private/local URL hits. Re-run it with `python analysis/scripts/audit_release_package.py`.
- Raw Worker/Reviewer provider messages, provider logs, full run databases, evaluator raw responses, and failed evaluator workspaces are excluded. The failed-attempt summary publishes aggregate categories and source hashes only.

## Historical absolute-path metadata

The eight frozen `freeze.json` files contain twelve references to one historical credential-source path value. They occur in `worker_provider.credential_source.path` in all eight configurations and in `reviewer_provider.credential_source.path` in the four Explicit-collaboration configurations. The only path points to the historical checkout's `.env` file; the metadata contains no username, token, company name, or internal-server path.

The frozen configurations remain unchanged. This is an **accepted historical metadata disclosure for this review**, not a publication blocker. The expected package scan therefore reports twelve absolute-path findings, all in those eight frozen configurations. Any additional path finding requires review.

## Selected Reviewer workspace evidence

The Reviewer workspace case study contains three selected Python source files. Before inclusion, each was checked for credential patterns, absolute paths, and raw provider/message content. Their byte hashes match both the source workspace files and the sanitized Reviewer workspace-change events. The complete Reviewer workspace and message history remain excluded.

## Other exclusions and package boundary

The package contains no hidden benchmark/reference solution, API key, authorization header, cookie, private endpoint, full SQLite runtime state, or raw provider trace. The source repository's LFS provider logs and unselected evaluator results remain outside this package. No Git LFS object is required to inspect or verify the staged package. The package contains no symlink escape.

These checks do not themselves establish redistribution rights. The twelve reviewed path references are accepted as historical metadata and are not a publication blocker. License scope is recorded in `LICENSE.md`; historical provider-term caveats and the accepted factual attribution decision are recorded in `PROVIDER_TERMS_REVIEW.md`. Blind Codex reviews remain model-based post-hoc evidence, not formal engineering ground truth; `UGS_FORMAL_STATE=NOT READY`.
