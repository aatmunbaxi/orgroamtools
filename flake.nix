{
  description = "orgroamtools development environment";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = nixpkgs.legacyPackages.${system};
        python = pkgs.python3;

        pythonEnv = python.withPackages (ps: with ps; [
          # runtime
          networkx
          orgparse

          # build backend (for the editable install)
          poetry-core
          pip

          # tests and type checking
          pytest
          mypy

          # pretty_viz.py
          matplotlib
          numpy

          # docs (docs/requirements.txt)
          sphinx
          sphinx-rtd-theme
          sphinx-autodoc-typehints
          mock
        ]);

        # Only needed to regenerate tests/fixtures/org-roam.db
        emacsEnv = (pkgs.emacsPackagesFor pkgs.emacs-nox).withPackages (epkgs: [
          epkgs.org-roam
        ]);
      in
      {
        devShells.default = pkgs.mkShell {
          packages = [ pythonEnv pkgs.ruff ];

          shellHook = ''
            # Venv layered on the Nix Python so all packages above are visible,
            # while orgroamtools itself is installed in editable mode.
            root="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
            if [ ! -d "$root/.venv" ]; then
              ${pythonEnv}/bin/python -m venv --system-site-packages "$root/.venv"
            fi
            source "$root/.venv/bin/activate"

            if ! pip show --quiet orgroamtools 2>/dev/null; then
              pip install --quiet --no-deps --no-build-isolation -e "$root"
            fi
          '';
        };

        devShells.fixtures = pkgs.mkShell {
          packages = [ emacsEnv ];
        };
      });
}
