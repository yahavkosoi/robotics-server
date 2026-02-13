param(
  [string]$RootDir = '',
  [int]$MaxWaitSeconds = 90
)

$ErrorActionPreference = 'Stop'

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

if (-not $RootDir) {
  $RootDir = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
}

$script:RootDir = $RootDir
$script:WebDir = Join-Path $script:RootDir 'web'
$script:SettingsPath = Join-Path $script:RootDir 'data\settings.json'
$script:LogsDir = Join-Path $script:RootDir 'data\logs'
$script:BackendLogPath = Join-Path $script:LogsDir 'backend.log'
$script:WebLogPath = Join-Path $script:LogsDir 'web.log'

New-Item -ItemType Directory -Path $script:LogsDir -Force | Out-Null

$createdNew = $false
$script:Mutex = New-Object System.Threading.Mutex($true, 'Global\RoboticsServerTray', [ref]$createdNew)
if (-not $createdNew) {
  [System.Windows.Forms.MessageBox]::Show('Robotics tray is already running.', 'Robotics Server', [System.Windows.Forms.MessageBoxButtons]::OK, [System.Windows.Forms.MessageBoxIcon]::Information) | Out-Null
  exit 0
}

$script:BackendProcess = $null
$script:WebProcess = $null
$script:IsBusy = $false
$script:NotifyIcon = $null

function Get-PortConfig {
  $defaultBackend = 8080
  $defaultWeb = 5173

  if (-not (Test-Path -LiteralPath $script:SettingsPath)) {
    return @{
      backend_port = $defaultBackend
      web_port = $defaultWeb
    }
  }

  try {
    $raw = Get-Content -LiteralPath $script:SettingsPath -Raw -Encoding UTF8
    $parsed = ConvertFrom-Json -InputObject $raw
  } catch {
    return @{
      backend_port = $defaultBackend
      web_port = $defaultWeb
    }
  }

  $backendPort = $defaultBackend
  if ($parsed.backend_port -is [int] -and $parsed.backend_port -ge 1 -and $parsed.backend_port -le 65535) {
    $backendPort = $parsed.backend_port
  }

  $webPort = $defaultWeb
  if ($parsed.web_port -is [int] -and $parsed.web_port -ge 1 -and $parsed.web_port -le 65535) {
    $webPort = $parsed.web_port
  }

  return @{
    backend_port = $backendPort
    web_port = $webPort
  }
}

function Show-TrayBalloon {
  param(
    [string]$Title,
    [string]$Text,
    [ValidateSet('Info', 'Warning', 'Error')]
    [string]$Icon = 'Info'
  )

  if (-not $script:NotifyIcon) {
    return
  }

  $tooltipIcon = [System.Windows.Forms.ToolTipIcon]::$Icon
  $script:NotifyIcon.ShowBalloonTip(4000, $Title, $Text, $tooltipIcon)
}

function Set-TrayStatusText {
  param([string]$Text)

  if (-not $script:NotifyIcon) {
    return
  }

  # NotifyIcon tooltip text has a max length of 63 chars.
  $script:NotifyIcon.Text = $Text.Substring(0, [Math]::Min(63, $Text.Length))
}

function Stop-ManagedProcess {
  param(
    [ref]$ProcessRef,
    [string]$Name
  )

  $proc = $ProcessRef.Value
  if (-not $proc) {
    return
  }

  try {
    if (-not $proc.HasExited) {
      & taskkill /PID $proc.Id /T /F | Out-Null
    }
  } catch {
    # Ignore stop failures; process may have already exited.
  } finally {
    $ProcessRef.Value = $null
  }
}

function Stop-AllServices {
  Stop-ManagedProcess -ProcessRef ([ref]$script:WebProcess) -Name 'web'
  Stop-ManagedProcess -ProcessRef ([ref]$script:BackendProcess) -Name 'backend'
}

function Start-BackendProcess {
  param([int]$BackendPort)

  $backendCmd = "cd /d ""$script:RootDir"" && call ""venv\Scripts\activate.bat"" && python -m server.run >> ""$script:BackendLogPath"" 2>&1"
  return Start-Process -FilePath 'cmd.exe' -ArgumentList '/c', $backendCmd -WindowStyle Hidden -PassThru
}

function Start-WebProcess {
  $installStep = 'if not exist "node_modules" (npm install)'
  $webCmd = "(cd /d ""$script:WebDir"" && $installStep && npm run dev) >> ""$script:WebLogPath"" 2>&1"
  return Start-Process -FilePath 'cmd.exe' -ArgumentList '/c', $webCmd -WindowStyle Hidden -PassThru
}

function Wait-BackendHealthy {
  param(
    [string]$HealthUrl,
    [int]$TimeoutSeconds,
    [System.Diagnostics.Process]$BackendProc
  )

  for ($i = 0; $i -lt $TimeoutSeconds; $i++) {
    if ($BackendProc -and $BackendProc.HasExited) {
      return $false
    }

    try {
      Invoke-WebRequest -UseBasicParsing -Uri $HealthUrl -TimeoutSec 3 | Out-Null
      return $true
    } catch {
      Start-Sleep -Seconds 1
    }
  }

  return $false
}

