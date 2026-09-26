# The NixOS module: two listeners over one package, and a config.toml written into the store
# Every tuned constant stays in the recipe files, so nothing measured is an option here
{ config, lib, pkgs, ... }:

let
  cfg = config.services.graphiv;
  toml = pkgs.formats.toml { };

  # the daemon reads these four sections and nothing else in the file
  base = {
    database.PG_DEST = cfg.database.dsn;
    dataset = {
      GRAPH_PATH = toString cfg.corpus.graph;
      HTML_PATH = toString cfg.corpus.html;
      PDF_PATH = toString cfg.corpus.pdf;
    };
    serve = {
      HOST = cfg.listenAddress;
      API_PORT = cfg.api.port;
      FRONTEND_PORT = cfg.frontend.port;
      ALLOWED_HOSTS = cfg.allowedHosts;
      RECIPE_PATH = toString cfg.recipes;
      RUNS_PATH = toString cfg.runsDir;
      CACHE_PATH = toString cfg.cacheDir;
      FETCH = cfg.fetch;
    };
    endpoints = {
      EMBED_API = cfg.endpoints.embed.url;
      EMBED_NAME = cfg.endpoints.embed.name;
      LLM_API = cfg.endpoints.llm.url;
      LLM_NAME = cfg.endpoints.llm.name;
    };
  };

  file = toml.generate "graphiv-config.toml" (lib.recursiveUpdate base cfg.settings);

  # a fetched paper lands in the corpus beside the bulk store, so both roots are writable
  writable = map toString [ cfg.cacheDir cfg.runsDir cfg.corpus.html cfg.corpus.pdf ];
  readable = [ (toString cfg.corpus.graph) ];

  unit = role: {
    description = "GraphIV ${role}";
    wantedBy = [ "multi-user.target" ];
    wants = [ "network-online.target" ];
    after = [ "network-online.target" ];
    environment.GRAPHIV_CONFIG = "${file}";
    serviceConfig = {
      ExecStart = "${cfg.package}/bin/graphiv-serve --http --role ${role}";
      User = cfg.user;
      Group = cfg.group;
      Restart = "on-failure";
      RestartSec = 10;
      # the api loads a 400MB graph export before it answers anything
      TimeoutStartSec = "5min";
      RequiresMountsFor = lib.unique ([ (toString cfg.dataDir) ] ++ writable ++ readable);
      UMask = "0002";
      NoNewPrivileges = true;
      PrivateTmp = true;
      ProtectSystem = "strict";
      ProtectKernelTunables = true;
      ProtectControlGroups = true;
      RestrictSUIDSGID = true;
      ReadWritePaths = lib.unique writable;
      ReadOnlyPaths = readable;
    };
  };
