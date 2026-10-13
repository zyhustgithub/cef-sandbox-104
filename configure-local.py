from pathlib import Path
import os, subprocess
root=Path('/Users/zengyong/work/cef-sandbox-104')
src=root/'chromium/src'
assert (root/'state/05-local-sandbox-patch.done').exists()
p=src/'build/config/mac/BUILD.gn'
s=p.read_text()
if 'cef_legacy_clang_modern_sdk' not in s:
 anchor='config("runtime_library") {'
 assert anchor in s
 s=s.replace(anchor,'''declare_args() {
  # Opt-in for native desktop builds of Chromium 104 with a newer installed SDK.
  cef_legacy_clang_modern_sdk = false
}

'''+anchor,1)
 anchor='  defines = [ "__ASSERT_MACROS_DEFINE_VERSIONS_WITHOUT_UNDERSCORES=0" ]'
 assert anchor in s
 s=s.replace(anchor,anchor+'''
  if (cef_legacy_clang_modern_sdk) {
    # Clang 15 treats unknown target-environment names as the native (unknown)
    # environment. New SDK exclave checks then incorrectly disable TARGET_OS_OSX.
    # Native macOS has none of these special environments (simulator/macabi/etc).
    defines += [ "__is_target_environment(x)=0" ]
    cflags += [ "-Wno-builtin-macro-redefined" ]
  }
''',1)
 p.write_text(s)
 subprocess.run(['git','-C',str(src),'add','build/config/mac/BUILD.gn'],check=True)
 subprocess.run(['git','-C',str(src),'commit','-m','Add opt-in Clang 15 compatibility for native macOS builds with newer SDKs'],check=True)
env=os.environ.copy()
env['GN_DEFINES']='is_official_build=false is_component_build=false symbol_level=0 use_thin_lto=false target_cpu="arm64" enable_nacl=false mac_sdk_path="/Library/Developer/CommandLineTools/SDKs/MacOSX15.4.sdk" mac_deployment_target="12.0" mac_min_system_version="12.0" treat_warnings_as_errors=false clang_use_chrome_plugins=false cef_legacy_clang_modern_sdk=true'
(root/'state/gn-defines.txt').write_text(env['GN_DEFINES']+'\n')
subprocess.run(['python3','tools/gclient_hook.py'],cwd=src/'cef',env=env,check=True)
(root/'state/06-configure.done').touch()
