Set-Location c:/Aditya/cvantage-py
$ErrorActionPreference = 'Stop'
$owner = 'adityaparab'
$repo = 'CVantage-py'
$repoArg = "$owner/$repo"

$labels = @(
  @{name='type:epic'; color='5319e7'; desc='Epic issue'},
  @{name='type:task'; color='0e8a16'; desc='Task issue'},
  @{name='area:server'; color='1d76db'; desc='Backend/server work'},
  @{name='area:client'; color='fbca04'; desc='Frontend/client work'},
  @{name='area:infra'; color='d93f0b'; desc='Infrastructure/DevOps work'},
  @{name='area:docs'; color='0052cc'; desc='Documentation work'},
  @{name='priority:P0'; color='b60205'; desc='Blocking/critical priority'},
  @{name='priority:P1'; color='d93f0b'; desc='Required priority'},
  @{name='priority:P2'; color='fbca04'; desc='Polish priority'}
)
0..11 | ForEach-Object { $labels += @{name="phase:$_"; color='c2e0c6'; desc="Phase $_ work"} }
foreach ($l in $labels) { gh label create $l.name --repo $repoArg --color $l.color --description $l.desc --force | Out-Null }

$existingMilestones = gh api repos/$owner/$repo/milestones --paginate --jq '.[].title'
$existingSet = @{}
foreach ($m in $existingMilestones) { $existingSet[$m.Trim()] = $true }
0..11 | ForEach-Object {
  $title = "M$_"
  if (-not $existingSet.ContainsKey($title)) {
    gh api repos/$owner/$repo/milestones -f title="$title" -f state='open' | Out-Null
  }
}

$planPath = 'c:/Aditya/cvantage-py/PLAN.md'
$lines = Get-Content $planPath
$epics = @()
$tasks = @()
$currentEpic = $null
$currentTask = $null

function Get-IssueMaps {
  $issueList = gh issue list --repo $repoArg --state all --limit 200 --json number,title | ConvertFrom-Json
  $titleToNumber = @{}
  foreach ($i in $issueList) {
    $titleToNumber[$i.title] = [int]$i.number
  }

  $numberToRestId = @{}
  foreach ($kvp in $titleToNumber.GetEnumerator()) {
    $num = [int]$kvp.Value
    $restId = gh api repos/$owner/$repo/issues/$num --jq .id
    $numberToRestId[$num] = [int64]$restId
  }

  return @{
    TitleToNumber = $titleToNumber
    NumberToRestId = $numberToRestId
  }
}

function Ensure-Issue {
  param(
    [string]$Title,
    [string]$Body,
    [string]$Milestone,
    [string[]]$Labels,
    [hashtable]$TitleToNumber,
    [hashtable]$NumberToRestId
  )

  if ($TitleToNumber.ContainsKey($Title)) {
    return [int]$TitleToNumber[$Title]
  }

  $tmpBodyFile = Join-Path $env:TEMP ("cvantage_issue_" + [guid]::NewGuid().ToString() + ".md")
  Set-Content -Path $tmpBodyFile -Value $Body -Encoding UTF8

  $args = @('issue','create','--repo',$repoArg,'--title',$Title,'--body-file',$tmpBodyFile,'--milestone',$Milestone)
  foreach ($lbl in ($Labels | Select-Object -Unique)) { $args += @('--label',$lbl) }

  $url = $null
  try {
    $url = gh @args
  }
  finally {
    if (Test-Path $tmpBodyFile) { Remove-Item $tmpBodyFile -Force }
  }
  $numMatch = [regex]::Match($url, '/issues/(\d+)$')
  if (-not $numMatch.Success) {
    throw "Unable to parse issue number from gh output: $url"
  }

  $num = [int]$numMatch.Groups[1].Value
  $TitleToNumber[$Title] = $num
  $restId = gh api repos/$owner/$repo/issues/$num --jq .id
  $NumberToRestId[$num] = [int64]$restId
  return $num
}

