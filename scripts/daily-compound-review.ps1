<#
.SYNOPSIS
    Runs the Daily Compound Review process.
.DESCRIPTION
    This script is designed to be run nightly (e.g., via Task Scheduler).
    It ensures the repo is up to date, then instructs the AI agent to review recent work
    and update AGENTS.md with new learnings.
#>

$ErrorActionPreference = "Stop"

# Navigate to project root
$ProjectRoot = "C:\Users\nicol\workspace\github.com\thenic95\drep-tracking-mvp"
Set-Location -Path $ProjectRoot

Write-Host "Starting Daily Compound Review..."

# Ensure we're on main and up to date
git checkout main
git pull origin main

# Define the Prompt
$Prompt = "Load the compound-engineering skill. Look through and read each Amp thread from the last 24 hours. For any thread where we did NOT use the Compound Engineering skill to compound our learnings at the end, do so now - extract the key learnings from that thread and update the relevant AGENTS.md files so we can learn from our work and mistakes. Commit your changes and push to main."

# Execute Agent (adjust 'claude' or 'amp' as needed)
# Using 'claude' as default placeholder based on plan
Write-Host "Executing AI Agent..."
claude -p "$Prompt" --dangerously-skip-permissions

Write-Host "Daily Compound Review Completed."
