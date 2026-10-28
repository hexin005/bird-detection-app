$ErrorActionPreference = 'Stop'

$projectRoot = Split-Path -Parent $PSScriptRoot
$rulesPath = Join-Path $projectRoot 'Agents.md'
$strictUtf8 = [System.Text.UTF8Encoding]::new($false, $true)
$actual = [System.IO.File]::ReadAllText($rulesPath, $strictUtf8).Replace("`r`n", "`n").TrimEnd()
$expected = @'
注意事项：
- 每次改动完成后，都必须创建一个对应的git commit，以便后续追踪和回滚
- 每次改动后，都必须编写或更新相关测试，并在交付给用户前，确保所有测试和验证全部通过
'@

if ($actual -cne $expected.Replace("`r`n", "`n").TrimEnd()) {
    throw 'Agents.md must contain the requested rules exactly.'
}

$repositoryRoot = & git -C $projectRoot rev-parse --show-toplevel
if ($LASTEXITCODE -ne 0) {
    throw 'The project must be initialized as a Git repository.'
}
if ([System.IO.Path]::GetFullPath($repositoryRoot.Trim()) -ine [System.IO.Path]::GetFullPath($projectRoot)) {
    throw 'The Git repository root must be the project directory.'
}

Write-Output 'PASS: Agents.md is valid UTF-8 and contains both requested rules.'
Write-Output 'PASS: The project directory is the Git repository root.'
