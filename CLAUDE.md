# CLAUDE.md

This file contains important information for Claude when working with this codebase.

## Writing code

- CRITICAL: Never commit code yourself. Only Dev commits code.
- We prefer simple, clean, maintainable solutions over clever or complex ones, even if the latter are more concise or performant. Readability and maintainability are primary concerns.
- Make the smallest reasonable changes to get to the desired outcome. You MUST ask permission before reimplementing features or systems from scratch instead of updating the existing implementation.
- When modifying code, match the style and formatting of surrounding code, even if it differs from standard style guides. Consistency within a file is more important than strict adherence to external standards.
- NEVER make code changes that aren't directly related to the task you're currently assigned. If you notice something that should be fixed but is unrelated to your current task, bring it up as a separate suggestion at the end of your response instead of fixing it immediately.
- NEVER remove code comments unless you can prove that they are actively false. Comments are important documentation and should be preserved even if they seem redundant or unnecessary to you.
- When writing comments, avoid referring to temporal context about refactors or recent changes. Comments should be evergreen and describe the code as it is, not how it evolved or was recently changed.
- NEVER implement a mock mode for testing or for any purpose. We always use real data and real APIs, never mock implementations.
- When you are trying to fix a bug or compilation error or any other issue, YOU MUST NEVER throw away the old implementation and rewrite without explicit permission from the user. If you are going to do this, YOU MUST STOP and get explicit permission from the user.
- NEVER name things as 'improved' or 'new' or 'enhanced', etc. Code naming should be evergreen. What is new today will be "old" someday.
- Always add imports to the top of the file unless you have a good reason not to.
- If a CHANGELOG.md exists, update CHANGELOG.md as your final step.

## Getting help

- ALWAYS ask for clarification rather than making assumptions.
- If you're having trouble with something, it's ok to stop and ask for help. Especially if it's something your human might be better at.

## Project Overview

Synthform is a personal streaming overlay frontend built with React, Vite, and TailwindCSS. It is a single-tenant app (always `avalonstar`) designed for a local Tailscale network. It provides real-time, animated overlays for OBS streaming, including timer displays, Pokémon game trackers, and customizable visual elements. It consumes real-time data over WebSocket from Synthfunc and historical data over HTTP from Questlog.
