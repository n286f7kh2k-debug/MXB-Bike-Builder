using HelixToolkit.SharpDX;
using HelixToolkit.SharpDX.Assimp;
using HelixToolkit.SharpDX.Model.Scene;
using MXBRaceDayLive.PaintCreator.Models;
using System.Globalization;
using System.Numerics;
using System.Security.Cryptography;
using System.Text;

namespace MXBRaceDayLive.PaintCreator.Services;

/// <summary>
/// Resolves the stock rider preview from PiBoSo's public mxb_rider_template.FBX.
/// The FBX is imported by HelixToolkit and converted by our own UV-preserving OBJ writer.
/// We intentionally do not use Helix/Assimp export here because export support can vary by
/// native build even when FBX import itself succeeds.
/// </summary>
public sealed class OfficialMxBikesPreviewModelService : IGearPreviewModelService
{
    private const string StockRiderAssetId = "piboso-default-mx-rider-template";
    private const string CacheFormatVersion = "3";
    private readonly SemaphoreSlim _gate = new(1, 1);
    private readonly OfficialMxBikesToolchainService _toolchain = new();

    public async Task<GearPreviewModelResult> ResolveAsync(PaintTargetType target, PaintCreatorContext context, CancellationToken cancellationToken = default)
    {
        string configured = GetConfiguredPath(target, context);
        if (!string.IsNullOrWhiteSpace(configured) && File.Exists(configured))
            return new GearPreviewModelResult(configured, "MATCHING MX BIKES UV MODEL", false, "external");
        if (target != PaintTargetType.Rider)
            return new GearPreviewModelResult(null, $"{Friendly(target).ToUpperInvariant()} 3D MODEL PACK NOT INSTALLED");

        await _gate.WaitAsync(cancellationToken).ConfigureAwait(false);
        try
        {
            string root = GetManagedModelRoot(context);
            string assetRoot = Path.Combine(root, StockRiderAssetId);
            string objPath = Path.Combine(assetRoot, "mxb_rider_template.obj");
            string stampPath = Path.Combine(assetRoot, "asset.version");
            Directory.CreateDirectory(assetRoot);
            string fbxPath = await _toolchain.EnsureRiderFbxAsync(context, cancellationToken).ConfigureAwait(false);
            string sourceHash = ComputeSha256(fbxPath);
            if (IsValidCache(objPath, stampPath, sourceHash))
            {
                context.RiderPreviewObjPath = objPath;
                return new GearPreviewModelResult(objPath, "PIBOSO MXB_RIDER_TEMPLATE.FBX", true, CacheFormatVersion);
            }

            string pendingObj = objPath + ".new";
            ConvertFbxToObj(fbxPath, pendingObj);
            var mesh = ObjUvMeshLoader.Load(pendingObj);
            if (mesh.Positions.Count < 3 || mesh.TriangleIndices.Count < 3 || mesh.TextureCoordinates.Count != mesh.Positions.Count)
                throw new InvalidDataException("The official MX Bikes rider FBX is missing usable geometry or UV coordinates after conversion.");
            string objHash = ComputeSha256(pendingObj);
            File.Move(pendingObj, objPath, overwrite: true);
            await File.WriteAllTextAsync(stampPath,
                $"cache_format={CacheFormatVersion}\nsource={OfficialMxBikesToolchainService.RiderModelTemplatesUrl}\nfbx_sha256={sourceHash}\nobj_sha256={objHash}\n",
                Encoding.UTF8, cancellationToken).ConfigureAwait(false);
            context.RiderPreviewObjPath = objPath;
            return new GearPreviewModelResult(objPath, "PIBOSO MXB_RIDER_TEMPLATE.FBX", true, CacheFormatVersion);
        }
        catch (OperationCanceledException) { throw; }
        catch (Exception ex) { return new GearPreviewModelResult(null, $"RIDER MODEL LOAD ERROR • {ex.Message}"); }
        finally { _gate.Release(); }
    }

    private static void ConvertFbxToObj(string fbxPath, string objPath)
    {
        using var importer = new Importer();
        var scene = importer.Load(fbxPath) ?? throw new InvalidDataException("PiBoSo mxb_rider_template.FBX could not be imported.");
        Directory.CreateDirectory(Path.GetDirectoryName(objPath)!);
        using var writer = new StreamWriter(objPath, false, new UTF8Encoding(false));
        writer.WriteLine("# MXB Race Day Live viewer cache");
        writer.WriteLine("# Source: PiBoSo mxb_rider_template.FBX");
        int vertexOffset = 0;
        int meshCount = WriteNode(scene.Root, Matrix4x4.Identity, writer, ref vertexOffset);
        writer.Flush();
        if (meshCount == 0 || vertexOffset == 0 || !File.Exists(objPath) || new FileInfo(objPath).Length < 256)
            throw new InvalidDataException("PiBoSo rider FBX imported but contained no UV mesh that could be cached for the viewer.");
    }

