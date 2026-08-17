$ErrorActionPreference='Stop'
$test=Join-Path $env:RUNNER_TEMP 'v10-hotswap';New-Item -ItemType Directory -Force $test|Out-Null
$contracts=Join-Path $env:SRC 'src\MXBRaceDayLive.PaintCreator.Contracts\MXBRaceDayLive.PaintCreator.Contracts.csproj'
$demo=Join-Path $env:SRC 'src\MXBRaceDayLive.PaintCreator.Demo\MXBRaceDayLive.PaintCreator.Demo.csproj'
@"
<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup><OutputType>Exe</OutputType><TargetFramework>net8.0-windows</TargetFramework><UseWPF>true</UseWPF><ImplicitUsings>enable</ImplicitUsings><Nullable>enable</Nullable></PropertyGroup><ItemGroup><ProjectReference Include="$contracts"/><ProjectReference Include="$demo"/></ItemGroup></Project>
"@|Set-Content (Join-Path $test 'HotSwap.csproj')
@'
using System.IO;using MXBRaceDayLive.PaintCreator.Contracts;using MXBRaceDayLive.PaintCreator.Demo;
internal sealed class Services:IPaintCreatorHostServices{public Task<HostPaintOffer> GetExportOfferAsync(HostPaintExportRequest r,CancellationToken c=default)=>Task.FromResult(new HostPaintOffer(r.ProductId,"TEST",1m,"USD"));public Task<HostPaintAuthorization> CheckExportAsync(HostPaintExportRequest r,CancellationToken c=default)=>Task.FromResult(new HostPaintAuthorization(true,"OK"));public Task<HostPaintAuthorization> PurchaseExportAsync(HostPaintExportRequest r,CancellationToken c=default)=>Task.FromResult(new HostPaintAuthorization(true,"OK"));}
internal static class Program{[STAThread]static void Main(){var app=new System.Windows.Application();var dir=Environment.GetEnvironmentVariable("MODULE")!;var root=Path.Combine(Path.GetTempPath(),"mxb-v10-state-"+Guid.NewGuid().ToString("N"));var s=PaintCreatorModuleSession.Load(dir,new PaintCreatorHostOptions(root,"ci"),new Services());if(s.Module.View==null)throw new Exception("view missing");var state=s.Module.CaptureState();if(!s.Module.ModuleVersion.StartsWith("10.0.0"))throw new Exception("wrong version "+s.Module.ModuleVersion);s.Module.RestoreState(state);Console.WriteLine("HOT_SWAP_READY VERSION="+s.Module.ModuleVersion+" STATE="+state.Length);s.Dispose();}}
'@|Set-Content (Join-Path $test 'Program.cs')
dotnet run --project (Join-Path $test 'HotSwap.csproj') -c Release
if($LASTEXITCODE){exit $LASTEXITCODE}
