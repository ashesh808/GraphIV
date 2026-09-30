# The tree the daemons run from, and the wrappers that start them over a venv uv fills from uv.lock
# Nix supplies the interpreter, uv and the native libraries the wheels load, and no Python package
{
  lib,
  stdenv,
  stdenvNoCC,
  symlinkJoin,
  writeShellScriptBin,
  python313,
  uv,
  zlib,
  libGL,
}:

let
  version = "0.3.0";

  tree = stdenvNoCC.mkDerivation {
    pname = "graphiv-tree";
    inherit version;
    src = lib.cleanSource ../.;
    installPhase = ''
      mkdir -p $out/share/graphiv
      cp -r src scripts retrieval_recipes pyproject.toml uv.lock .python-version $out/share/graphiv/
    '';
  };

  root = "${tree}/share/graphiv";
  python = "${python313}/bin/python3.13";

  # manylinux wheels load these by soname, and NixOS keeps the driver's libcuda under /run
  libraryPath =
    "/run/opengl-driver/lib:"
    + lib.makeLibraryPath [
      stdenv.cc.cc.lib
      zlib
      libGL
    ];

  venv = ''venv="''${GRAPHIV_VENV:-''${XDG_STATE_HOME:-$HOME/.local/state}/graphiv/venv}"'';

  # uv rebuilds the venv whenever the interpreter it was made with is not this one
  sync = writeShellScriptBin "graphiv-sync" ''
    ${venv}
    export UV_PROJECT_ENVIRONMENT="$venv" UV_PYTHON=${python} UV_PYTHON_DOWNLOADS=never
    exec ${uv}/bin/uv sync --frozen --no-install-project --project ${root} "$@"
  '';

  run =
    name: script:
    writeShellScriptBin name ''
      ${venv}
      export PYTHONPATH=${root} PYTHONDONTWRITEBYTECODE=1
      export LD_LIBRARY_PATH=${libraryPath}''${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}
      exec "$venv/bin/python" ${root}/${script} "$@"
    '';
in
symlinkJoin {
  pname = "graphiv";
  inherit version;
  paths = [
    tree
    sync
    (run "graphiv-serve" "scripts/serve.py")
    (run "graphiv-manager" "scripts/graphiv_manager/main.py")
  ];

  passthru = {
    inherit libraryPath python313 uv;
  };

  meta = {
    description = "A grounded literature review endpoint over the arXiv citation graph";
    homepage = "https://git.kuroma.dev/kkuroma/graphiv";
    license = lib.licenses.gpl3Only;
    mainProgram = "graphiv-serve";
    platforms = lib.platforms.linux;
  };
}
