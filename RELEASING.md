# Releasing

Releases are built and published from a machine with `uv` and PyPI
credentials (the maintainer's Mac).

## 1. Prepare (any machine)

1. Bump `__version__` in `supercomputer.py`. That is the only place the
   version lives; `pyproject.toml` reads it from there.
2. Move the `[Unreleased]` notes in `CHANGELOG.md` under the new version and
   date.
3. Commit and push: `git commit -am "Release X.Y.Z" && git push`.

## 2. Build and check (release machine)

```sh
cd ~/dev/supercomputer
git pull
rm -rf dist
uv build                               # sdist + wheel in dist/
uvx twine check dist/*                 # README renders, metadata valid
uvx --from dist/*.whl supercomputer --version
```

## 3. Publish

```sh
uvx twine upload dist/*              # reads ~/.pypirc (uv publish does not)
```

To try it on TestPyPI first:
`uv publish --publish-url https://test.pypi.org/legacy/`.

Then check the real thing:

```sh
uvx --from supercomputer-console supercomputer --version
```

## 4. Tag and announce

```sh
git tag -a vX.Y.Z -m "vX.Y.Z" && git push --tags
gh release create vX.Y.Z dist/* --title "vX.Y.Z" --notes "See CHANGELOG.md"
```

## 5. Update the Homebrew tap

The formula lives in `~/dev/homebrew-tap` (github.com/rdubar/homebrew-tap).
Take the sdist's URL and sha256 from PyPI:

```sh
curl -s https://pypi.org/pypi/supercomputer-console/X.Y.Z/json | python3 -c \
  "import json,sys;[print(u['url'],u['digests']['sha256']) for u in json.load(sys.stdin)['urls'] if u['packagetype']=='sdist']"
```

Put them in `Formula/supercomputer.rb`, then check, commit and push:

```sh
cd ~/dev/homebrew-tap
brew audit --strict --online rdubar/tap/supercomputer
git commit -am "supercomputer X.Y.Z" && git push
brew upgrade rdubar/tap/supercomputer && brew test rdubar/tap/supercomputer
```

Use the full `packages/2f/...` URL from PyPI, not the short
`packages/source/...` form: that one is fussy about the project name.

## Notes

- PyPI never lets you reuse a version number, even after deleting a
  release. If something is wrong, bump the patch version and release again.
- The PyPI distribution name is `supercomputer-console`; the command and
  module stay `supercomputer`.
