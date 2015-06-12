This repository contains the scripts which have been written and used to perform the migration to Github.

## Requirements

[BFG](https://rtyley.github.io/bfg-repo-cleaner) is used for removing large files from the history, along with git.

The following Python libraries are required:
  - aniso8601
  - argh
  - jira
  - pygithub
  - unidecode

You can install them with pip as follows:

```pip3 install aniso8601 argh jira pygithub unidecode```

Confluence to markdown translation is handled with [confluence2markdown](https://www.npmjs.com/package/confluence2markdown):

```npm install -g confluence2markdown```

## Configuration

Using the script requires to define two environment variables:

| Environment variable | Description                                               |
| -------------------- | ----------------------------------------------------------|
| BFG_JAR_PATH         | Absolute path to BFG JAR file
| GITHUB_TOKEN         | The access token for using Github API                     |
| GITHUB_ORGANIZATION  | Organization name on Github where to push repositories    |
| OW2_ORGANIZATION     | Organization name on OW2 used to pull repositories        |

Then, you have to configure the mapping between projects in 'mapping-*.txt' files.

## Examples

Repositories and projects from JIRA to migrate are defined in .

    $> migration.py github create-repositories
    $> migration.py github delete-repositories
    $> migration.py github edit-repositories --has-issues True
    
    $> migration.py ow2 clone-repositories --working-dir $TMP/ow2-github-migration
    $> migration.py ow2 gc-repositories --working-dir $TMP/ow2-github-migration
    $> migration.py ow2 prune-repositories --working-dir $TMP/ow2-github-migration
    $> migration.py github import-repositories --working-dir $TMP/ow2-github-migration

    $> migration.py github import-attachments https://jira.activeeon.com backup-attachments-jira
    $> migration.py github import-issues https://jira.activeeon.com backup-attachments-jira
