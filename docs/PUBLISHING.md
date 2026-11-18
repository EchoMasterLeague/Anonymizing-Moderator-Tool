# Publishing to the dedicated GitHub repository

Target: `https://github.com/EchoMasterLeague/Anonymizing-Moderator-Tool`

This is a **separate public repository**, not `origin/dev` of the operational EML bot repository. Do not run the older `EML_Anonymous_Ticket_Reply_Publish_DEV.ps1` script for this target.

The accompanying root ZIP can be unpacked into a new, isolated clone of the dedicated GitHub repository. The provided guarded PowerShell publisher accepts an initially **empty** GitHub repository; it checks the remote URL and SHA-256 of the package, and uses an ordinary (non-force) push to `main`.

Before first publication, verify the target repository is intended to be public and that sharing this code is permitted under EML governance. The package intentionally excludes secrets, database files, private audit records and ticket transcripts.

Do not use this archive to overwrite the operating EML bot's source or configuration.
