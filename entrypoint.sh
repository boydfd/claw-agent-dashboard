#!/bin/sh
# Fix /data ownership for bind-mounted volumes (host dir may be root-owned)
chown -R 1000:1000 /data 2>/dev/null || true

# Run the command as-is (supervisord stays root so /dev/stdout is accessible;
# child processes drop to appuser via the user= directive in supervisord.conf)
exec "$@"
