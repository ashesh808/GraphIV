# The daemon, which is the interpreter, the seven libraries it imports, and the tree it runs from
# Nothing here pulls torch or CUDA, since every model the serve path uses is an endpoint
{ lib, stdenvNoCC, makeWrapper, python3 }:

let
  # src/ is put on the path rather than installed, so it never takes that name in site-packages
  env = python3.withPackages (p: [
    p.mcp
    p.numpy
    p.psycopg
    p.pydantic
    p.scipy
    p.selectolax
    p.starlette
    p.uvicorn
  ]);
in
stdenvNoCC.mkDerivation {
  pname = "graphiv";
  version = "0.2.0";
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

    runHook postInstall
  '';

  passthru = { pythonEnv = env; };

  meta = {
    description = "A grounded literature review endpoint over the arXiv citation graph";
    homepage = "https://git.kuroma.dev/kkuroma/graphiv";
    license = lib.licenses.gpl3Only;
    mainProgram = "graphiv-serve";
    platforms = lib.platforms.linux;
  };
}