function Wait-WebReady {
  param(
    [int]$WebPort,
    [int]$TimeoutSeconds,
    [System.Diagnostics.Process]$WebProc
  )

  $webUrl = "http://127.0.0.1:$WebPort/"
  for ($i = 0; $i -lt $TimeoutSeconds; $i++) {
    if ($WebProc -and $WebProc.HasExited) {
      return $false
    }

    try {
      Invoke-WebRequest -UseBasicParsing -Uri $webUrl -TimeoutSec 3 | Out-Null
      return $true
    } catch {
      Start-Sleep -Seconds 1
    }
  }

  return $false
}

function Get-LogTail {
  param(
    [string]$Path,
    [int]$Lines = 20
  )

  if (-not (Test-Path -LiteralPath $Path)) {
    return "Log missing: $Path"
  }

  try {
    $tail = Get-Content -LiteralPath $Path -Tail $Lines
    if (-not $tail) {
      return "Log exists but is empty: $Path"
    }
    return ($tail -join "`n")
  } catch {
    return "Failed reading log: $Path"
  }
}

function Start-AllServices {
  if ($script:IsBusy) {
    return
  }

  $script:IsBusy = $true
  try {
    Stop-AllServices

    $ports = Get-PortConfig
    $healthUrl = "http://127.0.0.1:$($ports.backend_port)/api/health"

    Set-TrayStatusText -Text "Robotics Server (Starting)"
    Show-TrayBalloon -Title 'Robotics Server' -Text "Starting backend on port $($ports.backend_port), then web on port $($ports.web_port)." -Icon Info

    $started = $false
    for ($attempt = 1; $attempt -le 2; $attempt++) {
      try {
        $script:BackendProcess = Start-BackendProcess -BackendPort $ports.backend_port

        if (-not (Wait-BackendHealthy -HealthUrl $healthUrl -TimeoutSeconds $MaxWaitSeconds -BackendProc $script:BackendProcess)) {
          throw "Backend did not pass health check at $healthUrl"
        }

        $script:WebProcess = Start-WebProcess
        if (-not (Wait-WebReady -WebPort $ports.web_port -TimeoutSeconds $MaxWaitSeconds -WebProc $script:WebProcess)) {
          $webExit = ""
          if ($script:WebProcess -and $script:WebProcess.HasExited) {
            $webExit = " (web process exited with code $($script:WebProcess.ExitCode))"
          }
          $logTail = Get-LogTail -Path $script:WebLogPath -Lines 10
          throw "Web did not become reachable on port $($ports.web_port)$webExit.`n$logTail"
        }

        Set-TrayStatusText -Text "Robotics Server (Running)"
        Show-TrayBalloon -Title 'Robotics Server' -Text 'Backend and web are running.' -Icon Info
        $started = $true
        break
      } catch {
        $errText = $_.Exception.Message
        Stop-AllServices
        if ($attempt -lt 2) {
          Start-Sleep -Seconds 2
        } else {
          Set-TrayStatusText -Text "Robotics Server (Error)"
          Show-TrayBalloon -Title 'Robotics Server' -Text ("Startup failed: " + $errText) -Icon Error
        }
      }
    }

    if (-not $started) {
      Set-TrayStatusText -Text "Robotics Server (Error)"
    }
  } finally {
    $script:IsBusy = $false
  }
}

$script:NotifyIcon = New-Object System.Windows.Forms.NotifyIcon
$script:NotifyIcon.Icon = [System.Drawing.SystemIcons]::Application
$script:NotifyIcon.Visible = $true
Set-TrayStatusText -Text "Robotics Server (Starting)"

$menu = New-Object System.Windows.Forms.ContextMenuStrip
$restartItem = New-Object System.Windows.Forms.ToolStripMenuItem 'Restart'
$quitItem = New-Object System.Windows.Forms.ToolStripMenuItem 'Quit'

$restartItem.Add_Click({
  Start-AllServices
})

$quitItem.Add_Click({
  Stop-AllServices
  $script:NotifyIcon.Visible = $false
  $script:NotifyIcon.Dispose()
  [System.Windows.Forms.Application]::ExitThread()
})

[void]$menu.Items.Add($restartItem)
[void]$menu.Items.Add($quitItem)
$script:NotifyIcon.ContextMenuStrip = $menu

$null = Register-EngineEvent -SourceIdentifier PowerShell.Exiting -Action {
  try {
    Stop-AllServices
  } catch {
  }
}

try {
  Start-AllServices
  $context = New-Object System.Windows.Forms.ApplicationContext
  [System.Windows.Forms.Application]::Run($context)
} finally {
  Stop-AllServices
  if ($script:NotifyIcon) {
    $script:NotifyIcon.Visible = $false
    $script:NotifyIcon.Dispose()
  }
  if ($script:Mutex) {
    $script:Mutex.ReleaseMutex() | Out-Null
    $script:Mutex.Dispose()
  }
}
