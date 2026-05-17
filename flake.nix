{
  description = "arxiv_kg";
  inputs.nixpkgs.url = "github:nixos/nixpkgs/8a1b0127302ea51e05bf4ea5a291743fac442406";
  outputs = { self, nixpkgs }:
  let
    pkgs = import nixpkgs { system = "x86_64-linux"; config.allowUnfree = true; };
    lib = nixpkgs.lib;
  in {
    devShells.x86_64-linux.default = pkgs.mkShell {
      packages = with pkgs; [
        python3
        uv
        ruff
        black
        pyright
        cudaPackages.cuda_cudart
        cudaPackages.libcublas
        cudaPackages.cuda_cccl
        git
      ];
      DEV_SHELL = "arxiv_kg";
      LD_LIBRARY_PATH = "/run/opengl-driver/lib:" + lib.makeLibraryPath (with pkgs; [ stdenv.cc.cc.lib zlib libGL cudaPackages.cuda_cudart cudaPackages.libcublas cudaPackages.cuda_cccl ]);
      shellHook = ''
        if [ -d .venv ]; then
          export VIRTUAL_ENV="$PWD/.venv"
          export PATH="$PWD/.venv/bin:$PATH"
        fi
        [[ $- == *i* ]] && exec zsh
      '';
    };
  };
}
