---
status: accepted
---

# Use Local Drafts only for Issue creation

The Issue Draft Uploader uses a Local Draft only to create unpublished Issue Content. Uploading does not publish it; all subsequent editing and publication occur on GitHub. After creation, the GitHub Issue is the sole authoritative representation, and the uploader does not bind the local file to that Issue or use it for later synchronization. This deliberately gives up ongoing local-first editing and bidirectional synchronization in exchange for a smaller authoring boundary and conflict-free editing through GitHub.
