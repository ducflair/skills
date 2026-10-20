/**
 * Semantic Release configuration
 * https://semantic-release.gitbook.io/semantic-release
 */
module.exports = {
  branches: ['main'],
  plugins: [
    // 1. Analyze commits using Conventional Commits
    '@semantic-release/commit-analyzer',

    // 2. Generate release notes from commits
    '@semantic-release/release-notes-generator',

    // 3. Package skill folders into dist/ and notify skills.sh on success
    [
      '@semantic-release/exec',
      {
        prepareCmd:
          'python3 scripts/package_skills.py --version ${nextRelease.version} --out-dir dist',
        successCmd: 'npx --yes skills add ducflair/skills --list || true',
      },
    ],

    // 4. Create git tag, GitHub Release, and upload skill packages
    [
      '@semantic-release/github',
      {
        assets: [
          { path: 'dist/*.tar.gz', label: 'Tarball Package' },
          { path: 'dist/*.zip', label: 'Zip Package' },
          { path: 'dist/checksums.txt', label: 'SHA-256 Checksums' },
        ],
      },
    ],
  ],
};
