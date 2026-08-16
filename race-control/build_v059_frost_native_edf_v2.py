from pathlib import Path

base=Path('race-control/build_v059_frost_native_edf.py')
s=base.read_text(encoding='utf-8')
old="""for marker in ('mxb_asset_decoder.exe','decode_pnt','embedded_edf_textures',\"'rider.edf'\",\"'protections'\",'_decode_edf','assemble'):\n    assert marker in view,'gate:real_asset_pipeline:'+marker\n"""
new="""for marker in ('mxb_asset_decoder.exe','decode_pnt','embedded_edf_textures',\"'rider.edf'\",\"'protections'\",'_decode_edf'):\n    assert marker in view,'gate:real_asset_pipeline:'+marker\ndecoder_source=Path('race-control/frost-decoder/src/main.rs').read_text(encoding='utf-8')\nassert 'edf::assemble_bike(&mut nodes' in decoder_source,'gate:geom_assembly_in_native_decoder'\nassert 'edf::to_right_handed(&mut nodes)' in decoder_source,'gate:frost_handedness_in_native_decoder'\n"""
if old not in s:raise SystemExit('v0.5.9 assembly gate patch anchor missing')
s=s.replace(old,new,1)
exec(compile(s,str(base),'exec'),{'__name__':'__main__','__file__':str(base)})
