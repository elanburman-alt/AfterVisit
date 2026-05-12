# email-voice-mgo

Voice anchoring for thank-you emails written by a major gift officer. References live in `references/`; each is a real email body with YAML frontmatter. Given a `meeting_type` and a `donor_segment`, the skill returns up to three matching references for an LLM to use as voice exemplars. Routing is metadata-driven — exact `meeting_type` match, exact `donor_segment` with adjacency fallback — per the rules in `SKILL.md`.

## Adding a new reference

Drop a new `.md` file into `references/`. The frontmatter must include `id`, `meeting_type`, `donor_segment`, `program`, `tone`, `tags`, and `notes`; the body is the email itself, signed by the MGO. Use any existing reference file as the template — frontmatter fields, paragraph rhythm, and sign-off conventions vary by tier.

## Using from Claude Code

Drop the entire `email-voice/` folder into your project's `skills/` directory. Claude Code reads `SKILL.md` and discovers the skill through its frontmatter `description`; references are loaded from `references/` automatically when the routing rules apply.

## Using from the Agent SDK

Load the `SKILL.md` description into the agent's instructions and provide `references/*.md` as files the agent can read on demand. The agent applies the metadata-routing rules from `SKILL.md` when it picks references. No runtime to install.
