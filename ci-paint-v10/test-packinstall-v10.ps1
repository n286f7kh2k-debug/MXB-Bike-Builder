$ErrorActionPreference='Stop'
$test=Join-Path $env:RUNNER_TEMP 'v10-packinstall';New-Item -ItemType Directory -Force $test|Out-Null
$lib=Join-Path $env:SRC 'src\MXBRaceDayLive.PaintCreator\MXBRaceDayLive.PaintCreator.csproj'
@"
<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup><OutputType>Exe</OutputType><TargetFramework>net8.0-windows</TargetFramework><UseWPF>true</UseWPF><ImplicitUsings>enable</ImplicitUsings><Nullable>enable</Nullable></PropertyGroup><ItemGroup><ProjectReference Include="$lib" /></ItemGroup></Project>
"@|Set-Content (Join-Path $test 'PackInstall.csproj')
@'
using MXBRaceDayLive.PaintCreator.Models;
using MXBRaceDayLive.PaintCreator.Services;
using System.Diagnostics;
using System.IO;

var root=Path.Combine(Path.GetTempPath(),"mxb-v10-pack-"+Guid.NewGuid().ToString("N"));
var mods=Path.Combine(root,"mods");var project=Path.Combine(root,"project");Directory.CreateDirectory(mods);Directory.CreateDirectory(project);
var tga=Path.Combine(project,"rider.tga");WriteTga(tga,64,64);
var ctx=new PaintCreatorContext{ProjectRoot=project,ModsRoot=mods,UserId="ci"};
var svc=new PaintEdCliPackService();
var result=await svc.PackAndInstallAsync(ctx,PaintTargetType.Rider,tga,"Race Day Live v10 CI");
if(!File.Exists(result.PntPath)||new FileInfo(result.PntPath).Length==0)throw new Exception("packed PNT missing");
if(!File.Exists(result.InstalledPath))throw new Exception("installed PNT missing");
var expected=Path.GetFullPath(Path.Combine(mods,"rider","paints"))+Path.DirectorySeparatorChar;
if(!Path.GetFullPath(result.InstalledPath).StartsWith(expected,StringComparison.OrdinalIgnoreCase))throw new Exception("wrong MX Bikes install path: "+result.InstalledPath);
var extract=Path.Combine(root,"extract");Directory.CreateDirectory(extract);
var psi=new ProcessStartInfo{FileName=result.PaintEdPath,WorkingDirectory=Path.GetDirectoryName(result.PaintEdPath)!,UseShellExecute=false,CreateNoWindow=true,RedirectStandardOutput=true,RedirectStandardError=true};
psi.ArgumentList.Add("e");psi.ArgumentList.Add(result.InstalledPath);psi.ArgumentList.Add(extract);
using var p=new Process{StartInfo=psi};p.Start();var stdout=p.StandardOutput.ReadToEndAsync();var stderr=p.StandardError.ReadToEndAsync();using var cts=new CancellationTokenSource(TimeSpan.FromSeconds(30));await p.WaitForExitAsync(cts.Token);var text=(await stdout)+(await stderr);
if(p.ExitCode!=0)throw new Exception("PaintEd extract failed: "+text);
var recovered=Directory.GetFiles(extract,"rider.tga",SearchOption.AllDirectories).FirstOrDefault();if(recovered==null)throw new Exception("installed PNT did not extract rider.tga");
Console.WriteLine($"PNT_PACK_INSTALL_OK PNT={new FileInfo(result.PntPath).Length} INSTALLED={result.InstalledPath} EXTRACTED={new FileInfo(recovered).Length}");

static void WriteTga(string path,int width,int height){var b=new byte[18+width*height*3];b[2]=2;b[12]=(byte)(width&255);b[13]=(byte)((width>>8)&255);b[14]=(byte)(height&255);b[15]=(byte)((height>>8)&255);b[16]=24;b[17]=32;for(int i=18;i<b.Length;i+=3){b[i]=30;b[i+1]=120;b[i+2]=220;}File.WriteAllBytes(path,b);}
'@|Set-Content (Join-Path $test 'Program.cs')
dotnet run --project (Join-Path $test 'PackInstall.csproj') -c Release
if($LASTEXITCODE){exit $LASTEXITCODE}
