# Sponsors — drop folder

Drop new sponsor images HERE (any reasonable size/format), then either:

- tell an agent: "new sponsor in the drop folder — Name, optional link", or
- run it yourself:
  `python sponsors/install.py <filename> "Sponsor Name" [https://link]`

The installer normalizes the image, moves it to `site/sponsors/`, updates
`site/data/sponsors.json`, and consumes the dropped file — this folder should
be empty between installs. Deploy = commit + push, same as everything else.

Other commands: `--list` (current set), `--remove "Name"` (deactivate).
