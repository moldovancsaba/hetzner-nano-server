# Daily recovery backups

Paperclip creates one full recovery point each day at 03:20 Europe/Budapest. Retention is seven days on both the server and owner Mac. The separate hourly native database backup is disabled; the Mac LaunchAgent has only its daily calendar trigger, with its existing guarded startup check.

Each full archive contains one newly completed native SQL snapshot, the consistent factory SQLite snapshot and the existing persistent files, deployment configuration and credentials. Rolling SQL history and live PostgreSQL files are excluded. This avoids copying the entire hourly history into every daily archive. The existing private archive format and restore paths remain compatible.

The Mac verifies the archive checksum, required components, gzip integrity and factory SQLite integrity before acknowledging it to the server. Only then can retention remove older recovery points and reduce legacy hourly SQL history to daily points. Expiry uses capture time, not the number of manual runs. A newer verified point replaces an earlier point from the same Budapest calendar day. The most recent verified point is always protected, including when a future backup fails. Missing verification or a changed latest checksum holds cleanup. Unknown filenames and symbolic links are not cleanup targets.

The native SQL directory is also reduced to daily points within seven days after a verified off-server acknowledgment. This does not touch the live database or its WAL. Daily backup frequency and retention are independent of business jobs, search budgets and notification schedules.

## Recovery and operations

Run backup.py through its existing daily LaunchAgent. A manual `--force` run is an explicit recovery verification and replaces an earlier same-day point only after verification. `--prune-only` applies the same local retention without creating a snapshot; scheduled-backup.py `prune` applies the server archive policy. Both require a current verified point. No hourly wake or new timer is installed.

archive_snapshot.py refuses absent, corrupt or incomplete fresh SQL, existing output paths and non-private output directories. An incomplete output remains private for inspection and is never marked verified. backup_retention.py implements the shared age and daily-point policy on both hosts. Existing verified snapshots stay available if transport, checksum, gzip, SQLite or acknowledgment fails.

The 6 November recovery temporarily reduced the root filesystem's reserved block count from 401138 to 100000 after disk exhaustion. The original count is restored after verified retention recovered sufficient headroom. That reservation is emergency space, not additional storage capacity. Application startup recovery and the original data volumes remain authoritative; no old database is restored over current writes.

The isolated restore uses a half CPU, an 1800 MiB container limit and a 1280 MiB application heap, with host-memory admission before startup. The SQL restore deadline scales with dump size and remains capped at fifteen minutes. The complete historical metrics response has a separate ninety-second rehearsal allowance; measured latency is reported and does not establish a production performance target. Other HTTP checks retain their existing limits. Agents, routines and automatic backups are disabled in the clone; its network has no external route. Production memory settings remain unchanged.

Current rollout, cleanup and isolated restoration evidence is in [maintenance verification](maintenance-verification-20261106.json). Earlier failed rehearsal diagnostics remain private; replacement-host DNS/TLS and real failover require separate verification.
