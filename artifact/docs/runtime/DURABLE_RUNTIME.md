# Durable runtime

The Worker and Reviewer use durable DBOS workflows backed by SQLite. Workflow steps, review requests, provider attempts, workspace changes, and recovery metadata are recorded outside the model context. A process can resume from its durable state after an interruption.

The implementation includes:

- a direct DeepSeek provider adapter with request-boundary metadata, response parsing, retry classification, and bounded backoff;
- separate Worker and Reviewer workflow contexts;
- snapshot creation and read-only submission mounts;
- Docker execution with a read-only brief and writable project or review directory;
- tool validation, `finish_project`, and `finish_review` handling;
- durable store and hash/manifest helpers.

Durable recovery does not establish exactly-once remote provider execution when a request ends without a response. A crash after a Python side effect and before its result is recorded also leaves an exactly-once uncertainty. The frozen run evidence retains these boundaries.

Only the direct DeepSeek provider used by the frozen runs is included. No local-model or alternate provider implementation is claimed.
