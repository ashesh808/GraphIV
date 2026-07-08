{
  description = "GraphIV";
  inputs.nixpkgs.url = "github:nixos/nixpkgs/8a1b0127302ea51e05bf4ea5a291743fac442406";
  outputs = { self, nixpkgs }:
  let
    system = "x86_64-linux";
    pkgs = import nixpkgs { inherit system; config.allowUnfree = true; };
    lib = nixpkgs.lib;

    # Postgres 17 with pgvector — the SINGLE project store (metadata + citations + embeddings +
    # topic tree). Launched from THIS flake (not the global systemd service): a user-owned cluster
    # over a PROJECT-LOCAL unix socket, so it needs no password (peer auth) and never clashes with
    # any global postgres on :5432.
    pgWithVec = pkgs.postgresql_17.withPackages (p: [ p.pgvector ]);

    # Project-owned cluster, fully self-contained under ./data/pg (real dir, no symlink) on the
    # current NVMe. Socket + port are project-local so it never clashes with a global postgres.
    pgEnv = ''
      export PGDATA="''${PGDATA:-$PWD/data/pg}"
      export PGHOST="''${PGHOST:-$PWD/.pg}"
      export PGPORT="''${PGPORT:-5433}"
      export PGDATABASE="''${PGDATABASE:-arxivkg}"
    '';

    pg-init = pkgs.writeShellScriptBin "pg-init" ''
      set -euo pipefail
      ${pgEnv}
      if [ -d "$PGDATA/base" ]; then echo "cluster already initialized at $PGDATA"; exit 0; fi
      mkdir -p "$PGDATA" "$PGHOST"
      ${pgWithVec}/bin/initdb -D "$PGDATA" --encoding=UTF8 --no-locale -U "$USER"
      {
        echo "unix_socket_directories = '$PGHOST'"
        echo "listen_addresses = '''"                 # socket-only; no TCP exposure
        echo "port = $PGPORT"
        echo "default_toast_compression = lz4"        # compress in-DB text (sentence, etc.)
        echo "shared_buffers = 4GB"
        echo "work_mem = 256MB"
        echo "maintenance_work_mem = 2GB"             # speeds HNSW + index builds
        echo "max_parallel_maintenance_workers = 4"
      } >> "$PGDATA/postgresql.conf"
      echo "initialized. start with: pg-start"
    '';

    pg-start = pkgs.writeShellScriptBin "pg-start" ''
      set -euo pipefail
      ${pgEnv}
      ${pgWithVec}/bin/pg_ctl -D "$PGDATA" -l "$PGDATA/server.log" start
      # create the database + schema on first start (idempotent)
      ${pgWithVec}/bin/createdb -h "$PGHOST" -p "$PGPORT" "$PGDATABASE" 2>/dev/null || true
      ${pgWithVec}/bin/psql -h "$PGHOST" -p "$PGPORT" -d "$PGDATABASE" -v ON_ERROR_STOP=1 \
        -f "$PWD/data/metadata/pg_schema.sql"
      echo "up: host=$PGHOST port=$PGPORT db=$PGDATABASE"
    '';

    pg-stop = pkgs.writeShellScriptBin "pg-stop" ''
      set -euo pipefail
      ${pgEnv}
      ${pgWithVec}/bin/pg_ctl -D "$PGDATA" stop -m fast
    '';

    pg-console = pkgs.writeShellScriptBin "pg-console" ''
      set -euo pipefail
      ${pgEnv}
      exec ${pgWithVec}/bin/psql -h "$PGHOST" -p "$PGPORT" -d "$PGDATABASE" "$@"
    '';
  in {
    devShells.${system}.default = pkgs.mkShell {
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
        pgWithVec
        pg-init
        pg-start
        pg-stop
        pg-console
        # LaTeX for the experiment reports + paper (latexmk + the packages they use)
        (texlive.combined.scheme-medium)
      ];
      DEV_SHELL = "GraphIV";
      LD_LIBRARY_PATH = "/run/opengl-driver/lib:" + lib.makeLibraryPath (with pkgs; [ stdenv.cc.cc.lib zlib libGL cudaPackages.cuda_cudart cudaPackages.libcublas cudaPackages.cuda_cccl ]);
      shellHook = ''
        export PGHOST="''${PGHOST:-$PWD/.pg}"
        export PGPORT="''${PGPORT:-5433}"
        export PGDATABASE="''${PGDATABASE:-arxivkg}"
        export ARXIVKG_PG_DSN="''${ARXIVKG_PG_DSN:-host=$PWD/.pg port=5433 dbname=arxivkg}"
        if [ -d .venv ]; then
          export VIRTUAL_ENV="$PWD/.venv"
          export PATH="$PWD/.venv/bin:$PATH"
        fi
        [[ $- == *i* ]] && exec zsh
      '';
    };

    apps.${system} = {
      pg-init    = { type = "app"; program = "${pg-init}/bin/pg-init"; };
      pg-start   = { type = "app"; program = "${pg-start}/bin/pg-start"; };
      pg-stop    = { type = "app"; program = "${pg-stop}/bin/pg-stop"; };
      pg-console = { type = "app"; program = "${pg-console}/bin/pg-console"; };
    };
  };
}
