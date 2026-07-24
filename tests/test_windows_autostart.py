from pathlib import Path

from installer.engine import windows_autostart_task_script


def test_windows_autostart_task_script_registers_logon_and_startup_triggers():
    script = windows_autostart_task_script(Path(r"C:\ProgramData\anpr-edge-agent"))
    assert "New-ScheduledTaskTrigger -AtLogOn" in script
    assert "New-ScheduledTaskTrigger -AtStartup" in script
    assert "Trigger @($triggerLogon, $triggerBoot)" in script
    assert "$triggerBoot.Delay = 'PT2M'" in script


def test_windows_autostart_task_script_pins_install_dir_and_bypasses_execution_policy():
    script = windows_autostart_task_script(Path(r"C:\ProgramData\anpr-edge-agent"))
    assert 'set "ANPR_INSTALL_DIR=C:\\ProgramData\\anpr-edge-agent"' in script
    assert "-ExecutionPolicy Bypass" in script
    assert "run-agent.ps1" in script
