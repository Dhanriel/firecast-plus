# Completa o plugin com arquivos do Firecast ja instalado neste PC (o SDK Lua e o som de mencao) e instala.
# Assim o download do Firecast Plus nao leva nenhum arquivo do Firecast. Faz o mesmo que fcplus.py build_plugin().
#   powershell -ExecutionPolicy Bypass -File instalar.ps1 -Base dist\momotoro.firecast.plus.rpk -Destino <arquivo .rpk>
param([Parameter(Mandatory)][string]$Base, [Parameter(Mandatory)][string]$Destino)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.IO.Compression, System.IO.Compression.FileSystem

function Ler($entrada) {
    $ms = New-Object IO.MemoryStream
    $s = $entrada.Open(); $s.CopyTo($ms); $s.Close()
    , $ms.ToArray()
}

$res = Join-Path $env:LOCALAPPDATA 'Firecast\resource.zip'
if (Test-Path "$res.original") { $res = "$res.original" }  # backup feito pela primeira skin
if (-not (Test-Path $res)) { throw "Firecast nao encontrado ($res). Instale o Firecast 8 antes." }

$arq = @{}
$z = [IO.Compression.ZipFile]::OpenRead((Resolve-Path $Base))
foreach ($e in $z.Entries) { if ($e.Name) { $arq[$e.FullName] = Ler $e } }
$z.Dispose()

$r = [IO.Compression.ZipFile]::OpenRead($res)
$arq['sons/highlight.mp3'] = Ler $r.GetEntry('sons/highlight.mp3')
$au = New-Object IO.Compression.ZipArchive -ArgumentList (New-Object IO.MemoryStream -ArgumentList (, (Ler $r.GetEntry('complementosPadroes/AutoUpdater.rpk'))))
foreach ($e in $au.Entries) {
    if ($e.Name -and ($e.FullName.StartsWith('sdk/') -or $e.FullName -eq '_rdkCompiledLang.cln')) { $arq[$e.FullName] = Ler $e }
}
$au.Dispose(); $r.Dispose()

# module.xml ganha data, sha1 de todos os arquivos (em ordem de nome, como o sorted() do Python) e um id unico
$nomes = [string[]]@($arq.Keys)
[Array]::Sort($nomes, [StringComparer]::Ordinal)
$sha = [Security.Cryptography.SHA1]::Create()
foreach ($n in $nomes) { $b = $arq[$n]; [void]$sha.TransformBlock($b, 0, $b.Length, $null, 0) }
[void]$sha.TransformFinalBlock([byte[]]@(), 0, 0)
$digest = -join ($sha.Hash | ForEach-Object { $_.ToString('x2') })
$uid = -join (1..12 | ForEach-Object { '{0:x2}' -f (Get-Random -Maximum 256) })
$attrs = " compilationDate=`"$(Get-Date -Format ddMMyyyyHHmmss)`" compilationDigest=`"$digest`" compilationUniqueID=`"$uid`""
$xml = [Text.Encoding]::UTF8.GetString($arq['module.xml'])
$arq['module.xml'] = [Text.Encoding]::UTF8.GetBytes(([regex]'<module ').Replace($xml, '<module' + $attrs + ' ', 1))

$tmp = "$Destino.tmp"
if (Test-Path $tmp) { Remove-Item $tmp }
$out = [IO.Compression.ZipFile]::Open($tmp, 'Create')
foreach ($n in $nomes) {
    $s = $out.CreateEntry($n, 'Optimal').Open(); $s.Write($arq[$n], 0, $arq[$n].Length); $s.Close()
}
$out.Dispose()
Move-Item -Force $tmp $Destino
Write-Output "digest $digest"
