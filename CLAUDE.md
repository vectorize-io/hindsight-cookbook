# Hindsight Cookbook

## README Frontmatter

Every application under `applications/` must have a README.md with a YAML frontmatter block at the top. Use `applications/chat-memory/README.md` as the reference example.

### Required format

```markdown
---
description: "Short description of what the app does"
tags: { sdk: "<sdk-name>", topic: "<topic>" }
---
```

### Fields

- **description**: A concise one-line description of the application.
- **tags**: An object with at least:
  - `sdk`: the primary Hindsight SDK or client used (e.g. `"hindsight-client"`, `"hindsight-js"`)
  - `topic`: the main topic or use-case category (e.g. `"Chat"`, `"Memory"`, `"RAG"`)

### Example

```markdown
---
description: "Real-time chat app with per-user memory using Groq and Hindsight"
tags: { sdk: "hindsight-client", topic: "Chat" }
---
```
