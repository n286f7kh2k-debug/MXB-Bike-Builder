$ErrorActionPreference='Stop'
$test=Join-Path $env:RUNNER_TEMP 'v9-toolchain';New-Item -ItemType Directory -Force $test|Out-Null
$lib=Join-Path $env:SRC 'src\MXBRaceDayLive.PaintCreator\MXBRaceDayLive.PaintCreator.csproj'
@"
<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup><OutputType>Exe</OutputType><TargetFramework>net8.0-windows</TargetFramework><UseWPF>true</UseWPF><ImplicitUsings>enable</ImplicitUsings><Nullable>enable</Nullable></PropertyGroup><ItemGroup><ProjectReference Include="$lib" /></ItemGroup></Project>
"@|Set-Content (Join-Path $test 'Toolchain.csproj')
@'
using System.IO;using MXBRaceDayLive.PaintCreator.Models;using MXBRaceDayLive.PaintCreator.Services;
var root=Path.Combine(Path.GetTempPath(),"mxb-v9-official-"+Guid.NewGuid().ToString("N"));Directory.CreateDirectory(root);var ctx=new PaintCreatorContext{ProjectRoot=root};var tools=new OfficialMxBikesToolchainService();
var template=await tools.EnsurePaintTemplateAsync(PaintTargetType.Rider,ctx);if(!File.Exists(template.PsdPath)||!string.Equals(Path.GetFileName(template.PsdPath),"rider.psd",StringComparison.OrdinalIgnoreCase))throw new Exception("official rider.psd missing");if(!File.Exists(template.PreviewPngPath)||template.Width<512||template.Height<512)throw new Exception("rider.psd preview failed");
var fbx=await tools.EnsureRiderFbxAsync(ctx);if(!File.Exists(fbx)||!string.Equals(Path.GetFileName(fbx),"mxb_rider_template.FBX",StringComparison.OrdinalIgnoreCase))throw new Exception("official rider FBX missing");
var painted=await tools.EnsurePaintEdAsync(ctx);if(!File.Exists(painted)||!string.Equals(Path.GetFileName(painted),"painted.exe",StringComparison.OrdinalIgnoreCase))throw new Exception("official PaintEd missing");
Console.WriteLine($"PSD={Path.GetFileName(template.PsdPath)} SIZE={template.Width}x{template.Height}");Console.WriteLine($"FBX={Path.GetFileName(fbx)}");Console.WriteLine($"PAINTED={Path.GetFileName(painted)}");
'@|Set-Content (Join-Path $test 'Program.cs')
dotnet run --project (Join-Path $test 'Toolchain.csproj') -c Release;if($LASTEXITCODE){exit $LASTEXITCODE}
