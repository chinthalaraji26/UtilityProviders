---
name: mermaid-to-png
description: Render Mermaid diagram source (flowchart, sequence, class, ER, state, gantt, etc.) into a PNG image file on disk. Use whenever the user gives Mermaid code and asks to render it, export it as an image, save it as a PNG, or turn a diagram into a picture file — as opposed to just showing a diagram inline in a Claude Code reply or an Artifact.
---

Render the given Mermaid diagram to a PNG file using the bundled script at
`render.py` in this skill's directory.

## Steps

1. Get the Mermaid source.
   - If the user pasted Mermaid code directly, use it as-is.
   - If they named a file (`.mmd`, `.mermaid`, or a fenced ```mermaid block
     in a markdown file), read it.
   - Do not invent or "clean up" the diagram — render exactly what was given
     unless the user asks you to change it.

2. Pick an output path.
   - If the user gave one, use it (create parent directories if needed).
   - Otherwise write to the project's scratchpad/temp directory with a
     descriptive name, e.g. `diagram.png`, and tell the user where it landed.
   - Always give the file a `.png` extension.

3. Run the renderer:

   ```
   python "<skill_dir>/render.py" --file "<mermaid_source_file>" --out "<output.png>"
   ```

   or, for short inline diagrams, pass the code directly instead of a file
   (be careful with shell quoting — prefer writing it to a temp `.mmd` file
   first if the diagram contains quotes, backticks, or is more than a couple
   of lines):

   ```
   python "<skill_dir>/render.py" --code "graph TD; A-->B;" --out "<output.png>"
   ```

   Useful optional flags (all pass straight through to mermaid.ink):
   - `--theme default|dark|forest|neutral`
   - `--bg white|transparent|"#1e1e1e"` — background color
   - `--width 1200` — output width in px
   - `--scale 2` — render at 2x resolution for crisper output
   - `--local` — skip the network call and render via a local
     `npx @mermaid-js/mermaid-cli` instead (needs Node/npx; first run
     downloads a headless Chromium, so it's slower). The script also falls
     back to this automatically if the mermaid.ink request fails (e.g. no
     network, or the diagram is too large for a URL).

4. Verify the script reported success and the output file exists and is
   non-trivial in size. If it failed with a mermaid.ink error, the most
   common cause is a Mermaid syntax error — read the message, fix the
   diagram source, and retry rather than immediately falling back to
   `--local`.

5. Tell the user the output path. If they're likely to want to view it
   inline rather than just get a file path, use the Read tool on the PNG
   to display it in the conversation.

## Notes

- `render.py` has no third-party dependencies — it only needs Python 3 and,
  for the default (non-`--local`) path, outbound network access to
  `mermaid.ink`.
- mermaid.ink encodes the whole diagram into the URL, so extremely large
  diagrams can exceed URL length limits and fail; use `--local` for those.
