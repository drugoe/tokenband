← [Back to Quick start](quickstart.md)

# Example: hypothetical search task

*This is an illustrative fictional walkthrough. It is not an observed app build, benchmark, UI screenshot or recorded experiment.*

A user asks their agent: 'Add search to the Notes app so users can find notes by title and body text.' Because this changes application behavior, the manager opens a persistent task chat and records the scope in the project's single `TODO.md`.

The configured executor implements search by note title only. The manager passes the draft to an independent reviewer with the same task materials.

The reviewer checks the acceptance cases:

- Search covers both note titles and body text.
- An empty query shows all notes.
- Matching is case-insensitive.
- No match shows an empty state.

The reviewer finds that body text is not searched and requires correction. The executor updates the implementation so both title and body are covered, and the acceptance cases pass. The manager accepts the task only after the reviewer confirms the final result.

If the user had instead asked a simple factual question, the manager would answer directly without opening a task chat. This example shows why author completion is not acceptance: an independent pass caught the missing scope before the work was marked done.

← [Back to Quick start](quickstart.md)