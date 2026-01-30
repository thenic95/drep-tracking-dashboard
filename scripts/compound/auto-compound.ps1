<#
.SYNOPSIS
    Runs the Auto-Compound Implementation process.
.DESCRIPTION
    Full pipeline: report -> PRD -> tasks -> implementation -> PR
#>

$ErrorActionPreference = "Stop"
$ProjectRoot = "C:\Users\nicol\workspace\github.com\thenic95\drep-tracking-mvp"
Set-Location -Path $ProjectRoot

# Source environment variables if needed (simplistic approach for ps1)
# if (Test-Path .env.local) { Get-Content .env.local | ForEach-Object { $k,$v = $_.Split('='); [Environment]::SetEnvironmentVariable($k, $v) } }

# Fetch latest
git fetch origin main
git reset --hard origin/main

# Find the latest prioritized report
$LatestReport = Get-ChildItem "reports\*.md" | Sort-Object LastWriteTime -Descending | Select-Object -First 1

if (-not $LatestReport) {
    Write-Error "No reports found in reports/ directory."
}

Write-Host "Latest Report: $($LatestReport.Name)"

# Analyze and pick #1 priority
# Note: This assumes analyze-report.sh equivalent is skipped or integrated. 
# For this MVP, we will ask the AI to Pick the priority item directly from the report content.

$ReportContent = Get-Content $LatestReport.FullName -Raw
$AnalysisPrompt = "Read the following report content and extract the #1 priority item to build. Return ONLY a JSON object with keys 'priority_item' and 'branch_name'. Report Content: $ReportContent"

Write-Host "Analyzing report for priority item..."
# We use a temporary file to capture output reliably or assume standard out
# Here we'll rely on the agent to output the JSON string.
$AnalysisJsonRaw = claude -p "$AnalysisPrompt" --dangerously-skip-permissions | Out-String

# Robust cleanup: Extract content between first { and last }
$StartIndex = $AnalysisJsonRaw.IndexOf('{')
$EndIndex = $AnalysisJsonRaw.LastIndexOf('}')

if ($StartIndex -ge 0 -and $EndIndex -gt $StartIndex) {
    $AnalysisJson = $AnalysisJsonRaw.Substring($StartIndex, $EndIndex - $StartIndex + 1)
} else {
    $AnalysisJson = $AnalysisJsonRaw
}


try {
    $AnalysisObj = $AnalysisJson | ConvertFrom-Json
    $PriorityItem = $AnalysisObj.priority_item
    $BranchName = $AnalysisObj.branch_name
} catch {
    Write-Error "Failed to parse analysis JSON. Output was: $AnalysisJson"
}

Write-Host "Priority Item: $PriorityItem"
Write-Host "Branch Name: $BranchName"

# Create feature branch
git checkout -b "$BranchName"

# Create PRD
$PrdFilename = "tasks\prd-$($BranchName | Split-Path -Leaf).md"
$PrdPrompt = "Load the prd skill. Create a PRD for: $PriorityItem. Save to $PrdFilename"
claude -p "$PrdPrompt" --dangerously-skip-permissions

# Convert to tasks
$PrdJsonPath = "$PSScriptRoot\prd.json"
if (Test-Path $PrdJsonPath) { Remove-Item $PrdJsonPath }

$TasksPrompt = "Load the tasks skill. Convert the PRD at $PrdFilename to scripts/compound/prd.json"
claude -p "$TasksPrompt" --dangerously-skip-permissions

# Run the execution loop
& "$PSScriptRoot\loop.ps1" -Iterations 25

# Create PR
git push -u origin "$BranchName"

if (Get-Command "gh" -ErrorAction SilentlyContinue) {
    gh pr create --draft --title "Compound: $PriorityItem" --base main
} else {
    Write-Warning "GitHub CLI ('gh') not found. Skipping automatic PR creation."
    Write-Host "Action Required: Please create a Pull Request manually for branch '$BranchName'."
}