in
{
  options.services.graphiv = {
    enable = lib.mkEnableOption "the GraphIV literature review endpoint";

    package = lib.mkPackageOption pkgs "graphiv" { };

    user = lib.mkOption {
      type = lib.types.str;
      default = "graphiv";
      description = ''
        The unix user both listeners run as, and the owner of every directory below.
        Peer auth maps it to the postgres role of the same name, which needs SELECT and no more.
      '';
    };

    group = lib.mkOption {
      type = lib.types.str;
      default = "graphiv";
      description = "The group owning those directories, which a human member can also write.";
    };

    stateDir = lib.mkOption {
      type = lib.types.path;
      default = "/var/lib/graphiv";
      description = ''
        The root the three directories below default under.
        Nothing is read from here directly, so pointing it at another disk is a one line change.
      '';
    };

    dataDir = lib.mkOption {
      type = lib.types.path;
      default = "${cfg.stateDir}/data";
      defaultText = lib.literalExpression ''"''${stateDir}/data"'';
      description = ''
        The cold data: the corpus, the graph export, and a cluster this module never provisions.
        It is the one directory that holds anything expensive to rebuild.
      '';
    };

    cacheDir = lib.mkOption {
      type = lib.types.path;
      default = "${cfg.stateDir}/cache";
      defaultText = lib.literalExpression ''"''${stateDir}/cache"'';
      description = "Model replies keyed by their prompt, which is safe to delete at any time.";
    };

    runsDir = lib.mkOption {
      type = lib.types.path;
      default = "${cfg.stateDir}/runs";
      defaultText = lib.literalExpression ''"''${stateDir}/runs"'';
      description = "One directory per report written, which the dashboard reads and lists.";
    };

    listenAddress = lib.mkOption {
      type = lib.types.str;
      default = "127.0.0.1";
      description = "The interface both listeners bind, which a reverse proxy sits in front of.";
    };

    allowedHosts = lib.mkOption {
      type = lib.types.listOf lib.types.str;
      default = [ ];
      example = [ "graphiv.example.com" ];
      description = ''
        Host headers the transport answers to, on top of the address it is bound to.
        Empty rejects every forwarded name, which is what a proxy has to rewrite around.
      '';
    };

    fetch = lib.mkOption {
      type = lib.types.bool;
      default = true;
      description = ''
        Whether a paper the corpus never had may be fetched from arXiv, one request every three
        seconds, into the corpus itself. Turn it off when those paths cannot be written.
      '';
    };

    recipes = lib.mkOption {
      type = lib.types.path;
      default = "${cfg.package}/share/graphiv/retrieval_recipes";
      defaultText = lib.literalExpression ''"''${package}/share/graphiv/retrieval_recipes"'';
      description = "The tuned recipes, which ship with the package and are read only.";
    };

    database.dsn = lib.mkOption {
      type = lib.types.str;
      example = "host=/run/graphiv port=5433 dbname=arxivkg";
      description = ''
        The store, which this module never provisions.
        It needs pgvector and the four tables the published dump restores.
      '';
    };

    corpus.graph = lib.mkOption {
      type = lib.types.path;
      default = "${cfg.dataDir}/citation_graph_export.npy";
      defaultText = lib.literalExpression ''"''${dataDir}/citation_graph_export.npy"'';
      description = ''
        The citation graph export, loaded once at start and never written.
        The dump does not carry it, so `stage2_export_graph.py` writes it after a restore.
      '';
    };

    corpus.html = lib.mkOption {
      type = lib.types.path;
      default = "${cfg.dataDir}/arxiv/html";
      defaultText = lib.literalExpression ''"''${dataDir}/arxiv/html"'';
      description = ''
        A tree of `YYMM/<id>.html`, which a fetch also writes into.
        Point it at the real path rather than a symlink, so the unit orders on the right mount.
      '';
    };

    corpus.pdf = lib.mkOption {
      type = lib.types.path;
      default = "${cfg.dataDir}/arxiv/pdfs";
      defaultText = lib.literalExpression ''"''${dataDir}/arxiv/pdfs"'';
      description = "A tree of `YYMM/<id>v<n>.pdf`, on the same terms.";
    };

    endpoints.embed.url = lib.mkOption {
      type = lib.types.str;
      default = "http://127.0.0.1:11435";
      description = "A llama-server hosting the embedding model, which must expose /tokenize.";
    };

    endpoints.embed.name = lib.mkOption {
      type = lib.types.str;
      default = "nomic-embed-text-v2-moe";
      description = "The embedding model, which has to be the one the corpus was built with.";
    };

    endpoints.llm.url = lib.mkOption {
      type = lib.types.str;
      default = "http://127.0.0.1:11434/v1";
      description = "Any OpenAI compatible host.";
    };

    endpoints.llm.name = lib.mkOption {
      type = lib.types.str;
      example = "Gemma-4-26B";
      description = "The model every call goes to, a 26B instruct class being the reference.";
    };

    api.enable = lib.mkOption {
      type = lib.types.bool;
      default = true;
      description = "Serve the tools over streamable-http.";
    };

    api.port = lib.mkOption {
      type = lib.types.port;
      default = 6767;
      description = "The port the tools listen on.";
    };

    api.readOnly = lib.mkOption {
      type = lib.types.bool;
      default = false;
      description = "Register every tool but write_report, the only one that writes a file.";
    };

    frontend.enable = lib.mkOption {
      type = lib.types.bool;
      default = true;
      description = ''
        Serve the dashboard from a second process carrying no tools.
        It opens neither the store nor the graph, so it cannot reach the corpus.
      '';
    };

    frontend.port = lib.mkOption {
      type = lib.types.port;
      default = 6969;
      description = "The port the dashboard listens on.";
    };

    settings = lib.mkOption {
      type = toml.type;
      default = { };
      example = lib.literalExpression ''{ serve.FETCH = false; }'';
      description = "Merged over the generated config.toml, for a key this module does not name.";
    };
  };

  config = lib.mkIf cfg.enable {
    assertions = [
      {
        assertion = cfg.api.enable || cfg.frontend.enable;
        message = "services.graphiv needs at least one of api.enable and frontend.enable";
      }
      {
        assertion = cfg.api.port != cfg.frontend.port;
        message = "services.graphiv.api.port and frontend.port must differ";
      }
    ];

    users.users = lib.mkIf (cfg.user == "graphiv") {
      graphiv = {
        isSystemUser = true;
        group = cfg.group;
        home = cfg.stateDir;
        description = "GraphIV";
      };
    };

    users.groups = lib.mkIf (cfg.group == "graphiv") { graphiv = { }; };

    # setgid so a human in the group can read and delete what the daemon wrote, and a symlinked
    # corpus is left alone rather than followed and chmodded
    systemd.tmpfiles.rules = map (d: "d ${d} 2775 ${cfg.user} ${cfg.group} - -") (
      lib.unique [
        (toString cfg.stateDir)
        (toString cfg.dataDir)
        (toString cfg.cacheDir)
        (toString cfg.runsDir)
      ]
    );

    systemd.services.graphiv-api = lib.mkIf cfg.api.enable (
      lib.recursiveUpdate (unit "api") {
        environment.GRAPHIV_READONLY = lib.mkIf cfg.api.readOnly "1";
      }
    );

    systemd.services.graphiv-frontend = lib.mkIf cfg.frontend.enable (unit "frontend");
  };
}
