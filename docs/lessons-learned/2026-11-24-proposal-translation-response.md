# 2026-11-24 — Translation response contracts

## Context

The proposal comparison needed Korean editing suggestions while preserving the original imported descriptions and existing approvals. The shared model gateway returns an assistant message object with a text `content` field.

## Incident

The first translation handler parsed that message object directly as JSON. Its test substitute returned a string, so local tests failed to exercise the actual gateway interface. One provider call completed and its response was retained, but the translation operation failed during local processing. No translation was applied or approved.

## Correction

Parse the message's text content and test with the actual assistant-message structure. Accept a single complete JSON code fence as a documented presentation wrapper; preserve its original bytes and reject unrelated commentary rather than extracting arbitrary fragments. Preserve the failed operation and its paid call. A separately recorded offline processing operation can validate the saved response against the exact original messages, source revision and requested IDs without another provider call. The recovery must retain original request and response hashes and identify the original failed operation and provider call. It must not overwrite the failure or invent another successful provider attempt.

## Verification boundary

Korean text, expected IDs and response structure do not establish correct business meaning. The source description remains visible, translation is a review suggestion, and existing approvals remain unchanged. Missing descriptions stay missing.
