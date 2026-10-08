$ErrorActionPreference = 'Stop'
$Tools = Join-Path $env:LOCALAPPDATA 'QuoteCraftAPKBuilder\tools'
New-Item -ItemType Directory -Path $Tools -Force | Out-Null
$Zip = Join-Path $Tools 'gradle-8.11.1-bin.zip'
$Url = 'https://services.gradle.org/distributions/gradle-8.11.1-bin.zip'
Write-Host 'Downloading Gradle 8.11.1 from its official distribution site...'
Invoke-WebRequest -Uri $Url -OutFile $Zip
$Expected = (Invoke-WebRequest -Uri ($Url + '.sha256')).Content.Trim()
$Actual = (Get-FileHash -LiteralPath $Zip -Algorithm SHA256).Hash.ToLower()
if ($Actual -ne $Expected.ToLower()) { throw 'Gradle checksum did not match. Extraction stopped.' }
Expand-Archive -LiteralPath $Zip -DestinationPath $Tools -Force
Write-Host 'Gradle installed. Open the builder and click Check build tools again.'
