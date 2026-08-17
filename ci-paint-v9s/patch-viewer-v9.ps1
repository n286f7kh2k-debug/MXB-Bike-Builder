$ErrorActionPreference='Stop'
$path=Join-Path $env:SRC 'src\MXBRaceDayLive.PaintCreator\Services\OfficialMxBikesPreviewModelService.cs'
@'
using HelixToolkit.SharpDX;
using HelixToolkit.SharpDX.Assimp;
using HelixToolkit.SharpDX.Model.Scene;
using MXBRaceDayLive.PaintCreator.Models;
using System.IO;
using System.Numerics;
using System.Security.Cryptography;
using System.Text;

namespace MXBRaceDayLive.PaintCreator.Services;

public sealed class OfficialMxBikesPreviewModelService : IGearPreviewModelService
{
    private const string StockRiderAssetId = "piboso-default-mx-rider-template";
    private const string CacheFormatVersion = "3";
    private readonly SemaphoreSlim _gate = new(1,1);
    private readonly OfficialMxBikesToolchainService _toolchain = new();

    public async Task<GearPreviewModelResult> ResolveAsync(PaintTargetType target, PaintCreatorContext context, CancellationToken cancellationToken=default)
    {
        string configured=GetConfiguredPath(target,context);
        if(!string.IsNullOrWhiteSpace(configured)&&File.Exists(configured)) return new(configured,"MATCHING MX BIKES UV MODEL",false,"external");
        if(target!=PaintTargetType.Rider) return new(null,$"{Friendly(target).ToUpperInvariant()} 3D MODEL PACK NOT INSTALLED");
        await _gate.WaitAsync(cancellationToken).ConfigureAwait(false);
        try
        {
            string root=GetManagedModelRoot(context), assetRoot=Path.Combine(root,StockRiderAssetId), objPath=Path.Combine(assetRoot,"mxb_rider_template.obj"), stampPath=Path.Combine(assetRoot,"asset.version");
            Directory.CreateDirectory(assetRoot);
            string fbxPath=await _toolchain.EnsureRiderFbxAsync(context,cancellationToken).ConfigureAwait(false);
            string sourceHash=ComputeSha256(fbxPath);
            if(IsValidCache(objPath,stampPath,sourceHash)){context.RiderPreviewObjPath=objPath;return new(objPath,"PIBOSO MXB_RIDER_TEMPLATE.FBX",true,CacheFormatVersion);}
            string pending=objPath+".new";
            ConvertFbxToObjCache(fbxPath,pending);
            var mesh=ObjUvMeshLoader.Load(pending);
            if(mesh.Positions.Count<100||mesh.TriangleIndices.Count<300||mesh.TextureCoordinates.Count!=mesh.Positions.Count) throw new InvalidDataException("The PiBoSo rider FBX did not produce a usable UV mesh.");
            string objHash=ComputeSha256(pending);File.Move(pending,objPath,true);
            await File.WriteAllTextAsync(stampPath,$"cache_format={CacheFormatVersion}\nsource={OfficialMxBikesToolchainService.RiderModelTemplatesUrl}\nfbx_sha256={sourceHash}\nobj_sha256={objHash}\n",Encoding.UTF8,cancellationToken).ConfigureAwait(false);
            context.RiderPreviewObjPath=objPath;return new(objPath,"PIBOSO MXB_RIDER_TEMPLATE.FBX",true,CacheFormatVersion);
        }
        catch(OperationCanceledException){throw;}
        catch(Exception ex){return new(null,$"RIDER MODEL LOAD ERROR • {ex.Message}");}
        finally{_gate.Release();}
    }

