# Windows Real Telemetry & Background Collector Setup

This document describes the privacy-conscious local Windows telemetry collection system in **Smart Battery AI**, including how charging sessions and activity are measured, and instructions for running the background collector manually or as an optional Windows scheduled task.

---

## 1. System Architecture

The Windows telemetry layer runs locally on the host machine to bridge real laptop charging behavior into the Smart Battery AI machine learning personalization pipeline.

```
+-------------------------------------------------------------------------------+
|                             WINDOWS LAPTOP HOST                               |
|                                                                               |
|  +---------------------------+       +-------------------------------------+  |
|  | psutil.sensors_battery()  |       | Win32 user32.GetLastInputInfo       |  |
|  | (SoC %, Plugged, Seconds) |       | (Aggregate idle/active tick count)  |  |
|  +-------------+-------------+       +------------------+------------------+  |
|                |                                        |                     |
|                +-------------------+--------------------+                     |
|                                    |                                          |
|                                    v                                          |
|                   +----------------------------------+                        |
|                   |    WindowsTelemetryService       |                        |
|                   |  - Transition State Machine      |                        |
|                   |  - Restart Recovery & Anti-dupe  |                        |
|                   |  - Sleep / Wake Gap Detection    |                        |
|                   +----------------+-----------------+                        |
|                                    |                                          |
|               +--------------------+--------------------+                     |
|               |                                         |                     |
|               v                                         v                     |
|     +--------------------+                    +--------------------+          |
|     |  ChargingSession   |                    |  TelemetrySample   |          |
|     | (data_source=REAL) |                    | (Rate-limited 2m)  |          |
|     +---------+----------+                    +---------+----------+          |
|               |                                         |                     |
|               +--------------------+--------------------+                     |
|                                    |                                          |
|                                    v                                          |
|                      SQLite: data/battery_charging.db                         |
|                                    |                                          |
|          +-------------------------+-------------------------+                |
|          |                                                   |                |
|          v                                                   v                |
|  +-------------------------------+                   +---------------+        |
|  | ML Personalization Engine     |                   | React UI /    |        |
|  | 0-2: Learning (Global)        |                   | Real Data Tab |        |
|  | 3-6: Blended                  |                   +---------------+        |
|  | 7+:  Personalized             |                                            |
|  +-------------------------------+                                            |
+-------------------------------------------------------------------------------+
```

---

## 2. Privacy Guarantees

The telemetry collector is strictly local, zero-cloud, and privacy-conscious:
- **No Keystroke Content**: Keystrokes, letters, or words are **never** logged. The Win32 `GetLastInputInfo` API only reads the operating system's millisecond tick counter since the last user activity event.
- **No Screen or App Content**: Application titles, browser URLs, files, notifications, and screen captures are never accessed or stored.
- **Local Storage**: All data remains exclusively on your laptop inside the local SQLite database (`data/battery_charging.db`).

---

## 3. Charging Session Detection State Machine

The collector polls battery status at a configurable interval (default: 120 seconds):

1. **Unplugged $\to$ Plugged**:
   - Detects the transition to AC power.
   - Creates a new `ChargingSession` record with:
     - `data_source = "REAL_WINDOWS"`
     - `start_time = now (UTC)`
     - `start_battery_percent = current_soc`
     - `end_time = None` (in-progress)
     - `previous_day_usage_minutes = yesterday_active_minutes`
2. **Plugged $\to$ Unplugged**:
   - Detects cable disconnection.
   - Finalizes the open `ChargingSession` record with:
     - `end_time = now (UTC)`
     - `end_battery_percent = current_soc`
     - `charging_duration_minutes = (end_time - start_time)`
     - `screen_usage_minutes = active_usage_during_session`
     - `idle_usage_minutes = idle_time_during_session`
3. **Continuous Plugged / Duplicate Prevention**:
   - Repeated polls while plugged in **never** create duplicate rows.
   - Updates in-memory active/idle counters and periodically checkpoints latest battery percentage.
4. **Restart Recovery**:
   - If the collector process or machine restarts while a session was open, the collector scans the database on startup and resumes tracking the active session without creating duplicates.
5. **Sleep/Wake Detection**:
   - If the time delta between consecutive polls exceeds $2.2\times$ the polling interval (e.g. laptop lid was closed for 40 minutes), the collector records a sleep gap and does not falsely count suspended time as active usage.

---

## 4. Running the Collector (Development Command)

Run the background collector independently from the React frontend using the following command:

```powershell
# Default: 120s polling interval, User ID 1
python scripts/run_windows_collector.py

# Custom polling interval (e.g. 180s = 3 minutes)
python scripts/run_windows_collector.py --poll-interval 180 --user-id 1

# Single verification poll (tests sensors and exits)
python scripts/run_windows_collector.py --once

# Verbose debug logging
python scripts/run_windows_collector.py -v
```

> **Note**: The browser does not need to stay open. Data collection will continue uninterrupted in the background as long as the Python script is running.

---

## 5. Optional Setup: Windows Task Scheduler (Non-Automatic)

If you wish to have the collector start automatically in the background when logging into Windows, you can optionally configure Windows Task Scheduler using PowerShell.

> [!IMPORTANT]
> This configuration is **optional** and is not installed automatically by the project.

### Step-by-Step Manual Setup:

1. Open **PowerShell** as your current user.
2. Define the path to Python and the collector script:

```powershell
$PythonPath = (Get-Command python).Source
$ScriptPath = "C:\projects\smart-battery-ai\scripts\run_windows_collector.py"
$WorkingDirectory = "C:\projects\smart-battery-ai"

# Define the scheduled task action and trigger (At Logon)
$Action = New-ScheduledTaskAction -Execute $PythonPath -Argument "$ScriptPath --poll-interval 180" -WorkingDirectory $WorkingDirectory
$Trigger = New-ScheduledTaskTrigger -AtLogOn
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Days 365)

# Register the task for your user account
Register-ScheduledTask -TaskName "SmartBatteryAI_TelemetryCollector" -Action $Action -Trigger $Trigger -Settings $Settings -Description "Background battery telemetry collector for Smart Battery AI"
```

### To Verify or Check Task Status:
```powershell
Get-ScheduledTask -TaskName "SmartBatteryAI_TelemetryCollector"
```

### To Remove the Scheduled Task:
```powershell
Unregister-ScheduledTask -TaskName "SmartBatteryAI_TelemetryCollector" -Confirm:$false
```

---

## 6. Personalization Learning Progression

The cold-start personalization tier automatically transitions based on the number of completed real sessions:

| Completed Real Sessions | Personalization Stage | Model Strategy | Description |
| :--- | :--- | :--- | :--- |
| **0 – 2 sessions** | `LEARNING` | Global Circular Baseline | Safe population priors while gathering initial baseline behavior. |
| **3 – 6 sessions** | `BLENDED` | Circular Blended Ensemble | Dynamically blends population weights with user historical circular means. |
| **7+ sessions** | `PERSONALIZED` | Full Personalization Model | Inference driven by the user's specific circular diurnal schedule and variance. |

### Evaluation Timeline Recommendation:
Collect real data for **7 to 14 days** (or at least 10 completed charging cycles covering both weekdays and weekends) before formally evaluating model accuracy against your personal unplug patterns.
