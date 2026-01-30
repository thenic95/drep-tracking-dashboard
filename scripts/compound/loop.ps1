param (
    [int]$Iterations = 25
)

$ErrorActionPreference = "Stop"

Write-Host "Starting Execution Loop ($Iterations iterations)..."

for ($i = 1; $i -le $Iterations; $i++) {
    Write-Host "Iteration $i / $Iterations"
    
    # Check if tasks are done (heuristic: check if prd.json exists or has content indicating pending tasks)
    # For now, we delegate the 'check if done' logic to the agent prompt or exit code.
    
    $LoopPrompt = "Load the compound execution skill. Read scripts/compound/prd.json. Pick the next pending task and execute it. If all tasks are complete, output 'ALL_TASKS_COMPLETE' and exit. If stuck, mark the task as failed and move on."
    
    # Capture output to check for completion signal
    $Output = claude -p "$LoopPrompt" --dangerously-skip-permissions
    
    Write-Host $Output
    
    if ($Output -match "ALL_TASKS_COMPLETE") {
        Write-Host "All tasks completed successfully."
        break
    }
}
