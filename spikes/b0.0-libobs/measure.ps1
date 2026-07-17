# Mesure le coût CPU moyen + mémoire d'un ou plusieurs processus sur une fenêtre donnée.
# Même méthode pour Hikari et pour OBS nu → le SURCOÛT est comparable (épreuve c, ADR-014).
# CPU % = secondes-CPU consommées / secondes-horloge / cœurs logiques × 100.
param(
  [string[]]$Names,
  [int]$DurationSec = 120,
  [int]$WarmupSec = 8,
  [string]$Label = "run",
  [string]$OutFile = "mesures/epreuve-c-surcout.md"
)

$cores = (Get-CimInstance Win32_ComputerSystem).NumberOfLogicalProcessors

function CpuSeconds($names) {
  $s = 0.0
  foreach ($n in $names) {
    foreach ($p in (Get-Process $n -ErrorAction SilentlyContinue)) { $s += $p.TotalProcessorTime.TotalSeconds }
  }
  return $s
}
function WorkingSetMB($names) {
  $s = 0.0
  foreach ($n in $names) {
    foreach ($p in (Get-Process $n -ErrorAction SilentlyContinue)) { $s += $p.WorkingSet64 }
  }
  return [math]::Round($s / 1MB, 1)
}

Write-Host "[$Label] échauffement ${WarmupSec}s..."
Start-Sleep -Seconds $WarmupSec

function GpuSample() {
  # utilisation GPU globale + utilisation de l'encodeur NVENC (le vrai coût de l'encodage).
  $o = & nvidia-smi --query-gpu=utilization.gpu,utilization.encoder --format=csv,noheader,nounits 2>$null
  if ($o) { return ($o -split ',' | ForEach-Object { [double]($_.Trim()) }) } else { return @($null, $null) }
}

$c0 = CpuSeconds $Names
$t0 = Get-Date
$ws = @()
$gpu = @()
$enc = @()
$end = (Get-Date).AddSeconds($DurationSec)
while ((Get-Date) -lt $end) {
  $ws += (WorkingSetMB $Names)
  $g = GpuSample
  if ($null -ne $g[0]) { $gpu += $g[0]; $enc += $g[1] }
  Start-Sleep -Seconds 5
}
$c1 = CpuSeconds $Names
$wall = ((Get-Date) - $t0).TotalSeconds

$cpuPct = [math]::Round(($c1 - $c0) / $wall / $cores * 100, 1)
$wsAvg = [math]::Round(($ws | Measure-Object -Average).Average, 1)
$wsMax = ($ws | Measure-Object -Maximum).Maximum
$gpuAvg = if ($gpu.Count) { [math]::Round(($gpu | Measure-Object -Average).Average, 1) } else { "n/a" }
$encAvg = if ($enc.Count) { [math]::Round(($enc | Measure-Object -Average).Average, 1) } else { "n/a" }

$line = "$Label : CPU ${cpuPct}% (moy, $cores coeurs) - GPU ${gpuAvg}% - encodeur ${encAvg}% - RAM ${wsAvg} Mo moy / ${wsMax} Mo max - fenetre $([math]::Round($wall))s - $(Get-Date -Format 'yyyy-MM-dd HH:mm')"
Write-Host $line
Add-Content -Path $OutFile -Value $line
