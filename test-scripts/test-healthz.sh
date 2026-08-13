#!/bin/bash
# GET /healthz → 200 {status, driver, disk_free_bytes, degraded}
source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"
echo "── healthz ──"
R="$(req GET /healthz)"
assert_status 200 "$R" "healthz 200"
if body_of "$R" | grep -q '"status":"ok"'; then echo "  ✅ status ok"; else echo "  ❌ missing status ok"; FAILED=1; fi
if body_of "$R" | grep -q '"disk_free_bytes"'; then echo "  ✅ disk_free_bytes present"; else echo "  ❌ no disk_free_bytes"; FAILED=1; fi
finish
