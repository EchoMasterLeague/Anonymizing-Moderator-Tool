# Verification, traceability and release boundary

**Snapshot date:** 2026-11-17

## Source and test identity

| Evidence | Reported / observed result |
|---|---|
| RC1.2b application source commit | `dfdcccb` |
| Separate harness repair commit (accepted) | `588da4977bf6688251cabea43861722106cf1d16` |
| DEV branch synchronization | `origin/dev` and local HEAD matched at `588da4977bf6688251cabea43861722106cf1d16` in the verified preflight |
| RC1.2b DEV candidate Docker tag | `eml-discord-bot:dev-anon-ticket-rc1-2b` |
| RC1.2b DEV candidate image ID | `sha256:98746e583f08ee4b7853ba01f2ff8e0aaf205212723e15116b9e6ebdc0dd7545` |
| Dedicated feature regression | **61/61 PASS** |
| Separate baseline / candidate disciplinary regression | **673/673 PASS** in each image |
| Corrected isolated general regression | **837/837 PASS**, no errors or failures |

The general-suite count increased after fixing test discovery. **837 is the accepted collected count**, not 13 newly added behavioral requirements. The 837-test run mounted three accepted test-only corrections into an isolated RC1.2b candidate container. Do not imply the candidate image itself had been rebuilt with the harness repairs.

## PROD operational verification (Nov 17, 2026)

Operator-provided Discord screenshots demonstrated:

1. The one-time setup command created the private persistent **EML Ticket Reply Center** dashboard.
2. After Ticket Tool Support Team Roles were configured to include the `League Bot` role, a newly generated League Support ticket appeared automatically, alongside an earlier eligible ticket.
3. The operator submitted a sample reply through the button/modal.
4. The actual League Support ticket displayed a bot-authored message headed **EML Support** with no moderator name in its reply text.
5. The private audit channel displayed moderator attribution and the response body, ticket reference, and status **DELIVERED**, with a link to the delivered message.
6. The confirmation in the reply center identified successful delivery and private audit recording.

**Evidence classification:** direct operator screenshots of PROD workflow; not independent read-only verification of every Discord participant's effective permissions. The record demonstrated delivery and audit for one controlled sample; it did not exhaustively test unauthorized-member visibility.

## Source snapshot qualification

The accompanying ZIP contains the two uploaded RC1.2b implementation modules and seven uploaded feature-test modules. The audit-layout test source has been updated in the snapshot to reflect the **separately accepted package-import correction** from the harness-repair commit. The full host Git object identities of each source file have **not** been independently compared by this packaging environment; verify repository blobs before claiming the archive is a bit-identical export of commit `588da49`.

The existing code header refers to a "DEV-only" adapter. That wording is historical; the November 17 operational screenshots demonstrate PROD use. This documentation does not silently edit the accepted implementation.

## Governing release boundary

Documenting or publishing this snapshot **does not authorize modifying production source, restarting a bot, changing SQL authority, or promoting an unapproved build**. Preserve the governing Owner/Supervisor release procedures and report results separately.
