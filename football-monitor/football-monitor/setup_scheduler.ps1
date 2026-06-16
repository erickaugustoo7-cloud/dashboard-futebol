# Football Monitor - Configurador de Agendamento Automatico
# Execute UMA VEZ no PowerShell como Administrador:
#   Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
#   .\setup_scheduler.ps1

$ErrorActionPreference = "Stop"

$ProjectDir = Split-Path -Parent $PSScriptRoot
$PythonExe  = (Get-Command python -ErrorAction SilentlyContinue).Source

if (-not $PythonExe) {
    Write-Error "Python nao encontrado no PATH."
    exit 1
}

$OrchestratorScript = Join-Path $ProjectDir "scripts\orchestrator.py"
$LogsDir = Join-Path $ProjectDir "logs"

if (-not (Test-Path $LogsDir)) {
    New-Item -ItemType Directory -Path $LogsDir | Out-Null
}

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  FOOTBALL MONITOR - CONFIGURADOR DE TAREFAS AGENDADAS" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Python : $PythonExe" -ForegroundColor Yellow
Write-Host "  Projeto: $ProjectDir" -ForegroundColor Yellow
Write-Host "  Script : $OrchestratorScript" -ForegroundColor Yellow
Write-Host ""

# TAREFA 1: PIPELINE MATINAL (08:00 todos os dias)
# Sync ESPN -> Recalcula ELO -> Resolve pendentes -> Gera predicoes
$Task1Name = "FootballMonitor_MorningPipeline"
$Task1Args = "`"$OrchestratorScript`" --mode morning --days 3 --no-ai"

$Task1Action = New-ScheduledTaskAction `
    -Execute $PythonExe `
    -Argument $Task1Args `
    -WorkingDirectory $ProjectDir

$Task1Trigger = New-ScheduledTaskTrigger -Daily -At "08:00"

$Task1Settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -RunOnlyIfNetworkAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 30) `
    -MultipleInstances IgnoreNew

Unregister-ScheduledTask -TaskName $Task1Name -Confirm:$false -ErrorAction SilentlyContinue

Register-ScheduledTask `
    -TaskName    $Task1Name `
    -Action      $Task1Action `
    -Trigger     $Task1Trigger `
    -Settings    $Task1Settings `
    -RunLevel    Highest `
    -Description "Football Monitor: Pipeline completo. Roda as 08:00 diariamente." | Out-Null

Write-Host "  [OK] Tarefa 1 criada: $Task1Name (08:00 diario)" -ForegroundColor Green

# TAREFA 2: RESOLUCAO NOTURNA (02:00)
# Garante que jogos que terminaram a noite sejam resolvidos
$Task2Name = "FootballMonitor_NightResolve"
$Task2Args = "`"$OrchestratorScript`" --mode resolve"

$Task2Action = New-ScheduledTaskAction `
    -Execute $PythonExe `
    -Argument $Task2Args `
    -WorkingDirectory $ProjectDir

$Task2Trigger = New-ScheduledTaskTrigger -Daily -At "02:00"

$Task2Settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -RunOnlyIfNetworkAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 10) `
    -MultipleInstances IgnoreNew

Unregister-ScheduledTask -TaskName $Task2Name -Confirm:$false -ErrorAction SilentlyContinue

Register-ScheduledTask `
    -TaskName    $Task2Name `
    -Action      $Task2Action `
    -Trigger     $Task2Trigger `
    -Settings    $Task2Settings `
    -RunLevel    Highest `
    -Description "Football Monitor: Resolucao noturna de predicoes pendentes. Roda as 02:00 diariamente." | Out-Null

Write-Host "  [OK] Tarefa 2 criada: $Task2Name (02:00 diario)" -ForegroundColor Green

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  TAREFAS REGISTRADAS COM SUCESSO!" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Para testar manualmente agora:" -ForegroundColor White
Write-Host "  Start-ScheduledTask -TaskName '$Task1Name'" -ForegroundColor Yellow
Write-Host "  Start-ScheduledTask -TaskName '$Task2Name'" -ForegroundColor Yellow
Write-Host ""
Write-Host "  Para ver as tarefas: Win+R -> taskschd.msc" -ForegroundColor Gray
Write-Host ""

Get-ScheduledTask | Where-Object { $_.TaskName -like "FootballMonitor_*" } | Format-Table TaskName, State -AutoSize
