param(
  [switch]$Pi,
  [string]$PiHost = "192.168.88.115",
  [string]$PiPath = "/home/pi/secaudit",
  [string]$ApiKey = $env:SECAUDIT_API_KEY,
  [string]$ProjectId = ""
)

$ErrorActionPreference = "Stop"

function Step($Message) {
  Write-Host ""
  Write-Host "== $Message ==" -ForegroundColor Cyan
}

function Fail($Message) {
  Write-Host "FAIL: $Message" -ForegroundColor Red
  exit 1
}

function RequireFile($Path, $Label) {
  if (-not (Test-Path $Path)) {
    Fail "$Label not found: $Path"
  }
}

Step "Local syntax checks"
node --check static\js\main.js
node --check static\js\ui.js
node --check static\js\projects.js
$pyFiles = @(
  "main.py",
  "db.py",
  "models.py",
  "llm_service.py",
  "routers\projects.py",
  "routers\audit.py",
  "routers\findings.py"
)
foreach ($file in $pyFiles) {
  python -c "import ast,pathlib,sys; ast.parse(pathlib.Path(sys.argv[1]).read_text(encoding='utf-8'), filename=sys.argv[1])" $file
}

Step "Version consistency"
$main = Get-Content main.py -Raw
$index = Get-Content static\index.html -Raw
$readme = Get-Content README.md -Raw

if ($main -notmatch 'APP_VERSION = "([^"]+)"') {
  Fail "APP_VERSION not found in main.py"
}
$version = $Matches[1]
Write-Host "Local version: $version"

if ($index -notmatch [regex]::Escape("v=$version")) {
  Fail "static/index.html asset query string does not match $version"
}

if ($index -notmatch [regex]::Escape("v$version")) {
  Fail "static/index.html visible version does not match $version"
}

if ($readme -notmatch [regex]::Escape($version)) {
  Fail "README.md does not mention $version"
}

Step "Frontend critical hooks"
$mainJs = Get-Content static\js\main.js -Raw
$projectsJs = Get-Content static\js\projects.js -Raw
$frontendJs = "$mainJs`n$projectsJs"
foreach ($needle in @(
  "window.navigate = navigate",
  "window.startAudit = startAudit",
  "window.generateReport = generateReport",
  "syncFrameworksFromDom()",
  "formatJobElapsed",
  "formatJobTime",
  "renderQuestionGenerationWarning",
  "question-generation-warning",
  "createProjectsModule",
  "pollQuestionGeneration",
  "pollReportGeneration"
)) {
  if ($frontendJs -notmatch [regex]::Escape($needle)) {
    Fail "Missing frontend hook: $needle"
  }
}

Step "LLM adapter critical hooks"
$llmService = Get-Content llm_service.py -Raw
foreach ($needle in @(
  "_force_direct_answer_messages",
  "_extract_message_content",
  "/no_think",
  "reasoning_content"
)) {
  if ($llmService -notmatch [regex]::Escape($needle)) {
    Fail "Missing LLM adapter hook: $needle"
  }
}

Step "Static browser wiring checks"
$moduleScripts = [regex]::Matches($index, '<script[^>]+type="module"[^>]+src="([^"]+)"')
if ($moduleScripts.Count -lt 1) {
  Fail "No module script found in static/index.html"
}

foreach ($match in $moduleScripts) {
  $src = $match.Groups[1].Value.Split("?")[0]
  $scriptPath = Join-Path "static" ($src -replace "/", "\")
  RequireFile $scriptPath "Module script"
}

$importMatches = [regex]::Matches($mainJs, 'from\s+[''"]([^''"]+)[''"]')
foreach ($match in $importMatches) {
  $importPath = $match.Groups[1].Value.Split("?")[0]
  if ($importPath.StartsWith("./")) {
    $localPath = Join-Path "static\js" $importPath.Substring(2)
    RequireFile $localPath "Imported module"
  }
}

$onclickHandlers = [regex]::Matches($index, 'onclick="([A-Za-z_][A-Za-z0-9_]*)\(')
$windowExports = @{}
foreach ($match in [regex]::Matches($mainJs, 'window\.([A-Za-z_][A-Za-z0-9_]*)\s*=')) {
  $windowExports[$match.Groups[1].Value] = $true
}
foreach ($match in $onclickHandlers) {
  $handler = $match.Groups[1].Value
  if (-not $windowExports.ContainsKey($handler)) {
    Fail "HTML onclick handler is not exported on window: $handler"
  }
}

foreach ($needle in @(
  'class="sidebar-close-btn"',
  'id="sidebar-backdrop"',
  'onclick="closeSidebar()"',
  'window.closeSidebar = closeSidebar',
  'window.toggleSidebar = toggleSidebar'
)) {
  $source = if ($needle.StartsWith("window.")) { $mainJs } else { $index }
  if ($source -notmatch [regex]::Escape($needle)) {
    Fail "Missing browser wiring: $needle"
  }
}

if ($Pi) {
  Step "Pi deployment checks"
  $remoteVersion = ssh pi@$PiHost "curl -fsS http://127.0.0.1:18000/api/version"
  Write-Host $remoteVersion
  if ($remoteVersion -notmatch [regex]::Escape($version)) {
    Fail "Pi /api/version does not match local version $version"
  }

  ssh pi@$PiHost "docker ps --filter name=secaudit --format 'table {{.Names}}\t{{.Ports}}\t{{.Status}}'"
  ssh pi@$PiHost "cd $PiPath && grep -n 'APP_VERSION' main.py"
  ssh pi@$PiHost "cd $PiPath && grep -n '$version' static/index.html README.md"

  if ($ApiKey) {
    Step "Pi API smoke checks"
    $projectsJson = ssh pi@$PiHost "curl -fsS -H 'X-API-Key: $ApiKey' http://127.0.0.1:18000/api/projects"
    $projects = $projectsJson | ConvertFrom-Json
    Write-Host "Projects: $($projects.Count)"

    if ($ProjectId) {
      $projectJson = ssh pi@$PiHost "curl -fsS -H 'X-API-Key: $ApiKey' http://127.0.0.1:18000/api/projects/$ProjectId"
      $project = $projectJson | ConvertFrom-Json
      $frameworkCount = @($project.frameworks).Count
      Write-Host "Project: $($project.name)"
      Write-Host "Frameworks: $frameworkCount"
      Write-Host "Question target: $($project.question_count)"
      if ($frameworkCount -lt 1) {
        Fail "Project $ProjectId has no selected frameworks"
      }

      $questionsJson = ssh pi@$PiHost "curl -fsS -H 'X-API-Key: $ApiKey' http://127.0.0.1:18000/api/projects/$ProjectId/questions"
      $questions = $questionsJson | ConvertFrom-Json
      Write-Host "Questions: $(@($questions).Count)"

      $jobsJson = ssh pi@$PiHost "curl -fsS -H 'X-API-Key: $ApiKey' http://127.0.0.1:18000/api/projects/$ProjectId/jobs"
      $jobs = $jobsJson | ConvertFrom-Json
      if ($jobs.questions) {
        Write-Host "Question job: $($jobs.questions.status) $($jobs.questions.question_count)"
        if ($jobs.questions.status -eq "done" -and $jobs.questions.question_count -lt $project.question_count) {
          Fail "Question job is done but count is below target"
        }
      }
    }
  } else {
    Write-Host "Skipping authenticated API checks because ApiKey was not provided." -ForegroundColor Yellow
  }
}

Write-Host ""
Write-Host "Smoke checks passed." -ForegroundColor Green
