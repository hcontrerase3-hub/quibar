$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
Set-Location (Join-Path $PSScriptRoot '..\..')
$arguments = @($args)
$dev = $false
if ($arguments.Count -gt 0 -and $arguments[0] -eq '--dev') {
    $dev = $true
    $arguments = @($arguments | Select-Object -Skip 1)
}
if ($arguments.Count -eq 0) {
    Write-Host 'Uso: quibar.cmd [--dev] iniciar|desarrollar|detener|logs|probar|admin|respaldo|importar-mapa|preparar-rutas|importar-datos [argumentos]'
    exit 0
}
$action = $arguments[0]
$rest = @($arguments | Select-Object -Skip 1)
if ($action -eq 'desarrollar') { $dev = $true; $action = 'iniciar' }
if ($action -notin @('iniciar','detener','logs','probar','admin','respaldo','importar-mapa','preparar-rutas','importar-datos')) {
    throw 'Accion desconocida'
}
function Invoke-Docker {
    & docker @args
    if ($LASTEXITCODE -ne 0) { throw "Docker termino con codigo $LASTEXITCODE" }
}
Invoke-Docker compose version
& docker info *> $null
if ($LASTEXITCODE -ne 0) { throw 'Inicia Docker Desktop con contenedores Linux.' }
New-Item -ItemType Directory -Force '.quibar' | Out-Null
$config = '.quibar/production.env'
$project = 'quibar'
if ($dev) { $config = '.quibar/development.env'; $project = 'quibar-dev' }
if (-not (Test-Path $config)) {
    Copy-Item docker.env.example $config
    if ($dev) { Add-Content $config "`nQUIBAR_PORT=8001`nQUIBAR_ROUTER_PORT=18003`nQUIBAR_VOICE_PORT=15001" }
}
$mode = 'docker'
$remoteUrl = ''
foreach ($line in Get-Content $config) {
    if ($line -match '^QUIBAR_OLLAMA_MODE=(.*)$') { $mode = $Matches[1].Trim() }
    if ($line -match '^OLLAMA_URL=(.*)$') { $remoteUrl = $Matches[1].Trim() }
}
$env:QUIBAR_MODEL_PULL = '1'
if ($mode -eq 'native') { $env:OLLAMA_URL = 'http://host.docker.internal:11434' }
elseif ($mode -eq 'docker') { $env:OLLAMA_URL = 'http://ollama:11434' }
elseif ($mode -eq 'remote') {
    if ($remoteUrl -notmatch '^https?://') { throw 'Configura OLLAMA_URL con el servidor remoto' }
    $env:OLLAMA_URL = $remoteUrl
    $env:QUIBAR_MODEL_PULL = '0'
}
else { throw 'QUIBAR_OLLAMA_MODE debe ser docker, native o remote' }
$compose = @('compose','--project-name',$project,'--env-file',$config,'-f','compose.yaml')
if ($dev) { $compose += @('-f','compose.dev.yaml') }
$compose += @('--profile','tools','--profile','model','--profile','ollama','--profile','territory')
function DC { Invoke-Docker @compose @args }
$lock = $null
try {
if ($action -notin @('logs','probar')) {
    $lockPath = ".quibar/$project.lock"
    New-Item -ItemType Directory $lockPath | Out-Null
    $lock = $lockPath
}
switch ($action) {
    iniciar {
        $services = @('app','nginx','maintenance')
        if ($dev) { $services += 'web' }
        DC up -d --build --wait @services
        DC up -d --build routing speech
        if ($mode -eq 'docker') { DC up -d ollama }
        DC up -d --force-recreate model-init
        Write-Host 'Modelo en preparacion; consulta quibar.cmd logs model-init.'
        if ($dev) { Write-Host 'Interfaz: http://127.0.0.1:3000' }
        else { Write-Host 'Interfaz: http://127.0.0.1:8000 (o QUIBAR_PORT configurado)' }
        DC exec app python -m backend.cli setup-admin
    }
    detener { DC stop }
    logs { DC logs --tail 100 -f @rest }
    admin {
        if ($rest.Count -eq 0) { DC exec app python -m backend.cli setup-admin }
        else { DC exec app python -m backend.cli @rest }
    }
    probar {
        DC build app
        DC run --rm --no-deps -e QUIBAR_DB_PATH=/tmp/test.sqlite3 tools python -m unittest backend.test_quibar backend.test_stack backend.test_container backend.test_territory backend.test_routes backend.test_demo_points -v
        Invoke-Docker build --target frontend -t "$project-frontend-tests" .
        Invoke-Docker run --rm "$project-frontend-tests" npm test
    }
    respaldo {
        New-Item -ItemType Directory -Force backups | Out-Null
        $destination = "backups/$([DateTime]::UtcNow.ToString('yyyyMMddTHHmmssZ')).tar.gz"
        if ($rest.Count -gt 0) { $destination = $rest[0] }
        if (Test-Path $destination) { throw 'El destino ya existe' }
        $running = @(& docker @compose ps --status running --services app maintenance routing)
        if ($LASTEXITCODE -ne 0) { throw 'No se pudo consultar los servicios' }
        $container = "$project-backup-$([Guid]::NewGuid().ToString('N'))"
        try {
            DC stop app maintenance routing
            # docker cp preserves binary archives on Windows PowerShell 5.1.
            DC run --name $container -T --no-deps tools python -m backend.container_ops backup /tmp/backup.tar.gz
            Invoke-Docker cp "${container}:/tmp/backup.tar.gz" $destination
            Write-Host "Respaldo: $destination. Guarda tambien $config por separado."
        } finally {
            & docker rm $container *> $null
            foreach ($service in $running) { DC start $service }
        }
    }
    importar-mapa {
        if ($rest.Count -eq 0 -or -not (Test-Path -PathType Leaf $rest[0])) { throw 'Indica un archivo MBTiles' }
        $source = (Resolve-Path $rest[0]).Path
        $extra = @($rest | Select-Object -Skip 1)
        DC run --rm --no-deps -v "${source}:/import/map.mbtiles:ro" tools python -m backend.cli import-map /import/map.mbtiles @extra
    }
    preparar-rutas {
        if ($rest.Count -eq 0 -or -not (Test-Path -PathType Leaf $rest[0])) { throw 'Indica un archivo .osm.pbf' }
        $source = (Resolve-Path $rest[0]).Path
        $extra = @($rest | Select-Object -Skip 1)
        DC build app
        DC stop routing
        try {
            DC run --rm --no-deps --user 0:0 -v "${source}:/import/region.osm.pbf:ro" tools python -m backend.cli import-roads /import/region.osm.pbf @extra
        } finally {
            DC up -d --force-recreate routing
        }
    }
    importar-datos {
        if ($rest.Count -ne 1 -or -not (Test-Path -PathType Container $rest[0])) { throw 'Indica una carpeta con quibar.sqlite3, media/ y map.mbtiles' }
        $running = @(& docker @compose ps --status running -q app maintenance routing)
        if ($LASTEXITCODE -ne 0 -or $running.Count -gt 0) { throw 'Deten primero la aplicacion' }
        $source = (Resolve-Path $rest[0]).Path
        DC build app
        DC run --rm --no-deps --user 0:0 -v "${source}:/import:ro" tools python -m backend.container_ops import /import
    }
}
} finally {
    if ($null -ne $lock) { Remove-Item -LiteralPath $lock }
}