    private static void ConvertFbxToObjCache(string fbxPath,string objPath)
    {
        using var importer=new Importer();
        var scene=importer.Load(fbxPath)??throw new InvalidDataException("PiBoSo mxb_rider_template.FBX could not be imported.");
        Directory.CreateDirectory(Path.GetDirectoryName(objPath)!);
        using var w=new StreamWriter(objPath,false,new UTF8Encoding(false));
        w.WriteLine("# MXB Race Day Live UV cache generated from PiBoSo mxb_rider_template.FBX");
        int vertexBase=1,meshCount=0,triangleCount=0;
        Walk(scene.Root,Matrix4x4.Identity);
        w.Flush();
        if(meshCount==0||triangleCount==0||new FileInfo(objPath).Length<256) throw new InvalidDataException("PiBoSo rider FBX imported but contained no usable triangle UV mesh.");

        void Walk(SceneNode node,Matrix4x4 parentWorld)
        {
            Matrix4x4 world=node.ModelMatrix*parentWorld;
            if(node is GeometryNode geo && geo.Geometry is MeshGeometry3D mesh && mesh.Positions is {Count:>0} && mesh.TriangleIndices is {Count:>2}) WriteMesh(mesh,world,node.Name);
            if(node is GroupNodeBase group) foreach(var child in group.Items) Walk(child,world);
        }

        void WriteMesh(MeshGeometry3D mesh,Matrix4x4 world,string? name)
        {
            int count=mesh.Positions!.Count;
            bool hasUv=mesh.TextureCoordinates!=null&&mesh.TextureCoordinates.Count==count;
            bool hasNormals=mesh.Normals!=null&&mesh.Normals.Count==count;
            w.WriteLine($"o {Safe(name)}");
            for(int i=0;i<count;i++)
            {
                Vector3 p=Vector3.Transform(mesh.Positions[i],world);
                w.WriteLine(FormattableString.Invariant($"v {p.X:R} {p.Y:R} {p.Z:R}"));
            }
            for(int i=0;i<count;i++)
            {
                Vector2 uv=hasUv?mesh.TextureCoordinates![i]:Vector2.Zero;
                w.WriteLine(FormattableString.Invariant($"vt {uv.X:R} {uv.Y:R}"));
            }
            for(int i=0;i<count;i++)
            {
                Vector3 n=hasNormals?Vector3.TransformNormal(mesh.Normals![i],world):Vector3.UnitY;
                n=n.LengthSquared()>1e-12f?Vector3.Normalize(n):Vector3.UnitY;
                w.WriteLine(FormattableString.Invariant($"vn {n.X:R} {n.Y:R} {n.Z:R}"));
            }
            var indices=mesh.TriangleIndices!;
            for(int i=0;i+2<indices.Count;i+=3)
            {
                int a=vertexBase+indices[i],b=vertexBase+indices[i+1],c=vertexBase+indices[i+2];
                w.WriteLine($"f {a}/{a}/{a} {b}/{b}/{b} {c}/{c}/{c}");triangleCount++;
            }
            vertexBase+=count;meshCount++;
        }
        static string Safe(string? s)=>string.IsNullOrWhiteSpace(s)?"mesh":new string(s.Select(ch=>char.IsLetterOrDigit(ch)||ch=='_'||ch=='-'?ch:'_').ToArray());
    }

    private static bool IsValidCache(string objPath,string stampPath,string fbxHash){try{if(!File.Exists(objPath)||!File.Exists(stampPath)||new FileInfo(objPath).Length<256)return false;string s=File.ReadAllText(stampPath);return s.Contains($"cache_format={CacheFormatVersion}")&&s.Contains($"fbx_sha256={fbxHash}");}catch{return false;}}
    private static string GetManagedModelRoot(PaintCreatorContext c)=>Path.Combine(!string.IsNullOrWhiteSpace(c.ProjectRoot)?c.ProjectRoot:Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),"MXBRaceDayLive","PaintCreator"),"Models");
    private static string GetConfiguredPath(PaintTargetType t,PaintCreatorContext c)=>t switch{PaintTargetType.Rider=>c.RiderPreviewObjPath,PaintTargetType.Helmet=>c.HelmetPreviewObjPath,PaintTargetType.Gloves=>c.GlovesPreviewObjPath,PaintTargetType.Boots=>c.BootsPreviewObjPath,_=>string.Empty};
    private static string Friendly(PaintTargetType t)=>t switch{PaintTargetType.Rider=>"Rider",PaintTargetType.Helmet=>"Helmet",PaintTargetType.Gloves=>"Gloves",PaintTargetType.Boots=>"Boots",_=>t.ToString()};
    private static string ComputeSha256(string p){using var s=File.OpenRead(p);return Convert.ToHexString(SHA256.HashData(s)).ToLowerInvariant();}
}
'@ | Set-Content -LiteralPath $path -Encoding utf8
Write-Host 'Patched PiBoSo viewer cache writer against exact HelixToolkit.SharpDX 3.1.2 MeshGeometry3D API.'