    private static int WriteNode(SceneNode node, Matrix4x4 parentTransform, StreamWriter writer, ref int vertexOffset)
    {
        Matrix4x4 combined = node.ModelMatrix * parentTransform;
        int meshes = 0;
        if (node is MeshNode meshNode && meshNode.Geometry is MeshGeometry3D mesh)
        {
            WriteMesh(mesh, combined, writer, ref vertexOffset);
            meshes++;
        }
        if (node is GroupNode group)
            foreach (var child in group.Items) meshes += WriteNode(child, combined, writer, ref vertexOffset);
        return meshes;
    }

    private static void WriteMesh(MeshGeometry3D mesh, Matrix4x4 transform, StreamWriter writer, ref int vertexOffset)
    {
        var positions = mesh.Positions;
        var indices = mesh.Indices;
        var tex = mesh.TextureCoordinates;
        var normals = mesh.Normals;
        if (positions == null || positions.Count == 0 || indices == null || indices.Count < 3) return;
        if (tex == null || tex.Count != positions.Count)
            throw new InvalidDataException("PiBoSo rider mesh does not contain one UV coordinate per vertex.");
        bool hasNormals = normals != null && normals.Count == positions.Count;
        int firstObjIndex = vertexOffset + 1;
        writer.WriteLine($"o rider_mesh_{firstObjIndex}");
        foreach (var p in positions)
        {
            Vector3 v = Vector3.Transform(p, transform);
            writer.WriteLine(FormattableString.Invariant($"v {v.X:R} {v.Y:R} {v.Z:R}"));
        }
        foreach (var uv in tex) writer.WriteLine(FormattableString.Invariant($"vt {uv.X:R} {uv.Y:R}"));
        if (hasNormals)
        {
            foreach (var n in normals!)
            {
                Vector3 normal = Vector3.TransformNormal(n, transform);
                if (normal.LengthSquared() > 0f) normal = Vector3.Normalize(normal);
                writer.WriteLine(FormattableString.Invariant($"vn {normal.X:R} {normal.Y:R} {normal.Z:R}"));
            }
        }
        for (int i = 0; i + 2 < indices.Count; i += 3)
        {
            int a = firstObjIndex + indices[i]; int b = firstObjIndex + indices[i + 1]; int c = firstObjIndex + indices[i + 2];
            writer.WriteLine(hasNormals ? $"f {a}/{a}/{a} {b}/{b}/{b} {c}/{c}/{c}" : $"f {a}/{a} {b}/{b} {c}/{c}");
        }
        vertexOffset += positions.Count;
    }

    private static bool IsValidCache(string objPath, string stampPath, string fbxHash)
    {
        try
        {
            if (!File.Exists(objPath) || !File.Exists(stampPath) || new FileInfo(objPath).Length < 256) return false;
            string stamp = File.ReadAllText(stampPath);
            return stamp.Contains($"cache_format={CacheFormatVersion}", StringComparison.Ordinal) && stamp.Contains($"fbx_sha256={fbxHash}", StringComparison.Ordinal);
        }
        catch { return false; }
    }

    private static string GetManagedModelRoot(PaintCreatorContext context)
    {
        string projectRoot = !string.IsNullOrWhiteSpace(context.ProjectRoot) ? context.ProjectRoot : Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "MXBRaceDayLive", "PaintCreator");
        return Path.Combine(projectRoot, "Models");
    }
    private static string GetConfiguredPath(PaintTargetType target, PaintCreatorContext context) => target switch
    {
        PaintTargetType.Rider => context.RiderPreviewObjPath, PaintTargetType.Helmet => context.HelmetPreviewObjPath,
        PaintTargetType.Gloves => context.GlovesPreviewObjPath, PaintTargetType.Boots => context.BootsPreviewObjPath, _ => string.Empty
    };
    private static string Friendly(PaintTargetType target) => target switch
    { PaintTargetType.Rider => "Rider", PaintTargetType.Helmet => "Helmet", PaintTargetType.Gloves => "Gloves", PaintTargetType.Boots => "Boots", _ => target.ToString() };
    private static string ComputeSha256(string path) { using var stream = File.OpenRead(path); return Convert.ToHexString(SHA256.HashData(stream)).ToLowerInvariant(); }
}
