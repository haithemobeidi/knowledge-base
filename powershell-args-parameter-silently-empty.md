---
stack: [powershell, windows, process, debugging, testing]
kind: gotcha
last_verified: 2026-10-26
---

# A PowerShell parameter named `$args` is silently empty, and a launch probe must prove what it launched

**One-liner:** `$args` is PowerShell's automatic variable for unbound arguments. Declare a function parameter with that name and the parser accepts it, but the variable inside the body is always an empty array: whatever the caller passed is gone, with no warning. Hand that empty array to `Start-Process -ArgumentList` and the target starts with no arguments, also without error, and does whatever its no-argument default is. Measured 2026-10-26 on PowerShell 7.6: a "harmless" probe of a game launcher, written to pass a nonexistent exe name so nothing could possibly start, ran the launcher bare, and the launcher's bare default is "start the real game", which opened on the user's screen. The second half of the lesson is the one that would have caught it: a probe that spawns a process has to record what it actually spawned, by watching the probe's children as they appear or by reading the host's own launch log, because checking for survivors afterwards is blind to a child that already ran and exited.

## Symptom

A helper like this prints an empty argument list and starts the target with no arguments:

```powershell
function Probe($label, $args) {
    "$label : launcher.exe $($args -join ' ')"        # prints "x : launcher.exe "  (nothing after it)
    Start-Process launcher.exe -ArgumentList $args    # runs launcher.exe with NO arguments, no error
}
Probe 'x' @('doesnotexist.exe')
```

Measured on PowerShell 7.6.6: inside the body `@($args).Count` is `0` and `$null -eq $args` is `$false` (an empty array, not null), whether the caller passed an array or a single string. Renaming the parameter to `$exeArgs` binds normally (`count=2` for a two-element array).

## Cause

`$args` is reserved: inside any function it holds the arguments that did not bind to a declared parameter. Declaring a parameter with the same name does not give you a variable of your own; the body reads the automatic one, and it is empty. The parser does not object, no strictness setting flags it, and nothing is logged. I did not chase why the passed value vanishes instead of landing in the automatic variable; the observable is what matters: the parameter reads as an empty array, silently.

`Start-Process -ArgumentList` accepts an empty array or `$null` and starts the executable bare. Verified: `-ArgumentList $null` starts `cmd.exe` with no error thrown.

## Fix

- Never name a parameter after an automatic variable: not `$args`, `$input`, `$this`, `$PSItem`, `$_`. Use `$launchArgs`, `$exeArgs`.
- Before any `Start-Process` whose target has a consequential no-argument default, assert the list is non-empty: `if (-not $launchArgs) { throw 'refusing to launch with no arguments' }`.
- Print the exact command line the probe is about to run and READ it before trusting the probe's outcome. In the incident the probe printed `launcher.exe ` with nothing after it; the empty tail went unnoticed until the game was on screen.

## The second lesson: a launch probe needs a witness, not a survivor check

The same session had an earlier probe whose arguments were passed correctly. It started the launcher with a nonexistent exe name, waited 25 seconds, then listed game processes: none alive, so the conclusion was "nothing launched". Wrong. The launcher ignores its argument, started the real game within two seconds, and that instance had already come and gone by the time the survivor check ran. The platform's own process log showed the whole chain; the probe's "no leftovers" check could not.

A spawn probe must capture the children as they appear:

```powershell
$p = Start-Process $exe -ArgumentList $launchArgs -PassThru
$seen = @{}
$deadline = (Get-Date).AddSeconds(20)
while ((Get-Date) -lt $deadline) {
    Get-CimInstance Win32_Process -Filter "ParentProcessId = $($p.Id)" |
        Where-Object { -not $seen.ContainsKey($_.ProcessId) } |
        ForEach-Object { $seen[$_.ProcessId] = $true; "child: [$($_.Name)] $($_.CommandLine)" }
    if ($p.HasExited) { break }
    Start-Sleep -Milliseconds 150
}
```

And read the host's own record where one exists. Steam keeps `logs/gameprocess_log.txt` with the full command line of every process it tracked, which is also how you learn what a launcher really does with the arguments you gave it; an app's crash-handler temp folders carry one timestamped folder per boot. A probe with no witness is the launch-time form of [[negative-control-before-trusting-a-probe]]: "no survivors" was an instrument that could not come back red.

## Related

- [[negative-control-before-trusting-a-probe]] — the general rule: prove the instrument can fail before believing it.
- [[powershell-51-utf8-no-bom-string-breakage]] — the other PowerShell trap that errors nowhere near its cause.
