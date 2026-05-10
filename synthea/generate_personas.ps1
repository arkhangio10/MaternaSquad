# Generate the 3 MaternaSquad demo personas using Synthea.
#
# Personas:
#   - Aisha Williams    (the demo star: preeclampsia + postpartum critical event)
#   - Sofia Ramirez     (Spanish-language GDM journey)
#   - Jordan Bell       (rural, postpartum mental-health risk)
#
# Output: synthea/output/fhir/*.json (one Bundle per patient)

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$SyntheaDir  = Join-Path $ProjectRoot "synthea"
$Jar         = Join-Path $SyntheaDir "synthea-with-dependencies.jar"
$ModulesDir  = Join-Path $SyntheaDir "modules"
$OutputDir   = Join-Path $SyntheaDir "output"

# 1. Download Synthea jar if missing
if (-not (Test-Path $Jar)) {
    Write-Host "Downloading Synthea jar (about 90 MB)..." -ForegroundColor Yellow
    $url = "https://github.com/synthetichealth/synthea/releases/download/master-branch-latest/synthea-with-dependencies.jar"
    Invoke-WebRequest -Uri $url -OutFile $Jar -UseBasicParsing
}

# 2. Verify Java 17+
if (-not (Get-Command java -ErrorAction SilentlyContinue)) {
    throw "Java not on PATH. Install OpenJDK 17 first (winget install Microsoft.OpenJDK.17)."
}
$javaVersion = (cmd /c "java -version 2>&1") -join " "
if ($javaVersion -notmatch "17|18|19|2[0-9]") {
    Write-Warning "Java 17+ recommended. Current: $javaVersion"
}

# 3. Generate personas
function Invoke-Synthea {
    param(
        [string]$Seed,
        [string]$City,
        [string]$State,
        [string]$Race,
        [string]$Ethnicity,
        [string]$Gender = "F",
        [int]$AgeMin,
        [int]$AgeMax,
        [string]$Label
    )

    Write-Host ""
    Write-Host "Generating: $Label" -ForegroundColor Cyan
    java -jar $Jar `
        -p 1 `
        -s $Seed `
        -cs $Seed `
        --exporter.fhir.export=true `
        --exporter.fhir.use_us_core_ig=true `
        --exporter.baseDirectory=$OutputDir `
        --exporter.years_of_history=10 `
        --generate.only_alive_patients=true `
        --generate.only_dead_patients=false `
        --generate.default_modules=true `
        --module-dir=$ModulesDir `
        -a "$AgeMin-$AgeMax" `
        -g $Gender `
        -r (Get-Date).ToString("yyyy-MM-dd") `
        $State $City
}

Write-Host "Generating 3 demo personas..." -ForegroundColor Green

# Aisha Williams: 32, Black, Detroit, preeclampsia + preterm history
Invoke-Synthea -Seed "8001" -City "Detroit" -State "Michigan" `
    -Race "black" -Ethnicity "nonhispanic" -AgeMin 30 -AgeMax 34 `
    -Label "Aisha Williams (preeclampsia, demo star)"

# Sofia Ramirez: 28, Hispanic, Houston, GDM Spanish-language
Invoke-Synthea -Seed "8002" -City "Houston" -State "Texas" `
    -Race "hispanic" -Ethnicity "hispanic" -AgeMin 26 -AgeMax 30 `
    -Label "Sofia Ramirez (GDM, Spanish locale)"

# Jordan Bell: 19, White, rural Kentucky, postpartum mental health
Invoke-Synthea -Seed "8003" -City "Hazard" -State "Kentucky" `
    -Race "white" -Ethnicity "nonhispanic" -AgeMin 18 -AgeMax 21 `
    -Label "Jordan Bell (rural, mental health)"

Write-Host ""
Write-Host "Done. Output bundles:" -ForegroundColor Green
Get-ChildItem (Join-Path $OutputDir "fhir") -Filter "*.json" | ForEach-Object {
    Write-Host "  $($_.Name)"
}

Write-Host ""
Write-Host "Next: .\synthea\load_to_hapi.ps1" -ForegroundColor Cyan
