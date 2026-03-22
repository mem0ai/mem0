# Security Exceptions

This document records intentional exceptions to security scan findings that have been reviewed and approved.

## How to Add Exceptions

When the security scanner flags something that is a false positive or intentional:

1. Document it in this file with:
   - Finding description
   - File and line number
   - Reason for exception
   - Date and reviewer

2. The security-check.sh script will NOT automatically skip these - they serve as documentation for manual review.

## Approved Exceptions

### None Currently

No security exceptions have been approved yet.

---

## Template for New Exceptions

```markdown
### [EXCEPTION-001] Description

- **Finding**: What the scanner detected
- **Location**: `path/to/file.py:line_number`
- **Pattern**: The pattern that triggered the alert
- **Reason**: Why this is safe/intentional
- **Mitigations**: Any safeguards in place
- **Approved By**: Name
- **Date**: YYYY-MM-DD
- **Review Date**: When to re-review (max 6 months)
```

## Revoked Exceptions

Exceptions that were previously approved but have been revoked:

### None Currently

---

*Last updated: Initial document creation*
