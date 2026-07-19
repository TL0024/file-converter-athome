# Security policy

## Supported version

Security fixes are applied to the latest published release and the `main` branch.

## Reporting a vulnerability

Use the repository's **Security** tab to submit a private vulnerability report. Do not include sensitive exploit details in a public issue. Include the affected version, reproduction steps, expected impact, and any suggested mitigation.

## Local security model

- The service binds only to `127.0.0.1`; it is not exposed to the local network.
- Conversion files remain in operating-system temporary storage and are deleted after two hours, when a batch is cleared, or when the app exits.
- User filenames are sanitized and never used as working paths.
- Browser lifecycle endpoints use unguessable, page-scoped tokens.
- External converters are invoked with argument arrays and without a command shell.
- The bundled FFmpeg binary comes from the declared `imageio-ffmpeg` package.
- CI audits Python dependencies, pull-request dependency changes, source with CodeQL and Bandit, JavaScript with ESLint, and workflow definitions with zizmor.

Local conversion is not a sandbox for hostile documents or media. Keep the application and its dependencies updated, and do not process untrusted files on a privileged account.

The Windows executable is currently unsigned. Verify the SHA-256 digest published with each release when authenticity matters.
