# SaiTech Incident Response Policy

Synthetic company document · Owner: Security and Reliability · Version 1.0 · Effective 1 January 2026

## Reporting an incident

Report a suspected security incident immediately to security@saitech.example and notify the on-call engineer through the Service Desk. Include the time observed, affected systems, and a short description. Do not post credentials or customer data in the incident channel. Preserve logs and avoid changing the affected system unless the incident commander requests it.

## Severity levels

SEV1 means a company-wide outage, confirmed active data exposure, or loss of a critical production capability. SEV2 means a major feature is unavailable for multiple customers with no reasonable workaround. SEV3 means a limited issue with a working mitigation.

## Response targets

The on-call engineer acknowledges SEV1 incidents within 15 minutes and SEV2 incidents within 30 minutes. The incident commander sends SEV1 stakeholder updates every 30 minutes until mitigation. These are response targets, not guarantees of resolution time.

## Incident roles

The incident commander coordinates decisions. The technical lead directs diagnosis and mitigation. The communications lead maintains a shared incident timeline and stakeholder updates. Only the communications lead publishes external incident statements after approval.

## Post-incident review

Complete a blameless review within five working days of a SEV1 or SEV2 incident. Record impact, timeline, contributing factors, and corrective actions with owners and due dates. Track corrective actions to completion in the engineering backlog.
