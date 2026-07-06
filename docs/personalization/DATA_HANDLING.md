# Personalization Data Handling

## Current Storage

Personalization data is stored locally as JSON under
`geode/web/data/personalization/users/`.

## Encryption Posture

Current local development storage is not encrypted at the application layer. Production use
must place this store behind encrypted disk storage or replace it with an encrypted managed
profile store before external reliance.

## Access Control Model

Only the application process should read or write personalization files. Administrative access
must be limited to maintainers who are authorized to operate Geode.

## Retention Policy

Behavior events are capped at the latest 250 events per profile. Private explicit answers
should be deleted when the user clears personalization data.

## Boundary

This document defines the posture. It does not claim that production-grade encryption,
identity management, or retention enforcement has been externally audited.
