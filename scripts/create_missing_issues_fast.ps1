Set-Location c:/Aditya/cvantage-py
$ErrorActionPreference = 'Stop'
$owner = 'adityaparab'
$repo = 'CVantage-py'
$repoArg = "$owner/$repo"

$lines = Get-Content ./PLAN.md

$entries = @()
$currentPhase = $null
for ($i = 0; $i -lt $lines.Count; $i++) {
  $line = $lines[$i]

  if ($line -match '^### E(?<enum>\d+)\s+·\s+Phase\s+(?<phase>\d+)\s+—\s+(?<title>.+?)\s+`M(?<milestone>\d+)`') {
    $entries += [ordered]@{
      title = "[E$($Matches['enum'])] Phase $($Matches['phase']) - $($Matches['title'].Trim())"
      milestone = "M$($Matches['milestone'])"
      labels = @('type:epic', "phase:$($Matches['phase'])", 'priority:P0')
      body = "Parent epic for Phase $($Matches['phase']) from PLAN.md."
    }
    $currentPhase = [int]$Matches['phase']
    continue
  }

  if ($line -match '^\*\*(?<code>\d+\.\d+)\s+(?<title>.+?)\*\*(?<meta>.*)$') {
    $code = $Matches['code']
    $taskTitle = $Matches['title']
    $meta = $Matches['meta']
    $areas = @([regex]::Matches($meta, 'area:(server|client|infra|docs)') | ForEach-Object { "area:$($_.Groups[1].Value)" } | Select-Object -Unique)
    $prioMatch = [regex]::Match($meta, '\bP[0-2]\b')
    $prio = if ($prioMatch.Success) { "priority:$($prioMatch.Value)" } else { 'priority:P1' }

    $bodyLines = @()
    $j = $i + 1
    while ($j -lt $lines.Count -and $lines[$j] -notmatch '^### E\d+' -and $lines[$j] -notmatch '^\*\*\d+\.\d+') {
      $bodyLines += $lines[$j]
      $j++
    }

    $entries += [ordered]@{
      title = "[$code] $($taskTitle.Trim())"
      milestone = "M$currentPhase"
      labels = @('type:task', "phase:$currentPhase", $prio) + $areas
      body = (("Source: PLAN.md task $code`n`n") + (($bodyLines -join "`n").Trim()))
    }
  }
}

$existingTitles = @{}
$existing = gh issue list --repo $repoArg --state all --limit 300 --json title | ConvertFrom-Json
foreach ($it in $existing) { $existingTitles[$it.title] = $true }

$created = 0
$skipped = 0
foreach ($e in $entries) {
  if ($existingTitles.ContainsKey($e.title)) {
    $skipped++
    continue
  }

  $tmp = Join-Path $env:TEMP ("cvantage_issue_" + [guid]::NewGuid().ToString() + ".md")
  Set-Content -Path $tmp -Value $e.body -Encoding UTF8
  try {
    $args = @('issue','create','--repo',$repoArg,'--title',$e.title,'--body-file',$tmp,'--milestone',$e.milestone)
    foreach ($lbl in ($e.labels | Select-Object -Unique)) { $args += @('--label',$lbl) }
    $url = gh @args
    Write-Output "created $url"
    $created++
  }
  finally {
    if (Test-Path $tmp) { Remove-Item $tmp -Force }
  }
}

Write-Output "SUMMARY created=$created skipped=$skipped total_entries=$($entries.Count)"
