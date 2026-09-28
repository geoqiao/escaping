---
status: accepted
---

# Use Local Drafts only for Issue creation

The Issue Draft Uploader uses a Local Draft only to create Issue Content. The new Issue is unpublished unless the user explicitly authorizes publishing that upload, in which case the `published` label is set when it is created; all subsequent editing, publishing and unpublishing occur on GitHub. After creation, the GitHub Issue is the sole authoritative representation, and the uploader does not bind the local file to that Issue or use it for later synchronization. This deliberately gives up ongoing local-first editing and bidirectional synchronization in exchange for a smaller authoring boundary and conflict-free editing through GitHub.
