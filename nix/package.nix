# The daemon, which is the interpreter, the libraries it imports, and the tree it runs from
# The serve path pulls no torch or CUDA, since every model it uses is an endpoint
# Only the manager variant carries what the preprocess stages load onto the GPU
{
  lib,
  stdenvNoCC,
  makeWrapper,
  python3,
  cudaPackages_13,
  withManager ? false,
}:

let
  serve = p: [
    p.mcp
    p.numpy
    p.psycopg
    p.pydantic
    p.scipy
    p.selectolax
    p.starlette
    p.uvicorn
  ];

  # the two classifiers, the projection, the clustering, the citation parser and the eval figures
  # torch-bin is the upstream CUDA wheel, since a CUDA torch built from source is hours of compile
  stages = p: [
    (torch p)
    p.transformers
    p.umap-learn
    p.scikit-learn
    p.joblib
    p.threadpoolctl
    p.rapidfuzz
    p.matplotlib
  ];

  # NVIDIA moved the v2.32.3-1 tag after some nixpkgs revs pinned it, and master carries this hash
  stale = "sha256-ytAJn8F0QEHhUadiOmVKTUiL7lsUnasoP4MOv/t60xk=";
  cuda = cudaPackages_13.overrideScope (
    _: prev: {
      nccl =
        if prev.nccl.src.outputHash == stale then
          prev.nccl.overrideAttrs (old: {
            src = old.src.overrideAttrs { outputHash = "sha256-xUllfdWAL0Ee9P9T9CZC2ddkPRnSXZXgwApgO398i6g="; };
          })
        else
          prev.nccl;
    }
  );

  # the wheel links CUDA 13, which the default cudaPackages predates
  torch =
    p:
    p.torch-bin.override {
      cudaPackages = cuda;
      cuda-bindings = p.cuda-bindings.override { cudaPackages = cuda; };
    };

  # src/ is put on the path rather than installed, so it never takes that name in site-packages
  env = python3.withPackages serve;
  heavy = python3.withPackages (p: serve p ++ stages p);
in
stdenvNoCC.mkDerivation {
  pname = if withManager then "graphiv-manager" else "graphiv";
  version = "0.3.0";
  src = lib.cleanSource ../.;

  nativeBuildInputs = [ makeWrapper ];

  installPhase = ''
    runHook preInstall

    mkdir -p $out/share/graphiv
    cp -r src scripts retrieval_recipes $out/share/graphiv/

    makeWrapper ${env}/bin/python $out/bin/graphiv-serve \
      --add-flags "$out/share/graphiv/scripts/serve.py" \
      --set PYTHONPATH "$out/share/graphiv" \
      --set PYTHONDONTWRITEBYTECODE 1
  ''
  + lib.optionalString withManager ''
    makeWrapper ${heavy}/bin/python $out/bin/graphiv-manager \
      --add-flags "$out/share/graphiv/scripts/graphiv_manager/main.py" \
      --set PYTHONPATH "$out/share/graphiv" \
      --set PYTHONDONTWRITEBYTECODE 1
  ''
  + ''
    runHook postInstall
  '';

  passthru = {
    pythonEnv = if withManager then heavy else env;
  };

  meta = {
    description = "A grounded literature review endpoint over the arXiv citation graph";
    homepage = "https://git.kuroma.dev/kkuroma/graphiv";
    license = lib.licenses.gpl3Only;
    mainProgram = if withManager then "graphiv-manager" else "graphiv-serve";
    platforms = lib.platforms.linux;
  };
}
