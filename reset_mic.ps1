# Disables and re-enables a USB microphone so it comes up cleanly after login.
# Needs an elevated shell. Pass the mic's name (wildcards allowed).
param([string]$Name = "*K670*")

Get-PnpDevice -Class MEDIA -FriendlyName $Name -ErrorAction SilentlyContinue | ForEach-Object {
    Disable-PnpDevice -InstanceId $_.InstanceId -Confirm:$false
    Start-Sleep -Seconds 2
    Enable-PnpDevice -InstanceId $_.InstanceId -Confirm:$false
}