for ($i = 0; $i -lt $lines.Count; $i++) {
  $line = $lines[$i]

  if ($line -match '^### E(?<enum>\d+)\s+·\s+Phase\s+(?<phase>\d+)\s+—\s+(?<title>.+?)\s+`M(?<milestone>\d+)`') {
    if ($currentTask -ne $null) { $tasks += $currentTask; $currentTask = $null }
    $currentEpic = [ordered]@{
      epicCode = "E$($Matches['enum'])"
      phase = [int]$Matches['phase']
      milestone = "M$($Matches['milestone'])"
      title = $Matches['title'].Trim()
      taskCodes = @()
    }
    $epics += $currentEpic
    continue
  }

  if ($line -match '^\*\*(?<code>\d+\.\d+)\s+(?<title>.+?)\*\*(?<meta>.*)$') {
    if ($currentTask -ne $null) { $tasks += $currentTask }
    $meta = $Matches['meta']
    $areas = @([regex]::Matches($meta, 'area:(server|client|infra|docs)') | ForEach-Object { "area:$($_.Groups[1].Value)" } | Select-Object -Unique)
    $prioMatch = [regex]::Match($meta, '\bP[0-2]\b')
    $prio = if ($prioMatch.Success) { "priority:$($prioMatch.Value)" } else { 'priority:P1' }

    $currentTask = [ordered]@{
      code = $Matches['code']
      title = $Matches['title'].Trim()
      phase = if ($currentEpic -ne $null) { $currentEpic.phase } else { [int]([double]$Matches['code']) }
      epicCode = if ($currentEpic -ne $null) { $currentEpic.epicCode } else { "E$([int]([double]$Matches['code']))" }
      labels = @('type:task', "phase:$($currentEpic.phase)", $prio) + $areas
      bodyLines = @()
    }
    if ($currentEpic -ne $null) { $currentEpic.taskCodes += $Matches['code'] }
    continue
  }

  if ($currentTask -ne $null) {
    if ($line -match '^### E\d+' -or $line -match '^\*\*\d+\.\d+') {
      $tasks += $currentTask
      $currentTask = $null
    }
    else {
      $currentTask.bodyLines += $line
    }
  }
}
if ($currentTask -ne $null) { $tasks += $currentTask }

$maps = Get-IssueMaps
$titleToNumber = $maps.TitleToNumber
$numberToRestId = $maps.NumberToRestId

$epicIssueNumbers = @{}
foreach ($e in $epics) {
  $epicTitle = "[$($e.epicCode)] Phase $($e.phase) - $($e.title)"
  $taskList = ($e.taskCodes | ForEach-Object { "- $_" }) -join "`n"
  $body = @"
Parent epic for Phase $($e.phase) in PLAN.md.

Milestone: $($e.milestone)

Sub-issues to be linked:
$taskList

Definition of Done:
- Code + tests green
- Lint/typecheck clean
- Docs/OpenAPI updated where applicable
- PR merged with Closes references
"@

  $num = Ensure-Issue -Title $epicTitle -Body $body -Milestone $e.milestone -Labels @('type:epic', "phase:$($e.phase)", 'priority:P0') -TitleToNumber $titleToNumber -NumberToRestId $numberToRestId
  $epicIssueNumbers[$e.epicCode] = [int]$num
}

$taskIssueIds = @{}
$taskIssueNumbers = @{}
foreach ($t in $tasks) {
  $taskTitle = "[$($t.code)] $($t.title)"

  $bodyText = ($t.bodyLines -join "`n").Trim()
  if ([string]::IsNullOrWhiteSpace($bodyText)) { $bodyText = "Implement scope for task $($t.code) from PLAN.md." }

  $body = @"
Source: PLAN.md task $($t.code)
Phase: $($t.phase)
Epic: $($t.epicCode)

$bodyText

Completion checklist:
- [ ] Implementation complete
- [ ] Tests added/updated and passing
- [ ] Lint/typecheck passing
- [ ] Docs/OpenAPI updated if needed
"@

  $num = Ensure-Issue -Title $taskTitle -Body $body -Milestone "M$($t.phase)" -Labels $t.labels -TitleToNumber $titleToNumber -NumberToRestId $numberToRestId
  $taskIssueNumbers[$t.code] = [int]$num
  $taskIssueIds[$t.code] = [int64]$numberToRestId[$num]
}

foreach ($t in $tasks) {
  $parentNum = $epicIssueNumbers[$t.epicCode]
  $subId = $taskIssueIds[$t.code]
  if ($parentNum -and $subId) {
    try {
      gh api repos/$owner/$repo/issues/$parentNum/sub_issues -f sub_issue_id=$subId | Out-Null
    }
    catch {
    }
  }
}

Write-Output "CREATED_OR_FOUND epics=$($epics.Count) tasks=$($tasks.Count) total=$($epics.Count + $tasks.Count)"
