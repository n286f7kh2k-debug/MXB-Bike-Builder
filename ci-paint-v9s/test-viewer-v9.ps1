$ErrorActionPreference='Stop'
$s=Join-Path $env:RUNNER_TEMP 'v9-viewer';New-Item -ItemType Directory -Force $s|Out-Null;$lib=Join-Path $env:SRC 'src\MXBRaceDayLive.PaintCreator\MXBRaceDayLive.PaintCreator.csproj'
@"
<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup><OutputType>Exe</OutputType><TargetFramework>net8.0-windows</TargetFramework><UseWPF>true</UseWPF><ImplicitUsings>enable</ImplicitUsings></PropertyGroup><ItemGroup><ProjectReference Include="$lib"/></ItemGroup></Project>
"@|Set-Content (Join-Path $s 'Viewer.csproj')
@'
using System.IO;using MXBRaceDayLive.PaintCreator.Models;using MXBRaceDayLive.PaintCreator.Services;
var root=Path.Combine(Path.GetTempPath(),"mxb-v9-viewer-"+Guid.NewGuid().ToString("N"));Directory.CreateDirectory(root);var r=await new OfficialMxBikesPreviewModelService().ResolveAsync(PaintTargetType.Rider,new PaintCreatorContext{ProjectRoot=root});if(!r.Ready||string.IsNullOrWhiteSpace(r.ObjPath))throw new Exception("rider model failed: "+r.Status);var m=ObjUvMeshLoader.Load(r.ObjPath);Console.WriteLine($"POSITIONS={m.Positions.Count} TRIANGLES={m.TriangleIndices.Count/3} UVS={m.TextureCoordinates.Count} STATUS={r.Status}");if(m.Positions.Count<100||m.TriangleIndices.Count<300||m.TextureCoordinates.Count!=m.Positions.Count)throw new Exception("bad official rider UV mesh");
'@|Set-Content (Join-Path $s 'Program.cs')
dotnet run --project (Join-Path $s 'Viewer.csproj') -c Release;if($LASTEXITCODE){exit $LASTEXITCODE}
